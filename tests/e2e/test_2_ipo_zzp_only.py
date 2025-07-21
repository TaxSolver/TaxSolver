from tests.helpers.scenario_helper import ScenarioHelper as scenario_test


def test_ipo_zzp_only_prog_brackets_all(backend):
    scenario = scenario_test(
        data_path="tests/e2e/ipo_fixtures/df_zzp_only_with_extreme_earners.xlsx",
        include_tags=["test"],
        exclude_tags=["enforce_progressive_tax"],
        backend=backend,
    )

    scenario.opt_sys.solve()

    assert scenario.opt_sys.solved
    scenario.opt_sys.close()
