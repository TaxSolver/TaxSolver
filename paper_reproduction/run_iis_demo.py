"""IIS demonstration for the Dutch reform (Section 5).

Runs the infeasible configuration (55% marginal-pressure cap, 96% income
floor, ±1.5% budget band) and computes an irreducible infeasible subsystem
(IIS) for the prose illustration in Section~\\ref{sec:iis}.

Usage (from this folder, with Gurobi available):
    python run_iis_demo.py
"""

from __future__ import annotations

import os
from collections import Counter
from copy import deepcopy

import TaxSolver as tx
from TaxSolver.backend.gurobi_backend import GurobiBackend
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.marginal_pressure_constraint import (
    MarginalPressureConstraint,
)
from TaxSolver.objective import BudgetObjective

from nld_rule_book import (
    NLDRuleBook,
    get_mutually_exclusive_constraints,
    setup_nl_optimization,
)

import run_stats_nl as rn

IIS_PATH = "systems/iis_cap55_floor096.ilp"
LEGACY_RULES = ["sq_kb", "sq_kgb", "sq_rental_support", "sq_zvw_benefit", "sq_kot"]
BUDGET_BAND = 0.015
INCOME_LOSS_LIMIT = 0.04  # 96% income floor
MAX_MARGINAL_PRESSURE = 0.55


def build_solver(
    households,
    income_loss_limit: float,
    max_marginal_pressure: float,
    *,
    budget_band: float = BUDGET_BAND,
    quiet: bool = True,
) -> tx.TaxSolver:
    backend = GurobiBackend()
    backend.model.setParam("TimeLimit", rn.TIME_LIMIT)
    backend.model.setParam("NumericFocus", 2)
    backend.model.setParam("DualReductions", 0)
    if quiet:
        backend.model.setParam("OutputFlag", 0)

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
        max_bln_mut_expenditure=current_tax_revenue * budget_band,
        min_bln_mut_expenditure=-current_tax_revenue * budget_band,
    )
    tax_solver.add_constraints(
        [
            IncomeConstraint(income_loss_limit, list(solver_households.values())),
            budget_constraint,
            MarginalPressureConstraint(max_marginal_pressure),
        ]
    )
    tax_solver.add_constraints(get_mutually_exclusive_constraints())
    tax_solver.add_objective(BudgetObjective(budget_constraint))
    return tax_solver


def solve_model(tax_solver: tx.TaxSolver) -> int:
    try:
        tax_solver.solve()
    except ValueError:
        pass
    return tax_solver.backend.model.Status


def legacy_values_from_reference(households) -> dict[str, dict[str, float]]:
    ref = build_solver(
        households,
        income_loss_limit=0.05,
        max_marginal_pressure=MAX_MARGINAL_PRESSURE,
    )
    status = solve_model(ref)
    if status != 2:
        ref.close()
        raise RuntimeError(
            f"Reference configuration (55% cap, 5% floor) unexpectedly status={status}"
        )
    values = {}
    for rule_name in LEGACY_RULES:
        rule = ref.get_rule(rule_name)
        values[rule_name] = {
            "b": float(ref.backend.get_value(rule.b)),
            "rate": float(ref.backend.get_value(rule.rate)),
        }
    ref.close()
    return values


def fix_legacy_activations(tax_solver: tx.TaxSolver, legacy_values: dict) -> None:
    model = tax_solver.backend.model
    for rule_name, vals in legacy_values.items():
        rule = tax_solver.get_rule(rule_name)
        b_var = model.getVarByName(rule.b.VarName)
        rate_var = model.getVarByName(rule.rate.VarName)
        b_var.LB = b_var.UB = vals["b"]
        rate_var.LB = rate_var.UB = vals["rate"]
    model.update()


def policy_prefix(name: str) -> str:
    if name.startswith("income_constraint_"):
        return "income_constraint"
    if name == "set_marginal_pressure_below_max":
        return name
    if name == "all_households min budget constraint":
        return name
    if name == "all_households max budget constraint":
        return name
    return "other"


def summarize_iis(model) -> dict:
    rows = [c.ConstrName for c in model.getConstrs() if c.IISConstr]
    prefixes = Counter(policy_prefix(n) for n in rows)
    income_rows = [n for n in rows if n.startswith("income_constraint_")]
    return {
        "total": len(rows),
        "prefixes": prefixes,
        "income_floor_count": len(income_rows),
        "has_marginal_cap": prefixes.get("set_marginal_pressure_below_max", 0) > 0,
        "has_budget_min": prefixes.get("all_households min budget constraint", 0) > 0,
        "has_budget_max": prefixes.get("all_households max budget constraint", 0) > 0,
    }


def print_iis_summary(label: str, summary: dict) -> None:
    print(f"\n=== IIS summary ({label}) ===")
    print(f"Total IIS constraint members: {summary['total']}")
    print(f"Household income floors in IIS: {summary['income_floor_count']}")
    for prefix, count in summary["prefixes"].most_common():
        if prefix != "other":
            print(f"  {count:5d}  {prefix}")
    if summary["prefixes"].get("other", 0):
        print(f"  {summary['prefixes']['other']:5d}  other (bracket bookkeeping)")


def compute_and_write_iis(tax_solver: tx.TaxSolver, path: str, label: str) -> dict:
    model = tax_solver.backend.model
    model.setParam("OutputFlag", 1)
    print(f"\nComputing IIS ({label}) ...")
    model.computeIIS()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    model.write(path)
    print(f"Wrote {path}")
    summary = summarize_iis(model)
    print_iis_summary(label, summary)
    return summary


def verify_single_commitment_removal(households) -> None:
    checks = [
        ("relax income floor to 10% loss", 0.10, MAX_MARGINAL_PRESSURE, BUDGET_BAND),
        ("relax marginal cap to 100%", INCOME_LOSS_LIMIT, 1.0, BUDGET_BAND),
        ("relax budget band to ±100%", INCOME_LOSS_LIMIT, MAX_MARGINAL_PRESSURE, 1.0),
    ]
    print("\n=== Single-commitment removal checks ===")
    for label, loss, cap, band in checks:
        solver = build_solver(households, loss, cap, budget_band=band)
        status = solve_model(solver)
        solver.close()
        ok = status == 2
        print(f"  {label}: {'feasible' if ok else f'status {status}'}")


def main() -> None:
    data_path = "./data/NL_persons_headers_preprocessed_equal_weights.xlsx"
    households = rn.load_nl_data(data_path)
    print(f"Loaded {len(households)} households")

    tax_solver = build_solver(
        households,
        income_loss_limit=INCOME_LOSS_LIMIT,
        max_marginal_pressure=MAX_MARGINAL_PRESSURE,
        quiet=False,
    )
    status = solve_model(tax_solver)
    print(f"Infeasible configuration status: {status} (expect 3)")

    legacy_values = legacy_values_from_reference(households)
    print("\nLegacy activations from 55% cap / 5% floor reference solve:")
    for name, vals in legacy_values.items():
        print(f"  {name}: b={vals['b']:.0f}, rate={vals['rate']:.3f}")

    fix_legacy_activations(tax_solver, legacy_values)
    summary = compute_and_write_iis(tax_solver, IIS_PATH, "legacy binaries fixed")

    print("\n=== Prose-ready counts ===")
    print(f"K (household income floors in IIS): {summary['income_floor_count']}")
    print(f"Marginal cap in IIS: {bool(summary['has_marginal_cap'])}")
    print(f"Budget min in IIS: {bool(summary['has_budget_min'])}")
    print(f"Budget max in IIS: {bool(summary['has_budget_max'])}")

    verify_single_commitment_removal(households)
    tax_solver.close()


if __name__ == "__main__":
    main()
