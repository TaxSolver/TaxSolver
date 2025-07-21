import TaxSolver as tx
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.objective import BudgetObjective
import pytest


@pytest.mark.skip
def test_e2e_basic_small(gurobi_env):
    household_tax_data = DataLoader(
        "tests/minimal_example/minimal_set.csv",
        input_vars=["kids"],
        group_vars=["work"],
    ).households

    # this step initializes the model and creates bookkeeping variables
    opt_sys = tx.TaxSolver(household_tax_data, env=gurobi_env)

    # this step creates the tax rules
    income_tax = tx.FlatTaxRule(
        name="income_tax",
        var_name="income_before_tax",
        ub=1,
        lb=0,
    )

    child_benefits = tx.BenefitRule(
        name="child_benefits",
        var_name="i_kids",
        ub=10_000,
    )

    general_deducitible = tx.BenefitRule(
        name="general_deductible",
        var_name="k_work_1",
        ub=10_000,
    )

    # this step adds the rules to the model
    opt_sys.add_rules([income_tax, child_benefits, general_deducitible])

    income_constraint = IncomeConstraint(0.00, household_tax_data.values())
    budget_constraint = BudgetConstraint(
        "total_budget_constraint", household_tax_data.values(), 0, 0
    )

    opt_sys.add_constraints([income_constraint, budget_constraint])

    opt_sys.add_objective(BudgetObjective(budget_constraint))

    opt_sys.solve()
