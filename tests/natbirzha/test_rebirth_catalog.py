from backend.natbirzha.catalogs.businesses import INDUSTRIES, visible_business_specs, validate_business_catalog


def test_every_industry_has_ten_rebirth_factories_and_reachable_level_gates():
    specs = visible_business_specs()
    assert all(spec['company_level_required'] <= 60 for spec in specs)
    for industry in INDUSTRIES:
        branches = [s for s in specs if s['specialization']==industry and s.get('rebirth_required',0)]
        assert len(branches)==10
        assert sorted(s['rebirth_required'] for s in branches)==list(range(1,11))
        assert len({s['name'] for s in branches})==10
    assert validate_business_catalog()
