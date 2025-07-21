from tests.helpers.scenario_helper import ScenarioHelper


def test_ipo_rent_all(backend):
    scenario = ScenarioHelper(
        data_path="tests/e2e/ipo_fixtures/df_rent.xlsx",
        include_tags=["test", "sq", "rent"],
        exclude_tags=["enforce_progressive_tax"],
        backend=backend,
    )

    scenario.solve()

    assert scenario.opt_sys.solved
    scenario.opt_sys.close()
