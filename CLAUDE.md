# CLAUDE.md — f1-race-strategy-predictor

Instruções para o Claude Code trabalhar neste repositório junto com a Fátima. Leia tudo antes de começar.

## 1. Objetivo do projeto

Projeto de portfólio em Data Science aplicado à Fórmula 1: **estratégia de corrida preditiva**.

1. Treinar um modelo de Machine Learning (XGBoost, com Random Forest como comparação) que prevê o **tempo de volta** a partir de desgaste de pneu, composto, volta da corrida, clima e tráfego.
2. Usar o modelo para **simular estratégias de pit stop** (1 parada, 2 paradas, volta da parada, composto) e escolher a de menor tempo total previsto.
3. Comparar a estratégia sugerida com a que as equipes realmente fizeram.

O público é recrutador/engenheiro de dados de F1. O repositório precisa ser limpo, reprodutível e honesto sobre as limitações.

## 2. Stack (tudo gratuito)

- Python 3.10+
- API pública [OpenF1](https://openf1.org) (gratuita, sem chave, dados a partir de 2023), acessada com `urllib` da biblioteca padrão.
  O `fastf1` foi descartado: a versão atual exige assinatura paga do F1TV para baixar os dados de timing.
- `pandas`, `numpy`, `scikit-learn`, `xgboost`
- `matplotlib` (gráficos; `seaborn` opcional)
- `pytest` (testes)
- `jupyter` (notebooks)

Não usar serviços pagos nem APIs com chave.

## 3. Estrutura do repositório

```
f1-race-strategy-predictor/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── cache/          # cache JSON da OpenF1 (NÃO versionar)
│   └── processed/      # datasets limpos (parquet/csv, NÃO versionar os grandes)
├── notebooks/
│   ├── 01_exploracao_dados.ipynb
│   ├── 02_features_e_modelo.ipynb
│   └── 03_simulacao_estrategias.ipynb
├── src/
│   ├── __init__.py
│   ├── data_loader.py   # baixa e limpa as voltas
│   ├── features.py      # cria as variáveis
│   ├── model.py         # treino e avaliação
│   └── simulator.py     # simula pit stops e soma o tempo
├── reports/
│   └── figures/         # gráficos usados no README
└── tests/
    └── test_simulator.py
```

Regra: lógica reutilizável vive em `src/`. Notebooks só importam de `src/`, mostram gráficos e contam a história. Não duplicar código entre notebook e `src/`.

## 4. Setup inicial

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` inicial:

```
pandas
numpy
scikit-learn
xgboost
matplotlib
seaborn
pytest
jupyter
pyarrow
```

`.gitignore` deve incluir: `.venv/`, `__pycache__/`, `.ipynb_checkpoints/`, `data/cache/`, `data/processed/*.parquet`, `.DS_Store`.

O cache é automático: `src/data_loader.fetch_openf1` salva cada resposta da API em `data/cache/` e só baixa de novo se o arquivo não existir.

## 5. Etapas de trabalho (faça uma por vez e PARE ao final de cada para a Fátima revisar; siga o protocolo da seção 9)

### Etapa 1 — Dados (`data_loader.py` + notebook 01)
- Função que carrega uma corrida pela OpenF1 (`load_clean_race(ano, país)`), juntando os endpoints `laps`, `stints`, `race_control`, `weather`, `drivers` e `position` em uma linha por piloto por volta (colunas: `Driver`, `LapNumber`, `LapTime`, `Compound`, `TyreLife`, `Stint`, `IsPitInLap`, `IsPitOutLap`, `IsNeutralised`, `IsAccurate`, `Position`, temperatura da pista/ar, chuva).
- Converter `LapTime` para segundos.
- **Limpeza obrigatória:** remover voltas de entrada e saída dos boxes, voltas sob safety car/VSC/bandeira vermelha (montadas a partir das mensagens de `race_control`), voltas sem tempo e voltas não precisas (`IsAccurate` falso: setores ausentes ou que não somam o tempo de volta). Documentar quantas voltas foram removidas.
- Começar com **uma corrida só** (sugestão: um GP de 2023 ou 2024 com pelo menos 2 paradas comuns). Generalizar para várias corridas só depois que tudo funcionar.
- **Pronto quando:** notebook 01 mostra o dataset limpo, distribuição dos tempos de volta e o efeito visível do desgaste do pneu.

### Etapa 2 — Features e modelo (`features.py`, `model.py` + notebook 02)
- Features: composto (one-hot ou ordinal), idade do pneu (`TyreLife`), número da volta, temperatura da pista, chuva, posição/tráfego (distância ou posição relativa ao carro da frente, se disponível).
- Considerar uma feature de "combustível" aproximada pela volta (carro fica mais leve ao longo da corrida).
- Modelo de base (linha de base simples, por exemplo média por composto) **antes** do XGBoost, para ter comparação.
- Treinar XGBoost e Random Forest. Métricas: MAE e RMSE em segundos.
- **Validação sem vazamento:** separar treino/teste por **corrida** (ou por piloto/stint), nunca embaralhando voltas aleatórias. Se começar com uma corrida só, separar por stint ou por pilotos e avisar no README que o ideal é validar em outras corridas.
- Mostrar importância das features e gráfico previsto vs. real.
- **Pronto quando:** o modelo bate a linha de base com margem clara e o notebook explica o erro de forma honesta.

### Etapa 3 — Simulação (`simulator.py` + notebook 03)
- Estimar o tempo perdido no pit stop **a partir dos dados** (diferença entre volta de entrada + saída e voltas normais) ou usar um valor fixo documentado (cerca de 20–25 s, varia por pista). Deixar parametrizável.
- Gerar estratégias candidatas: 1 parada e 2 paradas, variando a volta da parada e a sequência de compostos. Respeitar a regra de usar pelo menos dois compostos diferentes em corrida seca.
- Para cada estratégia: prever o tempo de cada volta com o modelo, somar e adicionar as perdas de pit stop.
- Ranking das estratégias e gráfico de tempo total por volta de parada.
- Comparar com a estratégia real do vencedor e de alguns pilotos.
- **Pronto quando:** existe um gráfico principal claro (o "resultado" que vai no README) e a função do simulador tem testes.

### Etapa 4 — Testes
- `tests/test_simulator.py`: poucos testes simples e determinísticos (ex.: tempo total = soma das voltas + pit loss; estratégia inválida é rejeitada; mais paradas aumentam o pit loss total).
- Rodar com `pytest`.

### Etapa 5 — Acabamento do portfólio
- Preencher o README com resultados reais (métricas, gráfico principal, estratégia sugerida vs. real). Os campos `TBD` do README devem ser todos substituídos.
- Salvar figuras em `reports/figures/` e referenciá-las no README.
- Conferir que os notebooks rodam do início ao fim (`Restart & Run All`) e estão com as saídas salvas.
- Revisar limitações no README (seção "Limitations").

## 6. Convenções de código

- Python limpo: funções pequenas, nomes claros em inglês, type hints e docstrings curtas.
- Código e comentários em inglês; conversa com a Fátima em português.
- Sem caminhos absolutos. Parâmetros (ano, GP, pit loss, seed) no topo ou em argumentos.
- Fixar seed (`random_state=42`) em tudo que for aleatório.
- Nada de lógica duplicada entre notebook e `src/`.
- Gráficos legíveis: título, eixos com unidade, legenda.

## 7. Git — REGRA PRINCIPAL: quem faz o commit é a Fátima

- **Nunca** rodar `git commit`, `git push`, `git add` com commit em seguida, `git merge`, `git rebase`, `git reset` ou criar/trocar branch por conta própria. Isso vale mesmo que pareça óbvio ou conveniente.
- Comandos de leitura são permitidos: `git status`, `git diff`, `git log`.
- Ao final de cada etapa, **sugerir** o commit para ela executar (formato na seção 9): lista de arquivos e mensagem pronta.
- Mensagens de commit em inglês, no imperativo, curtas: `Add data loader with lap cleaning`, `Train XGBoost baseline`.
- Um commit por etapa, no mínimo. Se a etapa tiver partes bem separadas, sugerir mais de um commit.
- Nunca sugerir commitar `data/cache/`, `.venv/`, arquivos de dados grandes ou saídas temporárias.
- Se ela pedir explicitamente para você commitar alguma vez, confirme uma vez antes de fazer.

## 8. O que NÃO fazer

- Não usar logos, imagens ou marcas oficiais da F1, nem dar a entender afiliação. O README deve ter o aviso de projeto não oficial.
- Não afirmar resultados que não foram medidos. Todo número no README vem de execução real.
- Não validar com voltas embaralhadas aleatoriamente (vazamento).
- Não ocultar limitações. O modelo não captura safety car, ultrapassagens, decisões de rivais nem falhas mecânicas, e isso deve estar escrito.
- Não instalar nada além do `requirements.txt` sem avisar.

## 9. Como trabalhar com a Fátima — protocolo de cada etapa

A Fátima é desenvolvedora back-end (C# .NET) e cursa Ciência de Dados. Ela conhece programação, mas precisa entender e saber **defender cada decisão de ML em entrevistas**. Por isso, o ritmo é: uma etapa por vez, com revisão dela antes de seguir.

### Antes de começar a etapa
- Diga em 2–3 linhas o que vai fazer e quais arquivos vai criar ou alterar.
- Se uma decisão puder mudar o escopo (outra corrida, outras features, outro modelo), pergunte antes.

### Durante a etapa
- Implemente só o que é daquela etapa. Não adiantar etapas seguintes.
- Rode o código e os notebooks para garantir que funcionam antes de entregar. Se algo falhar, corrija ou explique o erro.

### Ao final da etapa: PARE e entregue sempre estes 4 blocos, nesta ordem

1. **O que foi feito:** lista curta dos arquivos criados/alterados e o que cada um faz.
2. **Como funciona:** explicação em linguagem simples, passo a passo, do que o código faz e *por que* foi feito assim (por que esse filtro, esse split, essa feature). Use analogias com back-end quando ajudar. Inclua 2–3 perguntas que um entrevistador poderia fazer sobre essa etapa, com a resposta curta.
3. **Como conferir:** os comandos exatos para ela rodar e ver o resultado (por exemplo `pytest`, abrir o notebook, o que deve aparecer na tela).
4. **Commit sugerido (ela executa):**

```bash
git status
git add <arquivos listados explicitamente>
git commit -m "<mensagem em inglês>"
```

   Liste os arquivos um a um no `git add` (evite `git add .`) para nada indevido entrar. Depois do bloco, escreva: "Quando você fizer o commit, me avise para seguirmos para a Etapa X." E **espere**.

### Regras gerais
- Só avance para a próxima etapa depois que ela confirmar.
- Se ela pedir ajustes, faça e entregue de novo os 4 blocos (o commit sugerido passa a refletir o que mudou).
- Nunca afirmar que algo funciona sem ter rodado. Se não deu para rodar (por exemplo, sem internet para baixar dados), diga claramente.