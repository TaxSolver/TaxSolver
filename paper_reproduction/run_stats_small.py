"""Computational statistics for the illustrative examples (Section 3 of the
paper): the recovery and reform solves of case_1a, case_1b, and case_2, plus a
dynamic-bracketing demonstration (dense candidate grid, capped number of
active brackets).

The model setups replicate the corresponding notebook cells verbatim; the only
addition is the solve-statistics bookkeeping. Results are written to
systems/computational_stats_small.csv.
"""

import os

import pandas as pd

import TaxSolver as tx
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.marginal_pressure_constraint import (
    MarginalPressureConstraint,
)
from TaxSolver.constraints.bracket_constraint import BracketConstraint
from TaxSolver.objective import BudgetObjective
from TaxSolver.backend import GurobiBackend

from solve_stats import collect_stats, write_stats

RECORDS = []


def quiet_backend():
    backend = GurobiBackend()
    backend.model.setParam("OutputFlag", 1)
    return backend


def finish(tax_solver, label, extra=None):
    RECORDS.append(collect_stats(tax_solver, label, extra))
    print(
        f"[{label}] done: {RECORDS[-1]['runtime_s']}s, "
        f"{RECORDS[-1]['num_vars']} vars, {RECORDS[-1]['num_constrs']} constrs"
    )
    tax_solver.close()


# ---------------------------------------------------------------------------
# Case 1a: single tax group, single bracket rule (outcome_1)
# ---------------------------------------------------------------------------
file_path = os.path.join("data", "simple_simul_1000.xlsx")
df_1 = pd.read_excel(file_path)
df_1["tax"] = df_1["income_before_tax"] - df_1["outcome_1"]
df_1["hh_id"] = df_1.index


def case_1a_recovery():
    dl = DataLoader(
        path=df_1, income_before_tax="income_before_tax", income_after_tax="outcome_1"
    )
    ts = tx.TaxSolver(dl.households, backend=quiet_backend())
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=[0, 25_000, 50_000, 75_000, 100_000, 150_000],
        group_vars=["k_everybody"],
    )
    income_tax = tx.BracketRule(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )
    ts.add_rules([income_tax])
    budget = BudgetConstraint("All_households", dl.households.values(), 1_000, 1_000)
    ts.add_constraints([IncomeConstraint(0.0000001, dl.households.values()), budget])
    ts.add_objective(BudgetObjective(budget))
    ts.solve()
    finish(ts, "case_1a_recovery")


def case_1a_reform():
    dl = DataLoader(
        path=df_1, income_before_tax="income_before_tax", income_after_tax="outcome_1"
    )
    ts = tx.TaxSolver(dl.households, backend=quiet_backend())
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=[0, 25_000, 50_000, 75_000, 100_000, 1_000_000],
        group_vars=["k_everybody"],
    )
    income_tax = tx.BracketRule(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )
    ts.add_rules([income_tax])
    low = [
        hh
        for hh in dl.households.values()
        if hh.members[0]["income_before_tax"] < 70_000
    ]
    budget = BudgetConstraint("All_households", dl.households.values(), 1_000)
    bracket_constraint = BracketConstraint(
        rule_family="income_before_tax_k_everybody",
        max_brackets=None,
        ascending=True,
        start_from_first_inflection=False,
        last_bracket_zero=False,
    )
    bracket_constraint.brackets = income_tax.flat_rules
    ts.add_constraints(
        [
            IncomeConstraint(0.10, dl.households.values()),
            IncomeConstraint(-0.05, low),
            budget,
            MarginalPressureConstraint(1.0),
            bracket_constraint,
        ]
    )
    ts.add_objective(BudgetObjective(budget))
    ts.solve()
    finish(ts, "case_1a_reform")


# ---------------------------------------------------------------------------
# Case 1b: single tax group, multiple rules (outcome_2)
# ---------------------------------------------------------------------------
df_2 = pd.read_excel(file_path)
df_2["tax"] = df_2["income_before_tax"] - df_2["outcome_2"]
df_2["hh_id"] = df_2.index
df_2.rename(columns={"tax_2_children": "sq_a_tax_2_children"}, inplace=True)
df_2["sq_m_tax_2_children"] = 0


def case_1b_recovery():
    dl = DataLoader(
        path=df_2, income_before_tax="income_before_tax", income_after_tax="outcome_2"
    )
    ts = tx.TaxSolver(dl.households, backend=quiet_backend())
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=[0, 25_000, 30_000, 40_000, 50_000, 75_000, 100_000, 150_000],
        group_vars=["k_everybody"],
    )
    income_tax = tx.BracketRule(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )
    child_benefit = tx.BenefitRule(name="child_benefit", var_name="i_children")
    universal_benefit = tx.BenefitRule(name="universal_benefit", var_name="k_everybody")
    ts.add_rules([income_tax, child_benefit, universal_benefit])
    budget = BudgetConstraint("All_households", dl.households.values(), 1_000, 1_000)
    ts.add_constraints([IncomeConstraint(0.0000001, dl.households.values()), budget])
    ts.add_objective(BudgetObjective(budget))
    ts.solve()
    finish(ts, "case_1b_recovery")


def case_1b_reform():
    dl = DataLoader(
        path=df_2, income_before_tax="income_before_tax", income_after_tax="outcome_2"
    )
    ts = tx.TaxSolver(dl.households, backend=quiet_backend())
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=[0, 25_000, 50_000, 75_000, 100_000, 1_000_000],
        group_vars=["k_everybody"],
    )
    income_tax = tx.BracketRule(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )
    existing_child_benefit = tx.ExistingBenefit(
        name="existing_child_benefit",
        var_name="tax_2_children",
        lb=1,
        ub=1,
        weight=10,
    )
    universal_benefit = tx.BenefitRule(name="universal_benefit", var_name="k_everybody")
    ts.add_rules([income_tax, existing_child_benefit, universal_benefit])
    low = [
        hh
        for hh in dl.households.values()
        if hh.members[0]["income_before_tax"] < 70_000
    ]
    budget = BudgetConstraint("All_households", dl.households.values(), 1_000_000)
    bracket_constraint = BracketConstraint(
        rule_family="income_before_tax_k_everybody",
        max_brackets=None,
        ascending=True,
        start_from_first_inflection=False,
        last_bracket_zero=False,
    )
    bracket_constraint.brackets = income_tax.flat_rules
    ts.add_constraints(
        [
            IncomeConstraint(0.10, dl.households.values()),
            IncomeConstraint(-0.05, low),
            budget,
            MarginalPressureConstraint(0.6),
            bracket_constraint,
        ]
    )
    ts.add_objective(BudgetObjective(budget))
    ts.solve()
    finish(ts, "case_1b_reform")


# ---------------------------------------------------------------------------
# Case 2: multiple tax groups, multiple rules (outcome_3)
# ---------------------------------------------------------------------------
df_3 = pd.read_excel(file_path)
df_3["tax"] = df_3["income_before_tax"] - df_3["outcome_3"]


def case_2_recovery():
    dl = DataLoader(
        path=df_3, income_before_tax="income_before_tax", income_after_tax="outcome_3"
    )
    ts = tx.TaxSolver(dl.households, backend=quiet_backend())
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=[0, 25_000, 50_000, 75_000, 100_000, 200_000],
        group_vars=["k_everybody"],
    )
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="household_income_before_tax",
        inflection_points=[30_000, 40_000],
        group_vars=["k_single"],
    )
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="household_income_before_tax",
        inflection_points=[60_000, 75_000],
        group_vars=["k_couple"],
    )
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=[0, 15_000],
        group_vars=["k_zzp"],
    )
    rules = [
        tx.BracketRule(
            name="income_before_tax_k_everybody",
            var_name="income_before_tax",
            k_group_var="k_everybody",
            ub=1,
            lb=0,
        ),
        tx.BracketRule(
            name="household_income_before_tax_k_single",
            var_name="household_income_before_tax",
            k_group_var="k_single",
            ub=0.8,
            lb=-0.5,
        ),
        tx.BracketRule(
            name="household_income_before_tax_k_couple",
            var_name="household_income_before_tax",
            k_group_var="k_couple",
            ub=0.8,
            lb=-0.5,
        ),
        tx.BracketRule(
            name="income_before_tax_k_zzp",
            var_name="income_before_tax",
            k_group_var="k_zzp",
            ub=0.8,
            lb=-0.5,
        ),
        tx.BenefitRule(name="benefit_children", var_name="i_children"),
        tx.BenefitRule(name="benefit_couple", var_name="k_couple"),
        tx.BenefitRule(name="benefit_single", var_name="k_single"),
    ]
    ts.add_rules(rules)
    budget = BudgetConstraint("All_households", dl.households.values(), 100_000_000_000)
    ts.add_constraints(
        [
            IncomeConstraint(0.00000001, dl.households.values()),
            budget,
            MarginalPressureConstraint(1.0),
        ]
    )
    ts.add_objective(BudgetObjective(budget))
    ts.solve()
    finish(ts, "case_2_recovery")


def case_2_reform():
    dl = DataLoader(
        path=df_3, income_before_tax="income_before_tax", income_after_tax="outcome_3"
    )
    ts = tx.TaxSolver(dl.households, backend=quiet_backend())
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=[0, 25_000, 50_000, 75_000, 100_000, 200_000],
        group_vars=["k_everybody"],
    )
    income_tax = tx.BracketRule(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )
    ts.add_rules(
        [
            income_tax,
            tx.BenefitRule(name="benefit_children", var_name="i_children"),
            tx.BenefitRule(name="benefit_everybody", var_name="k_everybody"),
        ]
    )
    low = [
        hh
        for hh in dl.households.values()
        if hh.members[0]["household_income_before_tax"] < 85_000
    ]
    budget = BudgetConstraint("All_households", dl.households.values(), 10_000_000_000)
    bracket_constraint = BracketConstraint(
        rule_family="income_before_tax_k_everybody",
        max_brackets=None,
        ascending=True,
        start_from_first_inflection=False,
        last_bracket_zero=False,
    )
    bracket_constraint.brackets = income_tax.flat_rules
    ts.add_constraints(
        [
            IncomeConstraint(0.10, dl.households.values()),
            IncomeConstraint(-0.05, low),
            budget,
            MarginalPressureConstraint(0.6),
            bracket_constraint,
        ]
    )
    ts.add_objective(BudgetObjective(budget))
    ts.solve()
    finish(ts, "case_2_reform")


# ---------------------------------------------------------------------------
# Dynamic bracketing: dense candidate grid, capped number of active brackets
# (the endogenous-cutoff MILP of the "Dynamic bracketing" extension)
# ---------------------------------------------------------------------------
def dynamic_bracketing_demo(max_brackets=5):
    dl = DataLoader(
        path=df_1, income_before_tax="income_before_tax", income_after_tax="outcome_1"
    )
    ts = tx.TaxSolver(dl.households, backend=quiet_backend())
    dense_grid = list(range(0, 150_001, 5_000)) + [1_000_000]
    BracketInput.add_split_variables_to_solver(
        tx=ts,
        target_var="income_before_tax",
        inflection_points=dense_grid,
        group_vars=["k_everybody"],
    )
    income_tax = tx.BracketRule(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )
    ts.add_rules([income_tax])
    low = [
        hh
        for hh in dl.households.values()
        if hh.members[0]["income_before_tax"] < 70_000
    ]
    budget = BudgetConstraint("All_households", dl.households.values(), 1_000)
    bracket_constraint = BracketConstraint(
        rule_family="income_before_tax_k_everybody",
        max_brackets=max_brackets,
        ascending=True,
        start_from_first_inflection=False,
        last_bracket_zero=False,
    )
    bracket_constraint.brackets = income_tax.flat_rules
    ts.add_constraints(
        [
            IncomeConstraint(0.10, dl.households.values()),
            IncomeConstraint(-0.05, low),
            budget,
            MarginalPressureConstraint(1.0),
            bracket_constraint,
        ]
    )
    ts.add_objective(BudgetObjective(budget))
    ts.solve()
    finish(
        ts,
        "dynamic_bracketing_demo",
        extra={"max_brackets": max_brackets, "candidate_brackets": len(dense_grid)},
    )


if __name__ == "__main__":
    case_1a_recovery()
    case_1a_reform()
    case_1b_recovery()
    case_1b_reform()
    case_2_recovery()
    case_2_reform()
    dynamic_bracketing_demo()
    write_stats(RECORDS, "systems/computational_stats_small.csv")
