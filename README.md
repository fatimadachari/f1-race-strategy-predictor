# 🏎️ F1 Race Strategy Predictor

Predicting lap times with machine learning and simulating pit-stop strategies to find the fastest way to run a Formula 1 race.

> **Status:** 🚧 in progress. Results below are filled in as each stage is completed.
>
> *Unofficial project. Not affiliated with, endorsed by, or connected to Formula 1, the FIA, or any team.*

## Overview

Race strategy comes down to a trade-off: tyres degrade, pit stops cost time, traffic slows cars down and track conditions change. This project answers one question:

**Given a race, which pit-stop strategy minimises predicted total race time?**

The approach has two parts:

1. **Lap-time model.** A gradient-boosting model (XGBoost, compared against Random Forest and a simple baseline) predicts lap time from tyre compound, tyre age, lap number, track temperature, rain and traffic.
2. **Strategy simulator.** For each candidate strategy (number of stops, stop lap, tyre sequence), the model predicts every lap, the simulator adds pit-stop losses, and the strategies are ranked by total predicted race time.

## Key result

| Item | Value |
|---|---|
| Race analysed | TBD |
| Baseline MAE (s) | TBD |
| XGBoost MAE (s) | TBD |
| Best predicted strategy | TBD |
| Actual winning strategy | TBD |

## Data

- Source: [FastF1](https://github.com/theOehrly/Fast-F1), an open-source Python library that exposes public timing and telemetry data (2018 onwards).
- No API key or account required.
- Raw data is cached locally in `data/cache/` and is **not** committed to the repository.

### Cleaning applied
- Removed in-laps and out-laps (pit entry and exit).
- Removed laps under safety car, virtual safety car and red flag.
- Removed laps without a valid lap time or flagged as inaccurate.

## Method

- **Features:** tyre compound, tyre age, lap number (proxy for fuel load), track temperature, rain, traffic/relative position.
- **Models:** baseline (mean lap time per compound), Random Forest, XGBoost.
- **Validation:** split by race or stint, never by random laps, to avoid leakage between laps of the same stint.
- **Metrics:** MAE and RMSE in seconds.
- **Simulation:** candidate 1-stop and 2-stop strategies respecting the two-compound rule; pit-stop loss estimated from data or set as a documented parameter.

## Repository structure

```
f1-race-strategy-predictor/
├── data/
│   ├── cache/            # FastF1 cache (git-ignored)
│   └── processed/        # cleaned datasets
├── notebooks/
│   ├── 01_exploracao_dados.ipynb      # data exploration
│   ├── 02_features_e_modelo.ipynb     # features and model
│   └── 03_simulacao_estrategias.ipynb # strategy simulation
├── src/
│   ├── data_loader.py    # download and clean laps
│   ├── features.py       # feature engineering
│   ├── model.py          # training and evaluation
│   └── simulator.py      # pit-stop strategy simulator
├── reports/figures/      # plots used in this README
└── tests/
    └── test_simulator.py
```

## Getting started

```bash
git clone https://github.com/fatimadachari/f1-race-strategy-predictor.git
cd f1-race-strategy-predictor

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

jupyter notebook notebooks/
```

Run the tests:

```bash
pytest
```

You can also open the notebooks in Google Colab, no local setup needed.

## Limitations

This is a simplified model. It does **not** capture:

- Safety cars, virtual safety cars and red flags (these laps are removed, not modelled).
- Overtaking difficulty and the effect of dirty air beyond a simple traffic feature.
- Rival strategies and in-race decision-making.
- Mechanical failures, damage and driver errors.
- Differences in pit-stop time between teams and stops (a single loss value is used per track).

Results should be read as an estimate of relative strategy quality, not as a real-time race engineer's recommendation.

## Roadmap

- [ ] Stage 1: data loading and cleaning
- [ ] Stage 2: features and lap-time model
- [ ] Stage 3: strategy simulator
- [ ] Stage 4: tests
- [ ] Stage 5: multi-race validation

## Tech stack

Python · FastF1 · pandas · scikit-learn · XGBoost · matplotlib · pytest

## Author

**Fátima Dachari**
GitHub: [@fatimadachari](https://github.com/fatimadachari)

## Disclaimer

F1, Formula 1 and related marks are trademarks of their respective owners. This repository is for educational and portfolio purposes only and uses publicly available data.
