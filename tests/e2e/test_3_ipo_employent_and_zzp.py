from tests.helpers.scenario_helper import ScenarioHelper


def test_ipo_employment_and_zzp_prog_brackets_all(backend):
    scenario = ScenarioHelper(
        data_path="tests/e2e/ipo_fixtures/df_employment_and_zzp.xlsx",
        include_tags=["test"],
        exclude_tags=["enforce_progressive_tax", "enforce_kot"],
        backend=backend,
    )
    scenario.solve()

    assert scenario.opt_sys.solved
    scenario.opt_sys.close()
