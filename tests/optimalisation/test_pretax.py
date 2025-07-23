import pytest
from TaxSolver.objective import NullObjective
from TaxSolver.tax_solver import TaxSolver
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.rule import (
    PreTaxBenefit,
    FlatTaxRule,
)
from TaxSolver.constraints.rule_constraints import ForceRateConstraint
from TaxSolver.population.person import Person
from TaxSolver.population.household import Household
from TaxSolver.backend import GurobiBackend


@pytest.fixture
def simple_person():
    person_data = {
        "id": "p_1",
        "hh_id": "hh_1",
        "weight": 100,
        "income_before_tax": 50000,
        "income_after_tax": 50000,
        "k_everybody": 1,
    }
    person = Person(person_data)
    return person


@pytest.fixture
def simple_household(simple_person):
    hh = Household(id="hh_1", members=[simple_person])
    return hh


@pytest.fixture
def tax_solver(simple_household):
    households = {"hh_1": simple_household}
    backend = GurobiBackend()
    solver = TaxSolver(households, backend=backend)
    solver.add_objective(NullObjective())
    return solver


def test_pre_tax_rule_with_budget_constraint(tax_solver):
    """Test that a PreTaxBenefit is optimized with a budget constraint."""
    tax_rule = FlatTaxRule(
        name="income_tax",
        var_name="income_before_tax",
        ub=1,
        lb=0,
        marginal_pressure=True,
    )

    pre_tax_benefit = PreTaxBenefit(
        name="test_pre_tax_benefit",
        var_name="k_everybody",
        ub=100_000,
        lb=0,
    )

    tax_solver.add_rules([tax_rule, pre_tax_benefit])

    budget_constraint = BudgetConstraint(
                max_bln_mut_expenditure=0, 
                min_bln_mut_expenditure=0, 
                name="budget_constraint",
                households=tax_solver.households.values(),
            )

    # Budget constraint: net government revenue should be 0
    tax_solver.add_constraints(
        [
            ForceRateConstraint(
                ['income_tax'],
                rate=0.4,
            ),
            budget_constraint,
        ]
    )

    tax_solver.solve()

    person = tax_solver.households["hh_1"].members[0]

    # With a 40% tax rate on an income of 50,000, the tax is 20,000.
    # To be budget neutral, the pre-tax benefit must offset this.
    # The value of the benefit is rate * (1 - marginal_tax_rate)
    # So, rate * (1 - 0.4) = 20,000
    # rate * 0.6 = 20,000
    # rate = 20,000 / 0.6 = 33333.33...

    print(tax_solver.backend.get_value(pre_tax_benefit.rate))
    print(tax_solver.backend.get_value(budget_constraint.new_expenditures))
    print(tax_solver.backend.get_value(budget_constraint.current_expenditures))

    # Total tax should be zero, so net income equals gross income
    assert tax_solver.backend.get_value(person.new_net_income) == pytest.approx(50000)

    # The rate of the pre_tax_benefit should be optimized to balance the budget.
    assert tax_solver.backend.get_value(pre_tax_benefit.rate) == pytest.approx(
        20000 / 0.6, abs=1
    )

    
