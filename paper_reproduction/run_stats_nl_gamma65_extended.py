"""One-off extended run: does the gamma=0.65 cardinality stage close its
12.8% gap (Table A.8) given a 4-hour instead of 30-minute time limit?

Reuses run_stats_nl.py's exact model setup (load_nl_data, run_nl_optimization)
with TIME_LIMIT overridden before the solve. Appends its record to
systems/computational_stats_nl.csv with label 'nl_gamma_65_sequential_4h'.
"""

import run_stats_nl as rn
from solve_stats import collect_stats

rn.TIME_LIMIT = 4 * 60 * 60  # 14,400s, matching the scaling experiment's budget

if __name__ == "__main__":
    households = rn.load_nl_data(
        "./data/NL_persons_headers_preprocessed_equal_weights.xlsx"
    )
    print(f"Loaded {len(households)} households; TIME_LIMIT={rn.TIME_LIMIT}s")

    solver = rn.run_nl_optimization(households, 0.65, "sequential")

    extra = {
        "gamma": 0.65,
        "objective_mode": "sequential",
        "time_limit_s": rn.TIME_LIMIT,
    }
    if solver.solved:
        r_and_r = solver.rules_and_rates_table()
        extra["active_rules"] = int(r_and_r["b"].sum())
        extra["weighted_rule_count"] = int((r_and_r["b"] * r_and_r["weight"]).sum())

    rec = collect_stats(solver, "nl_gamma_65_sequential_4h", extra)
    print(
        {
            k: rec[k]
            for k in ["label", "runtime_s", "status", "mip_gap", "weighted_rule_count"]
            if k in rec
        }
    )
    solver.close()

    import pandas as pd
    import os

    row = pd.DataFrame([rec])
    path = "systems/computational_stats_nl.csv"
    if os.path.exists(path):
        row = pd.concat([pd.read_csv(path), row], ignore_index=True)
    row.to_csv(path, index=False)
    print(f"Appended to {path}")
