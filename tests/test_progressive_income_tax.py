from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.population.person import Person
from TaxSolver.objective import ComplexityObjective
import TaxSolver as tx
from TaxSolver.data_wrangling.bracket_input import BracketInput
import pytest


def test_progressive_tax_rules_factory(people_and_households):
    people, households = people_and_households

    tax_solver = tx.TaxSolver(
        households=households,
    )

    BracketInput.add_split_variables_to_solver(
        tax_solver,
        "income_before_tax",
        [0, 50, 100, 200],
    )

    income_constraint = IncomeConstraint(0.00, [v for v in households.values()])

    budget_constraint = BudgetConstraint(
        "all_households", [v for v in households.values()], 0, 0
    )

    universal_brackets = tx.Brackets(
        name="progressive_income_tax",
        var_name="income_before_tax",
        ub=1,
        lb=0,
    )

    tax_solver.add_objective(ComplexityObjective())
    tax_solver.add_rules([universal_brackets])
    tax_solver.add_constraints(
        [
            income_constraint,
            budget_constraint,
        ]
    )

    # Verify the households
    assert len(tax_solver.rules) == 3
    assert (
        tax_solver.rules[0].name
        == "progressive_income_tax__income_before_tax_k_everybody_0_50"
    )
    assert tax_solver.rules[1].rule_considered_inactive_at == tax_solver.rules[0]

    # Verify the people
    p: Person = people["0"]
    assert p[tax_solver.rules[0].var_name[0]] == 50
    assert p[tax_solver.rules[1].var_name[0]] == 50
    assert pytest.approx(p[tax_solver.rules[2].var_name[0]], abs=0.01) == 0.01
    tax_solver.close()
