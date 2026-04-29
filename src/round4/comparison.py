"""
Round 4 Manual Trading - Comprehensive Source Comparison

Sources:
1. manual1.py (MC analysis)
2. Second open source (fair values provided)
3. montecarlo.py (MC with arbitrage focus)
"""

import pandas as pd

# Market data (all sources agree on this)
MARKET = {
    "AC":        {"bid": 49.975, "ask": 50.025, "max_vol": 200},
    "AC_50_P":   {"bid": 12.00,  "ask": 12.05,  "max_vol": 50},
    "AC_50_C":   {"bid": 12.00,  "ask": 12.05,  "max_vol": 50},
    "AC_35_P":   {"bid": 4.33,   "ask": 4.35,   "max_vol": 50},
    "AC_40_P":   {"bid": 6.50,   "ask": 6.55,   "max_vol": 50},
    "AC_45_P":   {"bid": 9.05,   "ask": 9.10,   "max_vol": 50},
    "AC_60_C":   {"bid": 8.80,   "ask": 8.85,   "max_vol": 50},
    "AC_50_P_2": {"bid": 9.70,   "ask": 9.75,   "max_vol": 50},
    "AC_50_C_2": {"bid": 9.70,   "ask": 9.75,   "max_vol": 50},
    "AC_50_CO":  {"bid": 22.20,  "ask": 22.30,  "max_vol": 50},
    "AC_40_BP":  {"bid": 5.00,   "ask": 5.10,   "max_vol": 50},
    "AC_45_KO":  {"bid": 0.15,   "ask": 0.175,  "max_vol": 500},
}

# Source 1: manual1.py MC analysis results
SOURCE1_FAIR = {
    "AC":        49.921,   # MC fair
    "AC_50_P":   12.00,    # BS fair ~12.027
    "AC_50_C":   11.92,    # MC fair (slightly different from put)
    "AC_35_P":   4.306,    # MC fair
    "AC_40_P":   6.473,    # MC fair
    "AC_45_P":   9.054,    # MC fair
    "AC_60_C":   8.693,    # MC fair
    "AC_50_P_2": 9.871,    # BS fair
    "AC_50_C_2": 9.871,    # BS fair
    "AC_50_CO":  21.757,   # MC fair (chooser)
    "AC_40_BP":  4.763,    # MC fair (binary)
    "AC_45_KO":  0.211,    # MC fair (knock-out)
}

# Source 2: Second open source fair values
SOURCE2_FAIR = {
    "AC":        50.00,    # not provided, assume mid
    "AC_50_P":   12.027,   # BS fair
    "AC_50_C":   12.027,   # BS fair
    "AC_35_P":   4.336,    # BS fair
    "AC_40_P":   6.510,    # BS fair
    "AC_45_P":   9.089,    # BS fair
    "AC_60_C":   8.792,    # BS fair
    "AC_50_P_2": 9.871,    # BS fair
    "AC_50_C_2": 9.871,    # BS fair
    "AC_50_CO":  21.898,   # Rubinstein formula
    "AC_40_BP":  4.768,    # MC fair
    "AC_45_KO":  0.213,    # MC fair
}

# Source 3: montecarlo.py MC edge results (edge = fair - ask)
# Reconstructing fair = edge + ask
SOURCE3_EDGE = {
    "AC_50_P":   -0.0212,  # edge = fair - ask
    "AC_35_P":   -0.0116,
    "AC_60_C":   -0.0687,
    "AC_50_C_2": +0.0341,
    "AC_40_BP":  -0.3275,
    "AC_45_KO":  +0.0295,
    "AC":        -0.0210,  # spot edge
}

def calculate_source3_fair():
    """Reconstruct fair values from montecarlo.py edges"""
    fair = {}
    for prod, edge in SOURCE3_EDGE.items():
        if prod == "AC":
            fair[prod] = 49.975 + edge  # bid for short
        else:
            fair[prod] = MARKET[prod]["ask"] + edge
    # Not computed in montecarlo.py - use BS/Rubinstein
    fair["AC_50_C"] = 12.027
    fair["AC_40_P"] = 6.510
    fair["AC_45_P"] = 9.089
    fair["AC_50_P_2"] = 9.75 + 0.0341  # same edge as call
    fair["AC_50_CO"] = 12.05 + 9.75  # Rubinstein: Call(21d) + Put(14d)
    return fair

SOURCE3_FAIR = calculate_source3_fair()

def compare_all_sources():
    """Create comparison table for all products across all sources"""

    rows = []
    for prod in MARKET:
        bid = MARKET[prod]["bid"]
        ask = MARKET[prod]["ask"]
        max_vol = MARKET[prod]["max_vol"]
        mid = (bid + ask) / 2

        fair1 = SOURCE1_FAIR.get(prod, None)
        fair2 = SOURCE2_FAIR.get(prod, None)
        fair3 = SOURCE3_FAIR.get(prod, None)

        # Calculate edges (fair - ask for buy, bid - fair for sell)
        if fair1:
            buy_edge1 = fair1 - ask
            sell_edge1 = bid - fair1
            action1 = "BUY" if buy_edge1 > sell_edge1 and buy_edge1 > 0 else \
                      "SELL" if sell_edge1 > 0 else "HOLD"
            edge1 = max(buy_edge1, sell_edge1) if max(buy_edge1, sell_edge1) > 0 else 0
        else:
            buy_edge1 = sell_edge1 = edge1 = None
            action1 = "?"

        if fair2:
            buy_edge2 = fair2 - ask
            sell_edge2 = bid - fair2
            action2 = "BUY" if buy_edge2 > sell_edge2 and buy_edge2 > 0 else \
                      "SELL" if sell_edge2 > 0 else "HOLD"
            edge2 = max(buy_edge2, sell_edge2) if max(buy_edge2, sell_edge2) > 0 else 0
        else:
            buy_edge2 = sell_edge2 = edge2 = None
            action2 = "?"

        if fair3:
            buy_edge3 = fair3 - ask
            sell_edge3 = bid - fair3
            action3 = "BUY" if buy_edge3 > sell_edge3 and buy_edge3 > 0 else \
                      "SELL" if sell_edge3 > 0 else "HOLD"
            edge3 = max(buy_edge3, sell_edge3) if max(buy_edge3, sell_edge3) > 0 else 0
        else:
            buy_edge3 = sell_edge3 = edge3 = None
            action3 = "?"

        # Check if all sources agree
        actions = [action1, action2, action3]
        agree = len(set(a for a in actions if a != "?")) <= 1

        rows.append({
            "Product": prod,
            "Bid": bid,
            "Ask": ask,
            "MaxVol": max_vol,
            "Fair_S1": fair1,
            "Fair_S2": fair2,
            "Fair_S3": fair3,
            "Action_S1": action1,
            "Action_S2": action2,
            "Action_S3": action3,
            "Edge_S1": edge1,
            "Edge_S2": edge2,
            "Edge_S3": edge3,
            "Agree": "✓" if agree else "✗",
        })

    return pd.DataFrame(rows)

def main():
    print("=" * 100)
    print("ROUND 4 MANUAL TRADING - CROSS-SOURCE COMPARISON")
    print("=" * 100)
    print("\nSources:")
    print("  S1: manual1.py (MC analysis)")
    print("  S2: Second open source (BS + Rubinstein)")
    print("  S3: montecarlo.py (MC with arbitrage)")
    print()

    df = compare_all_sources()

    # Display fair value comparison
    print("=" * 100)
    print("FAIR VALUE COMPARISON")
    print("=" * 100)
    cols = ["Product", "Bid", "Ask", "Fair_S1", "Fair_S2", "Fair_S3"]
    print(df[cols].to_string(index=False, float_format="%.3f"))

    # Display action comparison
    print("\n" + "=" * 100)
    print("ACTION & EDGE COMPARISON")
    print("=" * 100)
    cols = ["Product", "Action_S1", "Action_S2", "Action_S3", "Edge_S1", "Edge_S2", "Edge_S3", "Agree"]
    print(df[cols].to_string(index=False))

    # Key findings
    print("\n" + "=" * 100)
    print("KEY FINDINGS - WHERE SOURCES AGREE")
    print("=" * 100)

    # The riskless arbitrage
    print("\n*** RISKLESS ARBITRAGE (ALL SOURCES AGREE) ***")
    print("  SELL 50 AC_50_CO (chooser) @ 22.20")
    print("  BUY  50 AC_50_C  (21d call) @ 12.05")
    print("  BUY  50 AC_50_P_2 (14d put) @ 9.75")
    print("  ---------------------------------")
    print("  Net credit = 22.20 - 12.05 - 9.75 = +0.40/unit = +20.00 total")
    print("  This is PATH-INDEPENDENT by Rubinstein's chooser formula (r=0)")

    print("\n*** HIGH-EDGE CONSENSUS TRADES ***")
    consensus = [
        ("AC_45_KO", "BUY", 500, "~0.03-0.04", "Knock-out underpriced"),
        ("AC_40_BP", "SELL", 50, "~0.23-0.33", "Binary overpriced"),
        ("AC_50_C_2", "BUY", 50, "~0.03-0.12", "2w call underpriced"),
        ("AC_50_P_2", "BUY", 50, "~0.03-0.12", "2w put underpriced (part of arb)"),
    ]
    for prod, action, vol, edge, note in consensus:
        print(f"  {action:4} {vol:3} {prod:12} edge: {edge:12}  ({note})")

    print("\n*** VANILLA 3W OPTIONS (ROUGHLY FAIR) ***")
    vanilla = ["AC_50_P", "AC_50_C", "AC_35_P", "AC_40_P", "AC_45_P", "AC_60_C"]
    for prod in vanilla:
        row = df[df["Product"] == prod].iloc[0]
        print(f"  {prod:10} actions: S1={row['Action_S1']}, S2={row['Action_S2']}, S3={row['Action_S3']}")

    print("\n" + "=" * 100)
    print("RECOMMENDED PORTFOLIO (COMBINING ALL INSIGHTS)")
    print("=" * 100)
    print("""
CORE (High Confidence - All Sources Agree):
  1. RISKLESS ARB (+20.00 guaranteed):
     SELL 50 AC_50_CO @ 22.20
     BUY  50 AC_50_C  @ 12.05
     BUY  50 AC_50_P_2 @ 9.75

  2. BUY 500 AC_45_KO @ 0.175 (edge ~0.03/unit = ~15 total)

  3. SELL 50 AC_40_BP @ 5.00 (edge ~0.23/unit = ~11.5 total)

  4. BUY 50 AC_50_C_2 @ 9.75 (edge ~0.12/unit = ~6 total)
     (Note: AC_50_P_2 already in arb)

OPTIONAL (Lower confidence - for higher risk/return):
  - Add vanilla hedges per manual1.py repo for lower variance
  - Or go naked on the above for ~52.5 expected total edge
""")

if __name__ == "__main__":
    main()
