import pytest
import TaxSolver as tx
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.data_wrangling.bracket_input import BracketInput
from tests.helpers.solved_system.solved_system import SolvedSystem
from TaxSolver.constraints.marginal_pressure_constraint import (
    MarginalPressureConstraint,
)
from TaxSolver.objective import (
    BudgetObjective,
    ComplexityObjective,
)
from TaxSolver.backend import CvxpyBackend


def test_e2e_basic_small(people_and_households):
    people, households = people_and_households

    tax_solver = tx.TaxSolver(households)

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

    backend = tax_solver.backend

    # Print the solution
    assert tax_solver.solved
    assert backend.get_value(tax_solver.rules[0].rate) == pytest.approx(0.1)
    assert backend.get_value(
        marginal_pressure_constraint.highest_marginal_pressure
    ) == pytest.approx(0.1)
    assert backend.get_value(tax_solver.rules[1].rate) == pytest.approx(20)
    assert backend.get_value(budget_constraint.new_expenditures) == pytest.approx(
        budget_constraint.current_expenditures
    )

    solved_system = SolvedSystem.from_solved_system(tax_solver)

    solver_new_expenditures = backend.get_value(budget_constraint.new_expenditures)
    tax_system_new_expenditures = sum(solved_system.rule_outcomes["weighted_amount"])
    assert solver_new_expenditures == pytest.approx(tax_system_new_expenditures)

    net_incomes = solved_system.calculate_net_incomes()

    solver_net_income = backend.get_value(
        tax_solver.households["hh_0"].new_net_household_income
    )
    tax_system_net_income = net_incomes[net_incomes["hh_id"] == "hh_0"][
        "new_net_income"
    ].values[0]

    assert pytest.approx(solver_net_income) == pytest.approx(tax_system_net_income)

    marginal_pressure = solved_system.calculate_marginal_pressure()
    assert marginal_pressure.loc["0"]["new_marginal_pressure"] == pytest.approx(0.1)

    tax_solver.close()


def test_e2e_basic_budget(people_and_households, gurobi_env):
    people, households = people_and_households

    backend = CvxpyBackend()
    tax_solver = tx.TaxSolver(households, backend=backend)

    income_constraint = IncomeConstraint(0.00, [v for v in households.values()])
    budget_constraint = BudgetConstraint(
        "all_households", [v for v in households.values()], 0, 0
    )

    tax_solver.add_constraints([income_constraint, budget_constraint])

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


def test_e2e_basic_small_progressive(people_and_households):
    people, households = people_and_households

    backend = CvxpyBackend()
    tax_solver = tx.TaxSolver(households, backend=backend)

    income_constraint = IncomeConstraint(0.00001, [v for v in households.values()])
    budget_constraint = BudgetConstraint(
        "all_households", [v for v in households.values()], 0, 0
    )

    BracketInput.add_split_variables_to_solver(
        tx=tax_solver,
        target_var="income_before_tax",
        inflection_points=[0, 50, 100, 200, 10000000],
        group_vars=["k_everybody"],
    )

    brackets = tx.BracketRule(
        name="income_brackets",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=-1,
    )

    child_benefits = tx.HouseholdBenefit(
        name="child_benefits",
        var_name="kids",
        ub=10_000,
    )

    general_deducitible = tx.BenefitRule(
        name="algemene_heffingskorting",
        var_name="bool_algemene_heffingskorting",
        ub=10_000,
    )

    tax_solver.add_constraints([income_constraint, budget_constraint])
    tax_solver.add_rules([brackets, child_benefits, general_deducitible])
    tax_solver.add_objective(ComplexityObjective())

    tax_solver.solve()

    # Print the solution
    assert tax_solver.solved
    assert pytest.approx(backend.get_value(tax_solver.rules[1].rate), abs=1e-3) == 0.1
    assert pytest.approx(backend.get_value(tax_solver.rules[4].rate), abs=1e-1) == 20
    assert (
        pytest.approx(
            backend.get_value(budget_constraint.new_expenditures),
            abs=1,
        )
        == budget_constraint.current_expenditures
    )

    tax_solver.close()


def test_e2e_basic_weighted(people_and_households, gurobi_env):
    people, households = people_and_households

    households["hh_0"].weight = 2
    people["0"].data["weight"] = 2

    backend = CvxpyBackend()
    tax_solver = tx.TaxSolver(households=households, backend=backend)

    income_constraint = IncomeConstraint(0.00, [v for v in households.values()])
    budget_constraint = BudgetConstraint(
        "all_households", [v for v in households.values()], 0, 0
    )

    tax_solver.add_constraints([income_constraint, budget_constraint])

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

    tax_solver.add_objective(ComplexityObjective())

    tax_solver.solve()

    unweighted_tax = backend.get_value(tax_solver.households["hh_0"].household_benefits)

    weighted_tax = backend.get_value(
        tax_solver.households["hh_0"].weighted_household_benefits
    )

    person_unweighted_tax = backend.get_value(tax_solver.people["0"].tax_balance)

    person_weighted_tax = backend.get_value(tax_solver.people["0"].weighted_tax_balance)

    # Print the solution
    assert tax_solver.solved
    assert pytest.approx(backend.get_value(tax_solver.rules[0].rate)) == 0.1
    assert pytest.approx(backend.get_value(tax_solver.rules[1].rate)) == 20
    assert (
        pytest.approx(backend.get_value(budget_constraint.new_expenditures))
        == budget_constraint.current_expenditures
    )
    assert pytest.approx(unweighted_tax * 2) == weighted_tax
    assert pytest.approx(person_unweighted_tax * 2, 1) == person_weighted_tax

    tax_solver.close()
