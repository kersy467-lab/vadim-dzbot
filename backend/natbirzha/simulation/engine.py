import random
from typing import Dict, Any, List, Optional
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, get_item_base_price, get_npc_buy_price, get_npc_sell_price
from backend.natbirzha.services.recipes import RECIPES

class SimPlayer:
    def __init__(self, player_id: int, specialization: str, seed: int):
        self.id = player_id
        self.specialization = specialization
        self.cash = nat_settings.STARTING_CASH
        self.nat_balance = 0
        self.level = 1
        self.xp = 0
        self.inventory: Dict[str, float] = {}
        self.factories: List[Dict[str, Any]] = []
        self.army_strength = 100
        self.is_bankrupt = False
        self.consecutive_idle_days = 0
        self.is_public = False
        self.shares = 10000
        self.recent_profits: List[float] = []

    def get_inv(self, item_id: str) -> float:
        return self.inventory.get(item_id, 0.0)

    def add_inv(self, item_id: str, qty: float):
        self.inventory[item_id] = round(self.inventory.get(item_id, 0.0) + qty, 2)

    def deduct_inv(self, item_id: str, qty: float) -> bool:
        if self.inventory.get(item_id, 0.0) >= qty:
            self.inventory[item_id] = round(self.inventory[item_id] - qty, 2)
            return True
        return False


class HeadlessSimulationEngine:
    def __init__(self, num_players: int = 5, days: int = 30, seed: int = 42):
        self.num_players = num_players
        self.days = days
        self.seed = seed
        self.rng = random.Random(seed)
        self.players: List[SimPlayer] = []
        self.metrics: Dict[str, Any] = {
            "deadlocks_detected": 0,
            "bankruptcies": 0,
            "total_npc_trades": 0,
            "total_p2p_trades": 0,
            "total_dividends_paid": 0.0,
            "tournaments_held": 0,
            "price_index_history": [],
            "bottlenecks": {}
        }

    def initialize_economy(self):
        specs = ["agrarian", "miner", "metallurgist", "oilman", "power_engineer", "forester", "chemist", "technoprom"]
        starter_factories = {
            "agrarian": "farm", "miner": "mine", "metallurgist": "smelter",
            "oilman": "oil_rig", "power_engineer": "hydro_solar",
            "forester": "logging_camp", "chemist": "chem_plant", "technoprom": "machinery_plant"
        }
        for i in range(1, self.num_players + 1):
            spec = specs[(i - 1) % len(specs)]
            player = SimPlayer(player_id=i, specialization=spec, seed=self.seed + i)
            player.factories.append({
                "type": starter_factories[spec],
                "specialization": spec,
                "level": 1,
                "efficiency": 1.0
            })
            self.players.append(player)

    def run_simulation(self) -> Dict[str, Any]:
        self.initialize_economy()

        for day in range(1, self.days + 1):
            # 1. Base municipal energy distribution
            for p in self.players:
                p.add_inv("grid_quota", nat_settings.BASE_MUNICIPAL_ENERGY_TICK)

            # 2. Production phase
            for p in self.players:
                made_progress = False
                for fac in p.factories:
                    recipe = next((r for r in RECIPES.values() if r["factory_type"] == fac["type"]), None)
                    if not recipe:
                        continue

                    # Procurement of missing inputs via NPC / Market
                    can_run = True
                    for in_item, in_qty in recipe["inputs"].items():
                        if p.get_inv(in_item) < in_qty:
                            cost = in_qty * get_npc_sell_price(in_item)
                            if p.cash >= cost:
                                p.cash -= cost
                                p.add_inv(in_item, in_qty)
                                self.metrics["total_npc_trades"] += 1
                            else:
                                can_run = False
                                self.metrics["bottlenecks"][in_item] = self.metrics["bottlenecks"].get(in_item, 0) + 1

                    if can_run:
                        # Deduct inputs
                        for in_item, in_qty in recipe["inputs"].items():
                            p.deduct_inv(in_item, in_qty)
                        # Add outputs
                        eff = 1.0 if fac["specialization"] == p.specialization else 0.10
                        for out_item, out_qty in recipe["outputs"].items():
                            p.add_inv(out_item, round(out_qty * eff, 2))
                        p.xp += 10
                        made_progress = True

                # Check idle status
                if not made_progress:
                    p.consecutive_idle_days += 1
                    if p.consecutive_idle_days >= 3 and p.cash < 50:
                        # Deadlock risk -> Trigger municipal distress recovery
                        self.metrics["deadlocks_detected"] += 1
                        p.cash += 5000.0  # Municipal emergency injection
                        p.is_bankrupt = True
                        self.metrics["bankruptcies"] += 1
                        p.consecutive_idle_days = 0
                else:
                    p.consecutive_idle_days = 0

                # 3. Commercial sale: sell produced goods to NPC to earn cash
                daily_revenue = 0.0
                for item_id, qty in list(p.inventory.items()):
                    if item_id in ("grid_quota", "energy", "water"):
                        continue
                    if qty >= 1.0:
                        sell_price = get_npc_buy_price(item_id)
                        payout = round(qty * sell_price, 2)
                        p.cash += payout
                        p.inventory[item_id] = 0.0
                        daily_revenue += payout
                        self.metrics["total_npc_trades"] += 1

                p.recent_profits.append(daily_revenue)
                if len(p.recent_profits) > 3:
                    p.recent_profits.pop(0)

                # 4. Expansion & IPO
                if p.cash >= 20000.0 and p.level == 1:
                    p.level = 2
                if p.level >= 2 and not p.is_public and p.cash >= 30000.0:
                    p.is_public = True

                # 5. Dividends (10% of closed revenue)
                if p.is_public and daily_revenue > 0:
                    div_pool = round(daily_revenue * 0.10, 2)
                    p.cash -= div_pool
                    self.metrics["total_dividends_paid"] += div_pool

                # 6. Army recruitment for tournament
                if p.cash >= 10000.0 and day % 3 == 0:
                    recruited = int(p.cash * 0.20 // 50)
                    if recruited > 0:
                        p.cash -= recruited * 50
                        p.army_strength += recruited * 10

            # 7. Tournament every 72 hours (3 days)
            if day % 3 == 0:
                self.metrics["tournaments_held"] += 1
                # Winner is player with highest army strength
                sorted_players = sorted(self.players, key=lambda pl: pl.army_strength, reverse=True)
                winner = sorted_players[0]
                winner.nat_balance += nat_settings.TOURNAMENT_WINNER_PRIZE_NAT

            # Track price index stability (fixed basket of steel, grain, oil, coal)
            basket_sum = sum(get_item_base_price(it) for it in ["steel", "grain", "oil_crude", "coal"])
            self.metrics["price_index_history"].append(basket_sum)

        avg_cash = sum(p.cash for p in self.players) / len(self.players)
        avg_nat = sum(p.nat_balance for p in self.players) / len(self.players)
        return {
            "num_players": self.num_players,
            "days": self.days,
            "seed": self.seed,
            "avg_cash": round(avg_cash, 2),
            "avg_nat": round(avg_nat, 2),
            "deadlocks_detected": self.metrics["deadlocks_detected"],
            "bankruptcies": self.metrics["bankruptcies"],
            "total_npc_trades": self.metrics["total_npc_trades"],
            "tournaments_held": self.metrics["tournaments_held"],
            "total_dividends_paid": round(self.metrics["total_dividends_paid"], 2),
            "all_players_alive": all(p.cash > 0 for p in self.players)
        }
