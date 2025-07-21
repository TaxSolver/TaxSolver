import pytest
import TaxSolver as tx
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.rule_constraints import ForceRateConstraint
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.constraints.labor_effects import LaborEffects
from TaxSolver.objective import BudgetObjective
from TaxSolver.tax_solver import TaxSolver
from TaxSolver.backend import GurobiBackend


def _setup_opt_sys(data_loader: DataLoader, gurobi_env):
    """Helper to create TaxSolver with new API and income/budget constraints."""
    households = data_loader.households

    backend = GurobiBackend(env=gurobi_env)
    tax_solver = TaxSolver(households, backend=backend)

    income_constraint = IncomeConstraint(0.0, list(households.values()))
    budget_constraint = BudgetConstraint(
        "all_households", list(households.values()), 10_000_000_000
    )
    labor_effects = LaborEffects()
    tax_solver.add_constraints([income_constraint, budget_constraint, labor_effects])

    income_tax = tx.FlatTaxRule(
        name="income_tax",
        var_name="income_before_tax",
        ub=1,
        lb=0,
    )
    tax_solver.add_rules([income_tax])

    tax_solver.add_objective(BudgetObjective(budget_constraint))

    tax_solver.add_constraints(
        [ForceRateConstraint(rule_names=["income_tax"], rate=0.25)]
    )

    return tax_solver, budget_constraint, labor_effects


@pytest.mark.gurobi
def test_solve_with_labor_effects(gurobi_env):
    data = DataLoader(
        "tests/labor_effects/labor_effects_hh_test.xlsx",
        income_before_tax="income_before_tax",
        income_after_tax="income_after_tax",
        weight="weight",
        id="id",
        hh_id="hh_id",
        mirror_id="mirror_id",
        input_vars=[
            "number_of_kids_0_5",
            "number_of_kids_6_11",
            "number_of_kids_12_15",
            "number_of_kids_16_17",
            "number_of_kids",
            "monthly_rent",
            "assets",
            "partner_income",
            "other_income",
            "woz",
            "mortgage_interest",
        ],
        group_vars=["fiscal_partner", "partner_type_of_income"],
    )

    # Build solver with modern API
    opt_sys, budget_constraint, labor_effects = _setup_opt_sys(data, gurobi_env)

    opt_sys.solve()

    assert opt_sys.solved

    assert (
        opt_sys.backend.get_value(budget_constraint.spend) == 20_000 * 200 * 0.25
    )  # income_before_tax times weights times lower tax rate

    assert opt_sys.backend.get_value(
        opt_sys.households["vhh_1"].first_member.new_net_income
    ) == 20_000 * (1 - 0.25)
    assert opt_sys.backend.get_value(
        opt_sys.households["mirror_vhh_1"].first_member.new_net_income
    ) == 40_000 * (1 - 0.25)

    assert opt_sys.households["vhh_1"].first_member.old_income_increase_factor == 1.25
    assert (
        opt_sys.backend.get_value(
            opt_sys.households["vhh_1"].first_member.new_income_increase_factor
        )
        == 1.6
    )

    assert (
        opt_sys.backend.get_value(
            opt_sys.households["vhh_1"].first_member.change_in_income_increase_factor
        )
        == 0.35
    )

    assert (
        pytest.approx(
            opt_sys.backend.get_value(
                opt_sys.households["vhh_1"].first_member.new_labor_effects_weight
            )
        )
        == 0.825
    )
    assert (
        pytest.approx(
            opt_sys.backend.get_value(
                opt_sys.households["mirror_vhh_1"].first_member.new_labor_effects_weight
            )
        )
        == 0.175
    )

    assert (
        pytest.approx(
            opt_sys.backend.get_value(
                opt_sys.households["vhh_1"].first_member.new_labor_effects_weight
            )
            + opt_sys.backend.get_value(
                opt_sys.households["mirror_vhh_1"].first_member.new_labor_effects_weight
            )
        )
        == 1
    )

    assert opt_sys.backend.get_value(labor_effects.new_wage_output) == 48750


@pytest.mark.gurobi
def test_solve_with_labor_effects_household_mix(gurobi_env):
    data = DataLoader("tests/labor_effects/labor_effects_incl_irrelevant_hh.xlsx")

    # Build solver with modern API
    opt_sys, budget_constraint, labor_effects = _setup_opt_sys(data, gurobi_env)

    opt_sys.solve()

    assert opt_sys.solved

    assert (
        opt_sys.backend.get_value(budget_constraint.spend)
        == 20_000 * 200 * 0.25 + 100_000 * 100 * 0.25
    )
    assert labor_effects.sq_wage_output == 40_000
    assert opt_sys.backend.get_value(labor_effects.new_wage_output) == 48750
