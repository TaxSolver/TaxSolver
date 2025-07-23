import pytest
import TaxSolver as tx
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.marginal_pressure_constraint import MarginalPressureConstraint
from TaxSolver.objective import BudgetObjective, WeightedMixedObjective
from TaxSolver.tax_solver import TaxSolver
from TaxSolver.brackets import Brackets
from TaxSolver.backend import CvxpyBackend
from TaxSolver.data_wrangling.bracket_input import BracketInput

@pytest.fixture
def tax_solver(data_loader):
    backend = CvxpyBackend()
    solver = TaxSolver(data_loader.households, backend=backend)

    # Use BracketInput to create bracket variables
    BracketInput.add_split_variables_to_solver(
        tx=solver,
        target_var='income_before_tax',
        inflection_points=[0, 20_000, 40_000, 60_000, 80_000, 1_000_000],
        group_vars=['k_everybody']
    )
    return solver


@pytest.fixture
def tax_solver_with_rules(tax_solver):
    universal_benefit = tx.BenefitRule(
        name="universal_benefit",
        var_name="k_everybody",
        ub=10_000,
    )

    budget_constraint = BudgetConstraint(
            "all_households",
            list(tax_solver.households.values()),
            max_bln_mut_expenditure=10_000_000,
            min_bln_mut_expenditure=0,
        )

    income_constraint = IncomeConstraint(
            0.05,
            list(tax_solver.households.values()),
        )

    tax_solver.add_rules([universal_benefit])
    tax_solver.add_constraints([budget_constraint, income_constraint])
    tax_solver.add_objective(BudgetObjective(budget_constraint))
    return tax_solver


def test_max_brackets_constraint_2(tax_solver_with_rules):
    """Test that the max_brackets constraint limits the number of active brackets."""
    bracket_rule = Brackets(
        name='income_tax',
        var_name='income_before_tax',
        k_group_var='k_everybody',
        max_brackets=2,
        ub=1,
        lb=0,
    )

    tax_solver_with_rules.add_rules([bracket_rule])
    tax_solver_with_rules.solve()

    active_brackets = sum(
        1
        for rule in bracket_rule.flat_rules
        if tax_solver_with_rules.backend.get_value(rule.b) > 0.99
    )
    assert active_brackets == 2

def test_max_brackets_constraint_3(tax_solver_with_rules):
    """Test that the max_brackets constraint limits the number of active brackets."""
    bracket_rule = Brackets(
        name='income_tax',
        var_name='income_before_tax',
        k_group_var='k_everybody',
        max_brackets=3,
        ub=1,
        lb=0,
    )

    tax_solver_with_rules.add_rules([bracket_rule])
    tax_solver_with_rules.solve()

    active_brackets = sum(
        1
        for rule in bracket_rule.flat_rules
        if tax_solver_with_rules.backend.get_value(rule.b) > 0.99
    )
    assert active_brackets == 3

def test_ascending_brackets_constraint(tax_solver_with_rules):
    """Test that the ascending=True constraint forces bracket rates to be ascending."""
    bracket_rule = Brackets(
        name='income_tax',
        var_name='income_before_tax',
        k_group_var='k_everybody',
        max_brackets=3,
        ascending=True,
        ub=1,
        lb=0,
    )

    tax_solver_with_rules.add_rules([bracket_rule])
    tax_solver_with_rules.solve()

    rates = [tax_solver_with_rules.backend.get_value(rule.rate) for rule in bracket_rule.flat_rules]
    # All rates should be at the upper bound to maximize revenue
    for rate in rates:
        assert rate < 1
    
    for i in range(len(rates) - 1):
        assert rates[i] <= rates[i+1] + 1e-6  # Add tolerance for float comparison

    assert rates[-1] > 0


def test_last_bracket_zero(tax_solver_with_rules):
    """Test that the ascending=True constraint forces bracket rates to be ascending."""
    bracket_rule = Brackets(
        name='income_tax',
        var_name='income_before_tax',
        k_group_var='k_everybody',
        last_bracket_zero=True,
        ub=10,
        lb=-10,
    )

    tax_solver_with_rules.add_rules([bracket_rule])
    tax_solver_with_rules.solve()

    rates = [tax_solver_with_rules.backend.get_value(rule.rate) for rule in bracket_rule.flat_rules]
    # All rates should be at the upper bound to maximize revenue
    for rate in rates:
        assert rate < 1
    
    assert rates[-1] == 0


