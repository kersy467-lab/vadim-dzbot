"""Structural and economic contract for the civilian NATBIRZHA 2.0 graph."""
import unittest
from unittest.mock import patch
from backend.natbirzha.next_game_catalog import (
    CORPORATIONS, NEXT_BRANCH_IDS, NEXT_GAME_BASE_PRICES, RECIPES,
    START_BRANCH_IDS, get_next_game_catalog, get_next_game_items,
)
from backend.natbirzha.next_catalog import LEGACY_CORPORATIONS, SECTOR_NODES


class NextGameCatalogDepthTests(unittest.TestCase):
    def setUp(self):
        self.catalog = get_next_game_catalog()
        self.rows = {row["id"]: row for sector in self.catalog for row in sector["branches"]}

    def test_every_saved_identity_and_parent_is_preserved(self):
        self.assertEqual(len(self.catalog), 7)
        self.assertEqual(len(self.rows), 205)
        for sector_id, _, _, _, old_rows in LEGACY_CORPORATIONS:
            actual = next(row for row in self.catalog if row["id"] == sector_id)
            self.assertTrue({row[0] for row in old_rows} <= {row["id"] for row in actual["branches"]})
        self.assertEqual(set(RECIPES), set(self.rows))

    def test_all_nodes_reachable_and_graph_has_no_cycles(self):
        visited, active = set(), set()
        def visit(key):
            self.assertNotIn(key, active, "Progression must never return to an already selected branch")
            if key in visited:
                return
            active.add(key)
            for target in NEXT_BRANCH_IDS[key]:
                self.assertIn(target, self.rows)
                visit(target)
            active.remove(key)
            visited.add(key)
        for starts in START_BRANCH_IDS.values():
            for key in starts:
                visit(key)
        self.assertEqual(visited, set(self.rows))

    def test_seven_new_epochs_have_real_unselected_alternatives(self):
        new_keys = {row[0] for nodes in SECTOR_NODES.values() for row in nodes}
        for key in new_keys:
            row = self.rows[key]
            choices = row["next_branch_ids"]
            if row["tier"] == 9:
                self.assertEqual(choices, [])
                self.assertTrue(row["terminal"])
            else:
                self.assertEqual(len(set(choices)), 2)
                self.assertTrue(all(self.rows[target]["tier"] == row["tier"] + 1 for target in choices))
                first, second = (self.rows[target] for target in choices)
                self.assertNotEqual(first["factory"]["inputs"], second["factory"]["inputs"])
        for starts in START_BRANCH_IDS.values():
            for start in starts:
                route = [start]
                route.append(next(key for key in NEXT_BRANCH_IDS[start] if key in new_keys))
                while NEXT_BRANCH_IDS[route[-1]]:
                    choices = set(NEXT_BRANCH_IDS[route[-1]]) - set(route)
                    self.assertEqual(len(choices), 2)
                    route.append(sorted(choices)[0])
                self.assertEqual(len(route), 8)
                self.assertEqual(len(route), len(set(route)))

    def test_civilian_supply_covers_every_item_and_recipe_input(self):
        items = get_next_game_items()
        produced = {recipe[0] for recipe in RECIPES.values()}
        used = {key for _, _, inputs, _ in RECIPES.values() for key in inputs}
        self.assertEqual(produced, set(items))
        self.assertTrue(used <= produced)
        self.assertFalse({"military_gear", "well_lease", "forest_fund"} & set(items))

    def test_all_recipes_are_profitable_at_real_npc_spread(self):
        prices = {key: row["base_price"] for key, row in get_next_game_items().items()}
        for key, row in self.rows.items():
            factory = row["factory"]
            cost = sum(prices[item] * 1.2 * qty for item, qty in factory["inputs"].items())
            profit = prices[factory["output_item"]] * 0.8 * factory["output_quantity"] - cost - factory["operating_cost"]
            self.assertGreater(profit, 0, key)
            self.assertAlmostEqual(factory["economics"]["npc_profit"], round(profit, 2))
            self.assertGreaterEqual(factory["build_cost"], 3000)
            if row["is_starting_branch"]:
                self.assertLessEqual(factory["build_cost"] + cost + factory["operating_cost"], 10000, key)
        self.assertGreater(len({row["factory"]["build_cost"] for row in self.rows.values()}), 30)
        self.assertEqual(len({row["factory"]["cycle_seconds"] for row in self.rows.values()}), 9)

    def test_legacy_price_mutation_cannot_change_new_market(self):
        from backend.natbirzha.models.inventory import CANONICAL_ITEMS
        original = dict(CANONICAL_ITEMS["energy"])
        with patch.dict(CANONICAL_ITEMS, {"energy": {**original, "base_price": 999999}}):
            self.assertEqual(get_next_game_items()["energy"]["base_price"], NEXT_GAME_BASE_PRICES["energy"])


if __name__ == "__main__":
    unittest.main()
