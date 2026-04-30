from datamodel import OrderDepth, TradingState, Order
import json
import numpy as np
import math
from statistics import NormalDist

_N = NormalDist()

####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL  

GALAXY_SYMBOLS = [
    'GALAXY_SOUNDS_DARK_MATTER',
    'GALAXY_SOUNDS_BLACK_HOLES',
    'GALAXY_SOUNDS_PLANETARY_RINGS',
    'GALAXY_SOUNDS_SOLAR_WINDS',
    'GALAXY_SOUNDS_SOLAR_FLAMES',
]

SLEEP_POD_SYMBOLS = [
    'SLEEP_POD_SUEDE',
    'SLEEP_POD_LAMB_WOOL',
    'SLEEP_POD_POLYESTER',
    'SLEEP_POD_NYLON',
    'SLEEP_POD_COTTON',
]

MICROCHIP_SYMBOLS = [
    'MICROCHIP_CIRCLE',
    'MICROCHIP_OVAL',
    'MICROCHIP_SQUARE',
    'MICROCHIP_RECTANGLE',
    'MICROCHIP_TRIANGLE',
]

PEBBLES_SYMBOLS = [
    'PEBBLES_XS',
    'PEBBLES_S',
    'PEBBLES_M',
    'PEBBLES_L',
    'PEBBLES_XL',
]

ROBOT_SYMBOLS = [
    'ROBOT_VACUUMING',
    'ROBOT_MOPPING',
    'ROBOT_DISHES',
    'ROBOT_LAUNDRY',
    'ROBOT_IRONING',
]

UV_VISOR_SYMBOLS = [
    'UV_VISOR_YELLOW',
    'UV_VISOR_AMBER',
    'UV_VISOR_ORANGE',
    'UV_VISOR_RED',
    'UV_VISOR_MAGENTA',
]

TRANSLATOR_SYMBOLS = [
    'TRANSLATOR_SPACE_GRAY',
    'TRANSLATOR_ASTRO_BLACK',
    'TRANSLATOR_ECLIPSE_CHARCOAL',
    'TRANSLATOR_GRAPHITE_MIST',
    'TRANSLATOR_VOID_BLUE',
]

PANEL_SYMBOLS = [
    'PANEL_1X2',
    'PANEL_2X2',
    'PANEL_1X4',
    'PANEL_2X4',
    'PANEL_4X4',
]

OXYGEN_SHAKE_SYMBOLS = [
    'OXYGEN_SHAKE_MORNING_BREATH',
    'OXYGEN_SHAKE_EVENING_BREATH',
    'OXYGEN_SHAKE_MINT',
    'OXYGEN_SHAKE_CHOCOLATE',
    'OXYGEN_SHAKE_GARLIC',
]

SNACKPACK_SYMBOLS = [
    'SNACKPACK_CHOCOLATE',
    'SNACKPACK_VANILLA',
    'SNACKPACK_PISTACHIO',
    'SNACKPACK_STRAWBERRY',
    'SNACKPACK_RASPBERRY',
]

SNACKPACK_PSR_SYMBOLS = [
    'SNACKPACK_PISTACHIO',
    'SNACKPACK_STRAWBERRY',
    'SNACKPACK_RASPBERRY',
]

SNACKPACK_VC_SYMBOLS = [
    'SNACKPACK_VANILLA',
    'SNACKPACK_CHOCOLATE',
]

MC_SR_SYMBOLS = [
    'MICROCHIP_SQUARE',
    'MICROCHIP_RECTANGLE',
]

XLS_SYMBOLS = [
    'PEBBLES_XL',
    'PEBBLES_S',
]

SPPS_SYMBOLS = [
    'SLEEP_POD_SUEDE',
    'SLEEP_POD_POLYESTER',
]

R_VI_SYMBOLS = [
    'ROBOT_VACUUMING',
    'ROBOT_IRONING',
]

PANEL_PAIR_SYMBOLS = [
    'PANEL_1X2',
    'PANEL_2X2',
]

POS_LIMIT = 10

LONG, NEUTRAL, SHORT = 1, 0, -1

# ---------------------------------------------
################### BASKET #####################
# ---------------------------------------------

############### TRANSLATOR ###############

TRANSLATOR_BETA = [ 18.54104359, -26.43758433,   9.15449103,  28.68298071]
TRANSLATOR_SPREAD_MEAN = 276.8511333284233
TRANSLATOR_SPREAD_STD = 1.00
TRANSLATOR_THRESHOLD = 1.5

################# GALAXY_SOUNDS ##############

GS_BETA = [ 1.23248065, 15.74276142, -4.92857599, 15.29650459, 16.62256435]
GS_SPREAD_MEAN = 407.36001200029426
GS_SPREAD_STD = 1.00
GS_THRESHOLD = 1.5

############### MICROCHIP ###############

MICROCHIP_BETA = [16.34572941, -13.59596011, -31.82337302]
MICROCHIP_SPREAD_MEAN = -268.3509747533391
MICROCHIP_SPREAD_STD = 1.0003801297138426
MICROCHIP_THRESHOLD = 1.2

############## UV ########################

UV_BETA = [21.38397387, 34.02936129,  9.20705138, 26.7099268 ,  2.96050108]
UV_SPREAD_MEAN = 870.1087979178878
UV_SPREAD_STD = 1.00
UV_THRESHOLD = 1.0

################# OS ##########################

OS_BETA = [21.16614083,  -7.30450388, -16.93241485,  -1.96112573, -5.93961389]
OS_SPREAD_MEAN = -104.36703744993089
OS_SPREAD_STD = 1.00
OS_THRESHOLD = 1.0

############# ROBOT ###########################

R_BETA = [21.89333144, 15.9365944 , 19.54685174, 22.14675073, -1.25250787]
R_SPREAD_MEAN = 720.6105166538539
R_SPREAD_STD = 1.00
R_THRESHOLD = 1.0

############# SLEEP_POD ########################

SP_BETA = [ 16.52581225, -17.71073443,   4.43916018, -30.5677949 , 13.10313787]
SP_SPREAD_MEAN = -133.3254401958018
SP_SPREAD_STD = 1.00
SP_THRESHOLD = 1.2

################ PEBBLES ###########################

P_BETA = [18.5541452 ,  3.13788003, -6.4503152 ]
P_SPREAD_MEAN = 141.10941049216513
P_SPREAD_STD = 1.00
P_THRESHOLD = 1.5

############ SNACKPACK ####################

SNACKPACK_BETA = [148.80325814, -30.6227267 , -29.35608255,  29.80545624, 110.53788623]
SNACKPACK_SPREAD_MEAN = 2112.7705132541355
SNACKPACK_SPREAD_STD = 1.00
SNACKPACK_THRESHOLD = 1.5

# ---------------------------------------------
################### PAIRS #####################
# ---------------------------------------------

############### PSR ############### 

PSR_ALPHA = 11.513697565779395
PSR_BETA = -0.25385583527783534
PSR_SPREAD_STD = 0.01767577401357323
PSR_THRESHOLD = 1.8

############### VC ############### 

VC_ALPHA = 16.556141389751517
VC_BETA = -0.7979115826032864
VC_SPREAD_STD = 0.006755144417558233
VC_THRESHOLD = 1.0

############### MICROCHIP SR ###############

MC_SR_ALPHA = 14.12013720211347
MC_SR_BETA = -0.5310378074106424
MC_SR_SPREAD_STD = 0.041064546822360985
MC_SR_THRESHOLD = 1.5

############### XLS ###############

XLS_ALPHA = 20.046814838632574
XLS_BETA = -1.1620345624315502
XLS_SPREAD_STD = 0.08139014676398257
XLS_THRESHOLD = 1.5

############## SPSP ##################

SP_PS_ALPHA = 1.00
SP_PS_BETA = 0.8966634571296795
SP_PS_SPREAD_STD = 0.042500341857436744
SP_PS_THRESHOLD = 1.5

################# RVI ################

R_VI_ALPHA = 4.426698507726565
R_VI_BETA = 0.5177892335261596
R_VI_SPREAD_STD = 0.035195973627684174
R_VI_THRESHOLD = 1.0

############## PANELS ######################

PANEL_ALPHA = 13.684655128137374
PANEL_BETA = -0.5008962559589548
PANEL_SPREAD_STD = 0.05610591832106225
PANEL_THRESHOLD = 2

# This is the base ProductTrader class that has all the commonly used utility attributes and methods already implemented for individual traders
class ProductTrader:

    def __init__(self, name, state, prints, new_trader_data, product_group=None):

        self.orders = []

        self.name = name
        self.state = state
        self.prints = prints
        self.new_trader_data = new_trader_data
        self.product_group = name if product_group is None else product_group

        self.last_traderData = self.get_last_traderData()

        self.position_limit = POS_LIMIT
        self.initial_position = self.state.position.get(self.name, 0) # position at beginning of round

        self.expected_position = self.initial_position # update this if you expect a certain change in position e.g. to already hedge


        self.mkt_buy_orders, self.mkt_sell_orders = self.get_order_depth()
        self.bid_wall, self.wall_mid, self.ask_wall = self.get_walls()
        self.best_bid, self.best_ask = self.get_best_bid_ask()

        self.max_allowed_buy_volume, self.max_allowed_sell_volume = self.get_max_allowed_volume() # gets updated when order created
        self.total_mkt_buy_volume, self.total_mkt_sell_volume = self.get_total_market_buy_sell_volume()

    def get_last_traderData(self):
                        
        last_traderData = {}
        try:
            if self.state.traderData != '':
                last_traderData = json.loads(self.state.traderData)
        except: self.log("ERROR", 'td')

        return last_traderData


    def get_best_bid_ask(self):

        best_bid = best_ask = None

        try:
            if len(self.mkt_buy_orders) > 0:
                best_bid = max(self.mkt_buy_orders.keys())
            if len(self.mkt_sell_orders) > 0:
                best_ask = min(self.mkt_sell_orders.keys())
        except: pass

        return best_bid, best_ask


    def get_walls(self):

        bid_wall = wall_mid = ask_wall = None

        try: bid_wall = min([x for x,_ in self.mkt_buy_orders.items()])
        except: pass
        
        try: ask_wall = max([x for x,_ in self.mkt_sell_orders.items()])
        except: pass

        try: wall_mid = (bid_wall + ask_wall) / 2
        except: pass

        return bid_wall, wall_mid, ask_wall
    
    def get_total_market_buy_sell_volume(self):

        market_bid_volume = market_ask_volume = 0

        try:
            market_bid_volume = sum([v for p, v in self.mkt_buy_orders.items()])
            market_ask_volume = sum([v for p, v in self.mkt_sell_orders.items()])
        except: pass

        return market_bid_volume, market_ask_volume
    

    def get_max_allowed_volume(self):
        max_allowed_buy_volume = self.position_limit - self.initial_position
        max_allowed_sell_volume = self.position_limit + self.initial_position
        return max_allowed_buy_volume, max_allowed_sell_volume

    def get_order_depth(self):

        order_depth, buy_orders, sell_orders = {}, {}, {}

        try: order_depth: OrderDepth = self.state.order_depths[self.name]
        except: pass
        try: buy_orders = {bp: abs(bv) for bp, bv in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)}
        except: pass
        try: sell_orders = {sp: abs(sv) for sp, sv in sorted(order_depth.sell_orders.items(), key=lambda x: x[0])}
        except: pass

        return buy_orders, sell_orders
    

    def bid(self, price, volume, logging=True):
        abs_volume = min(abs(int(volume)), self.max_allowed_buy_volume)
        order = Order(self.name, int(price), abs_volume)
        if logging: self.log("BUYO", {"p":price, "s":self.name, "v":int(volume)}, product_group='ORDERS')
        self.max_allowed_buy_volume -= abs_volume
        self.orders.append(order)

    def ask(self, price, volume, logging=True):
        abs_volume = min(abs(int(volume)), self.max_allowed_sell_volume)
        order = Order(self.name, int(price), -abs_volume)
        if logging: self.log("SELLO", {"p":price, "s":self.name, "v":int(volume)}, product_group='ORDERS')
        self.max_allowed_sell_volume -= abs_volume
        self.orders.append(order)

    def log(self, kind, message, product_group=None):
        if product_group is None: product_group = self.product_group

        if product_group == 'ORDERS':
            group = self.prints.get(product_group, [])
            group.append({kind: message})
        else:
            group = self.prints.get(product_group, {})
            group[kind] = message

        self.prints[product_group] = group

    def get_orders(self):
        # overwrite this in each trader
        return {}
    
class PSRTrader:
    def __init__(self, state, prints, new_trader_data):
        self.pistachio = ProductTrader("SNACKPACK_PISTACHIO", state, prints, new_trader_data)
        self.strawberry = ProductTrader("SNACKPACK_STRAWBERRY", state, prints, new_trader_data)
        self.raspberry = ProductTrader("SNACKPACK_RASPBERRY", state, prints, new_trader_data)

        self.state = state
        self.new_trader_data = new_trader_data

        self.z_spread = self.calculate_z_spread()

    def calculate_z_spread(self):
        pistachio_pred = PSR_ALPHA + PSR_BETA * np.log(self.strawberry.wall_mid)
        raw_spread = np.log(self.pistachio.wall_mid) - pistachio_pred
        z_spread = raw_spread / PSR_SPREAD_STD
        return z_spread
    
    def get_orders(self):
        p = self.pistachio
        s = self.strawberry
        r = self.raspberry

        orders = {}

        if self.z_spread > PSR_THRESHOLD and p.max_allowed_sell_volume > 0:
            p.ask(p.bid_wall, p.max_allowed_sell_volume)
            s.ask(s.bid_wall, s.max_allowed_sell_volume)
            r.bid(r.ask_wall, r.max_allowed_buy_volume)
        elif self.z_spread < -PSR_THRESHOLD and p.max_allowed_buy_volume > 0:
            p.bid(p.ask_wall, p.max_allowed_buy_volume)
            s.bid(s.ask_wall, s.max_allowed_buy_volume)
            r.ask(r.bid_wall, r.max_allowed_sell_volume)

        orders.update({p.name: p.orders, s.name: s.orders, r.name: r.orders})

        return orders
    
class PairsTrader:
    """
    Z-spread pair/basket trader using a fixed regression:
        log(legs[0].mid) ~ alpha + beta * log(legs[1].mid)
        z = (log(y_mid) - alpha - beta * log(x_mid)) / spread_std

    Each leg has a `side` (+1 / -1) describing its direction at z > +threshold:
        side=+1 → ask; side=-1 → bid. Signs flip at z < -threshold.

    legs[0] is the lead: its volume gates entry, its position drives flatten.
    flatten=True closes every leg at |initial_position| once the spread fully
    mean-reverts (z crosses 0 against the open lead position).
    """

    def __init__(self, state, prints, new_trader_data, *,
                 legs, alpha, beta, spread_std, threshold, flatten=True):
        self.state = state
        self.new_trader_data = new_trader_data
        self.threshold = threshold
        self.flatten = flatten

        self.legs = [
            {'pt': ProductTrader(leg['symbol'], state, prints, new_trader_data),
             'side': leg['side']}
            for leg in legs
        ]
        self.lead = self.legs[0]

        y_mid = self.legs[0]['pt'].wall_mid
        x_mid = self.legs[1]['pt'].wall_mid
        y_pred = alpha + beta * np.log(x_mid)
        self.z_spread = (np.log(y_mid) - y_pred) / spread_std

    @staticmethod
    def _do_ask(entry_sign, side):
        return (entry_sign * side) > 0

    def _entry_volume(self, entry_sign):
        lead_pt = self.lead['pt']
        if self._do_ask(entry_sign, self.lead['side']):
            return lead_pt.max_allowed_sell_volume
        return lead_pt.max_allowed_buy_volume

    def _trade(self, entry_sign, use_initial_position=False):
        for leg in self.legs:
            pt = leg['pt']
            do_ask = self._do_ask(entry_sign, leg['side'])
            if use_initial_position:
                vol = abs(pt.initial_position)
            else:
                vol = pt.max_allowed_sell_volume if do_ask else pt.max_allowed_buy_volume
            if do_ask:
                pt.ask(pt.bid_wall, vol)
            else:
                pt.bid(pt.ask_wall, vol)

    def get_orders(self):
        z = self.z_spread

        if z > self.threshold and self._entry_volume(+1) > 0:
            self._trade(+1)
        elif z < -self.threshold and self._entry_volume(-1) > 0:
            self._trade(-1)
        elif self.flatten:
            lead_pos = self.lead['pt'].initial_position
            lead_side = self.lead['side']
            # lead_pos>0 came from entry at z<-T → close on full reversion (z>=0)
            # lead_pos<0 came from entry at z>+T → close on full reversion (z<=0)
            if lead_pos > 0 and z >= 0:
                self._trade(lead_side, use_initial_position=True)
            elif lead_pos < 0 and z <= 0:
                self._trade(-lead_side, use_initial_position=True)

        return {l['pt'].name: l['pt'].orders for l in self.legs}


class VCTrader(PairsTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'SNACKPACK_VANILLA',   'side': +1},
                {'symbol': 'SNACKPACK_CHOCOLATE', 'side': -1},
            ],
            alpha=VC_ALPHA, beta=VC_BETA, spread_std=VC_SPREAD_STD,
            threshold=VC_THRESHOLD, flatten=True)


class MicrochipSRTrader(PairsTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'MICROCHIP_RECTANGLE', 'side': +1},
                {'symbol': 'MICROCHIP_SQUARE',    'side': +1},
            ],
            alpha=MC_SR_ALPHA, beta=MC_SR_BETA, spread_std=MC_SR_SPREAD_STD,
            threshold=MC_SR_THRESHOLD, flatten=True)


class XLSTrader(PairsTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'PEBBLES_XL', 'side': +1},
                {'symbol': 'PEBBLES_S',  'side': +1},
            ],
            alpha=XLS_ALPHA, beta=XLS_BETA, spread_std=XLS_SPREAD_STD,
            threshold=XLS_THRESHOLD, flatten=True)


class SPPSTrader(PairsTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'SLEEP_POD_POLYESTER', 'side': +1},
                {'symbol': 'SLEEP_POD_SUEDE',     'side': -1},
            ],
            alpha=SP_PS_ALPHA, beta=SP_PS_BETA, spread_std=SP_PS_SPREAD_STD,
            threshold=SP_PS_THRESHOLD, flatten=True)


class RVITrader(PairsTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'ROBOT_VACUUMING', 'side': +1},
                {'symbol': 'ROBOT_IRONING',   'side': -1},
            ],
            alpha=R_VI_ALPHA, beta=R_VI_BETA, spread_std=R_VI_SPREAD_STD,
            threshold=R_VI_THRESHOLD, flatten=True)
        
class PanelPairTrader(PairsTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'PANEL_1X2', 'side': +1},
                {'symbol': 'PANEL_2X2',   'side': -1},
            ],
            alpha=PANEL_ALPHA, beta=PANEL_BETA, spread_std=PANEL_SPREAD_STD,
            threshold=PANEL_THRESHOLD, flatten=True)


class BasketTrader:
    """
    Generic linear-basket mean-reversion trader with rolling-window stats.

    legs: list of dicts with keys
        symbol: product symbol
        side:   +1 / 0 / -1
                When z > +threshold we trade `side`: +1 → ask, -1 → bid, 0 → skip.
                When z < -threshold the directions flip.
        vol:    'self' (default) or float scale.
                'self'  -> use this leg's own max_allowed_{buy,sell}_volume.
                float k -> use k * lead's volume in the entry direction.

    The lead leg is the first leg with side != 0 and vol == 'self'; its
    volume gates entry and serves as the base for scaled legs.

    flatten: if True, when no entry fires and the lead carries a position
             whose sign disagrees with z, close every traded leg at its
             own |initial_position|.

    Rolling stats:
        Each timestep appends the current `beta · wall_mids` raw spread to a
        per-basket history kept in state.traderData under `key`. The history
        is trimmed to `window` samples; rolling mean/std are computed from
        it. Trading is skipped until the history has `min_samples` entries.
    """

    def __init__(self, state, prints, new_trader_data, *, legs,
                 beta, threshold, window, key, min_samples=None,
                 flatten=False):
        self.state = state
        self.new_trader_data = new_trader_data

        self.legs = []
        for leg in legs:
            pt = ProductTrader(leg['symbol'], state, prints, new_trader_data)
            self.legs.append({'pt': pt, 'side': leg['side'], 'vol': leg.get('vol', 'self')})

        self.beta = np.asarray(beta)
        self.threshold = threshold
        self.window = window
        self.key = key
        self.min_samples = window if min_samples is None else min_samples
        self.flatten = flatten

        self.lead = next(l for l in self.legs if l['side'] != 0 and l['vol'] == 'self')

        self.raw_spread = self._raw_spread()
        self.history = self._update_history(self.raw_spread)

        if len(self.history) >= self.min_samples:
            arr = np.asarray(self.history)
            self.spread_mean = float(arr.mean())
            std = float(arr.std())
            self.spread_std = std if std > 0 else 1.0
            self.z_spread = (self.raw_spread - self.spread_mean) / self.spread_std
        else:
            self.spread_mean = None
            self.spread_std = None
            self.z_spread = None

    def _raw_spread(self):
        y = np.log([l['pt'].wall_mid for l in self.legs])
        return float(y @ self.beta)

    def _update_history(self, sample):
        prev = self.lead['pt'].last_traderData
        history = list(prev.get(self.key, [])) if isinstance(prev, dict) else []
        history.append(float(sample))
        if len(history) > self.window:
            history = history[-self.window:]
        self.new_trader_data[self.key] = history
        return history

    @staticmethod
    def _do_ask(sign, side):
        return (sign * side) > 0

    def _lead_entry_vol(self, sign):
        lead_pt = self.lead['pt']
        if self._do_ask(sign, self.lead['side']):
            return lead_pt.max_allowed_sell_volume
        return lead_pt.max_allowed_buy_volume

    def _trade(self, sign, use_initial_position=False):
        lead_base = (abs(self.lead['pt'].initial_position)
                     if use_initial_position else self._lead_entry_vol(sign))

        for leg in self.legs:
            if leg['side'] == 0:
                continue
            pt = leg['pt']
            do_ask = self._do_ask(sign, leg['side'])
            if leg['vol'] == 'self':
                if use_initial_position:
                    vol = abs(pt.initial_position)
                else:
                    vol = pt.max_allowed_sell_volume if do_ask else pt.max_allowed_buy_volume
            else:
                vol = int(leg['vol'] * lead_base)
            if do_ask:
                pt.ask(pt.bid_wall, vol)
            else:
                pt.bid(pt.ask_wall, vol)

    def get_orders(self):
        z = self.z_spread

        if z is None:
            # Warming up rolling-stats window; persist history but no trades.
            return {l['pt'].name: l['pt'].orders for l in self.legs if l['side'] != 0}

        if z > self.threshold and self._lead_entry_vol(+1) > 0:
            self._trade(+1)
        elif z < -self.threshold and self._lead_entry_vol(-1) > 0:
            self._trade(-1)
        elif self.flatten:
            lead_pos = self.lead['pt'].initial_position
            lead_side = self.lead['side']
            # Closing trades the lead opposite to entry. Lead asks ⇔ sign*lead_side>0.
            # lead_pos>0 was acquired by bidding → close by asking → close_sign = lead_side.
            if lead_pos > 0 and z < 0:
                self._trade(lead_side, use_initial_position=True)
            elif lead_pos < 0 and z > 0:
                self._trade(-lead_side, use_initial_position=True)

        return {l['pt'].name: l['pt'].orders for l in self.legs if l['side'] != 0}


class StaticBasketTrader:
    """
    Generic linear-basket mean-reversion trader with static spread mean & std.

    Spread is computed from log prices:
        raw_spread = beta · log(wall_mids)
        z          = (raw_spread - spread_mean) / spread_std

    legs: list of dicts with keys
        symbol: product symbol
        side:   +1 / 0 / -1
                When z > +threshold we trade `side`: +1 → ask, -1 → bid, 0 → skip.
                When z < -threshold the directions flip.
        vol:    'self' (default) or float scale.
                'self'  -> use this leg's own max_allowed_{buy,sell}_volume.
                float k -> use k * lead's volume in the entry direction.

    The lead leg is the first leg with side != 0 and vol == 'self'; its
    volume gates entry and serves as the base for scaled legs.

    flatten: if True, when no entry fires and the lead carries a position
             whose sign disagrees with z, close every traded leg at its
             own |initial_position|.
    """

    def __init__(self, state, prints, new_trader_data, *, legs,
                 beta, spread_mean, spread_std, threshold, flatten=False):
        self.state = state
        self.new_trader_data = new_trader_data

        self.legs = []
        for leg in legs:
            pt = ProductTrader(leg['symbol'], state, prints, new_trader_data)
            self.legs.append({'pt': pt, 'side': leg['side'], 'vol': leg.get('vol', 'self')})

        self.beta = np.asarray(beta)
        self.spread_mean = float(spread_mean)
        self.spread_std = float(spread_std) if spread_std > 0 else 1.0
        self.threshold = threshold
        self.flatten = flatten

        self.lead = next(l for l in self.legs if l['side'] != 0 and l['vol'] == 'self')

        self.raw_spread = self._raw_spread()
        self.z_spread = (self.raw_spread - self.spread_mean) / self.spread_std

    def _raw_spread(self):
        y = np.log([l['pt'].wall_mid for l in self.legs])
        return float(y @ self.beta)

    @staticmethod
    def _do_ask(sign, side):
        return (sign * side) > 0

    def _lead_entry_vol(self, sign):
        lead_pt = self.lead['pt']
        if self._do_ask(sign, self.lead['side']):
            return lead_pt.max_allowed_sell_volume
        return lead_pt.max_allowed_buy_volume

    def _trade(self, sign, use_initial_position=False):
        lead_base = (abs(self.lead['pt'].initial_position)
                     if use_initial_position else self._lead_entry_vol(sign))

        for leg in self.legs:
            if leg['side'] == 0:
                continue
            pt = leg['pt']
            do_ask = self._do_ask(sign, leg['side'])
            if leg['vol'] == 'self':
                if use_initial_position:
                    vol = abs(pt.initial_position)
                else:
                    vol = pt.max_allowed_sell_volume if do_ask else pt.max_allowed_buy_volume
            else:
                vol = int(leg['vol'] * lead_base)
            if do_ask:
                pt.ask(pt.bid_wall, vol)
            else:
                pt.bid(pt.ask_wall, vol)

    def get_orders(self):
        z = self.z_spread

        if z > self.threshold:
            if self._lead_entry_vol(+1) > 0:
                self._trade(+1)
        elif z < -self.threshold:
            if self._lead_entry_vol(-1) > 0:
                self._trade(-1)
        elif self.flatten:
            lead_pos = self.lead['pt'].initial_position
            lead_side = self.lead['side']
            # Close on full mean reversion (z crosses 0 from the entry side).
            # lead_pos>0 came from entry at z<-T → close on z>=0.
            # lead_pos<0 came from entry at z>+T → close on z<=0.
            if lead_pos > 0 and z >= 0:
                self._trade(lead_side, use_initial_position=True)
            elif lead_pos < 0 and z <= 0:
                self._trade(-lead_side, use_initial_position=True)

        return {l['pt'].name: l['pt'].orders for l in self.legs if l['side'] != 0}

class TranslatorTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'TRANSLATOR_ASTRO_BLACK',       'side': 1},
                {'symbol': 'TRANSLATOR_ECLIPSE_CHARCOAL',  'side': -1},
                {'symbol': 'TRANSLATOR_SPACE_GRAY',        'side': 1},
                {'symbol': 'TRANSLATOR_VOID_BLUE',         'side': 1},
            ],
            beta=TRANSLATOR_BETA,
            spread_mean=TRANSLATOR_SPREAD_MEAN,
            spread_std=TRANSLATOR_SPREAD_STD,
            threshold=TRANSLATOR_THRESHOLD,
            flatten=True,
        )

class GSTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'GALAXY_SOUNDS_BLACK_HOLES',         'side': 0},
                {'symbol': 'GALAXY_SOUNDS_DARK_MATTER',         'side': 1},
                {'symbol': 'GALAXY_SOUNDS_PLANETARY_RINGS',     'side': -1},
                {'symbol': 'GALAXY_SOUNDS_SOLAR_FLAMES',        'side': 1},
                {'symbol': 'GALAXY_SOUNDS_SOLAR_WINDS',         'side': 1},
            ],
            beta=GS_BETA,
            spread_mean=GS_SPREAD_MEAN,
            spread_std=GS_SPREAD_STD,
            threshold=GS_THRESHOLD,
            flatten=True,
        )

class UVTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'UV_VISOR_AMBER',         'side': 0},
                {'symbol': 'UV_VISOR_MAGENTA',         'side': 1},
                {'symbol': 'UV_VISOR_ORANGE',     'side': 1},
                {'symbol': 'UV_VISOR_RED',        'side': 1},
                {'symbol': 'UV_VISOR_YELLOW',         'side': 1},
            ],
            beta=UV_BETA,
            spread_mean=UV_SPREAD_MEAN,
            spread_std=UV_SPREAD_STD,
            threshold=UV_THRESHOLD,
            flatten=True,
        )

class OSTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'OXYGEN_SHAKE_CHOCOLATE',                 'side': 1},
                {'symbol': 'OXYGEN_SHAKE_EVENING_BREATH',         'side': -1},
                {'symbol': 'OXYGEN_SHAKE_GARLIC',                   'side': -1},
                {'symbol': 'OXYGEN_SHAKE_MINT',                     'side': 0},
                {'symbol': 'OXYGEN_SHAKE_MORNING_BREATH',         'side': -1},
            ],
            beta=OS_BETA,
            spread_mean=OS_SPREAD_MEAN,
            spread_std=OS_SPREAD_STD,
            threshold=OS_THRESHOLD,
            flatten=True,
        )

class MicrochipTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'MICROCHIP_OVAL',                 'side': 1},
                {'symbol': 'MICROCHIP_RECTANGLE',         'side': -1},
                {'symbol': 'MICROCHIP_TRIANGLE',                   'side': -1},
            ],
            beta=MICROCHIP_BETA,
            spread_mean=MICROCHIP_SPREAD_MEAN,
            spread_std=MICROCHIP_SPREAD_STD,
            threshold=MICROCHIP_THRESHOLD,
            flatten=True,
        )

class RobotTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'ROBOT_DISHES',                 'side': 1},
                {'symbol': 'ROBOT_IRONING',         'side': 1},
                {'symbol': 'ROBOT_LAUNDRY',                   'side': 1},
                {'symbol': 'ROBOT_MOPPING',                     'side': 0},
                {'symbol': 'ROBOT_VACUUMING',         'side': 0},
            ],
            beta=R_BETA,
            spread_mean=R_SPREAD_MEAN,
            spread_std=R_SPREAD_STD,
            threshold=R_THRESHOLD,
            flatten=True,
        )

class SPTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'SLEEP_POD_COTTON',                 'side': 1},
                {'symbol': 'SLEEP_POD_LAMB_WOOL',         'side': -1},
                {'symbol': 'SLEEP_POD_NYLON',                   'side': 0},
                {'symbol': 'SLEEP_POD_POLYESTER',                     'side': -1},
                {'symbol': 'SLEEP_POD_SUEDE',         'side': 1},
            ],
            beta=SP_BETA,
            spread_mean=SP_SPREAD_MEAN,
            spread_std=SP_PS_SPREAD_STD,
            threshold=SP_THRESHOLD,
            flatten=True,
        )

class PebblesTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'PEBBLES_S',                 'side': 1},
                {'symbol': 'PEBBLES_XL',         'side': 1},
                {'symbol': 'PEBBLES_XS',                   'side': -1},
            ],
            beta=P_BETA,
            spread_mean=P_SPREAD_MEAN,
            spread_std=P_SPREAD_STD,
            threshold=P_THRESHOLD,
            flatten=True,
        )

class SnackpackTrader(StaticBasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'SNACKPACK_CHOCOLATE',                 'side': 1},
                {'symbol': 'SNACKPACK_PISTACHIO',         'side': -1},
                {'symbol': 'SNACKPACK_RASPBERRY',                   'side': -1},
                {'symbol': 'SNACKPACK_STRAWBERRY',                     'side': 1},
                {'symbol': 'SNACKPACK_VANILLA',         'side': 1},
            ],
            beta=SNACKPACK_BETA,
            spread_mean=SNACKPACK_SPREAD_MEAN,
            spread_std=SNACKPACK_SPREAD_STD,
            threshold=SNACKPACK_THRESHOLD,
            flatten=True,
        )

class Trader:

    def run(self, state: TradingState):
        result:dict[str,list[Order]] = {}
        try:
            new_trader_data = json.loads(state.traderData) if state.traderData else {}
            if not isinstance(new_trader_data, dict):
                new_trader_data = {}
        except Exception:
            new_trader_data = {}
        prints = {
            "GENERAL": {
                "TIMESTAMP": state.timestamp,
                "POSITIONS": state.position
            },
        }

        def export(prints):
            try: print(json.dumps(prints))
            except: pass


        product_traders = {
            TRANSLATOR_SYMBOLS[0]: TranslatorTrader,
            GALAXY_SYMBOLS[0]: GSTrader,
            UV_VISOR_SYMBOLS[0]: UVTrader,
            OXYGEN_SHAKE_SYMBOLS[0]: OSTrader,
            MICROCHIP_SYMBOLS[0]: MicrochipTrader,
            ROBOT_SYMBOLS[0]: RobotTrader,
            # -- Obsolete SNACKPACK_SYMBOLS[0]: SnackpackTrader,
            # -- Obsolete PEBBLES_SYMBOLS[0]: PebblesTrader,
            # -- Obsolete SLEEP_POD_SYMBOLS[0]: SPTrader,

            SNACKPACK_PSR_SYMBOLS[0]: PSRTrader,
            SNACKPACK_VC_SYMBOLS[0]: VCTrader,
            # -- Obsolete MC_SR_SYMBOLS[0]: MicrochipSRTrader,
            XLS_SYMBOLS[0]: XLSTrader,
            SPPS_SYMBOLS[0]: SPPSTrader,
            PANEL_PAIR_SYMBOLS[0]: PanelPairTrader,
            # - Obsolete R_VI_SYMBOLS[0]: RVITrader,
        }

        result, conversions = {}, 0
        for symbol, product_trader in product_traders.items():
            if symbol in state.order_depths:

                try:
                    trader = product_trader(state, prints, new_trader_data)
                    result.update(trader.get_orders())
                except: pass


        try: final_trader_data = json.dumps(new_trader_data)
        except: final_trader_data = ''


        export(prints)
        return result, conversions, final_trader_data