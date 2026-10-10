"""Preserve existing companies while adding paid assets and civilian services."""
async def migrate_next_game_operations(conn):
    from backend.natbirzha.models.next_game_operations import (
        NatNextGameOperations, NatNextGameFactoryOperations, NatNextGameEmployee, NatNextGameVehicle,
    )
    from backend.natbirzha.models.next_game_civic import (
        NatNextGameTaxAccount, NatNextGameTaxAssessment, NatNextGameCityOrder, NatNextGameEconomicEvent,
    )
    from backend.natbirzha.models.next_game_bankruptcy import (
        NatNextGameBankruptcy, NatNextGameLiquidationLot, NatNextGameDebtWriteoff,
    )
    for model in (NatNextGameOperations, NatNextGameFactoryOperations, NatNextGameEmployee, NatNextGameVehicle,
                  NatNextGameTaxAccount, NatNextGameTaxAssessment, NatNextGameCityOrder, NatNextGameEconomicEvent,
                  NatNextGameBankruptcy, NatNextGameLiquidationLot, NatNextGameDebtWriteoff):
        await conn.run_sync(lambda sync, table=model.__table__: table.create(sync, checkfirst=True))
