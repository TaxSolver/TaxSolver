from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.objective import ComplexityObjective
import TaxSolver as tx
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.backend.cvxpy_backend import CvxpyBackend


def test_progressive_marginal_rate(people_and_households):
    people, households = people_and_households

    backend = CvxpyBackend()
    tax_solver = tx.TaxSolver(
        households=households,
        backend=backend,
    )

    BracketInput.add_split_variables_to_solver(
        tax_solver,
        "income_before_tax",
        [0, 50, 100, 200, 1_000_000],
    )

    income_constraint = IncomeConstraint(0.0, [v for v in households.values()])

    budget_constraint = BudgetConstraint(
        "all_households", [v for v in households.values()], 0.1, 0.1
    )

    progressive_brackets = tx.Brackets(
        name="progressive_income_tax",
        var_name="income_before_tax",
        ub=1,
        lb=-1,
    )

    child_benefits = tx.HouseholdBenefit(
        name="child_benefits",
        var_name="kids",
        ub=100_000,
    )

    general_deducitible = tx.BenefitRule(
        name="algemene_heffingskorting",
        var_name="bool_algemene_heffingskorting",
        ub=100_000,
    )

    constraints = [
        income_constraint,
        budget_constraint,
    ]
    rules = [progressive_brackets, child_benefits, general_deducitible]

    tax_solver.add_objective(ComplexityObjective())
    tax_solver.add_constraints(constraints)
    tax_solver.add_rules(rules)

    tax_solver.solve()

    tax_solver.close()
