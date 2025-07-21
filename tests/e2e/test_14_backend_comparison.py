import pytest
from tests.helpers.scenario_helper import ScenarioHelper
from TaxSolver.backend import GurobiBackend, CvxpyBackend
from tests.helpers.solved_system.solved_system import SolvedSystem
import pandas as pd
import TaxSolver as tx
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.marginal_pressure_constraint import (
    MarginalPressureConstraint,
)
from TaxSolver.objective import (
    BudgetObjective,
)


@pytest.mark.gurobi
def test_backend_results_are_consistent(gurobi_env):
    """
    Runs the same scenario with Gurobi and CVXPY backends and compares key results.
    """
    # Define common scenario parameters
    scenario_params = {
        "data_path": "tests/e2e/ipo_fixtures/df_employment_only_with_extreme_earners.xlsx",
        "include_tags": ["test", "sq"],
        "exclude_tags": [],
    }

    # --- Run with Gurobi ---
    gurobi_backend = GurobiBackend(env=gurobi_env)
    scenario_gurobi = ScenarioHelper(backend=gurobi_backend, **scenario_params)
    scenario_gurobi.solve()
    assert scenario_gurobi.opt_sys.solved
    gurobi_budget = scenario_gurobi.opt_sys.backend.get_value(
        scenario_gurobi.budget_constraint.new_expenditures
    )
    gurobi_net_incomes = SolvedSystem.from_solved_system(
        scenario_gurobi.opt_sys
    ).calculate_net_incomes()

    # --- Run with CVXPY ---
    cvxpy_backend = CvxpyBackend()
    scenario_cvxpy = ScenarioHelper(backend=cvxpy_backend, **scenario_params)
    scenario_cvxpy.solve()
    assert scenario_cvxpy.opt_sys.solved
    cvxpy_budget = scenario_cvxpy.opt_sys.backend.get_value(
        scenario_cvxpy.budget_constraint.new_expenditures
    )
    cvxpy_net_incomes = SolvedSystem.from_solved_system(
        scenario_cvxpy.opt_sys
    ).calculate_net_incomes()

    # Compare the total budget
    assert gurobi_budget == pytest.approx(cvxpy_budget, abs=1)

    # Compare the new net incomes
    pd.testing.assert_series_equal(
        gurobi_net_incomes["new_net_income"].sort_index(),
        cvxpy_net_incomes["new_net_income"].sort_index(),
        check_exact=False,
        atol=10,
    )


@pytest.mark.gurobi
def test_backend_rule_rates_are_consistent_basic_small(
    people_and_households, gurobi_env
):
    """
    Replicates the first test of tests/test_basic_small.py and checks whether the rule rates are the same
    for Gurobi and CVXPY backends.
    """
    # --- Common setup from test_e2e_basic_small ---
    people, households = people_and_households

    def setup_and_solve(backend):
        tax_solver = tx.TaxSolver(households, backend=backend)

        income_constraint = IncomeConstraint(0.00, [v for v in households.values()])
        budget_constraint = BudgetConstraint(
            "all_households", [v for v in households.values()], 0, 0
        )
        marginal_pressure_constraint = MarginalPressureConstraint(1)

        tax_solver.add_constraints(
            [income_constraint, budget_constraint, marginal_pressure_constraint]
        )

        income_tax = tx.FlatTaxRule(
            name="income_tax",
            var_name="income_before_tax",
            ub=1,
            lb=0,
            marginal_pressure=True,
        )

        child_benefits = tx.BenefitRule(
            name="child_benefits",
            var_name="kids",
            ub=10_000,
        )

        general_deducitible = tx.BenefitRule(
            name="algemene_heffingskorting",
            var_name="bool_algemene_heffingskorting",
            ub=10_000,
        )

        tax_solver.add_rules([income_tax, child_benefits, general_deducitible])

        tax_solver.add_objective(BudgetObjective(budget_constraint))

        tax_solver.solve()
        assert tax_solver.solved

        rates = {
            rule.name: tax_solver.backend.get_value(rule.rate)
            for rule in tax_solver.rules
        }
        tax_solver.close()
        return rates

    # --- Run with Gurobi ---
    gurobi_backend = GurobiBackend(env=gurobi_env)
    gurobi_rates = setup_and_solve(gurobi_backend)

    # --- Run with CVXPY ---
    cvxpy_backend = CvxpyBackend()
    cvxpy_rates = setup_and_solve(cvxpy_backend)

    # Compare the rule rates
    assert gurobi_rates.keys() == cvxpy_rates.keys()
    for rule_name in gurobi_rates:
        assert gurobi_rates[rule_name] == pytest.approx(cvxpy_rates[rule_name])
