# Repo Workflow

This file describes how this repository is organized and how work should flow through it.

## Main Paths

- `src/trader.py`: active submission file.
- `src/datamodel.py`: local copy of the IMC datamodel; treat as fixed reference.
- `strategies/`: archived strategy snapshots worth keeping.
- `backtester/prosperity3bt/`: local backtester fork and round resources.
- `backtests/`: saved output logs from local backtests.
- `notebook_analysis/`: notebooks for exploratory analysis by round.
- `docs/`: concise project context and round plans.

## Normal Workflow

1. Inspect new round data in a notebook.
2. Write down round-level and product-level hypotheses in `docs/rounds/roundN/`.
3. Convert the best hypothesis into trader logic in `src/trader.py`.
4. Backtest locally across all available round days.
5. Record experiment outcome in the round experiment log.
6. Snapshot meaningful strategy milestones in `strategies/`.

## Backtester Workflow

From repo root with the venv active:

```bash
prosperity3bt src/trader.py 0
prosperity3bt src/trader.py 1
prosperity3bt src/trader.py 1 --merge-pnl
prosperity3bt src/trader.py 1-0
```

Current local convention:

- Round resources live under `backtester/prosperity3bt/resources/roundN/`.
- Product limits are configured in `backtester/prosperity3bt/data.py`.
- Logs are saved in `backtests/`.

## File Discipline

- Keep submission logic concentrated in `src/trader.py` until a clearer module split is justified.
- Keep research detail in notebooks, not in the trader.
- Move only validated strategy milestones into `strategies/`.
- Use docs for hypotheses, decisions, and next steps, not raw plots.
- Do not use ad hoc `print()` statements in `src/trader.py`; use a compact structured logger if logging is needed.

## On New Rounds

1. Add the new CSVs to `backtester/prosperity3bt/resources/roundN/`.
2. Update local position limits if needed.
3. Create or refresh the round notebook.
4. Update `docs/rounds/roundN/overview.md`.
5. Add product-specific notes for each new asset.
6. Start an experiment log before major code iteration.

## Agent Guidance

- Read stable docs first, then the current round folder.
- Work from product-specific notes when doing targeted analysis.
- Update the experiment log when a hypothesis is tested or rejected.
- Do not duplicate the same context across multiple markdown files.
- Treat prior-year public code as prior art, not as production-ready inheritance.
