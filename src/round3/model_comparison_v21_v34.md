# Round 3 Model Comparison: `v21`-`v34` vs `trader_v1`-`trader_v20`

## Scope

This note compares the newly added open-source models `v21` through `v34` against the earlier internal versions `trader_v1` through `trader_v20`.

The comparison is not just total PnL. It also looks at:
- product-by-product winners
- product-by-product failure cases
- what each strong or weak model was actually trying to do in code
- what those outcomes imply about where the real edge is and where the current traps are

Backtests were run locally with the existing Round 3 backtester after the Round 3 position-limit patch already made in the local backtester.

## Method

Batch command used for the new files:

```bash
source .venv/bin/activate
for f in src/round3/v21.py src/round3/v22.py src/round3/v23.py src/round3/v24.py src/round3/v25.py src/round3/v26.py src/round3/v27.py src/round3/v28.py src/round3/v29.py src/round3/v30.py src/round3/v31.py src/round3/v32.py src/round3/v33.py src/round3/v34.py; do
  prosperity3bt "$f" 3 --no-out --no-progress
done
```

All `v21`-`v34` files compile. This report also uses the previously collected `trader_v1`-`trader_v20` matrix.

## Overall Leaderboard

### Open-source models `v21`-`v34`

| Rank | Version | Total PnL |
| --- | --- | ---: |
| 1 | `v24` | 601,742 |
| 2 | `v25` | 431,042 |
| 3 | `v22` | 128,492 |
| 4 | `v27` | 124,713 |
| 5 | `v31` | 51,939 |
| 6 | `v32` | 48,142 |
| 7 | `v28` | 23,656 |
| 8 | `v34` | 8,410 |
| 9 | `v33` | 8,401 |
| 10 | `v26` | 938 |
| 11 | `v21` | -144,146 |
| 12 | `v23` | -249,097 |
| 13 | `v30` | -760,827 |
| 14 | `v29` | -764,638 |

### Best earlier internal models for reference

| Rank | Version | Total PnL |
| --- | --- | ---: |
| 1 | `trader_v19` | 33,697 |
| 2 | `trader_v7` | 29,254 |
| 3 | `trader_v8` | 29,037 |
| 4 | `trader_v5` | 28,316 |
| 5 | `trader_v6` | 28,058 |
| 6 | `trader_v1` | 26,144 |
| 7 | `trader_v11` | 23,728 |
| 8 | `trader_v10` | 21,630 |

### Worst earlier internal models for reference

| Version | Total PnL | Main failure |
| --- | ---: | --- |
| `trader_v14` | -892,361 | middle-strike spread overlay blew up in `VEV_5300` and `VEV_5400` |
| `trader_v20` | -206,339 | local-smile residual z-score mean reversion blew up in `VEV_5300` to `VEV_5500` |
| `trader_v18` | -142,574 | vertical-spread target logic failed badly in the far strikes |
| `trader_v17` | -135,275 | rolling-IV z-score target-position logic failed badly, especially `VEV_6000` |

## First Read Of The Results

The headline is not subtle:
- the strongest open-source models massively outperform the earlier in-house set on this backtester
- the best open-source winners are not all doing the same thing, but the common pattern is more aggressive and broader voucher participation than our first twenty versions
- the biggest losers are often not "bad overall traders" in the abstract; they usually have one sub-book that is catastrophically wrong while other sub-books are fine or even strong

The two biggest examples of that last point are:
- `v29` and `v30`: voucher and VELVET logic are actually positive, but `HYDROGEL_PACK` loses `-884,459` and destroys the book
- `v23`: the underlying and lower-strike logic still work, but the added skew and fair-exit logic detonates `VEV_5400` and `VEV_5500`

That matters because these are not useless failures. They isolate which local design choices are dangerous.

## Product Winners And Informative Losers

The table below uses aggregate round PnL per product across all tested versions. For the loser column, I use the worst active trader for that product rather than a model that simply never traded it.

| Product | Best version | Best PnL | What that winner was doing | Worst active version | Worst PnL | What that failure suggests |
| --- | --- | ---: | --- | --- | ---: | --- |
| `HYDROGEL_PACK` | `v24` | 137,772 | Kalman-style mean reversion to a static fair anchor with active taking and quoting | `v29` | -884,459 | the HYDRO engine can dominate total risk; sophisticated voucher logic does not save a broken underlier book |
| `VELVETFRUIT_EXTRACT` | `v24` | 87,908 | same Kalman-MR underlier engine, but with much better monetization than our simpler underlier-only designs | `v28` | -21,683 | pairing and voucher logic can still leave the underlying hedge book badly behaved |
| `VEV_4000` | `v24` | 44,785 | anchor-divergence plus market making around a broad running anchor | `v21` | -146,410 | pure misread of low-strike fair value is lethal; low-strike vouchers are not forgiving |
| `VEV_4500` | `v24` | 49,563 | same anchor-divergence/MM engine | `v22` | -32 | this strike is broadly stable; even weak active models did not lose much here |
| `VEV_5000` | `v24` | 86,591 | heavy participation in the central liquid region of the strip | `v32` | 100 | practically no active loser here; this is one of the safest monetizable strikes in the current sample |
| `VEV_5100` | `v24` | 83,634 | same as above, with balanced aggressive participation | `v28` | -668 | mild losses show this strike is tradable, but hedge construction still matters |
| `VEV_5200` | `v24` | 65,860 | same anchor-divergence/MM approach | `v27` | -5,451 | smile-fit and pair logic can still mis-handle the middle if inventory nets are not tight enough |
| `VEV_5300` | `v24` | 25,847 | aggressive but still controlled outright participation | `trader_v14` | -376,896 | middle-strike spread overlays can be violently wrong if spread-position control is weak |
| `VEV_5400` | `v24` | 17,513 | controlled outright participation | `trader_v14` | -364,443 | same conclusion; this strike punished overconfident relative-value overlays hard |
| `VEV_5500` | `v25` | 2,522 | aggressive anchor-divergence/MM, slightly better than `v24` at the top of the traded core strip | `v23` | -239,506 | Stoikov-style inventory skew and fair exits destabilized the high-middle strike regime |
| `VEV_6000` | `v27` | 450 | special-case wide-strike passive 0/1 quoting plus call-spread logic | `trader_v17` | -65,580 | far-strike target-position or rolling-zscore logic is dangerous when realized fill quality is poor |
| `VEV_6500` | `v27` | 450 | same special-case wide-strike passive MM logic | `trader_v18` | -37,096 | far-strike structures can lose badly when the model forces positions instead of waiting for obvious passive edge |

## Code-Level Comparison By Strategy Family

## 1. `v24` and `v25`: the clear winners

These two are the most important files in the new set.

### `v24`

Code pattern:
- two pipelines inside one trader
- `HYDROGEL_PACK` and `VELVETFRUIT_EXTRACT` use Kalman-style mean reversion toward fixed fair anchors
- `VEV_4000` through `VEV_5500` use anchor-divergence plus market making
- fair for options is based on a running anchor and full-depth fair, not on a narrow local residual-only signal
- the strategy is willing to trade many strikes, not just one or two names

Why it won:
- it made money almost everywhere instead of relying on one hero product
- it dominated both underliers and all core vouchers from `VEV_4000` to `VEV_5400`
- it did not bother with `VEV_6000` and `VEV_6500`, which is sensible because those strikes were low-value for most active approaches

Important nuance:
- this looks extremely backtester-friendly
- the code is broad, aggressive, and quote-heavy, which aligns well with tape-share environments
- that does not mean it is automatically the most robust live design, but on this local test it is the strongest benchmark by a wide margin

### `v25`

Code pattern:
- same broad family as `v24`, but explicitly more aggressive
- aggressor-flow adjustment, expanding anchor, divergence-taking, vol-aware spread widening, inventory skew
- thresholds are intentionally tuned lower to fire more often

Why it still matters despite finishing behind `v24`:
- it is still the second-best total model by a huge margin
- it is the best `VEV_5500` model in the entire sample
- unlike `v24`, its Hydro contribution is almost zero, so it is effectively showing that there is a massive voucher-only edge in this backtester even without much help from Hydro

Read-through:
- `v24` is the better all-book benchmark
- `v25` is the better evidence that aggressive voucher participation itself is enough to be highly competitive

## 2. `v22` vs `v23`: one good minimal-change model, one very informative failure

### `v22`

Code pattern:
- starts from an older successful template and changes one central thing
- replaces a running-mean option anchor with Black-Scholes plus a static smile anchor
- keeps the underlier mean-reversion book
- adds a decayed signed-flow tilt to thresholds

Why it worked:
- the change was conservative and coherent
- it moved the voucher anchor closer to a cross-product fair-value model without layering on too much extra inventory logic
- result: strong underlying PnL, moderate positive voucher PnL, no catastrophic strike

### `v23`

Code pattern:
- same base as `v22`
- adds Stoikov-style reservation-price skew
- adds flow-aware exit-at-fair logic
- modulates skew based on whether flow agrees with current inventory

Why it failed:
- the extra skew logic made the quote management more path-dependent
- that path dependence was harmless in lower strikes but disastrous in `VEV_5400` and `VEV_5500`
- aggregate losses there were so large that they overwhelmed otherwise positive underlier and lower-strike performance

The practical lesson:
- this is strong evidence against adding inventory-aware skew overlays to a working voucher baseline without very explicit strike-specific controls
- if we revisit this family, the right move is not to copy `v23`; it is to start from `v22` and add much narrower changes

## 3. `v27`: the most interesting non-anchor-divergence open-source model

Code pattern:
- underliers use explicit mean-reverting market making around fitted means
- VELVET uses an AR-style predicted mean around a long-run level
- vouchers use a live EWMA smile fit in log-moneyness, Black-Scholes fair values, passive MM, portfolio-delta leaning, and spread logic
- `VEV_6000` and `VEV_6500` are handled specially as wide 0/1 books

Why it stands out:
- it is the only model that produced the best aggregate results in `VEV_6000` and `VEV_6500`
- that strength did not come from forcing positions; it came from understanding that the far strikes should often be treated as a different market regime entirely
- it still made solid money in Hydro, Velvet, and several lower strikes

Where it was weaker:
- it lost money in `VEV_5200`, `VEV_5300`, and `VEV_5500`
- so it is not a universal winner across the strip

Best interpretation:
- `v27` is the best evidence so far that the far strikes need separate logic, not just smaller versions of the middle-strike logic
- its special-case wide-strike handling is worth isolating and reusing

## 4. `v31` and `v32`: robust hybrid strip engines, decent but not dominant

Code pattern:
- both use Black-Scholes as the coordinate system
- both build hybrid IV strip logic, side-aware fair bands, and voucher hedging around VELVET
- both try to be more robust and less day-specific than the most aggressive anchor-divergence models

Results:
- `v31`: 51,939, with strong voucher breadth but `VELVETFRUIT_EXTRACT` at `-10,927`
- `v32`: 48,142, lower voucher upside but `VELVETFRUIT_EXTRACT` is positive instead of sharply negative

What that says:
- these are credible robust baselines, but they are not extracting nearly as much edge from the strip as `v24` or `v25`
- they are useful more as design references than as final leaders
- if we want something structurally more conservative than `v24`, `v31` and `v32` are better foundations than the earlier internal family

## 5. `v28`: good voucher ideas, weak hedge book

Code pattern:
- clean Black-Scholes and IV-slice framework
- quote repair, hybrid local-IV fair values, pair-first strip logic, buffered dynamic hedge

Why the total is only 23,656:
- `VEV_4500` and `VEV_5000` are solid positives
- Hydro is positive
- but `VELVETFRUIT_EXTRACT` loses `-21,683`

Interpretation:
- the voucher layer is not the main problem here
- the hedge / underlier execution layer is
- this is similar in spirit to `v29` and `v30`, just much less catastrophic

## 6. `v29` and `v30`: catastrophic totals, but not because the vouchers are bad

This pair is easy to misread if you only look at total PnL.

Code pattern:
- sophisticated voucher stack
- repaired call slices, hybrid smile fits, pair support, active voucher selection, hedging logic
- clearly much more engineered than our early internal variants

Backtest reality:
- `v29` total: `-764,638`
- `v30` total: `-760,827`
- both lose `-884,459` in `HYDROGEL_PACK`
- both are positive in `VELVETFRUIT_EXTRACT`
- both are positive in `VEV_4000`, `VEV_4500`, `VEV_5000`, and `VEV_5100`

That means:
- these are not failed voucher models
- they are failed Hydro models attached to decent voucher models

This is one of the most useful observations in the entire batch, because it says the voucher engine may be salvageable if separated from the broken underlier engine.

## 7. `v33` and `v34`: heavily filtered pair/strip engines that barely fire

Code pattern:
- pair-first strip logic
- deep-pair gating
- cooldowns and feasibility checks
- much more selective activation than the aggressive winners

Results:
- both finish around `8.4k`
- almost no meaningful voucher realization compared with the top models

Interpretation:
- these are over-filtered for this backtester
- the issue is not obvious wrong-way risk like `v23` or `v29`
- the issue is under-participation

## Where The Earlier Internal Models Still Matter

## `trader_v19`: still the best simple underlier benchmark

Code pattern:
- underlying-only
- inspired by the old adverse-volume KELP architecture
- predicts a one-step mean-reverting fair and sizes quotes off edge to that fair

Why it still matters:
- it remains the best of our own `v1`-`v20` family
- it proves that a structurally different underlying engine can be strong even without vouchers
- it is still a useful control model because it is much simpler than the best open-source voucher engines

But it is now clearly not the overall frontier. The new open-source leaders outperform it by a large margin.

## `trader_v7`: still the best clean copy-inspired voucher baseline from our side

Code pattern:
- pure static smile using coefficients from a strong prior team
- clean outright voucher quoting baseline

Why it still matters:
- it is still the best simple voucher baseline in our internal set
- it makes the right point that a stable static smile is often better than noisy local-only adaptation

But the open-source leaders show that broader strike coverage and more aggressive participation are where the large backtester gains are coming from.

## `trader_v14` and `trader_v20`: the two most useful negative controls

### `trader_v14`

Code pattern:
- middle-strike cluster only
- local-only smile fitting
- tight adjacent-strike spread overlays

Result:
- worst active model in both `VEV_5300` and `VEV_5400`

Interpretation:
- the middle cluster is not a free relative-value zone
- local spread overlays can amplify inventory and basis risk instead of reducing it

### `trader_v20`

Code pattern:
- local-smile residual z-score model
- pure residual mean-reversion rebalance
- no passive quoting

Result:
- large losses in `VEV_5300`, `VEV_5400`, and `VEV_5500`

Interpretation:
- a local residual may be a useful diagnostic, but it is not a safe standalone execution rule
- this strongly argues against "middle residual extreme means revert immediately" as a primary trading thesis

## Main Conclusions

1. The strongest backtester edge in the current expanded sample is voucher breadth plus aggressive participation, not narrow single-strike specialization.

2. `v24` is the current benchmark. It wins the total leaderboard and wins almost every meaningful product leaderboard.

3. `v25` is nearly as important as `v24`, because it shows that very aggressive voucher participation alone can generate huge PnL even when Hydro contributes almost nothing.

4. `v22` is the best "controlled" open-source model. It is a good example of improving a decent base with one coherent valuation change rather than piling on layered inventory logic.

5. `v23` is one of the most useful failures. Stoikov-style skew and flow-aware exit logic are not harmless improvements; in this environment they can specifically blow up the upper-middle strikes.

6. `v27` has the best evidence for a separate far-strike regime. Its special handling of `VEV_6000` and `VEV_6500` is the best thing any model did in those names.

7. `v29` and `v30` should not be discarded wholesale. Their total PnL is terrible, but the data says the problem is overwhelmingly Hydro, not the voucher engine.

8. `trader_v14` and `trader_v20` remain important negative controls. They both say the same thing from different angles: aggressive middle-strike local-relative-value logic is currently one of the easiest ways to lose a lot of money.

## Recommended Next Directions

1. Build a new hybrid that starts from `v24` or `v25` for the core voucher strip, but replaces their underlier handling with the safer parts of `trader_v19` or `v22`.

2. Isolate `v27`'s `VEV_6000` and `VEV_6500` special-case handling and graft only that far-strike logic onto a `v24`-style core strip engine.

3. Split `v29` or `v30` into components and rerun them with Hydro disabled. Those files may contain useful voucher logic hidden behind one catastrophic underlier subsystem.

4. Use `v22` as the controlled baseline for future incremental experiments, not `v23`. The gap between those two files is one of the clearest warnings in the whole matrix.
