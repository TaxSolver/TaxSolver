import pytest
from tests.helpers.scenario_helper import ScenarioHelper
from tests.helpers.solved_system.solved_system import SolvedSystem


def test_ipo_employment_only_prog_brackets_all1(backend):
    scenario = ScenarioHelper(
        data_path="tests/e2e/ipo_fixtures/df_employment_only_with_extreme_earners.xlsx",
        include_tags=["test"],
        exclude_tags=["enforce_progressive_tax"],
        overall_income_constraint=0.01,
        backend=backend,
    )

    scenario.solve()

    assert scenario.opt_sys.solved

    solved_system = SolvedSystem.from_solved_system(scenario.opt_sys)
    solver_new_expenditures = scenario.opt_sys.backend.get_value(
        scenario.budget_constraint.new_expenditures
    )
    tax_system_new_expenditures = sum(solved_system.rule_outcomes["weighted_amount"])
    assert solver_new_expenditures == pytest.approx(tax_system_new_expenditures)

    net_incomes = solved_system.calculate_net_incomes()
    solver_net_income = scenario.opt_sys.backend.get_value(
        scenario.opt_sys.households["0"].new_net_household_income
    )
    tax_system_net_income = net_incomes[net_incomes["hh_id"] == "0"][
        "new_net_income"
    ].values[0]

    assert solver_net_income == pytest.approx(tax_system_net_income)
    scenario.opt_sys.close()
