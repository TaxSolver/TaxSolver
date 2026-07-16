"""Computational statistics for the Dutch case study (Section 4): the
two-stage lexicographic reform at every marginal-pressure cap gamma in the
paper's sweep, plus the stage-1 (revenue-loss) solve on its own so that its
terminal MIP gap is exposed (Gurobi does not report a MIPGap attribute for
sequential multi-objective models).

Model setup replicates fig09_10_dutch_case_study.ipynb / fig12_guarantee_frontier.ipynb
verbatim; the only addition is the solve-statistics bookkeeping. Results are
written to systems/computational_stats_nl.csv.
"""

from copy import deepcopy

import TaxSolver as tx
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.marginal_pressure_constraint import (
    MarginalPressureConstraint,
)
from TaxSolver.objective import SequentialMixedObjective, BudgetObjective
from TaxSolver.backend.gurobi_backend import GurobiBackend

from nld_rule_book import (
    NLDRuleBook,
    setup_nl_optimization,
    get_mutually_exclusive_constraints,
)

from solve_stats import collect_stats, write_stats

TIME_LIMIT = 30 * 60  # seconds, as in fig09_10_dutch_case_study.ipynb


def load_nl_data(data_path: str) -> dict:
    dl = DataLoader(
        path=data_path,
        income_before_tax="income_before_tax",
        income_after_tax="income_after_tax",
        weight="weight",
        id="id",
        hh_id="hh_id",
        mirror_id="mirror_id",
        input_vars=[
            "i_number_of_kids_0_5",
            "i_number_of_kids_6_11",
            "i_number_of_kids_12_15",
            "i_number_of_kids_16_17",
            "i_number_of_kids",
            "i_monthly_rent",
            "i_assets",
            "i_partner_income",
            "i_other_income",
            "i_woz",
            "i_mortgage_interest",
        ],
        group_vars=["fiscal_partner", "partner_type_of_income"],
    )
    return dl.households


def run_nl_optimization(households, max_marginal_pressure, objective_mode):
    """Identical to the case_nl / case_frontier setup: income floor 5%,
    budget band +/-1.5%, 1% second-stage budget slack."""
    backend = GurobiBackend()
    backend.model.setParam("TimeLimit", TIME_LIMIT)
    backend.model.setParam("NumericFocus", 2)

    solver_households = deepcopy(households)
    tax_solver = tx.TaxSolver(households=solver_households, backend=backend)

    setup_nl_optimization(
        tax_solver=tax_solver,
        k_groups=NLDRuleBook.default_k_groups(),
        include_tags=["basic"],
        exclude_tags=["verzilverbaar", "protect_other_koopkracht_groups"],
        add_main_brackets=True,
        add_k_group_brackets=True,
        add_household_brackets=False,
    )

    current_tax_revenue = sum(
        hh.members[0]["weight"]
        * sum(p["income_before_tax"] - p["income_after_tax"] for p in hh.members)
        for hh in solver_households.values()
    )

    budget_constraint = BudgetConstraint(
        "all_households",
        list(solver_households.values()),
        max_bln_mut_expenditure=current_tax_revenue * 0.015,
        min_bln_mut_expenditure=-current_tax_revenue * 0.015,
    )
    tax_solver.add_constraints(
        [
            IncomeConstraint(0.05, list(solver_households.values())),
            budget_constraint,
            MarginalPressureConstraint(max_marginal_pressure),
        ]
    )
    tax_solver.add_constraints(get_mutually_exclusive_constraints())

    if objective_mode == "sequential":
        objective = SequentialMixedObjective(
            budget_constraint,
            objectives={"budget": 2, "complexity": 1},
            tolerances={"budget": current_tax_revenue * 0.01, "complexity": 10},
        )
    else:
        objective = BudgetObjective(budget_constraint)
    tax_solver.add_objective(objective)

    try:
        tax_solver.solve()
    except ValueError:
        print("No feasible solution found for this configuration.")

    return tax_solver


if __name__ == "__main__":
    data_path = "./data/NL_persons_headers_preprocessed_equal_weights.xlsx"
    households = load_nl_data(data_path)
    print(f"Loaded {len(households)} households")

    records = []
    for gamma in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        for mode in ["budget_only", "sequential"]:
            label = f"nl_gamma_{int(gamma * 100)}_{mode}"
            print(f"\n===== {label} =====")
            solver = run_nl_optimization(households, gamma, mode)
            extra = {"gamma": gamma, "objective_mode": mode}
            if solver.solved:
                r_and_r = solver.rules_and_rates_table()
                extra["active_rules"] = int(r_and_r["b"].sum())
                extra["weighted_rule_count"] = int(
                    (r_and_r["b"] * r_and_r["weight"]).sum()
                )
            records.append(collect_stats(solver, label, extra))
            print(
                {
                    k: records[-1][k]
                    for k in [
                        "label",
                        "runtime_s",
                        "status",
                        "mip_gap",
                        "num_cont_vars",
                        "num_bin_vars",
                        "num_constrs",
                    ]
                }
            )
            solver.close()
            # checkpoint after every solve
            write_stats(records, "systems/computational_stats_nl.csv")
