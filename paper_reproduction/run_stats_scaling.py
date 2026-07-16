"""Scaling experiment in the number of sampled records N for the Dutch
two-stage reform (gamma = 0.65): N = 13,500 -> 135,000 -> 1,350,000 taxpayer
records, obtained by replicating the base sample 1x / 10x / 100x with weights
divided by the replication factor (so all weighted aggregates, and hence the
optimal reform, are unchanged).

The decision variables (bracket rates, lump sums, activation binaries) are
fixed by the support and tax-group inventory and do not grow with N; the
per-taxpayer bookkeeping variables and the constraint rows (one income
guarantee per household) grow linearly with N.

Also computes the number of DISTINCT household profiles: households whose
members have identical bracketed inputs and group memberships contribute
identical constraint rows and could be aggregated with counts.

Usage: python run_stats_scaling.py <factor>   (factor in {1, 10, 100})
Results are appended to systems/computational_stats_scaling.csv.
"""

import os
import sys
import time

import pandas as pd

import TaxSolver as tx
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.population.person import Person
from TaxSolver.population.household import Household
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

from solve_stats import collect_stats

GAMMA = 0.65
DATA_PATH = "./data/NL_persons_headers_preprocessed_equal_weights.xlsx"
CSV_PATH = "systems/computational_stats_scaling.csv"
# 30 min (paper standard) for the base and 10x instances; the 100x instance
# is attempted under a longer limit and reported at whatever gap it reaches.
TIME_LIMITS = {1: 30 * 60, 10: 30 * 60, 100: 4 * 60 * 60}


def replicate_df(df: pd.DataFrame, factor: int) -> pd.DataFrame:
    """Replicate the processed dataframe `factor` times with unique string ids
    and weights divided by `factor` (weighted aggregates unchanged)."""
    if factor == 1:
        return df.copy()
    copies = []
    for r in range(factor):
        c = df.copy()
        c["id"] = c["id"].astype(str) + f"_r{r}"
        c["hh_id"] = c["hh_id"].astype(str) + f"_r{r}"
        c["weight"] = c["weight"] / factor
        copies.append(c)
    return pd.concat(copies, ignore_index=True)


def build_households(df: pd.DataFrame) -> dict:
    """Groupby-based replacement for DataLoader._create_people_and_households
    (which is quadratic in the number of households)."""
    households = {}
    records = df.to_dict("records")
    by_hh = {}
    for rec in records:
        by_hh.setdefault(str(rec["hh_id"]), []).append(rec)
    for hh_id, members in by_hh.items():
        persons = []
        for rec in members:
            p = Person(rec)
            p.init_labor_effect_weight = None
            persons.append(p)
        hh = Household(hh_id, persons, weight=persons[0]["weight"])
        hh.mirror_hh = hh
        for p in persons:
            p.data["mirror_id"] = hh_id
        households[hh_id] = hh
    return households


def profile_columns(df: pd.DataFrame) -> list:
    """Columns through which a household enters the constraint matrix:
    incomes, model inputs, group memberships, and status-quo rule pressures."""
    return sorted(
        c
        for c in df.columns
        if c in ("income_before_tax", "income_after_tax")
        or c.startswith(("i_", "k_", "sq_a_", "sq_m_"))
    )


def distinct_household_profiles(df: pd.DataFrame) -> int:
    cols = profile_columns(df)
    person_profile = pd.util.hash_pandas_object(df[cols].round(6), index=False)
    hh_profiles = (
        pd.DataFrame({"hh_id": df["hh_id"].values, "p": person_profile.values})
        .sort_values(["hh_id", "p"])
        .groupby("hh_id")["p"]
        .apply(tuple)
    )
    return int(hh_profiles.nunique())


def run(factor: int, objective_mode: str = "sequential"):
    time_limit = TIME_LIMITS[factor]

    print(f"Loading base data (factor {factor}, mode {objective_mode}) ...")
    dl = DataLoader(
        path=DATA_PATH,
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

    base_df = dl.df
    df = replicate_df(base_df, factor)
    n_records = len(df)
    print(f"Records: {n_records:,}")

    n_distinct = distinct_household_profiles(df)
    print(f"Distinct household profiles: {n_distinct:,}")

    build_start = time.perf_counter()
    households = build_households(df)
    print(f"Households: {len(households):,}")

    backend = GurobiBackend()
    backend.model.setParam("TimeLimit", time_limit)
    backend.model.setParam("NumericFocus", 2)

    tax_solver = tx.TaxSolver(households=households, backend=backend)

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
        for hh in households.values()
    )
    print(f"Current tax revenue (weighted): {current_tax_revenue:,.2f}")

    budget_constraint = BudgetConstraint(
        "all_households",
        list(households.values()),
        max_bln_mut_expenditure=current_tax_revenue * 0.015,
        min_bln_mut_expenditure=-current_tax_revenue * 0.015,
    )
    tax_solver.add_constraints(
        [
            IncomeConstraint(0.05, list(households.values())),
            budget_constraint,
            MarginalPressureConstraint(GAMMA),
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
        print("No feasible solution found.")
    build_and_solve = time.perf_counter() - build_start

    extra = {
        "scale_factor": factor,
        "objective_mode": objective_mode,
        "n_records": n_records,
        "distinct_hh_profiles": n_distinct,
        "build_and_solve_wall_s": round(build_and_solve, 1),
        "gamma": GAMMA,
    }
    if tax_solver.solved:
        r_and_r = tax_solver.rules_and_rates_table()
        extra["active_rules"] = int(r_and_r["b"].sum())
        extra["weighted_rule_count"] = int((r_and_r["b"] * r_and_r["weight"]).sum())

    rec = collect_stats(tax_solver, f"nl_scaling_x{factor}_{objective_mode}", extra)
    print(
        {
            k: rec[k]
            for k in [
                "label",
                "runtime_s",
                "status",
                "num_vars",
                "num_bin_vars",
                "num_constrs",
            ]
        }
    )

    os.makedirs("systems", exist_ok=True)
    row = pd.DataFrame([rec])
    if os.path.exists(CSV_PATH):
        row = pd.concat([pd.read_csv(CSV_PATH), row], ignore_index=True)
    row.to_csv(CSV_PATH, index=False)
    print(f"Appended record to {CSV_PATH}")

    tax_solver.close()


if __name__ == "__main__":
    factor = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    mode = sys.argv[2] if len(sys.argv) > 2 else "sequential"
    if mode == "both":
        run(factor, "budget_only")
        run(factor, "sequential")
    else:
        run(factor, mode)
