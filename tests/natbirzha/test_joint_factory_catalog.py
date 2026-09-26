"""Shared-factory recipes form a complete, affordable industry network."""

from collections import defaultdict


def _recipes():
    import backend.natbirzha.catalogs.businesses as catalog

    recipes = getattr(catalog, "JOINT_FACTORY_RECIPES", None)
    assert recipes is not None, "joint-factory recipes should be exported by the active catalog"
    return catalog.INDUSTRIES, recipes


def test_each_industry_has_two_unique_joint_factory_partners():
    industries, recipes = _recipes()

    assert len(recipes) == 12
    partners = defaultdict(set)
    unordered_pairs = set()
    for recipe in recipes.values():
        left, right = recipe["specializations"]
        assert left != right
        pair = frozenset((left, right))
        assert pair not in unordered_pairs
        unordered_pairs.add(pair)
        partners[left].add(right)
        partners[right].add(left)

    assert set(partners) == set(industries)
    assert {industry: len(options) for industry, options in partners.items()} == {
        industry: 2 for industry in industries
    }


def test_joint_factory_levels_have_no_running_expenses_and_lower_owner_yield():
    _industries, recipes = _recipes()

    for recipe in recipes.values():
        assert len(recipe["levels"]) == 4
        for level_number, level in enumerate(recipe["levels"], start=1):
            assert level["level"] == level_number
            assert level["inputs_per_hour"] == {}
            assert level["maintenance_per_hour"] == 0
            assert len(level["outputs_per_hour"]) == 2
            assert all(quantity > 0 for quantity in level["outputs_per_hour"].values())
            for industry in recipe["specializations"]:
                assert level["owner_share_reference_value"] < level["industry_benchmarks"][industry]


def test_construction_and_each_upgrade_require_both_owners_to_contribute():
    _industries, recipes = _recipes()

    for recipe in recipes.values():
        for level in recipe["levels"]:
            contributions = level["contributions"]
            assert set(contributions) == set(recipe["specializations"])
            assert all(float(row["cash"]) > 0 for row in contributions.values())
            assert all(len(row["resources"]) == 1 for row in contributions.values())
            assert all(float(next(iter(row["resources"].values()))) > 0 for row in contributions.values())
