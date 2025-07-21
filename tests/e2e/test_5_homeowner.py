from tests.helpers.scenario_helper import ScenarioHelper


def test_ipo_homeowner_all(backend):
    scenario = ScenarioHelper(
        data_path="tests/e2e/ipo_fixtures/df_homeowner.xlsx",
        include_tags=["test", "basis"],
        exclude_tags=["enforce_progressive_tax", "enforce_kot"],
        backend=backend,
    )

    scenario.solve()

    assert scenario.opt_sys.solved
    scenario.opt_sys.close()
