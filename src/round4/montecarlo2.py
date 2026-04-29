from math import exp, sqrt
from statistics import NormalDist
from random import gauss

# Provided by IMC
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY

def weeks_to_years(weeks: float) -> float:
    # 5 business days per week, annualized to 252 trading days
    return (weeks * 5) / TRADING_DAYS_PER_YEAR

def steps_for_weeks(weeks: float) -> int:
    return int(round(weeks * 5 * STEPS_PER_DAY))

# Information about the underlying AETHER_CRYSTAL product
DRIFT = 0
VOLATILITY = 2.51
S_0 = 50  # The bid is 49.975 and the ask is 50.025

class Option:
    def __init__(self, option_name, expiry, bid_size, bid, ask, ask_size, price, option_type, strike_price):
        self.option_name = option_name
        self.expiry = expiry
        self.bid_size = bid_size
        self.bid = bid
        self.ask = ask
        self.ask_size = ask_size
        self.price = price
        self.option_type = option_type
        self.strike_price = strike_price

        self.available_choices = {"buy": "buy", "sell": "sell"}

        # We need to decide this
        self.buy_or_sell_choice = None
        self.volume = None
        self.decided_volume_signed = None

        self.total_payoff = 0
        self.fair_value = 0

        self.base_fair_value = None
        self.increased_fair_value = None
        self.delta = 0

class Available_Trades:
    def __init__(self):
        self.available_options = []

        # Initialize all of the options provided
        option_names = ["AC", "AC_50_P", "AC_50_C", "AC_35_P", "AC_40_P", "AC_45_P", "AC_60_C", "AC_50_P_2", "AC_50_C_2", "AC_50_CO", "AC_40_BP", "AC_45_KO"]
        expirys = ["N/A", 21, 21, 21, 21, 21, 21, 14, 14, "14/21", 21, 21]
        bid_sizes = [200, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 500]
        bids = [49.975, 12, 12, 4.33, 6.5, 9.05, 8.8, 9.7, 9.7, 22.2, 5, 0.15]
        asks = [50.025, 12.05, 12.05, 4.35, 6.55, 9.1, 8.85, 9.75, 9.75, 22.3, 5.1, 0.175]
        ask_sizes = [200, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 500]
        prices = [0.71, 2.71, -0.45, 0.42, 0, -0.48, 0.42, 0.71, 0.71, 0.71, 0.71, 0.71]
        option_types = ["N/A", "vanilla_put", "vanilla_call", "vanilla_put", "vanilla_put", "vanilla_put", "vanilla_call", "vanilla_put", "vanilla_call", "chooser", "binary_put", "knock-out_put"]
        strike_prices = ["N/A", 50, 50, 35, 40, 45, 60, 50, 50, 50, 40, 45]\
        
        for index, option in enumerate(option_names):
            self.available_options.append(Option(option, expirys[index], bid_sizes[index], bids[index], asks[index],
                                                 ask_sizes[index], prices[index], option_types[index], strike_prices[index]))
    
    def run_monte_carlo(self, starting_price):
        # Reset everything for now
        for option in self.available_options:
            option.total_payoff = 0
            option.fair_value = 0
            option.delta = 0
            option.buy_or_sell_choice = None
            option.volume = None
        
        NUMBER_OF_SIMULATIONS = 50_000

        for i in range(NUMBER_OF_SIMULATIONS):
            twenty_one_day_path = self.run_path(21, starting_price)
            fourteen_day_path = twenty_one_day_path[:(14 * STEPS_PER_DAY) + 1]

            for option in self.available_options:
                if option.expiry == "N/A":
                    continue
                
                chosen_path = fourteen_day_path

                if option.expiry == 14:
                    chosen_path = fourteen_day_path

                elif option.expiry == 21:
                    chosen_path = twenty_one_day_path

                elif option.expiry == "14/21":
                    chosen_path = twenty_one_day_path
                
                payoff = 0

                if option.option_type == "knock-out_put":
                    if min(chosen_path) >= option.strike_price:
                        payoff = max(option.strike_price - chosen_path[-1], 0)
                
                elif option.option_type == "chooser":
                    call = max(chosen_path[-1] - option.strike_price, 0)
                    put = max(option.strike_price - chosen_path[-1], 0)

                    payoff = max(call, put)

                elif option.option_type == "binary_put":
                    if chosen_path[-1] < option.strike_price:
                        payoff = 10

                    else:
                        payoff = 0

                else:
                    if option.option_type == "vanilla_call":
                        payoff = max(chosen_path[-1] - option.strike_price, 0)
                    
                    else:
                        payoff = max(option.strike_price - chosen_path[-1], 0)

                option.total_payoff += payoff
        
        for option in self.available_options:
            if option.expiry == "N/A":
                continue

            option.fair_value = option.total_payoff / NUMBER_OF_SIMULATIONS

            buy_edge = option.fair_value - option.ask
            sell_edge = option.bid - option.fair_value

            minmimum_edge_allowed = max(0.10, abs(option.ask - option.bid))

            if buy_edge > 0 and buy_edge > minmimum_edge_allowed:
                option.buy_or_sell_choice = option.available_choices["buy"]
                option.volume = int(min(1, buy_edge) * option.ask_size)

            elif sell_edge > 0 and sell_edge > minmimum_edge_allowed:
                option.buy_or_sell_choice = option.available_choices["sell"]
                option.volume = int(min(1, sell_edge) * option.bid_size)
    
    def run_path(self, expiry_in_days, starting_price):
        dt = 1 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)

        # Geometric Brownian Motion (yes)
        # S_t = S_0 * exp((mu - ((VOLATILITY ** 2) / 2)) * t + (VOLATILITY * W_t))
        
        S_t = starting_price
        path = [starting_price]

        for i in range(expiry_in_days * STEPS_PER_DAY):
            # Z = NormalDist(mu=0, sigma=1)
            Z = gauss(mu=0, sigma=1)

            # S_after_dt = S_t * exp(-0.5 * (VOLATILITY ** 2) * dt + VOLATILITY * sqrt(dt) * Z)
            S_t = S_t * exp(-0.5 * (VOLATILITY ** 2) * dt + VOLATILITY * sqrt(dt) * Z)

            path.append(S_t)
        
        return path

    def calculate_and_print_trade_decisions(self):
        self.run_monte_carlo(S_0)

        # Print out the trade decisions for the options
        for option in self.available_options:
            if option.option_name == "AC":
                continue

            self.print_option_trade_decision_formatted(option)

        print("\nCalculating trading for AC (this might take a while)...\n")

        # Calculate the trade decision for the underlying AETHER_CRYSTAL product
        price_increase = 3
        overall_delta = 0

        for option in self.available_options:  # Save the previous fair value and volume information for each option
            if option.option_name == "AC":
                continue

            if option.volume is None:
                continue

            option.decided_volume_signed = option.volume
            if option.buy_or_sell_choice == option.available_choices["sell"]:
                option.decided_volume_signed *= -1

            option.base_fair_value = option.fair_value

        self.run_monte_carlo(S_0 + price_increase)

        for option in self.available_options:  # Calculate the delta for each option
            if option.decided_volume_signed is None:
                continue

            option.increased_fair_value = option.fair_value

            option.delta = (option.increased_fair_value - option.base_fair_value) / price_increase
            overall_delta += option.decided_volume_signed * option.delta
        
        for option in self.available_options:
            if option.option_name == "AC":
                if overall_delta < 0:
                    option.buy_or_sell_choice = option.available_choices["buy"]
                elif overall_delta > 0:
                    option.buy_or_sell_choice = option.available_choices["sell"]

                option.volume = abs(round(overall_delta))
                self.print_option_trade_decision_formatted(option)
                break

    def print_option_trade_decision_formatted(self, option):
        print(f"{option.option_name} : ", end="")

        buy_or_sell = option.buy_or_sell_choice
        if buy_or_sell is None:
            buy_or_sell = "DON'T TRADE\n"
        
        print(f"{buy_or_sell}", end="")

        if buy_or_sell is not None and option.volume is not None:
            print(f" with a volume of {option.volume}")

def main():
    round_4_manual_trading_market = Available_Trades()
    round_4_manual_trading_market.calculate_and_print_trade_decisions()

main()
