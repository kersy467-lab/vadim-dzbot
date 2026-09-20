import os
import sys

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.natbirzha.simulation.engine import HeadlessSimulationEngine

def run_simulation_matrix():
    cohorts = [1, 5, 20, 30]
    horizons = [30, 60, 120]
    seeds = [42, 1337, 2026]

    print("=" * 72)
    print("RUNNING NATBIRZHA HEADLESS ECONOMIC SIMULATION MATRIX")
    print("=" * 72)

    total_runs = 0
    passed_runs = 0

    for num_players in cohorts:
        for days in horizons:
            for seed in seeds:
                total_runs += 1
                engine = HeadlessSimulationEngine(num_players=num_players, days=days, seed=seed)
                res = engine.run_simulation()

                # Invariants check
                assert res["deadlocks_detected"] == 0, f"Deadlock detected in run {res}!"
                assert res["all_players_alive"] is True, f"Players went permanently bankrupt in run {res}!"
                assert res["avg_cash"] > 0, f"Avg cash collapsed in run {res}!"

                passed_runs += 1
                if days == 120 and seed == 42:
                    print(
                        f"  [PASS] {num_players:2d} Players | {days:3d} Days | Seed {seed:4d} => "
                        f"Avg Cash: {res['avg_cash']:10.1f} | Avg NAT: {res['avg_nat']:4.1f} | "
                        f"NPC Trades: {res['total_npc_trades']:6d} | Tournaments: {res['tournaments_held']:2d} | "
                        f"Dividends: {res['total_dividends_paid']:8.1f}"
                    )

    print("=" * 72)
    print(f"SIMULATION MATRIX COMPLETED: {passed_runs}/{total_runs} RUNS PASSED PERFECTLY (100%)!")
    print("=" * 72)

if __name__ == "__main__":
    run_simulation_matrix()
