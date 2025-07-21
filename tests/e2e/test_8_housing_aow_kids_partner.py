from tests.helpers.scenario_helper import ScenarioHelper


def test_ipo_homeowner_renter_aow_kids_partner_all(backend):
    scenario = ScenarioHelper(
        data_path="tests/e2e/ipo_fixtures/df_housing_aow_kids_partner.xlsx",
        include_tags=["test"],
        exclude_tags=[],
        backend=backend,
    )

    scenario.solve()

    assert scenario.opt_sys.solved
    scenario.opt_sys.close()
