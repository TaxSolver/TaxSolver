from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.tax_solver import TaxSolver
from TaxSolver.population.person import Person
from TaxSolver.objective import ComplexityObjective
from TaxSolver.backend import CvxpyBackend
from TaxSolver.backend import GurobiBackend
import TaxSolver as tx
import pytest


def test_alpha_k_b(people_and_households, gurobi_env):
    people, households = people_and_households

    backend = GurobiBackend(env=gurobi_env)
    tax_solver = TaxSolver(
        households,
        backend=backend,
    )

    BracketInput.add_split_variables_to_solver(
        tx=tax_solver,
        target_var="income_before_tax",
        inflection_points=[0, 50, 100, 200, 1_000_000],
        group_vars=["k_everybody"],
    )

    BracketInput.add_split_variables_to_solver(
        tx=tax_solver,
        target_var="income_before_tax",
        inflection_points=[0, 50, 100, 200, 1_000_000],
        group_vars=["k_test1"],
    )

    BracketInput.add_split_variables_to_solver(
        tx=tax_solver,
        target_var="income_before_tax",
        inflection_points=[0, 50, 100, 200, 1_000_000],
        group_vars=["k_test2"],
    )

    universal_brackets = tx.Brackets(
        name="universal_income_brackets",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=-1,
    )

    ktest1_brackets = tx.Brackets(
        name="ktest1_income_brackets",
        var_name="income_before_tax",
        k_group_var="k_test1",
        ub=1,
        lb=-1,
    )

    ktest2_brackets = tx.Brackets(
        name="ktest2_income_brackets",
        var_name="income_before_tax",
        k_group_var="k_test2",
        ub=1,
        lb=-1,
    )

    income_constraint = IncomeConstraint(0.01, [v for v in households.values()])

    budget_constraint = BudgetConstraint(
        "all_households", [v for v in households.values()], 0, 0
    )

    child_benefit = tx.HouseholdBenefit(
        name="child_benefits", var_name="kids", ub=100_000
    )

    constraints = [
        income_constraint,
        budget_constraint,
    ]

    tax_solver.add_objective(ComplexityObjective())
    tax_solver.add_constraints(constraints)
    tax_solver.add_rules(
        [universal_brackets, ktest1_brackets, ktest2_brackets, child_benefit]
    )

    tax_solver.solve()

    assert len(tax_solver.rules) == 13

    for p in people.values():
        p: Person
        if p["k_test1"] == 0 and p["k_test2"] == 0:
            assert p.new_marginal_rate.size() == 1
        if p["k_test1"] == 1 and p["k_test2"] == 0:
            assert p.new_marginal_rate.size() == 2
        if p["k_test1"] == 1 and p["k_test2"] == 1:
            assert p.new_marginal_rate.size() == 3

    tax_solver.close()


def test_zeta_k(people_and_households):
    people, households = people_and_households

    backend = CvxpyBackend()
    tax_solver = TaxSolver(households, backend=backend)

    income_constraint = IncomeConstraint(0.00, [v for v in households.values()])
    budget_constraint = BudgetConstraint(
        "all_households", [v for v in households.values()], 0, 0
    )

    rules = []
    for var in ["k_test1", "k_test2"]:
        rules.append(
            tx.BenefitRule(
                name=f"conditional_benefit_{var}",
                var_name=[var],
                ub=10_000,
            )
        )

    tax_solver.add_objective(ComplexityObjective())
    tax_solver.add_constraints([income_constraint, budget_constraint])
    tax_solver.add_rules(rules)

    assert len(tax_solver.rules) == 2
    tax_solver.close()
