from backend.natbirzha.next_game_catalog import get_next_game_catalog


def test_private_bank_has_reachable_atm_clearing_and_client_service_branches():
    catalog = get_next_game_catalog()
    bank = next(sector for sector in catalog if sector["id"] == "bank")
    branches = {branch["id"]: branch for branch in bank["branches"]}

    expected = {
        "atm_network": "Сеть банкоматов",
        "corporate_accounts": "Расчётные счета",
        "branch_network": "Региональные отделения",
        "clearing_house": "Межбанковский клиринг",
        "asset_management": "Управление активами",
        "merchant_acquiring": "Эквайринг торговых сетей",
    }
    assert all(branch_id in branches for branch_id in expected)
    assert {branch_id: branches[branch_id]["name"] for branch_id in expected} == expected
    assert all(not branches[branch_id]["is_starting_branch"] for branch_id in expected)
    assert branches["atm_network"]["factory"]["output_item"] == "payment_services"
    assert branches["clearing_house"]["factory"]["output_item"] == "investment_services"
    assert branches["branch_network"]["factory"]["output_item"] == "credit_services"
    assert all(len(branches[branch_id]["next_branch_ids"]) >= 2 for branch_id in expected)
    assert all(target in branches or any(target == node["id"] for sector in catalog for node in sector["branches"]) for branch_id in expected for target in branches[branch_id]["next_branch_ids"])
