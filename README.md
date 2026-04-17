## Setup
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the backtester as a local editable package
pip install -e backtester/
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

## Other info
Using fork of this backtester: https://github.com/jmerle/imc-prosperity-3-backtester/tree/master
This repo is very useful: https://github.com/MarkBrezina/Ctrl-Alt-DefeatTheMarket?tab=readme-ov-file


On new rounds:
- Download new data capsule → copy CSVs to backtester/prosperity3bt/resources/round{N}/
- Add new products to LIMITS in data.py
- Open notebooks/round{N}_analysis.ipynb, run the standard analysis (mid price over time, spread, autocorrelation, bot structure
- Form a hypothesis about each new product's behavior
- Implement strategy in src/trader.py, keeping previous round strategies intact
- Backtest, iterate on params, check consistency across days
- Submit → copy to strategies/ with timestamp and description