# Prosperity Trading

## Setup
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the backtester as a local editable package
pip install -e backtester/
```

## Repo Structure

```
prosperity-trading/
├── src/
│   ├── datamodel.py          # IMC's official datamodel — do not edit
│   └── trader.py             # Active submission file
├── strategies/               # Saved strategy snapshots
└── backtester/
    └── prosperity3bt/
        ├── data.py           # Add new products/limits here each round
        └── resources/
            ├── round0/       # Tutorial data (TOMATOES, EMERALDS)
            ├── round1/       # Add CSVs here as rounds are released
            └── ...
```

## Each Round: Adding New Data

1. Download the data capsule from the Prosperity dashboard
2. Copy the CSVs into `backtester/prosperity3bt/resources/round{N}/`
3. Add any new products and their position limits to `backtester/prosperity3bt/data.py`:
   ```python
   LIMITS = {
       "EMERALDS": 80,
       "TOMATOES": 80,
       # add new products here
   }
   ```

## Running Backtests

From the repo root, with your venv active:

```bash
# Backtest on all days in a round
prosperity3bt src/trader.py 0

# Specific day
prosperity3bt src/trader.py 0--1
prosperity3bt src/trader.py 0--2

# Merge PnL across all days in a round
prosperity3bt src/trader.py 0 --merge-pnl

# Save output log
prosperity3bt src/trader.py 0 --out logs/run.log

# Open result in visualizer
prosperity3bt src/trader.py 0 --vis
```

## Submitting

Upload `src/trader.py` directly to the Prosperity dashboard.