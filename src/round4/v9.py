"""
Round 4 trader — IMC Prosperity 4.

Two-layer strategy:

  1. Per-product overrides for products with known statistical structure.
     HYDROGEL_PACK price is a stationary Ornstein-Uhlenbeck process
     around mu = 10000 with sigma ~ 30 (cf. peg-defense / bond-near-par
     in real markets). Strategy: trade against z-score deviations.

  2. Generic toxicity-aware market maker for everything else, using
     per-counterparty markout, VPIN, aggression, and Bayesian belief
     over {informed, noise, mm}. Spread widens with flow toxicity,
     quotes skew away from informed flow, optional follow on strong
     directional toxic flow.

State persisted across ticks via state.traderData (JSON).
"""
from __future__ import annotations

import json
import math

from datamodel import Order, OrderDepth, Trade, TradingState


POSITION_LIMITS: dict[str, int] = {
    "RAINFOREST_RESIN": 50,
    "KELP": 50,
    "SQUID_INK": 50,
    "EMERALDS": 80,
    "TOMATOES": 80,
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
    # Round 4 (official wiki)
    "VELVETFRUIT_EXTRACT": 200,
    "HYDROGEL_PACK": 200,
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
    "VEV_6000": 300,
    "VEV_6500": 300,
}
DEFAULT_LIMIT = 50


# ── HYDROGEL_PACK OU parameters (calibrated from data) ─────────────────────
# Empirical: mean 9994.65, std 34.6, avg spread 15.7 ticks, range [9891, 10081].
# Process is mean-reverting BUT short-term drift can persist for thousands
# of ticks → naive z-score fade bleeds during the drift. Mitigations:
#   1. EWMA fair value blends global mu with local mid → adapts to drift.
#   2. Momentum filter: skip new entries while mid still moving against us.
#   3. Position cap < limit so we keep dry powder for further deviation.
HYDRO_MU = 9995.0
HYDRO_SIGMA = 35.0
HYDRO_TAKE_K = 0.4              # take threshold in sigmas
HYDRO_Z_FULL = 2.5              # z at which target = ±max_pos
HYDRO_MAX_POS_FRAC = 0.70       # cap target position at 70% of limit
HYDRO_LAYERS = (15, 30, 50)     # passive layer offsets (ticks from fair)
HYDRO_FAIR_ALPHA = 0.5          # weight on global mu vs EWMA mid
HYDRO_EWMA_LAM = 0.005          # very slow EWMA so fair barely drifts
HYDRO_MOMO_LOOKBACK = 50
HYDRO_MOMO_BRAKE = 25           # brake size scales when momo > this


# ── Toxicity model tunables ─────────────────────────────────────────────────
W_VPIN = 0.25
W_MARKOUT = 0.35
W_AGG = 0.15
W_BAYES = 0.25

BASE_SPREAD = 2
SPREAD_ALPHA = 6.0
SKEW_BETA = 4.0
FOLLOW_THRESHOLD = 0.7
FOLLOW_CLIP = 3

MARKOUT_DT = 500
TRADE_HISTORY_CAP = 50
PENDING_CAP = 400
RECENT_FLOW_WINDOW = 1000

TYPES = ("informed", "noise", "mm")
PRIOR = (0.2, 0.6, 0.2)
TYPE_MEANS = {
    "informed": (1.0, 0.7),
    "noise":    (0.0, 0.3),
    "mm":       (0.0, 0.1),
}
TYPE_SIGMA = 0.6


def _mid(od: OrderDepth) -> float | None:
    if not od.buy_orders or not od.sell_orders:
        return None
    return 0.5 * (max(od.buy_orders) + min(od.sell_orders))


def _gauss(x: float, mu: float, sigma: float) -> float:
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z)


class Trader:
    def run(self, state: TradingState):
        # ── Restore memory ───────────────────────────────────────────────
        try:
            mem = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            mem = {}
        cp: dict[str, dict] = mem.get("cp", {})
        last_mid: dict[str, float] = mem.get("last_mid", {})
        pending: list[dict] = mem.get("pending_markouts", [])
        hydro_state: dict = mem.get("hydro", {"ewma": HYDRO_MU, "tape": []})

        result: dict[str, list[Order]] = {}

        # ── Update last_mid ──────────────────────────────────────────────
        mids: dict[str, float] = {}
        for product, od in state.order_depths.items():
            m = _mid(od)
            if m is None:
                m = last_mid.get(product)
            if m is not None:
                last_mid[product] = m
                mids[product] = m

        # ── Ingest market trades ─────────────────────────────────────────
        for product, trades in state.market_trades.items():
            mid = mids.get(product)
            for tr in trades or []:
                self._record_trade(tr, product, mid, cp, pending)

        for product, trades in state.own_trades.items():
            mid = mids.get(product)
            for tr in trades or []:
                self._record_trade(tr, product, mid, cp, pending)

        # ── Resolve pending markouts ─────────────────────────────────────
        still: list[dict] = []
        for p in pending:
            now = mids.get(p["product"])
            if now is None:
                still.append(p)
                continue
            if state.timestamp - p["ts"] >= MARKOUT_DT:
                rec = cp.get(p["cp"])
                if rec is not None:
                    rec["mo_sum"] = rec.get("mo_sum", 0.0) + p["side"] * (now - p["mid"])
                    rec["mo_n"] = rec.get("mo_n", 0) + 1
                    self._bayes_update(rec)
            else:
                still.append(p)
        pending = still[-PENDING_CAP:]

        # ── Toxicity per cp ──────────────────────────────────────────────
        tox: dict[str, float] = {cp_id: self._toxicity(rec) for cp_id, rec in cp.items()}

        # ── Build orders per product ─────────────────────────────────────
        for product, od in state.order_depths.items():
            mid = mids.get(product)
            if mid is None:
                continue
            pos = state.position.get(product, 0)
            limit = POSITION_LIMITS.get(product, DEFAULT_LIMIT)

            # Per-product overrides
            if product == "HYDROGEL_PACK":
                orders = self._hydrogel_pack(od, mid, pos, limit, hydro_state)
            else:
                flow_tox, flow_dir = self._flow_toxicity(
                    state.market_trades.get(product, []), tox, state.timestamp
                )
                orders = self._toxicity_quote(product, mid, pos, limit, flow_tox, flow_dir)

            if orders:
                result[product] = orders

        # ── Prune & serialize ────────────────────────────────────────────
        self._prune(cp)
        out = {
            "cp": cp,
            "last_mid": last_mid,
            "pending_markouts": pending,
            "hydro": hydro_state,
        }
        return result, 0, json.dumps(out, separators=(",", ":"))

    # ──────────────────────────────────────────────────────────────────
    # HYDROGEL_PACK: Ornstein-Uhlenbeck mean reverter around mu = 10000.
    # ──────────────────────────────────────────────────────────────────
    def _hydrogel_pack(
        self,
        od: OrderDepth,
        mid: float,
        pos: int,
        limit: int,
        state: dict,
    ) -> list[Order]:
        orders: list[Order] = []
        best_bid = max(od.buy_orders) if od.buy_orders else None
        best_ask = min(od.sell_orders) if od.sell_orders else None
        sym = "HYDROGEL_PACK"

        # ── Update tape & EWMA fair ───────────────────────────────────
        ewma = state.get("ewma", HYDRO_MU)
        ewma = HYDRO_EWMA_LAM * mid + (1 - HYDRO_EWMA_LAM) * ewma
        state["ewma"] = ewma

        tape: list[float] = state.get("tape", [])
        tape.append(mid)
        if len(tape) > HYDRO_MOMO_LOOKBACK:
            tape = tape[-HYDRO_MOMO_LOOKBACK:]
        state["tape"] = tape

        # Blended fair: anchored to global mu, drifts with EWMA.
        fair = HYDRO_FAIR_ALPHA * HYDRO_MU + (1 - HYDRO_FAIR_ALPHA) * ewma
        z = (mid - fair) / HYDRO_SIGMA

        # ── Momentum brake: shrink target size when fading active drift ──
        # Don't BLOCK entries (kills too much edge) — just smaller clip.
        momo = (tape[-1] - tape[0]) if len(tape) >= HYDRO_MOMO_LOOKBACK else 0.0
        # 1.0 = full size, < 1.0 = shrunk when drift fights our fade.
        brake = 1.0
        if (momo > HYDRO_MOMO_BRAKE and z > 0) or (momo < -HYDRO_MOMO_BRAKE and z < 0):
            brake = max(0.25, HYDRO_MOMO_BRAKE / abs(momo))

        # ── Position target ──
        max_pos = int(limit * HYDRO_MAX_POS_FRAC)
        scale = max(0.0, min(1.0, abs(z) / HYDRO_Z_FULL)) * brake
        target = -int(math.copysign(max_pos * scale, z)) if abs(z) > 0 else 0

        buy_cap = limit - pos
        sell_cap = limit + pos

        # ── Edge taker: walk book only at favorable prices ──
        buy_edge = fair - HYDRO_TAKE_K * HYDRO_SIGMA
        sell_edge = fair + HYDRO_TAKE_K * HYDRO_SIGMA

        if best_ask is not None and target > pos and buy_cap > 0:
            for px in sorted(od.sell_orders):
                if px > buy_edge:
                    break
                avail = abs(od.sell_orders[px])
                want = min(avail, target - pos, buy_cap)
                if want <= 0:
                    break
                orders.append(Order(sym, px, want))
                pos += want
                buy_cap -= want

        if best_bid is not None and target < pos and sell_cap > 0:
            for px in sorted(od.buy_orders, reverse=True):
                if px < sell_edge:
                    break
                avail = abs(od.buy_orders[px])
                want = min(avail, pos - target, sell_cap)
                if want <= 0:
                    break
                orders.append(Order(sym, px, -want))
                pos -= want
                sell_cap -= want

        # ── Passive layered MM around fair ──
        # Skip layers on the side where momentum guard is active.
        clip = max(1, limit // (len(HYDRO_LAYERS) * 4))
        for offset in HYDRO_LAYERS:
            bid_px = int(round(fair - offset))
            ask_px = int(round(fair + offset))
            if buy_cap > 0 and (best_bid is None or bid_px <= best_bid):
                size = min(clip, buy_cap)
                orders.append(Order(sym, bid_px, size))
                buy_cap -= size
            if sell_cap > 0 and (best_ask is None or ask_px >= best_ask):
                size = min(clip, sell_cap)
                orders.append(Order(sym, ask_px, -size))
                sell_cap -= size

        return orders

    # ──────────────────────────────────────────────────────────────────
    # Toxicity-aware MM (generic products).
    # ──────────────────────────────────────────────────────────────────
    def _record_trade(
        self,
        tr: Trade,
        product: str,
        mid: float | None,
        cp: dict[str, dict],
        pending: list[dict],
    ) -> None:
        parties: list[tuple[str, int]] = []
        if tr.buyer:
            parties.append((tr.buyer, +1))
        if tr.seller:
            parties.append((tr.seller, -1))
        if not parties:
            return
        for cp_id, side in parties:
            rec = cp.setdefault(cp_id, {
                "bv": 0, "sv": 0,
                "mo_sum": 0.0, "mo_n": 0,
                "agg_n": 0, "agg_hit": 0,
                "trades": [],
                "belief": list(PRIOR),
            })
            qty = abs(int(tr.quantity))
            if side > 0:
                rec["bv"] += qty
            else:
                rec["sv"] += qty
            rec["agg_n"] += 1
            if mid is not None:
                if (side > 0 and tr.price > mid) or (side < 0 and tr.price < mid):
                    rec["agg_hit"] += 1
            rec["trades"].append([int(tr.timestamp), side, float(tr.price), qty])
            if len(rec["trades"]) > TRADE_HISTORY_CAP:
                rec["trades"] = rec["trades"][-TRADE_HISTORY_CAP:]
            if mid is not None:
                pending.append({
                    "ts": int(tr.timestamp),
                    "product": product,
                    "cp": cp_id,
                    "side": side,
                    "mid": float(mid),
                })

    def _toxicity(self, rec: dict) -> float:
        bv = rec.get("bv", 0)
        sv = rec.get("sv", 0)
        tot = bv + sv
        vpin = abs(bv - sv) / tot if tot > 0 else 0.0

        mo_n = rec.get("mo_n", 0)
        mo_avg = rec["mo_sum"] / mo_n if mo_n > 0 else 0.0
        markout_score = 0.5 * (math.tanh(mo_avg / 2.0) + 1.0)

        agg = rec["agg_hit"] / rec["agg_n"] if rec.get("agg_n") else 0.0
        p_inf = rec.get("belief", list(PRIOR))[0]

        t = W_VPIN * vpin + W_MARKOUT * markout_score + W_AGG * agg + W_BAYES * p_inf
        return max(0.0, min(1.0, t))

    def _bayes_update(self, rec: dict) -> None:
        bv, sv = rec.get("bv", 0), rec.get("sv", 0)
        tot = bv + sv
        vpin = abs(bv - sv) / tot if tot > 0 else 0.0
        mo_n = rec.get("mo_n", 0)
        mo_avg = rec["mo_sum"] / mo_n if mo_n > 0 else 0.0
        mo_z = math.tanh(mo_avg / 2.0)

        belief = rec.get("belief", list(PRIOR))
        post = []
        for i, t in enumerate(TYPES):
            mu_mo, mu_v = TYPE_MEANS[t]
            lik = _gauss(mo_z, mu_mo, TYPE_SIGMA) * _gauss(vpin, mu_v, TYPE_SIGMA)
            post.append(belief[i] * lik)
        s = sum(post)
        if s > 0:
            rec["belief"] = [p / s for p in post]

    def _flow_toxicity(
        self,
        trades: list[Trade],
        tox: dict[str, float],
        now_ts: int,
    ) -> tuple[float, float]:
        if not trades:
            return 0.0, 0.0
        num = den = dir_num = 0.0
        for tr in trades:
            if now_ts - tr.timestamp > RECENT_FLOW_WINDOW:
                continue
            qty = abs(int(tr.quantity))
            if tr.buyer:
                t = tox.get(tr.buyer, 0.0)
                num += t * qty
                dir_num += t * qty
                den += qty
            if tr.seller:
                t = tox.get(tr.seller, 0.0)
                num += t * qty
                dir_num -= t * qty
                den += qty
        if den == 0:
            return 0.0, 0.0
        return num / den, dir_num / den

    def _toxicity_quote(
        self,
        product: str,
        mid: float,
        pos: int,
        limit: int,
        flow_tox: float,
        flow_dir: float,
    ) -> list[Order]:
        spread = BASE_SPREAD + SPREAD_ALPHA * flow_tox
        skew = SKEW_BETA * flow_tox * flow_dir
        inv_skew = -0.05 * pos

        center = mid + skew + inv_skew
        bid_px = int(math.floor(center - spread / 2.0))
        ask_px = int(math.ceil(center + spread / 2.0))
        if ask_px <= bid_px:
            ask_px = bid_px + 1

        buy_cap = limit - pos
        sell_cap = limit + pos
        orders: list[Order] = []

        clip = max(1, limit // 5)
        if buy_cap > 0:
            orders.append(Order(product, bid_px, min(clip, buy_cap)))
        if sell_cap > 0:
            orders.append(Order(product, ask_px, -min(clip, sell_cap)))

        if flow_tox >= FOLLOW_THRESHOLD and abs(flow_dir) >= 0.5:
            size = min(FOLLOW_CLIP, buy_cap if flow_dir > 0 else sell_cap)
            if size > 0:
                if flow_dir > 0:
                    orders.append(Order(product, ask_px, size))
                else:
                    orders.append(Order(product, bid_px, -size))

        return orders

    def _prune(self, cp: dict[str, dict]) -> None:
        if len(cp) <= 200:
            return
        ranked = sorted(cp.items(),
                        key=lambda kv: kv[1].get("bv", 0) + kv[1].get("sv", 0),
                        reverse=True)
        keep = dict(ranked[:200])
        cp.clear()
        cp.update(keep)