"""Fail early when authored production data breaks a civilian economy invariant."""
from math import isfinite


def validate_tables(corporations, recipes, successors, starts, items):
    ids = [row[0] for *_, branches in corporations for row in branches]
    if len(ids) != len(set(ids)) or set(ids) != set(recipes) or set(ids) != set(successors):
        raise ValueError("Corporation IDs, recipes and progression must be one-to-one")
    producers = {recipe[0] for recipe in recipes.values()}
    if producers != set(items):
        raise ValueError("Every civilian market item must have a producer")
    for key, (output, quantity, inputs, operating) in recipes.items():
        if output not in items or not isfinite(quantity) or quantity <= 0 or operating < 0:
            raise ValueError(f"Invalid production recipe: {key}")
        for item, amount in inputs.items():
            if item not in producers or not isfinite(amount) or amount <= 0:
                raise ValueError(f"Missing supply or invalid input: {key}/{item}")
        income = quantity * items[output]["base_price"] * .8
        cost = operating + sum(amount * items[item]["base_price"] * 1.2 for item, amount in inputs.items())
        if income <= cost:
            raise ValueError(f"Unprofitable NPC recipe: {key}")
        if len(successors[key]) != len(set(successors[key])) or any(target not in recipes for target in successors[key]):
            raise ValueError(f"Invalid successor choices: {key}")
    done, active = set(), set()
    def visit(key):
        if key in active:
            raise ValueError(f"Cyclic progression: {key}")
        if key in done:
            return
        active.add(key)
        for target in successors[key]:
            visit(target)
        active.remove(key)
        done.add(key)
    for starting_ids in starts.values():
        for key in starting_ids:
            visit(key)
    if done != set(recipes):
        raise ValueError("Every corporation facility must be reachable from a start")
