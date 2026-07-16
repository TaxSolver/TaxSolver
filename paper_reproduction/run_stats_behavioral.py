"""Computational statistics for the behavioral-responses comparison
(Section 3.6 / Appendix): the direct nonconvex MIQP solve versus the
LP-only fixed-point scheme of Algorithm 1, on the elasticity grid of the
paper (delta in [0, 0.25]).

Model setups replicate fig08_behavioral_effects.ipynb verbatim; the only addition is the
solve-statistics bookkeeping. Results:
- systems/computational_stats_behavioral.csv: one row per Gurobi solve
  (one minimize-revenue-loss solve per delta for the direct solve;
  per-iteration LP solves of Algorithm 1 are aggregated).
"""

import os

import numpy as np
import pandas as pd

from case_helpers import (
    tx,
    DataLoader,
    BracketInput,
    BudgetConstraint,
    IncomeConstraint,
    MarginalPressureConstraint,
    BracketConstraint,
    BudgetObjective,
    GurobiBackend,
    get_sq_marginal_rate_case1,
)

from solve_stats import collect_stats, write_stats, Timer

# --- Data and status-quo quantities (identical to fig08_behavioral_effects.ipynb) -------------
file_path = os.path.join("data", "simple_simul_1000.xlsx")
df_taxpayers = pd.read_excel(file_path)

X_ORIG = df_taxpayers["income_before_tax"].to_numpy(float)
Y_SQ = (df_taxpayers["income_before_tax"] - df_taxpayers["outcome_1"]).to_numpy(float)
NET_SQ = X_ORIG - Y_SQ

df_taxpayers["marginal_rate_current"] = df_taxpayers["income_before_tax"].apply(
    get_sq_marginal_rate_case1
)
TAU_SQ = df_taxpayers["marginal_rate_current"].to_numpy(float)

INFLECTION_POINTS = [0, 25_000, 50_000, 75_000, 100_000, 1_000_000]
BRACKET_IDX = np.clip(np.searchsorted(INFLECTION_POINTS, X_ORIG, side="left") - 1, 0, 4)
LOW_INCOME = X_ORIG < 70_000

# No budget bound: the loose cap below is non-binding and only keeps the spend
# variable that defines the revenue-loss objective.
NON_BINDING_CAP = 1_000_000_000

RECORDS = []


def solve_reform(
    delta, x_incomes=None, behavioral=True, stats_label=None, stats_extra=None
):
    if x_incomes is None:
        x_incomes = X_ORIG

    df = pd.DataFrame(
        {
            "income_before_tax": x_incomes,
            "income_after_tax": NET_SQ,
            "marginal_rate_current": TAU_SQ,
        }
    )
    dl = DataLoader(
        path=df,
        income_before_tax="income_before_tax",
        income_after_tax="income_after_tax",
    )

    backend = GurobiBackend()
    backend.model.setParam("OutputFlag", 0)
    solver = tx.TaxSolver(
        dl.households,
        backend=backend,
        behavioral_effects=(behavioral and delta > 0),
        behavioral_elasticity=delta if (behavioral and delta > 0) else None,
    )

    BracketInput.add_split_variables_to_solver(
        tx=solver,
        target_var="income_before_tax",
        inflection_points=INFLECTION_POINTS,
        group_vars=["k_everybody"],
    )
    income_tax = tx.BracketRule(
        name="income_before_tax_k_everybody",
        var_name="income_before_tax",
        k_group_var="k_everybody",
        ub=1,
        lb=0,
    )
    solver.add_rules([income_tax])

    hhs = dl.households
    low = [hh for hh in hhs.values() if LOW_INCOME[int(hh.members[0]["id"])]]
    high = [hh for hh in hhs.values() if not LOW_INCOME[int(hh.members[0]["id"])]]

    budget = BudgetConstraint("All_households", list(hhs.values()), NON_BINDING_CAP)
    bracket_constraint = BracketConstraint(
        rule_family="income_before_tax_k_everybody",
        max_brackets=None,
        ascending=True,
        start_from_first_inflection=False,
        last_bracket_zero=False,
    )
    bracket_constraint.brackets = income_tax.flat_rules

    solver.add_constraints(
        [
            IncomeConstraint(-0.05, low),
            IncomeConstraint(0.10, high),
            budget,
            MarginalPressureConstraint(1.0),
            bracket_constraint,
        ]
    )
    solver.add_objective(BudgetObjective(budget))
    solver.solve()

    if stats_label is not None:
        RECORDS.append(collect_stats(solver, stats_label, stats_extra))

    r_and_r = solver.rules_and_rates_table()
    rates = r_and_r.loc[r_and_r["rule_type"] == "FlatTaxRule", "rate"].to_numpy(float)
    spend = float(solver.backend.get_value(budget.spend))
    revenue = -float(solver.backend.get_value(budget.new_expenditures))
    solver.close()
    return {"rates": rates, "spend": spend, "revenue": revenue}


DELTAS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]

# --- Direct (MIQP) solves ---------------------------------------------------
qp_results = {}
for delta in DELTAS:
    with Timer() as t:
        label = f"behavioral_direct_d{delta:.2f}"
        qp_results[delta] = solve_reform(
            delta,
            stats_label=label,
            stats_extra={"delta": delta},
        )
    print(
        f"direct delta={delta:.2f}: wall {t.elapsed:.2f}s, "
        f"revenue={qp_results[delta]['revenue']:,.0f}"
    )

# --- Algorithm 1 (fixed point, LP-only) --------------------------------------
DAMPING = 0.5
TOL_INCOME = 1.0
MAX_ITER = 40

fp_rows = []
for delta in DELTAS:
    x_new = X_ORIG.copy()
    iters = MAX_ITER
    with Timer() as t:
        for it in range(1, MAX_ITER + 1):
            prefix = f"behavioral_fixed_point_d{delta:.2f}_iter1" if it == 1 else None
            res = solve_reform(
                delta,
                x_incomes=x_new,
                behavioral=False,
                stats_label=prefix,
                stats_extra={"delta": delta} if prefix else None,
            )
            tau_new = res["rates"][BRACKET_IDX]
            x_target = X_ORIG * (1 + delta * (TAU_SQ - tau_new) / (1 - TAU_SQ))
            move = float(np.max(np.abs(x_target - x_new)))
            x_new = (1 - DAMPING) * x_new + DAMPING * x_target
            if move <= TOL_INCOME:
                iters = it
                break

    qp = qp_results[delta]
    fp_rows.append(
        {
            "delta": delta,
            "iterations": iters,
            "lp_solves": iters,
            "total_wall_s": round(t.elapsed, 2),
            "rate_gap_pp": float(np.max(np.abs(res["rates"] - qp["rates"]))) * 100,
            "revenue_gap": abs(res["revenue"] - qp["revenue"]),
        }
    )
    print(fp_rows[-1])

for r in fp_rows:
    RECORDS.append(
        {
            "label": f"behavioral_fixed_point_d{r['delta']:.2f}_total",
            "delta": r["delta"],
            "fp_iterations": r["iterations"],
            "fp_lp_solves": r["lp_solves"],
            "runtime_s": r["total_wall_s"],
            "fp_rate_gap_pp": r["rate_gap_pp"],
            "fp_revenue_gap": r["revenue_gap"],
        }
    )

os.makedirs("systems", exist_ok=True)
write_stats(RECORDS, "systems/computational_stats_behavioral.csv")
