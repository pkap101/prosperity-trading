from datamodel import OrderDepth, Order, TradingState
from typing import Dict, List, Tuple, Optional
import json
import math


class Trader:
    """
    Round 3 robust v5: Black-Scholes as coordinate system, with a hybrid IV strip engine.

    Design goal:
    - avoid day-specific anchors / overfit thresholds
    - use local book fair for HYDROGEL_PACK and VELVETFRUIT_EXTRACT
    - use VELVETFRUIT_EXTRACT as underlying for all VEV vouchers
    - respect actual limits: HYDROGEL_PACK=200, VELVETFRUIT_EXTRACT=200, vouchers=300 each

    The voucher model remains Black-Scholes based, but the edge is extracted in IV space:
        1) convert prices to implied vols
        2) combine a structural smile with a local IV EMA
        3) create side-aware fair bands from bid/ask IV surfaces
        4) route voucher trades pair-first where possible
        5) use VELVETFRUIT_EXTRACT as a buffered hedge instrument first

    Robustness choices:
    - final simulation starts at TTE=5 days
    - sigma starts from a conservative prior and is adjusted slowly from live implied vols
    - no day-specific price anchors are used
    - voucher sizing is confidence/inventory/delta aware
    """

    POSITION_LIMITS: Dict[str, int] = {
        "HYDROGEL_PACK": 200,
        "VELVETFRUIT_EXTRACT": 200,
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

    VOUCHER_STRIKES: Dict[str, int] = {
        "VEV_4000": 4000,
        "VEV_4500": 4500,
        "VEV_5000": 5000,
        "VEV_5100": 5100,
        "VEV_5200": 5200,
        "VEV_5300": 5300,
        "VEV_5400": 5400,
        "VEV_5500": 5500,
        "VEV_6000": 6000,
        "VEV_6500": 6500,
    }

    MIDDLE_STRIKES = {"VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400"}

    def run(self, state: TradingState):
        data = self._load_data(state.traderData)
        result: Dict[str, List[Order]] = {}

        mids: Dict[str, float] = {}
        micros: Dict[str, float] = {}
        spreads: Dict[str, float] = {}

        for product, depth in state.order_depths.items():
            mid = self._mid(depth)
            if mid is None:
                continue
            micro = self._microprice(depth)
            mids[product] = mid
            micros[product] = micro if micro is not None else mid
            bid, _ = self._best_bid(depth)
            ask, _ = self._best_ask(depth)
            if bid is not None and ask is not None:
                spreads[product] = ask - bid
            self._update_stats(data, product, mid)

        extract_fair = None
        if "VELVETFRUIT_EXTRACT" in mids and "VELVETFRUIT_EXTRACT" in state.order_depths:
            extract_pos = state.position.get("VELVETFRUIT_EXTRACT", 0)
            extract_fair = self._extract_fair(data, state.order_depths["VELVETFRUIT_EXTRACT"], mids, micros, extract_pos)

        # Store extract fair for fallback when the underlying book disappears briefly.
        if extract_fair is not None:
            data["last_extract_fair"] = extract_fair
        else:
            extract_fair = data.get("last_extract_fair")

        # Slowly learn market-implied volatility from currently visible voucher mids.
        # This is intentionally slow and bounded so it does not overfit one bad snapshot.
        if extract_fair is not None:
            self._update_voucher_sigma(data, state.order_depths, extract_fair, state.timestamp)

        # Build the strip context once so every voucher trade sees the same surface,
        # pair ranking and hedge state for this timestamp.
        strip_ctx = None
        if extract_fair is not None:
            strip_ctx = self._build_voucher_strip(
                data, state.order_depths, state.position, extract_fair, state.timestamp
            )

        for product, depth in state.order_depths.items():
            if product not in self.POSITION_LIMITS:
                continue

            pos = state.position.get(product, 0)
            orders: List[Order] = []

            if product == "VELVETFRUIT_EXTRACT":
                fair = self._extract_fair(data, depth, mids, micros, pos)
                if strip_ctx is not None:
                    orders = self._trade_extract_hedge(product, depth, pos, fair, strip_ctx)
                else:
                    orders = self._trade_local_mm(
                        product, depth, pos, fair,
                        take_edge=2.0,
                        quote_edge=2.0,
                        base_size=24,
                        min_spread_to_quote=3,
                        inv_skew=0.030,
                        max_take_size=42,
                    )

            elif product == "HYDROGEL_PACK":
                fair = self._hydrogel_fair(data, depth, mids, micros, pos)
                orders = self._trade_local_mm(
                    product, depth, pos, fair,
                    take_edge=5.0,
                    quote_edge=7.0,
                    base_size=18,
                    min_spread_to_quote=11,
                    inv_skew=0.055,
                    max_take_size=34,
                )

            elif product in self.VOUCHER_STRIKES and extract_fair is not None:
                if strip_ctx is not None:
                    fair_info = strip_ctx["products"].get(product)
                    if fair_info is not None:
                        orders = self._trade_voucher(product, depth, pos, fair_info, strip_ctx)
                    else:
                        fair = self._voucher_fair(product, extract_fair, state.timestamp, data)
                        delta = self._voucher_delta(product, extract_fair, state.timestamp, data)
                        orders = self._trade_voucher_fallback(product, depth, pos, fair, extract_fair, delta)
                else:
                    fair = self._voucher_fair(product, extract_fair, state.timestamp, data)
                    delta = self._voucher_delta(product, extract_fair, state.timestamp, data)
                    orders = self._trade_voucher_fallback(product, depth, pos, fair, extract_fair, delta)

            if orders:
                result[product] = orders
            else:
                result[product] = []

        return result, 0, json.dumps(data, separators=(",", ":"))

    # ---------------- Fair values ----------------

    def _extract_fair(self, data: dict, depth: OrderDepth, mids: Dict[str, float], micros: Dict[str, float], pos: int) -> float:
        p = "VELVETFRUIT_EXTRACT"
        mid = mids.get(p, self._mid(depth))
        micro = micros.get(p, mid)
        fast = data.get("ema_fast", {}).get(p, mid)
        slow = data.get("ema_slow", {}).get(p, mid)
        ret_ema = data.get("ret_ema", {}).get(p, 0.0)

        # Mostly local book. This is deliberate: historical daily means shift, so a fixed anchor overfits.
        fair = 0.50 * micro + 0.28 * mid + 0.17 * fast + 0.05 * slow

        # Weak mean-reverting correction. Do not chase hard because the days show noisy drift.
        trend = fast - slow
        fair += self._clip(-0.20 * trend, -2.0, 2.0)
        fair += self._clip(0.35 * ret_ema, -1.2, 1.2)
        fair += 0.9 * self._imbalance(depth)

        # Inventory penalty directly in fair and again in quote placement.
        fair -= 1.2 * (pos / self.POSITION_LIMITS[p])
        return fair

    def _hydrogel_fair(self, data: dict, depth: OrderDepth, mids: Dict[str, float], micros: Dict[str, float], pos: int) -> float:
        p = "HYDROGEL_PACK"
        mid = mids.get(p, self._mid(depth))
        micro = micros.get(p, mid)
        fast = data.get("ema_fast", {}).get(p, mid)
        slow = data.get("ema_slow", {}).get(p, mid)
        ret_ema = data.get("ret_ema", {}).get(p, 0.0)

        # Hydrogel is treated as local/random-walk with weak stabilization only.
        fair = 0.54 * micro + 0.25 * mid + 0.16 * fast + 0.05 * slow

        # Anti-chase: when recent movement is one-directional, require better prices to follow.
        trend = fast - slow
        fair += self._clip(-0.22 * trend, -3.0, 3.0)
        fair += self._clip(-0.25 * ret_ema, -2.0, 2.0)
        fair += 2.0 * self._imbalance(depth)
        fair -= 3.8 * (pos / self.POSITION_LIMITS[p])
        return fair

    def _voucher_fair(self, product: str, underlying_fair: float, timestamp: int, data: Optional[dict] = None) -> float:
        """Black-Scholes call fair value using the cross-day VEV volatility smile."""
        K = self.VOUCHER_STRIKES[product]
        T = self._tte_years(timestamp)
        sigma = self._sigma_for_product(data or {}, product, underlying_fair, timestamp)
        return self._black_scholes_call(underlying_fair, K, T, sigma, r=0.0)

    def _voucher_delta(self, product: str, underlying_fair: float, timestamp: int, data: Optional[dict] = None) -> float:
        K = self.VOUCHER_STRIKES[product]
        T = self._tte_years(timestamp)
        sigma = self._sigma_for_product(data or {}, product, underlying_fair, timestamp)
        return self._black_scholes_delta(underlying_fair, K, T, sigma, r=0.0)

    def _tte_years(self, timestamp: int) -> float:
        # Final simulation starts at 5 days to expiry. One Prosperity day is timestamp 0..1_000_000.
        day_progress = self._clip(timestamp / 1_000_000.0, 0.0, 1.0)
        tte_days = max(4.0, 5.0 - day_progress)
        return max(1e-6, tte_days / 365.0)

    def _sigma_for_product(self, data: dict, product: str, underlying_fair: Optional[float] = None, timestamp: Optional[int] = None) -> float:
        """Annualized BS sigma from the observed cross-day volatility smile.

        The smile fit predicts total volatility v_t = sigma * sqrt(T):
            v_t = 0.0009*m^3 - 0.0030*m^2 + 0.0003*m + 0.0328
            m = ln(K/S) / sqrt(T)
        A tiny live residual around the smile is allowed, but heavily bounded.
        """
        if underlying_fair is not None and timestamp is not None and product in self.VOUCHER_STRIKES:
            K = self.VOUCHER_STRIKES[product]
            T = self._tte_years(timestamp)
            sqrt_t = math.sqrt(max(T, 1e-9))
            m = math.log(max(K, 1e-9) / max(underlying_fair, 1e-9)) / sqrt_t
            total_vol = self._smile_total_vol(m)
            residual = data.get("smile_residual", 0.0)
            product_residual = data.get("smile_residual_by_product", {}).get(product, residual)
            total_vol += self._clip(0.70 * residual + 0.30 * product_residual, -0.0025, 0.0025)
            return self._clip(total_vol / sqrt_t, 0.11, 0.42)

        return self._clip(data.get("bs_sigma", 0.24), 0.11, 0.42)

    def _smile_total_vol(self, m: float) -> float:
        # Cross-day OLS fit from the VEV smile chart; clamp to avoid tail extrapolation.
        x = self._clip(m, -2.2, 2.9)
        v = 0.0009 * x ** 3 - 0.0030 * x ** 2 + 0.0003 * x + 0.0328
        return self._clip(v, 0.0245, 0.0380)

    def _black_scholes_call(self, S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
        if S <= 0 or K <= 0:
            return 0.0
        intrinsic = max(0.0, S - K)
        if T <= 1e-8 or sigma <= 1e-8:
            return intrinsic
        vol_sqrt_t = sigma * math.sqrt(T)
        if vol_sqrt_t <= 1e-10:
            return intrinsic
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return S * self._norm_cdf(d1) - K * math.exp(-r * T) * self._norm_cdf(d2)

    def _black_scholes_delta(self, S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
        if S <= 0 or K <= 0:
            return 0.0
        if T <= 1e-8 or sigma <= 1e-8:
            return 1.0 if S > K else 0.0
        vol_sqrt_t = sigma * math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / max(1e-10, vol_sqrt_t)
        return self._norm_cdf(d1)

    def _norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _update_voucher_sigma(self, data: dict, order_depths: Dict[str, OrderDepth], underlying_fair: float, timestamp: int) -> None:
        """Update structural, side-specific and local IV states for the voucher strip."""
        if "smile_residual_by_product" not in data:
            data["smile_residual_by_product"] = {}
        if "smile_bid_residual_by_product" not in data:
            data["smile_bid_residual_by_product"] = {}
        if "smile_ask_residual_by_product" not in data:
            data["smile_ask_residual_by_product"] = {}
        if "local_iv_ema" not in data:
            data["local_iv_ema"] = {}
        T = self._tte_years(timestamp)
        sqrt_t = math.sqrt(max(T, 1e-9))
        residuals = []
        bid_residuals = []
        ask_residuals = []

        for product, K in self.VOUCHER_STRIKES.items():
            depth = order_depths.get(product)
            if depth is None:
                continue
            best_bid, _ = self._best_bid(depth)
            best_ask, _ = self._best_ask(depth)
            mid = self._mid(depth)
            if mid is None or mid <= 0 or best_bid is None or best_ask is None:
                continue

            intrinsic = max(0.0, underlying_fair - K)
            extrinsic = mid - intrinsic
            m = math.log(max(K, 1e-9) / max(underlying_fair, 1e-9)) / sqrt_t

            # Far tails and almost-intrinsic options give unstable implied vols.
            if extrinsic < 0.5 or abs(m) > 1.75:
                continue

            iv = self._implied_vol_call(mid, underlying_fair, K, T)
            if iv is None:
                continue

            bid_iv = self._implied_vol_call(max(best_bid, intrinsic), underlying_fair, K, T)
            ask_iv = self._implied_vol_call(max(best_ask, intrinsic), underlying_fair, K, T)

            market_total_vol = self._clip(iv * sqrt_t, 0.020, 0.045)
            model_total_vol = self._smile_total_vol(m)
            residual = self._clip(market_total_vol - model_total_vol, -0.0040, 0.0040)

            old_p = data["smile_residual_by_product"].get(product, data.get("smile_residual", 0.0))
            data["smile_residual_by_product"][product] = self._clip(0.96 * old_p + 0.04 * residual, -0.0030, 0.0030)
            residuals.append(residual)

            if bid_iv is not None:
                bid_total = self._clip(bid_iv * sqrt_t, 0.020, 0.045)
                bid_resid = self._clip(bid_total - model_total_vol, -0.0040, 0.0040)
                old_bid = data["smile_bid_residual_by_product"].get(product, data.get("smile_bid_residual", 0.0))
                data["smile_bid_residual_by_product"][product] = self._clip(0.96 * old_bid + 0.04 * bid_resid, -0.0030, 0.0030)
                bid_residuals.append(bid_resid)

            if ask_iv is not None:
                ask_total = self._clip(ask_iv * sqrt_t, 0.020, 0.045)
                ask_resid = self._clip(ask_total - model_total_vol, -0.0040, 0.0040)
                old_ask = data["smile_ask_residual_by_product"].get(product, data.get("smile_ask_residual", 0.0))
                data["smile_ask_residual_by_product"][product] = self._clip(0.96 * old_ask + 0.04 * ask_resid, -0.0030, 0.0030)
                ask_residuals.append(ask_resid)

            old_local = data["local_iv_ema"].get(product, iv)
            data["local_iv_ema"][product] = self._clip(0.88 * old_local + 0.12 * iv, 0.11, 0.42)

        if residuals:
            residuals.sort()
            med = residuals[len(residuals) // 2]
            old = data.get("smile_residual", 0.0)
            data["smile_residual"] = self._clip(0.985 * old + 0.015 * med, -0.0025, 0.0025)
        if bid_residuals:
            bid_residuals.sort()
            med = bid_residuals[len(bid_residuals) // 2]
            old = data.get("smile_bid_residual", 0.0)
            data["smile_bid_residual"] = self._clip(0.985 * old + 0.015 * med, -0.0025, 0.0025)
        if ask_residuals:
            ask_residuals.sort()
            med = ask_residuals[len(ask_residuals) // 2]
            old = data.get("smile_ask_residual", 0.0)
            data["smile_ask_residual"] = self._clip(0.985 * old + 0.015 * med, -0.0025, 0.0025)

        # Legacy keys kept so old traderData does not break the bot.
        if "bs_sigma" not in data:
            data["bs_sigma"] = 0.24
        if "bs_sigma_by_product" not in data:
            data["bs_sigma_by_product"] = {}

    def _build_voucher_strip(self, data: dict, order_depths: Dict[str, OrderDepth], positions: Dict[str, int], underlying_fair: float, timestamp: int) -> dict:
        """Build one execution-aware strip snapshot for all vouchers."""
        T = self._tte_years(timestamp)
        sqrt_t = math.sqrt(max(T, 1e-9))
        provisional: Dict[str, dict] = {}
        usable = 0
        pre_residuals: List[float] = []

        for product, K in self.VOUCHER_STRIKES.items():
            depth = order_depths.get(product)
            if depth is None:
                continue
            bid, bid_vol = self._best_bid(depth)
            ask, ask_vol = self._best_ask(depth)
            mid = self._mid(depth)
            if bid is None or ask is None or mid is None or mid <= 0:
                continue

            intrinsic = max(0.0, underlying_fair - K)
            extrinsic = mid - intrinsic
            if extrinsic < 0.5:
                continue

            mid_iv = self._implied_vol_call(mid, underlying_fair, K, T)
            bid_iv = self._implied_vol_call(max(bid, intrinsic), underlying_fair, K, T)
            ask_iv = self._implied_vol_call(max(ask, intrinsic), underlying_fair, K, T)
            if mid_iv is None:
                continue

            m = math.log(max(K, 1e-9) / max(underlying_fair, 1e-9)) / sqrt_t
            base_tv = self._smile_total_vol(m)
            base_mid_iv = self._clip((base_tv + self._clip(0.70 * data.get("smile_residual", 0.0) + 0.30 * data.get("smile_residual_by_product", {}).get(product, data.get("smile_residual", 0.0)), -0.0025, 0.0025)) / sqrt_t, 0.11, 0.42)
            base_bid_iv = self._clip((base_tv + self._clip(0.70 * data.get("smile_bid_residual", 0.0) + 0.30 * data.get("smile_bid_residual_by_product", {}).get(product, data.get("smile_bid_residual", 0.0)), -0.0025, 0.0025)) / sqrt_t, 0.11, 0.42)
            base_ask_iv = self._clip((base_tv + self._clip(0.70 * data.get("smile_ask_residual", 0.0) + 0.30 * data.get("smile_ask_residual_by_product", {}).get(product, data.get("smile_ask_residual", 0.0)), -0.0025, 0.0025)) / sqrt_t, 0.11, 0.42)
            local_iv = self._clip(data.get("local_iv_ema", {}).get(product, mid_iv), 0.11, 0.42)

            provisional[product] = {
                "strike": K,
                "bid": bid,
                "ask": ask,
                "bid_vol": abs(bid_vol),
                "ask_vol": abs(ask_vol),
                "mid": mid,
                "spread": ask - bid,
                "mid_iv": mid_iv,
                "bid_iv": bid_iv,
                "ask_iv": ask_iv,
                "base_mid_iv": base_mid_iv,
                "base_bid_iv": base_bid_iv,
                "base_ask_iv": base_ask_iv,
                "local_iv": local_iv,
                "position": positions.get(product, 0),
            }
            usable += 1
            pre_residuals.append(abs(mid_iv - base_mid_iv))

        if not provisional:
            return {"products": {}, "strip_delta": 0.0, "avg_abs_iv_residual": 0.0, "pair_agreement_count": 0, "broad_dislocation": False, "resid_compression": 0.0, "hedge_ratio": 0.25, "top_cheap": [], "top_rich": [], "hedge_feasible_size_score": 1.0}

        smile_stability = self._clip(0.35 + 0.10 * usable - 18.0 * (sum(pre_residuals) / max(1, len(pre_residuals))), 0.0, 1.0)
        unstable_smile = usable < 4 or smile_stability < 0.42
        w_struct = 0.55 if unstable_smile else 0.75
        w_local = 1.0 - w_struct

        residual_map: Dict[str, float] = {}
        pair_agreement_count = 0
        middle_gross = 0
        strip_delta = 0.0
        product_infos: Dict[str, dict] = {}

        for product, info in provisional.items():
            hybrid_mid_iv = self._clip(w_struct * info["base_mid_iv"] + w_local * info["local_iv"], 0.11, 0.42)
            hybrid_bid_iv = self._clip(w_struct * info["base_bid_iv"] + w_local * info["local_iv"], 0.11, 0.42)
            hybrid_ask_iv = self._clip(w_struct * info["base_ask_iv"] + w_local * info["local_iv"], 0.11, 0.42)
            fair_mid = self._black_scholes_call(underlying_fair, info["strike"], T, hybrid_mid_iv, 0.0)
            fair_bid = self._black_scholes_call(underlying_fair, info["strike"], T, hybrid_bid_iv, 0.0)
            fair_ask = self._black_scholes_call(underlying_fair, info["strike"], T, hybrid_ask_iv, 0.0)
            delta = self._black_scholes_delta(underlying_fair, info["strike"], T, hybrid_mid_iv, 0.0)
            iv_resid = info["mid_iv"] - hybrid_mid_iv
            residual_map[product] = iv_resid
            strip_delta += info["position"] * delta
            if product in self.MIDDLE_STRIKES:
                middle_gross += abs(info["position"])
            product_infos[product] = {
                **info,
                "hybrid_mid_iv": hybrid_mid_iv,
                "hybrid_bid_iv": hybrid_bid_iv,
                "hybrid_ask_iv": hybrid_ask_iv,
                "fair_mid": fair_mid,
                "fair_bid": fair_bid,
                "fair_ask": fair_ask,
                "delta": delta,
                "iv_residual": iv_resid,
                "pair_bias": 0.0,
                "pair_gap": 0.0,
                "pair_partner": None,
                "hedge_feasible_size_score": 1.0,
            }

        ordered = sorted(product_infos.items(), key=lambda kv: kv[1]["strike"])
        for i in range(len(ordered) - 1):
            p0, v0 = ordered[i]
            p1, v1 = ordered[i + 1]
            if abs(v0["iv_residual"]) > 0.010 and abs(v1["iv_residual"]) > 0.010 and v0["iv_residual"] * v1["iv_residual"] > 0:
                pair_agreement_count += 1

        liquid = [
            (product, info)
            for product, info in product_infos.items()
            if info["bid_vol"] > 0 and info["ask_vol"] > 0 and info["spread"] <= 12
        ]
        cheap = sorted(liquid, key=lambda kv: kv[1]["iv_residual"])
        rich = sorted(liquid, key=lambda kv: kv[1]["iv_residual"], reverse=True)
        top_cheap = [p for p, info in cheap[:3] if info["iv_residual"] < -0.008]
        top_rich = [p for p, info in rich[:3] if info["iv_residual"] > 0.008]

        for cheap_p, cheap_info in cheap:
            if cheap_info["iv_residual"] >= -0.008:
                continue
            best_gap = 0.0
            best_partner = None
            for rich_p, rich_info in rich:
                if rich_info["iv_residual"] <= 0.008:
                    continue
                if abs(rich_info["strike"] - cheap_info["strike"]) > 600:
                    continue
                gap = rich_info["iv_residual"] - cheap_info["iv_residual"] - 0.0008 * (abs(rich_info["strike"] - cheap_info["strike"]) / 100.0)
                if gap > best_gap:
                    best_gap = gap
                    best_partner = rich_p
            if best_partner is not None and best_gap > 0.018:
                product_infos[cheap_p]["pair_bias"] = max(product_infos[cheap_p]["pair_bias"], 1.0)
                product_infos[cheap_p]["pair_gap"] = max(product_infos[cheap_p]["pair_gap"], best_gap)
                product_infos[cheap_p]["pair_partner"] = best_partner
                product_infos[best_partner]["pair_bias"] = min(product_infos[best_partner]["pair_bias"], -1.0)
                product_infos[best_partner]["pair_gap"] = max(product_infos[best_partner]["pair_gap"], best_gap)
                product_infos[best_partner]["pair_partner"] = cheap_p

        avg_abs_iv_residual = sum(abs(v["iv_residual"]) for v in product_infos.values()) / max(1, len(product_infos))
        resid_compression = max(0.0, data.get("last_strip_avg_abs_resid", 0.0) - avg_abs_iv_residual)
        broad_dislocation = (
            avg_abs_iv_residual > 0.012
            and pair_agreement_count >= 3
            and abs(strip_delta) < 180
            and middle_gross < 500
        )
        if broad_dislocation:
            w_struct = 0.55
            w_local = 0.45

        if broad_dislocation:
            hedge_ratio = 0.75
        elif avg_abs_iv_residual > 0.008:
            hedge_ratio = 0.50
        else:
            hedge_ratio = 0.25
        if resid_compression > 0.002:
            hedge_ratio *= 0.75

        hedge_feasible_size_score = self._clip(1.0 - 0.45 * abs(strip_delta) / 220.0 - 0.20 * middle_gross / 700.0, 0.40, 1.00)
        for product, info in product_infos.items():
            score = hedge_feasible_size_score
            if product in self.MIDDLE_STRIKES and abs(info["pair_bias"]) < 0.5:
                score *= 0.80
            if product in self.MIDDLE_STRIKES and abs(info["pair_bias"]) >= 0.5:
                score *= 0.95
            info["hedge_feasible_size_score"] = self._clip(score, 0.30, 1.10)

        data["last_strip_avg_abs_resid"] = avg_abs_iv_residual
        data["strip_diag"] = {
            "smile_stability": round(smile_stability, 4),
            "usable_strikes": usable,
            "avg_abs_iv_residual": round(avg_abs_iv_residual, 5),
            "pair_agreement_count": pair_agreement_count,
            "broad_dislocation": broad_dislocation,
            "resid_compression": round(resid_compression, 5),
            "strip_delta": round(strip_delta, 3),
            "hedge_ratio": round(hedge_ratio, 3),
            "top_cheap": top_cheap,
            "top_rich": top_rich,
        }

        return {
            "products": product_infos,
            "smile_stability": smile_stability,
            "avg_abs_iv_residual": avg_abs_iv_residual,
            "pair_agreement_count": pair_agreement_count,
            "broad_dislocation": broad_dislocation,
            "resid_compression": resid_compression,
            "strip_delta": strip_delta,
            "hedge_ratio": hedge_ratio,
            "top_cheap": top_cheap,
            "top_rich": top_rich,
            "hedge_feasible_size_score": hedge_feasible_size_score,
        }

    def _implied_vol_call(self, market_price: float, S: float, K: float, T: float) -> Optional[float]:
        intrinsic = max(0.0, S - K)
        if market_price < intrinsic - 0.2:
            return None

        lo, hi = 0.01, 1.00
        price_lo = self._black_scholes_call(S, K, T, lo, 0.0)
        price_hi = self._black_scholes_call(S, K, T, hi, 0.0)
        if market_price <= price_lo:
            return lo
        if market_price >= price_hi:
            return hi

        for _ in range(24):
            mid = (lo + hi) / 2.0
            price = self._black_scholes_call(S, K, T, mid, 0.0)
            if price < market_price:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    # ---------------- Execution ----------------

    def _trade_local_mm(self, product: str, depth: OrderDepth, pos: int, fair: float,
                        take_edge: float, quote_edge: float, base_size: int,
                        min_spread_to_quote: int, inv_skew: float, max_take_size: int) -> List[Order]:
        orders: List[Order] = []
        limit = self.POSITION_LIMITS[product]
        best_bid, bid_vol = self._best_bid(depth)
        best_ask, ask_vol = self._best_ask(depth)
        if best_bid is None or best_ask is None:
            return orders

        buy_cap = limit - pos
        sell_cap = limit + pos

        # Take clear edge. Scale with mispricing but cap to avoid one bad book snapshot killing us.
        if buy_cap > 0 and best_ask <= fair - take_edge:
            edge = fair - best_ask
            qty = min(buy_cap, abs(ask_vol), max_take_size, int(base_size + 3 * max(0.0, edge - take_edge)))
            if qty > 0:
                orders.append(Order(product, int(best_ask), qty))
                buy_cap -= qty

        if sell_cap > 0 and best_bid >= fair + take_edge:
            edge = best_bid - fair
            qty = min(sell_cap, abs(bid_vol), max_take_size, int(base_size + 3 * max(0.0, edge - take_edge)))
            if qty > 0:
                orders.append(Order(product, int(best_bid), -qty))
                sell_cap -= qty

        spread = best_ask - best_bid
        if spread >= min_spread_to_quote:
            inventory_pressure = inv_skew * pos
            adj = fair - inventory_pressure
            bid_px = min(best_bid + 1, math.floor(adj - quote_edge))
            ask_px = max(best_ask - 1, math.ceil(adj + quote_edge))

            if bid_px < ask_px:
                buy_size = min(buy_cap, self._inventory_scaled_size(base_size, pos, limit, side=1))
                sell_size = min(sell_cap, self._inventory_scaled_size(base_size, pos, limit, side=-1))

                # Near inventory limit: prioritize flattening, not adding.
                if pos > 0.75 * limit:
                    buy_size = 0
                    sell_size = min(sell_cap, max(sell_size, base_size))
                elif pos < -0.75 * limit:
                    sell_size = 0
                    buy_size = min(buy_cap, max(buy_size, base_size))

                if buy_size > 0:
                    orders.append(Order(product, int(bid_px), int(buy_size)))
                if sell_size > 0:
                    orders.append(Order(product, int(ask_px), -int(sell_size)))

        return orders

    def _trade_extract_hedge(self, product: str, depth: OrderDepth, pos: int, fair: float, strip_ctx: dict) -> List[Order]:
        """Use Velvet mainly as a buffered hedge instrument, with a small alpha overlay."""
        orders: List[Order] = []
        limit = self.POSITION_LIMITS[product]
        best_bid, bid_vol = self._best_bid(depth)
        best_ask, ask_vol = self._best_ask(depth)
        if best_bid is None or best_ask is None:
            return orders

        mid = (best_bid + best_ask) / 2.0
        strip_delta = float(strip_ctx.get("strip_delta", 0.0))
        hedge_ratio = float(strip_ctx.get("hedge_ratio", 0.25))
        resid_compression = float(strip_ctx.get("resid_compression", 0.0))
        broad_dislocation = bool(strip_ctx.get("broad_dislocation", False))

        hedge_target = 0.0 if abs(strip_delta) < 20 else -hedge_ratio * strip_delta
        if resid_compression > 0.002:
            hedge_target *= 0.65

        alpha_target = self._clip((fair - mid) / 2.5, -40.0, 40.0)
        if abs(strip_delta) > 60:
            alpha_target = 0.0

        final_target = self._clip(hedge_target + alpha_target, -100.0, 100.0)
        buy_cap = limit - pos
        sell_cap = limit + pos
        relative_pos = pos - final_target

        take_edge = 2.0 + (0.20 if abs(strip_delta) < 20 else 0.0)
        if broad_dislocation:
            take_edge -= 0.15

        if buy_cap > 0 and best_ask <= fair - take_edge and pos < final_target + 45:
            qty = min(buy_cap, abs(ask_vol), 42)
            if qty > 0:
                orders.append(Order(product, int(best_ask), int(qty)))
                buy_cap -= qty
                pos += qty

        if sell_cap > 0 and best_bid >= fair + take_edge and pos > final_target - 45:
            qty = min(sell_cap, abs(bid_vol), 42)
            if qty > 0:
                orders.append(Order(product, int(best_bid), -int(qty)))
                sell_cap -= qty
                pos -= qty

        # Clear toward the hedge target before layering passive quotes.
        if relative_pos > 28 and best_bid >= fair - 1.0:
            qty = min(sell_cap, abs(bid_vol), int(min(36, max(10, relative_pos))))
            if qty > 0:
                orders.append(Order(product, int(best_bid), -int(qty)))
                sell_cap -= qty
                pos -= qty
        elif relative_pos < -28 and best_ask <= fair + 1.0:
            qty = min(buy_cap, abs(ask_vol), int(min(36, max(10, -relative_pos))))
            if qty > 0:
                orders.append(Order(product, int(best_ask), int(qty)))
                buy_cap -= qty
                pos += qty

        spread = best_ask - best_bid
        if spread >= 3:
            reservation = fair - 0.040 * (pos - final_target)
            bid_px = min(best_bid + 1, math.floor(reservation - 2.0))
            ask_px = max(best_ask - 1, math.ceil(reservation + 2.0))
            if bid_px < ask_px:
                buy_size = min(buy_cap, self._inventory_scaled_size(20, int(pos - final_target), limit, side=1))
                sell_size = min(sell_cap, self._inventory_scaled_size(20, int(pos - final_target), limit, side=-1))
                if pos > final_target + 40:
                    buy_size = 0
                elif pos < final_target - 40:
                    sell_size = 0
                if buy_size > 0:
                    orders.append(Order(product, int(bid_px), int(buy_size)))
                if sell_size > 0:
                    orders.append(Order(product, int(ask_px), -int(sell_size)))

        return orders

    def _trade_voucher_fallback(self, product: str, depth: OrderDepth, pos: int, fair: float, underlying_fair: float, delta: float) -> List[Order]:
        orders: List[Order] = []
        limit = self.POSITION_LIMITS[product]
        best_bid, bid_vol = self._best_bid(depth)
        best_ask, ask_vol = self._best_ask(depth)
        if best_bid is None or best_ask is None:
            return orders

        K = self.VOUCHER_STRIKES[product]
        moneyness = underlying_fair - K
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2.0

        # Capacity is larger here, but the BS edge is only useful where delta/extrinsic are meaningful.
        # Deep ITM vouchers are almost equivalent to underlying exposure; far OTM vouchers are noisy lottery tickets.
        if 0.25 <= delta <= 0.75:
            base_size = 28
            take_edge = 1.4
            quote_edge = 1.0
        elif 0.10 <= delta < 0.25 or 0.75 < delta <= 0.92:
            base_size = 18
            take_edge = 1.2
            quote_edge = 0.9
        elif delta > 0.92:
            base_size = 14
            take_edge = 1.0
            quote_edge = 0.8
        else:
            base_size = 7
            take_edge = 0.8
            quote_edge = 0.8

        # Very low theoretical value: quote tiny size only, because model error dominates.
        if fair <= 1.20:
            base_size = min(base_size, 5)
            take_edge = 0.7

        # Realized-vol overlay is below implied vol in the smile chart. This means we should
        # be slightly more willing to sell rich vouchers than to buy small apparent discounts.
        buy_take_edge = take_edge + 0.35
        sell_take_edge = max(0.65, take_edge - 0.15)
        buy_quote_edge = quote_edge + 0.25
        sell_quote_edge = max(0.55, quote_edge - 0.10)

        # Inventory skew in price space. Stronger than local products because vouchers can be one-sided.
        inv_adj = fair - 0.018 * pos
        buy_cap = limit - pos
        sell_cap = limit + pos

        if buy_cap > 0 and best_ask <= fair - buy_take_edge:
            edge = fair - best_ask
            qty = min(buy_cap, abs(ask_vol), int(base_size + 2.0 * max(0.0, edge - buy_take_edge)))
            if qty > 0:
                orders.append(Order(product, int(best_ask), int(qty)))
                buy_cap -= qty

        if sell_cap > 0 and best_bid >= fair + sell_take_edge:
            edge = best_bid - fair
            qty = min(sell_cap, abs(bid_vol), int(base_size + 2.0 * max(0.0, edge - sell_take_edge)))
            if qty > 0:
                orders.append(Order(product, int(best_bid), -int(qty)))
                sell_cap -= qty

        # Passive quote only when spread gives protection. Avoid quoting useless far OTM unless spread is wide.
        if spread >= 2 and not (fair <= 1.05 and spread < 3):
            bid_px = min(best_bid + 1, math.floor(inv_adj - buy_quote_edge))
            ask_px = max(best_ask - 1, math.ceil(inv_adj + sell_quote_edge))

            if bid_px < ask_px:
                buy_size = min(buy_cap, self._inventory_scaled_size(base_size, pos, limit, side=1))
                sell_size = min(sell_cap, self._inventory_scaled_size(base_size, pos, limit, side=-1))

                # Do not keep adding to extreme positions; instead quote only the side that reduces risk.
                if pos > 0.70 * limit:
                    buy_size = 0
                    sell_size = min(sell_cap, max(sell_size, base_size))
                elif pos < -0.70 * limit:
                    sell_size = 0
                    buy_size = min(buy_cap, max(buy_size, base_size))

                # Guardrails: do not bid above fair or ask below fair after rounding.
                if buy_size > 0 and bid_px <= fair - 0.3:
                    orders.append(Order(product, int(bid_px), int(buy_size)))
                if sell_size > 0 and ask_px >= fair + 0.3:
                    orders.append(Order(product, int(ask_px), -int(sell_size)))

        return orders

    def _trade_voucher(self, product: str, depth: OrderDepth, pos: int, fair_info: dict, strip_ctx: dict) -> List[Order]:
        """Trade vouchers in IV space with side-aware fair bands and pair-first routing."""
        orders: List[Order] = []
        limit = self.POSITION_LIMITS[product]
        best_bid, bid_vol = self._best_bid(depth)
        best_ask, ask_vol = self._best_ask(depth)
        if best_bid is None or best_ask is None:
            return orders

        delta = float(fair_info["delta"])
        fair_mid = float(fair_info["fair_mid"])
        fair_bid = float(fair_info["fair_bid"])
        fair_ask = float(fair_info["fair_ask"])
        pair_bias = float(fair_info.get("pair_bias", 0.0))
        pair_gap = float(fair_info.get("pair_gap", 0.0))
        hedge_score = float(fair_info.get("hedge_feasible_size_score", 1.0))
        broad_dislocation = bool(strip_ctx.get("broad_dislocation", False))

        if 0.25 <= delta <= 0.75:
            base_size = 24
            take_edge = 1.30
            quote_edge = 0.95
        elif 0.10 <= delta < 0.25 or 0.75 < delta <= 0.92:
            base_size = 16
            take_edge = 1.15
            quote_edge = 0.85
        elif delta > 0.92:
            base_size = 12
            take_edge = 1.00
            quote_edge = 0.75
        else:
            base_size = 6
            take_edge = 0.80
            quote_edge = 0.75

        # Pair-backed trades can be a bit more assertive; unpaired middle strikes stay tighter.
        if pair_bias != 0.0:
            base_size = int(round(base_size * (1.10 if abs(pair_gap) > 0.020 else 1.00)))
            take_edge = max(0.55, take_edge - 0.15)
        elif product in self.MIDDLE_STRIKES:
            base_size = max(4, int(round(base_size * 0.70)))
            take_edge += 0.25
            quote_edge += 0.10

        if broad_dislocation:
            take_edge = max(0.55, take_edge - 0.10)
            base_size = int(round(base_size * 1.10))

        base_size = max(3, int(round(base_size * hedge_score)))
        if fair_mid <= 1.20:
            base_size = min(base_size, 5)
            take_edge = max(0.55, take_edge - 0.10)

        buy_take_edge = take_edge + 0.20
        sell_take_edge = max(0.55, take_edge - 0.10)
        if pair_bias > 0:
            buy_take_edge = max(0.50, buy_take_edge - 0.20)
            sell_take_edge += 0.15
        elif pair_bias < 0:
            sell_take_edge = max(0.50, sell_take_edge - 0.20)
            buy_take_edge += 0.15

        buy_cap = limit - pos
        sell_cap = limit + pos
        reservation = fair_mid - 0.020 * pos

        # Buy against the fair executable buy-side surface, not just the mid fair.
        if buy_cap > 0 and best_ask <= fair_bid - buy_take_edge:
            edge = fair_bid - best_ask
            qty = min(buy_cap, abs(ask_vol), int(base_size + 2.0 * max(0.0, edge - buy_take_edge)))
            if qty > 0:
                orders.append(Order(product, int(best_ask), int(qty)))
                buy_cap -= qty

        # Sell against the fair executable sell-side surface.
        if sell_cap > 0 and best_bid >= fair_ask + sell_take_edge:
            edge = best_bid - fair_ask
            qty = min(sell_cap, abs(bid_vol), int(base_size + 2.0 * max(0.0, edge - sell_take_edge)))
            if qty > 0:
                orders.append(Order(product, int(best_bid), -int(qty)))
                sell_cap -= qty

        spread = best_ask - best_bid
        if spread >= 2:
            bid_px = min(best_bid + 1, math.floor(reservation - quote_edge))
            ask_px = max(best_ask - 1, math.ceil(reservation + quote_edge))
            if bid_px < ask_px:
                buy_size = min(buy_cap, self._inventory_scaled_size(base_size, pos, limit, side=1))
                sell_size = min(sell_cap, self._inventory_scaled_size(base_size, pos, limit, side=-1))
                if pos > 0.70 * limit:
                    buy_size = 0
                elif pos < -0.70 * limit:
                    sell_size = 0

                # Keep passive prices outside the execution-aware no-trade band.
                if buy_size > 0 and bid_px <= fair_bid - 0.20:
                    orders.append(Order(product, int(bid_px), int(buy_size)))
                if sell_size > 0 and ask_px >= fair_ask + 0.20:
                    orders.append(Order(product, int(ask_px), -int(sell_size)))

        return orders

    # ---------------- State/stat helpers ----------------

    def _load_data(self, trader_data: str) -> dict:
        if not trader_data:
            return {"ema_fast": {}, "ema_slow": {}, "last_mid": {}, "ret_ema": {}, "bs_sigma": 0.24, "bs_sigma_by_product": {}, "smile_residual": 0.0, "smile_residual_by_product": {}, "smile_bid_residual": 0.0, "smile_ask_residual": 0.0, "smile_bid_residual_by_product": {}, "smile_ask_residual_by_product": {}, "local_iv_ema": {}, "last_strip_avg_abs_resid": 0.0, "strip_diag": {}}
        try:
            data = json.loads(trader_data)
            for k in ("ema_fast", "ema_slow", "last_mid", "ret_ema"):
                if k not in data:
                    data[k] = {}
            if "bs_sigma" not in data:
                data["bs_sigma"] = 0.20
            if "bs_sigma_by_product" not in data:
                data["bs_sigma_by_product"] = {}
            if "smile_residual" not in data:
                data["smile_residual"] = 0.0
            if "smile_residual_by_product" not in data:
                data["smile_residual_by_product"] = {}
            if "smile_bid_residual" not in data:
                data["smile_bid_residual"] = 0.0
            if "smile_ask_residual" not in data:
                data["smile_ask_residual"] = 0.0
            if "smile_bid_residual_by_product" not in data:
                data["smile_bid_residual_by_product"] = {}
            if "smile_ask_residual_by_product" not in data:
                data["smile_ask_residual_by_product"] = {}
            if "local_iv_ema" not in data:
                data["local_iv_ema"] = {}
            if "last_strip_avg_abs_resid" not in data:
                data["last_strip_avg_abs_resid"] = 0.0
            if "strip_diag" not in data:
                data["strip_diag"] = {}
            return data
        except Exception:
            return {"ema_fast": {}, "ema_slow": {}, "last_mid": {}, "ret_ema": {}, "bs_sigma": 0.24, "bs_sigma_by_product": {}, "smile_residual": 0.0, "smile_residual_by_product": {}, "smile_bid_residual": 0.0, "smile_ask_residual": 0.0, "smile_bid_residual_by_product": {}, "smile_ask_residual_by_product": {}, "local_iv_ema": {}, "last_strip_avg_abs_resid": 0.0, "strip_diag": {}}

    def _update_stats(self, data: dict, product: str, mid: float) -> None:
        prev_fast = data["ema_fast"].get(product, mid)
        prev_slow = data["ema_slow"].get(product, mid)
        prev_mid = data["last_mid"].get(product, mid)
        prev_ret = data["ret_ema"].get(product, 0.0)

        # Fast reacts within the current local regime; slow prevents pure tick chasing.
        data["ema_fast"][product] = 0.18 * mid + 0.82 * prev_fast
        data["ema_slow"][product] = 0.035 * mid + 0.965 * prev_slow
        data["ret_ema"][product] = 0.20 * (mid - prev_mid) + 0.80 * prev_ret
        data["last_mid"][product] = mid

    # ---------------- Order book helpers ----------------

    def _best_bid(self, depth: OrderDepth) -> Tuple[Optional[int], int]:
        if not depth.buy_orders:
            return None, 0
        px = max(depth.buy_orders.keys())
        return px, depth.buy_orders[px]

    def _best_ask(self, depth: OrderDepth) -> Tuple[Optional[int], int]:
        if not depth.sell_orders:
            return None, 0
        px = min(depth.sell_orders.keys())
        return px, depth.sell_orders[px]

    def _mid(self, depth: OrderDepth) -> Optional[float]:
        bid, _ = self._best_bid(depth)
        ask, _ = self._best_ask(depth)
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2.0

    def _microprice(self, depth: OrderDepth) -> Optional[float]:
        bid, bid_vol = self._best_bid(depth)
        ask, ask_vol = self._best_ask(depth)
        if bid is None or ask is None:
            return None
        b = abs(bid_vol)
        a = abs(ask_vol)
        if b + a <= 0:
            return (bid + ask) / 2.0
        return (bid * a + ask * b) / (a + b)

    def _imbalance(self, depth: OrderDepth) -> float:
        bid, bid_vol = self._best_bid(depth)
        ask, ask_vol = self._best_ask(depth)
        if bid is None or ask is None:
            return 0.0
        b = abs(bid_vol)
        a = abs(ask_vol)
        if b + a <= 0:
            return 0.0
        return self._clip((b - a) / (b + a), -1.0, 1.0)

    def _inventory_scaled_size(self, base: int, pos: int, limit: int, side: int) -> int:
        inv = pos / max(1, limit)
        if side == 1:
            # If already long, bid smaller. If short, bid larger to flatten.
            factor = 1.0 - 0.75 * max(0.0, inv) + 0.35 * max(0.0, -inv)
        else:
            # If already short, ask smaller. If long, ask larger to flatten.
            factor = 1.0 - 0.75 * max(0.0, -inv) + 0.35 * max(0.0, inv)
        return max(1, int(round(base * self._clip(factor, 0.20, 1.35))))

    def _clip(self, x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))