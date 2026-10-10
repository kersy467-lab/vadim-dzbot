"""Add separately owned market funding, bonds, projects and merger records."""
async def migrate_next_game_recovery(conn):
    from backend.natbirzha.models.next_game_advance import NatNextGameMarketAdvance
    from backend.natbirzha.models.next_game_partnerships import NatNextGameSupplyDeal, NatNextGameJointProject
    from backend.natbirzha.models.next_game_bonds import NatNextGameBondSeries, NatNextGameBondHolding, NatNextGameBondListing
    from backend.natbirzha.models.next_game_progression import NatNextGameMerger
    for model in (NatNextGameMarketAdvance, NatNextGameSupplyDeal, NatNextGameJointProject,
                  NatNextGameBondSeries, NatNextGameBondHolding, NatNextGameBondListing, NatNextGameMerger):
        await conn.run_sync(lambda sync, table=model.__table__: table.create(sync, checkfirst=True))
