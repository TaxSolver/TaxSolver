import os
import pandas as pd
import TaxSolver as tx
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.objective import BudgetObjective
import pytest


def test_readme_bracket_rule_optimization(backend):
    """Test readme: Bracket rule optimization with universal benefit and budget constraints."""

    # Load data
    file_path = os.path.join("data", "example", "simple_simul_1000.xlsx")

    # Verify the file exists
    assert os.path.exists(file_path), f"Test data file not found at {file_path}"

    df_taxpayers = pd.read_excel(file_path)
    df_taxpayers["tax"] = df_taxpayers["income_before_tax"] - df_taxpayers["outcome_2"]
    df_taxpayers["hh_id"] = df_taxpayers.index
    df_taxpayers.rename(columns={"tax_2_children": "sq_a_tax_2_children"}, inplace=True)
    df_taxpayers["sq_m_tax_2_children"] = 0

    dl = DataLoader(
        path=df_taxpayers,
        income_before_tax="income_before_tax",
        income_after_tax="outcome_2",
    )

    # Initialize the model
    tax_solver = tx.TaxSolver(dl.households, backend=backend)

    BracketInput.add_split_variables_to_solver(
        tx=tax_solver,
        target_var="income_before_tax",
        inflection_points=[0, 25_000, 30_000, 40_000, 50_000, 75_000, 100_000, 150_000],
        group_vars=["k_everybody"],
    )

    income_tax = tx.Brackets(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )

    child_benefit = tx.BenefitRule(
        name="child_benefit",
        var_name="i_children",
    )

    universal_benefit = tx.BenefitRule(
        name="universal_benefit",
        var_name="k_everybody",
    )

    tax_solver.add_rules([income_tax, child_benefit, universal_benefit])

    income_constraint = IncomeConstraint(0.0000001, dl.households.values())
    budget_constraint = BudgetConstraint(
        "All_households", dl.households.values(), 1_000, 1_000
    )

    tax_solver.add_constraints([income_constraint, budget_constraint])
    objective = BudgetObjective(budget_constraint)

    tax_solver.add_objective(objective)

    # Solve the system
    tax_solver.solve()

    # Get results and verify expected rates
    r_and_r = tax_solver.rules_and_rates_table()

    # Check that we have FlatTaxRule entries
    flat_tax_rules = r_and_r.loc[r_and_r["rule_type"] == "FlatTaxRule"]
    assert not flat_tax_rules.empty, "No FlatTaxRule entries found in results"

    # Check that we have BenefitRule entries
    benefit_tax_rules = r_and_r.loc[r_and_r["rule_type"] == "BenefitRule"]
    assert not benefit_tax_rules.empty, "No FlatTaxRule entries found in results"

    # Verify the expected rates
    expected_flat_rates = [0.1, 0.2, 0.35, 0.2, 0.3, 0.4, 0.5]
    actual_flat_rates = flat_tax_rules["rate"].tolist()

    for actual, expected in zip(actual_flat_rates, expected_flat_rates):
        assert actual == pytest.approx(expected, abs=0.01)

    # Verify the expected rates
    expected_benefit_rates = [800, 1_500]
    actual_benefit_rates = benefit_tax_rules["rate"].tolist()

    for actual, expected in zip(actual_benefit_rates, expected_benefit_rates):
        assert actual == pytest.approx(expected, abs=10)
