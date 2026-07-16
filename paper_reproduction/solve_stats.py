"""Solve-statistics instrumentation for the computational reporting appendix.

Collects, for every Gurobi solve launched from the reproduction scripts, the
model dimensions (continuous / binary variables, linear / general / quadratic
constraints), wall-clock runtime, termination status, and the terminal MIP gap
where Gurobi exposes it (single-objective models only; the sequential
multi-objective solves report the gap of each stage in the log but do not
expose a single MIPGap attribute).

Each run script builds a list of records via ``collect_stats`` and writes its
own CSV in ``systems/`` so that reruns overwrite rather than append.
"""

from __future__ import annotations

import datetime
import platform
import subprocess
import time

import pandas as pd

# Gurobi status codes -> human-readable
_STATUS = {
    1: "loaded",
    2: "optimal",
    3: "infeasible",
    4: "inf_or_unbd",
    5: "unbounded",
    9: "time_limit",
    11: "interrupted",
    13: "suboptimal",
}


def hardware_info() -> dict:
    """One-off description of the machine and solver used for the runs."""
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    if platform.system() == "Darwin":
        for key, name in [
            ("machdep.cpu.brand_string", "cpu"),
            ("hw.physicalcpu", "physical_cores"),
            ("hw.logicalcpu", "logical_cores"),
            ("hw.memsize", "ram_bytes"),
        ]:
            try:
                info[name] = subprocess.check_output(
                    ["sysctl", "-n", key], text=True
                ).strip()
            except Exception:
                info[name] = "unknown"
    try:
        import gurobipy as gp

        info["gurobi_version"] = ".".join(str(v) for v in gp.gurobi.version())
    except Exception:
        info["gurobi_version"] = "unknown"
    return info


def _get(model, attr):
    try:
        return getattr(model, attr)
    except Exception:
        return None


def collect_stats(tax_solver, label: str, extra: dict | None = None) -> dict:
    """Read model dimensions and solve outcomes off a (possibly unsolved)
    TaxSolver whose backend is Gurobi."""
    model = tax_solver.backend.model

    status_code = _get(model, "Status")
    n_persons = len(tax_solver.people)
    n_households = len(tax_solver.households)

    rec = {
        "label": label,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_persons": n_persons,
        "n_households": n_households,
        "num_vars": _get(model, "NumVars"),
        "num_bin_vars": _get(model, "NumBinVars"),
        "num_int_vars": _get(model, "NumIntVars"),
        "num_cont_vars": (
            _get(model, "NumVars") - _get(model, "NumIntVars")
            if _get(model, "NumVars") is not None
            and _get(model, "NumIntVars") is not None
            else None
        ),
        "num_constrs": _get(model, "NumConstrs"),
        "num_gen_constrs": _get(model, "NumGenConstrs"),
        "num_q_constrs": _get(model, "NumQConstrs"),
        "num_quad_obj_terms": None,
        "runtime_s": round(model.Runtime, 3)
        if _get(model, "Runtime") is not None
        else None,
        "status_code": status_code,
        "status": _STATUS.get(status_code, str(status_code)),
        "solved": bool(getattr(tax_solver, "solved", False)),
        "num_objectives": _get(model, "NumObj"),
        "mip_gap": None,
        "obj_val": None,
        "obj_bound": None,
        "time_limit_param": _get(model.Params, "TimeLimit"),
        "numeric_focus_param": _get(model.Params, "NumericFocus"),
        "threads_param": _get(model.Params, "Threads"),
        "mip_gap_param": _get(model.Params, "MIPGap"),
    }

    # Bilinear objective terms mark the MIQP instances
    try:
        obj = model.getObjective()
        rec["num_quad_obj_terms"] = obj.size() if hasattr(obj, "size") else 0
    except Exception:
        pass

    if getattr(tax_solver, "solved", False):
        rec["obj_val"] = _get(model, "ObjVal")
        rec["obj_bound"] = _get(model, "ObjBound")
        try:
            rec["mip_gap"] = model.MIPGap
        except Exception:
            pass  # not exposed for multi-objective models

    if extra:
        rec.update(extra)
    return rec


class Timer:
    """Context manager for wall-clock timing of code blocks (e.g. an entire
    fixed-point iteration of Algorithm 1)."""

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.perf_counter() - self.start


def write_stats(records: list[dict], path: str) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df.to_csv(path, index=False)
    print(f"Wrote {len(df)} solve records to {path}")
    return df


if __name__ == "__main__":
    for k, v in hardware_info().items():
        print(f"{k}: {v}")
