"""Download and clean race laps from the OpenF1 public API.

OpenF1 (https://openf1.org) is free and needs no API key for historical data
(2023 onwards). Responses are cached as JSON files so each race is downloaded
only once.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

API_URL = "https://api.openf1.org/v1"
DEFAULT_CACHE_DIR = Path("data/cache")

# Race control messages that neutralise the whole track.
NEUTRALISED_STATUSES = ("SC", "VSC", "RED")


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def fetch_openf1(
    endpoint: str,
    params: dict,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    retries: int = 6,
) -> pd.DataFrame:
    """Return an OpenF1 endpoint as a DataFrame, using a local JSON cache."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    query = urllib.parse.urlencode(sorted(params.items()))
    cache_file = cache_dir / f"{endpoint}__{query.replace('&', '__').replace('=', '-')}.json"

    if cache_file.exists():
        return pd.DataFrame(json.loads(cache_file.read_text(encoding="utf-8")))

    url = f"{API_URL}/{endpoint}?{query}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                data = json.load(response)
            break
        except urllib.error.HTTPError as err:
            if err.code == 404:  # OpenF1 uses 404 for "No results found."
                data = []
                break
            # Rate limit or server error: back off (2, 4, 8, ... s) and retry.
            if attempt == retries - 1 or err.code not in (429, 500, 502, 503):
                raise
            time.sleep(2 ** (attempt + 1))
    time.sleep(1.0)  # be polite with the free API

    cache_file.write_text(json.dumps(data), encoding="utf-8")
    return pd.DataFrame(data)


def get_session_key(
    year: int, country: str, session_name: str = "Race", cache_dir: Path | str = DEFAULT_CACHE_DIR
) -> int:
    """Find the OpenF1 session key for a given year, country and session."""
    sessions = fetch_openf1(
        "sessions",
        {"year": year, "country_name": country, "session_name": session_name},
        cache_dir,
    )
    if sessions.empty:
        raise ValueError(f"No '{session_name}' session found for {country} {year}.")
    if len(sessions) > 1:
        raise ValueError(f"More than one session matched {country} {year}: refine the query.")
    return int(sessions.loc[0, "session_key"])


def load_raw_race(
    year: int, country: str, cache_dir: Path | str = DEFAULT_CACHE_DIR
) -> dict[str, pd.DataFrame]:
    """Download every table needed for one race and return them by name."""
    key = get_session_key(year, country, "Race", cache_dir)
    tables = ["laps", "stints", "race_control", "weather", "drivers", "position"]
    raw = {name: fetch_openf1(name, {"session_key": key}, cache_dir) for name in tables}
    raw["session_key"] = key
    return raw


# --------------------------------------------------------------------------- #
# Build one row per lap
# --------------------------------------------------------------------------- #
def _add_tyres(laps: pd.DataFrame, stints: pd.DataFrame) -> pd.DataFrame:
    """Attach stint number, compound and tyre age (laps on the set) to each lap."""
    merged = laps.merge(stints, on="driver_number", how="left")
    in_stint = merged["lap_number"].between(merged["lap_start"], merged["lap_end"])
    merged = merged[in_stint]
    # TyreLife = 1 on the first lap of a new set (same convention as FastF1).
    merged["TyreLife"] = merged["tyre_age_at_start"] + merged["lap_number"] - merged["lap_start"] + 1
    cols = ["driver_number", "lap_number", "stint_number", "compound", "TyreLife"]
    return laps.merge(merged[cols], on=["driver_number", "lap_number"], how="left")


def _add_pit_in_flag(laps: pd.DataFrame) -> pd.DataFrame:
    """Flag in-laps: the lap right before a pit-out lap of the same driver."""
    out_laps = laps.loc[laps["is_pit_out_lap"], ["driver_number", "lap_number"]]
    in_lap_keys = set(zip(out_laps["driver_number"], out_laps["lap_number"] - 1))
    laps["IsPitInLap"] = [key in in_lap_keys for key in zip(laps["driver_number"], laps["lap_number"])]
    return laps


def neutralised_periods(race_control: pd.DataFrame) -> pd.DataFrame:
    """Return [start, end) time windows under safety car, VSC or red flag."""
    rc = race_control.copy()
    rc["date"] = pd.to_datetime(rc["date"], format="ISO8601")
    msg = rc["message"].fillna("").str.upper()

    events = pd.Series(pd.NA, index=rc.index, dtype="object")
    events[msg.str.contains("VIRTUAL SAFETY CAR DEPLOYED")] = "VSC_START"
    events[msg.str.contains("VIRTUAL SAFETY CAR ENDING")] = "VSC_END"
    events[msg.str.contains("SAFETY CAR DEPLOYED") & ~msg.str.contains("VIRTUAL")] = "SC_START"
    events[msg.str.contains("SAFETY CAR IN THIS LAP")] = "SC_END"
    events[rc["flag"].eq("RED")] = "RED_START"
    events[msg.str.contains("RESUME") | msg.str.contains("RESTART")] = "RED_END"
    rc["event"] = events
    rc = rc.dropna(subset=["event"]).sort_values("date")

    periods, open_since = [], {}
    for _, row in rc.iterrows():
        status, edge = row["event"].split("_")
        if edge == "START":
            open_since.setdefault(status, row["date"])
        elif status in open_since:
            periods.append((status, open_since.pop(status), row["date"]))
    # A period still open at the end of the race runs until the chequered flag.
    for status, start in open_since.items():
        periods.append((status, start, pd.Timestamp.max.tz_localize("UTC")))
    return pd.DataFrame(periods, columns=["status", "start", "end"])


def _add_neutralised_flag(laps: pd.DataFrame, periods: pd.DataFrame) -> pd.DataFrame:
    """Flag laps that overlap any neutralised period."""
    lap_end = laps["date_start"] + pd.to_timedelta(laps["lap_duration"].fillna(0), unit="s")
    flag = pd.Series(False, index=laps.index)
    for _, p in periods.iterrows():
        flag |= (laps["date_start"] < p["end"]) & (lap_end > p["start"])
    laps["IsNeutralised"] = flag
    return laps


def _add_time_series(laps: pd.DataFrame, weather: pd.DataFrame, position: pd.DataFrame) -> pd.DataFrame:
    """Attach latest weather sample and race position known at the start of each lap."""
    laps = laps.sort_values("date_start")

    w = weather.copy()
    w["date"] = pd.to_datetime(w["date"], format="ISO8601")
    w = w.sort_values("date")[["date", "track_temperature", "air_temperature", "rainfall", "humidity"]]
    laps = pd.merge_asof(laps, w, left_on="date_start", right_on="date", direction="backward")
    laps = laps.drop(columns="date")

    pos = position.copy()
    pos["date"] = pd.to_datetime(pos["date"], format="ISO8601")
    pos = pos.sort_values("date")[["date", "driver_number", "position"]]
    laps = pd.merge_asof(
        laps, pos, left_on="date_start", right_on="date", by="driver_number", direction="backward"
    )
    return laps.drop(columns="date")


def build_lap_table(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine the raw OpenF1 tables into one tidy row per driver per lap."""
    laps = raw["laps"].copy()
    laps["date_start"] = pd.to_datetime(laps["date_start"], format="ISO8601")
    laps["is_pit_out_lap"] = laps["is_pit_out_lap"].fillna(False).astype(bool)

    laps = _add_tyres(laps, raw["stints"])
    laps = _add_pit_in_flag(laps)
    laps = _add_neutralised_flag(laps, neutralised_periods(raw["race_control"]))
    laps = _add_time_series(laps, raw["weather"], raw["position"])

    drivers = raw["drivers"][["driver_number", "name_acronym", "team_name"]]
    laps = laps.merge(drivers, on="driver_number", how="left")

    sectors = ["duration_sector_1", "duration_sector_2", "duration_sector_3"]
    sector_sum = laps[sectors].sum(axis=1, min_count=3)
    # OpenF1 has no IsAccurate flag: a lap counts as accurate when all three
    # sectors exist and add up to the lap time (within 0.1 s).
    laps["IsAccurate"] = (sector_sum - laps["lap_duration"]).abs() < 0.1

    laps = laps.rename(
        columns={
            "name_acronym": "Driver",
            "team_name": "Team",
            "driver_number": "DriverNumber",
            "lap_number": "LapNumber",
            "lap_duration": "LapTime",  # already in seconds
            "stint_number": "Stint",
            "compound": "Compound",
            "is_pit_out_lap": "IsPitOutLap",
            "position": "Position",
            "track_temperature": "TrackTemp",
            "air_temperature": "AirTemp",
            "rainfall": "Rainfall",
            "humidity": "Humidity",
            "date_start": "LapStartDate",
        }
    )
    columns = [
        "Driver", "DriverNumber", "Team", "LapNumber", "LapStartDate", "LapTime",
        "Compound", "TyreLife", "Stint", "Position", "IsPitInLap", "IsPitOutLap",
        "IsNeutralised", "IsAccurate", "TrackTemp", "AirTemp", "Rainfall", "Humidity",
    ]
    return laps[columns].sort_values(["DriverNumber", "LapNumber"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def clean_laps(
    laps: pd.DataFrame, outlier_threshold: float = 1.07
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove non-representative laps and report how many each rule removed.

    Rules are applied in order, so each lap is counted under the first rule
    that removes it. The last rule drops laps slower than `outlier_threshold`
    times the driver's median of the laps that survived the other rules
    (failures, spins, damage). Returns (clean_laps, removal_report).
    """
    rules = [
        ("no lap time", laps["LapTime"].isna()),
        ("lap 1 (standing start)", laps["LapNumber"] == 1),
        ("pit in-lap", laps["IsPitInLap"]),
        ("pit out-lap", laps["IsPitOutLap"]),
        ("SC / VSC / red flag", laps["IsNeutralised"]),
        ("inaccurate timing", ~laps["IsAccurate"]),
        ("unknown compound", laps["Compound"].isna() | (laps["Compound"] == "UNKNOWN")),
    ]
    keep = pd.Series(True, index=laps.index)
    report = []
    for name, mask in rules:
        removed = keep & mask
        report.append({"rule": name, "laps_removed": int(removed.sum())})
        keep &= ~mask

    driver_median = laps["LapTime"].where(keep).groupby(laps["Driver"]).transform("median")
    outlier = keep & (laps["LapTime"] > outlier_threshold * driver_median)
    report.append({"rule": f"outlier (> {outlier_threshold:.0%} of driver median)",
                   "laps_removed": int(outlier.sum())})
    keep &= ~outlier

    report = pd.DataFrame(report)
    report.loc[len(report)] = {"rule": "TOTAL removed", "laps_removed": int((~keep).sum())}
    report.loc[len(report)] = {"rule": "kept", "laps_removed": int(keep.sum())}
    return laps[keep].reset_index(drop=True), report


def save_processed(
    laps: pd.DataFrame, year: int, country: str, processed_dir: Path | str = "data/processed"
) -> Path:
    """Save a lap table as parquet, e.g. data/processed/laps_2023_bahrain.parquet."""
    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    path = processed_dir / f"laps_{year}_{country.lower().replace(' ', '_')}.parquet"
    laps.to_parquet(path, index=False)
    return path


def load_clean_race(
    year: int, country: str, cache_dir: Path | str = DEFAULT_CACHE_DIR
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Download one race and return (all_laps, clean_laps, removal_report)."""
    all_laps = build_lap_table(load_raw_race(year, country, cache_dir))
    clean, report = clean_laps(all_laps)
    return all_laps, clean, report
