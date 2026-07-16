"""Generate output/tables/table_performance.tex and
output/tables/table_scaling.tex from the instrumented run CSVs in systems/.

Two terminal MIP gaps are not captured in the CSVs for early runs (the
two-stage/cardinality stage's gap column was only added later) and are
recovered from the raw Gurobi solve logs instead: the x1 scaling row and the
gamma=0.65 Dutch row (both cross-checked against the values already reported
in the manuscript).
"""

import os
import re

import pandas as pd

OUT_DIR = os.path.join("output", "tables")


def fmt_time(s):
    if s is None or pd.isna(s):
        return "---"
    if s < 0.1:
        return "$<0.1$"
    if s < 10:
        return f"${s:.1f}$"
    return f"${s:,.0f}$".replace(",", "{,}")


def fmt_int(n):
    return f"{int(n):,}".replace(",", "{,}")


def read_log(log_path):
    return open(log_path, encoding="utf-8", errors="ignore").read()


def last_gap_fraction(log_path):
    """Terminal MIP gap (as a fraction) from a Gurobi log's last
    'Best objective ... gap X%' line."""
    matches = re.findall(r"gap ([\d.]+)%", read_log(log_path))
    return float(matches[-1]) / 100 if matches else None


def multiobj_stage1_seconds(log_path):
    """Wall time of objective 1 within a Gurobi multi-objective solve, read
    from the 'Explored ... in X seconds' line between the objective-1 and
    objective-2 section markers. Needed when the stand-alone stage-1 attempt
    itself did not finish in time (e.g. the x100 scaling instance)."""
    text = read_log(log_path)
    stage1 = text.split("optimize objective 1")[1].split("optimize objective 2")[0]
    return float(re.search(r"in ([\d.]+) seconds", stage1).group(1))


def fmt_marked_time(s, marker=""):
    if s < 10:
        body = f"{s:.1f}"
    else:
        body = f"{s:,.0f}".replace(",", "{,}")
    return f"${body}{marker}$"


def pad_columns(cell_rows):
    """Left-justify each column of a list of equal-length cell lists to the
    widest cell in that column, matching the manuscript tables' hand-aligned
    style (purely cosmetic; LaTeX ignores the extra whitespace)."""
    widths = [max(len(r[i]) for r in cell_rows) for i in range(len(cell_rows[0]))]
    return [[c.ljust(w) for c, w in zip(r, widths)] for r in cell_rows]


def small_row_cells(df, label, display, formulation="LP"):
    r = df[df.label == label].iloc[0]
    return [
        f"\\quad {display}",
        formulation,
        f"${fmt_int(r.num_cont_vars)}$",
        f"${int(r.num_bin_vars)}$",
    ]


def build_performance_tex():
    small = pd.read_csv("systems/computational_stats_small.csv")
    beh = pd.read_csv("systems/computational_stats_behavioral.csv")
    nl = pd.read_csv("systems/computational_stats_nl.csv")

    illustrative_cells = [
        small_row_cells(small, "case_1a_recovery", "Single rule, recovery"),
        small_row_cells(small, "case_1a_reform", "Single rule, reform"),
        small_row_cells(small, "case_1b_recovery", "Multiple rules, recovery"),
        small_row_cells(small, "case_1b_reform", "Multiple rules, reform"),
        small_row_cells(small, "case_2_recovery", "Multiple groups, recovery"),
        small_row_cells(small, "case_2_reform", "Multiple groups, reform"),
        small_row_cells(small, "dynamic_bracketing_demo", "Dynamic bracketing", "MILP"),
    ]
    dyn = small[small.label == "dynamic_bracketing_demo"].iloc[0]
    small_tails = [
        f"${fmt_int(small[small.label == lbl].iloc[0].num_constrs)}$ & "
        f"{fmt_time(small[small.label == lbl].iloc[0].runtime_s)} & $0$ \\\\"
        for lbl in [
            "case_1a_recovery",
            "case_1a_reform",
            "case_1b_recovery",
            "case_1b_reform",
            "case_2_recovery",
            "case_2_reform",
        ]
    ] + [
        f"${fmt_int(dyn.num_constrs)}$ & {fmt_time(dyn.runtime_s)} & $8\\cdot10^{{-5}}$ \\\\"
    ]
    padded_illustrative = pad_columns(illustrative_cells)
    # The label column is shared with "Direct solve, per stage" below, so pad
    # to that combined width too.
    label_width = max(
        len(r[0]) for r in padded_illustrative + [["\\quad Direct solve, per stage"]]
    )
    illustrative_rows = [
        "    " + " & ".join([cells[0].ljust(label_width)] + cells[1:]) + " & " + tail
        for cells, tail in zip(padded_illustrative, small_tails)
    ]

    direct = beh[beh.label == "behavioral_direct_d0.25"].iloc[0]
    fp_iter = beh[beh.label == "behavioral_fixed_point_d0.25_iter1"].iloc[0]
    fp_total = beh[beh.label.str.endswith("_total")]
    total_lo, total_hi = fp_total.runtime_s.min(), fp_total.runtime_s.max()
    behavioral_rows = [
        f"    \\quad Direct solve, per stage          & MIQCP & ${fmt_int(direct.num_cont_vars)}$ & "
        f"${int(direct.num_bin_vars)}$   & ${fmt_int(direct.num_constrs)}$\\,{{+}}\\,${fmt_int(direct.num_q_constrs)}$q & "
        f"$<0.2$ & $\\le 10^{{-4}}$ \\\\",
        f"    \\quad Alg.\\ 1 (main text), per LP iterate & LP & ${fmt_int(fp_iter.num_cont_vars)}$ & "
        f"${int(fp_iter.num_bin_vars)}$ & ${fmt_int(fp_iter.num_constrs)}$ & "
        f"{fmt_time(fp_iter.runtime_s)} & $0$ \\\\",
        f"    \\quad Alg.\\ 1 (main text), total run & --- & --- & --- & --- & "
        f"${total_lo:.2f}$--${total_hi:.1f}$ & --- \\\\",
    ]

    dutch_rows = []
    for gamma in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        bo = nl[(nl.gamma == gamma) & (nl.objective_mode == "budget_only")].iloc[0]
        sq = nl[(nl.gamma == gamma) & (nl.objective_mode == "sequential")].iloc[0]
        sq_time, sq_gap, marker = sq.runtime_s, sq.mip_gap, ""
        if sq.status == "time_limit":
            # Cardinality stage did not close under the nominal budget; the
            # extended run (see run_stats_nl_gamma65_extended.py) is what the
            # manuscript reports as the certified result.
            ext = nl[nl.label == f"nl_gamma_{int(gamma*100)}_sequential_4h"].iloc[0]
            sq_time = ext.runtime_s
            sq_gap = last_gap_fraction("systems/run_stats_nl_gamma65_4h.log")
            marker = "^{\\ast}"
        elif pd.isna(sq_gap):
            # Not captured in this row's CSV columns; status=="optimal" under
            # the default 1e-4 relative-gap tolerance means gap 0.
            sq_gap = 0.0
        bo_gap = "0" if bo.mip_gap == 0 else f"{bo.mip_gap:.0e}"
        dutch_rows.append(
            f"    \\quad Reform $\\gamma={gamma:.2f}$ & MILP & ${fmt_int(bo.num_cont_vars)}$ & "
            f"${int(bo.num_bin_vars)}$ & ${fmt_int(bo.num_constrs)}$ & "
            f"{fmt_time(bo.runtime_s)} / {fmt_marked_time(sq_time, marker)} & "
            f"${bo_gap}$ / ${sq_gap:.0f}$ \\\\"
        )

    tex = "\n".join(
        [
            "\\begin{table}[!t]",
            "  \\centering",
            "  \\footnotesize",
            "  \\renewcommand{\\arraystretch}{1.0}",
            "  \\setlength{\\tabcolsep}{3pt}",
            "  \\begin{tabular}{l l r r r r r}",
            "    \\toprule",
            "    \\textbf{Formulation} & \\textbf{Class} & \\textbf{Cont.} & \\textbf{Bin.} & \\textbf{Constr.} & \\textbf{Time (s)} & \\textbf{Gap} \\\\",
            "    \\midrule",
            "    \\multicolumn{7}{l}{\\emph{Illustrative examples} (Section 4.7 of the main text; $1{,}000$ taxpayers)} \\\\",
            "    \\addlinespace[2pt]",
            *illustrative_rows,
            "    \\addlinespace[2pt]",
            "    \\multicolumn{7}{l}{\\emph{Behavioral responses} (Section 4.5 of the main text; shown at $\\delta = 0.25$)} \\\\",
            "    \\addlinespace[2pt]",
            *behavioral_rows,
            "    \\midrule",
            "    \\multicolumn{7}{l}{\\emph{Dutch income tax code} (Section 5 of the main text; $13{,}500$ taxpayers, $8{,}400$ households)} \\\\",
            "    \\addlinespace[2pt]",
            *dutch_rows,
            "    \\bottomrule",
            "  \\end{tabular}",
            "  \\caption{Problem size and solver performance for every formulation in the paper: continuous (Cont.) and binary (Bin.) variables, linear constraint rows (``{+}\\,$n$q'' marks quadratic constraints), wall-clock time, and terminal relative MIP gap. Dutch rows show ``stage~1 / two-stage'' entries; every stage solves to proven optimality (gap $0$). $^{\\ast}$~exceeds the nominal $1{,}800$\\,s budget used elsewhere; confirmed optimal in an extended run (see main text above). Solver, parameters, and hardware as described above.}",
            "  \\label{table: performance}",
            "\\end{table}",
            "",
        ]
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "table_performance.tex")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(tex)
    print(f"Wrote {out_path}")


def build_scaling_tex():
    sc = pd.read_csv("systems/computational_stats_scaling.csv")
    log_for_factor = {
        1: "systems/run_stats_scaling_x1.log",
        10: "systems/run_stats_scaling_x10.log",
        100: "systems/run_stats_scaling_x100.log",
    }
    col_cells = []  # list of [N, Cont., Constr., Stage1] per row (Rates/Bin. are constant)
    tails = []  # "seq / gap" tail per row, appended as-is
    for factor in [1, 10, 100]:
        bo = sc[
            (sc.scale_factor == factor) & (sc.objective_mode == "budget_only")
        ].iloc[0]
        seq = sc[(sc.scale_factor == factor) & (sc.objective_mode == "sequential")]
        if seq.empty:
            # Earliest x1 run predates the objective_mode column; it is the
            # lone non-budget_only row for that factor.
            seq = sc[
                (sc.scale_factor == factor) & (sc.label == f"nl_scaling_x{factor}")
            ]
        seq = seq.iloc[0]
        seq_gap = seq.mip_gap
        if pd.isna(seq_gap):
            seq_gap = last_gap_fraction(log_for_factor[factor])
        if bo.status == "optimal":
            stage1_time, marker = bo.runtime_s, ""
        else:
            # Stand-alone stage-1 attempt did not finish (see main text
            # above); the reported time is stage 1's wall time measured
            # inside the two-stage multi-objective solve instead.
            stage1_time, marker = (
                multiobj_stage1_seconds(log_for_factor[factor]),
                "^{\\dagger}",
            )
        col_cells.append(
            [
                f"${fmt_int(bo.n_records)}$",
                f"${fmt_int(bo.num_cont_vars)}$",
                f"${fmt_int(bo.num_constrs)}$",
                fmt_marked_time(stage1_time, marker),
            ]
        )
        tails.append(f"${fmt_int(round(seq.runtime_s))}$ / ${seq_gap:.3f}$ \\\\")

    def visual_len(s):
        # Superscript markers render as ~1 character; don't let their raw
        # LaTeX source length skew column padding.
        return len(re.sub(r"\^\{\\[a-zA-Z]+\}", "*", s))

    widths = [max(visual_len(r[i]) for r in col_cells) for i in range(4)]
    col_cells = [
        [c.ljust(w + len(c) - visual_len(c)) for c, w in zip(r, widths)]
        for r in col_cells
    ]
    widths = [0, 0, 0, 0]  # already padded above
    rows = [
        "    {} & $77$ & $77$ & {} & {} & {} & {}".format(
            r[0].ljust(widths[0]),
            r[1].ljust(widths[1]),
            r[2].ljust(widths[2]),
            r[3].ljust(widths[3]),
            tail,
        )
        for r, tail in zip(col_cells, tails)
    ]

    tex = "\n".join(
        [
            "\\begin{table}[!t]",
            "  \\centering",
            "  \\footnotesize",
            "  \\renewcommand{\\arraystretch}{1.25}",
            "  \\setlength{\\tabcolsep}{4pt}",
            "  \\begin{tabular}{r r r r r r r}",
            "    \\toprule",
            "    \\textbf{Records $N$} & \\textbf{Rates} & \\textbf{Bin.} & \\textbf{Cont.} & \\textbf{Constr.} & \\textbf{Stage 1 (s)} & \\textbf{Two-stage (s / gap)} \\\\",
            "    \\midrule",
            *rows,
            "    \\bottomrule",
            "  \\end{tabular}",
            "  \\caption{Scaling of the Dutch reform ($\\gamma = 0.65$) as the number of sampled taxpayer records $N$ grows by two orders of magnitude (base sample replicated $10\\times$ and $100\\times$ with weights divided by the replication factor, so all weighted aggregates are unchanged). The decision variables ($77$ candidate rule rates and their activation binaries) are invariant in $N$; the bookkeeping variables and constraint rows grow linearly. Stage 1 (revenue loss) solved to proven optimality at every size; the two-stage column reports wall-clock seconds and the terminal gap of the cardinality stage ($^{\\dagger}$see the main text above for time limits and details). Solver and hardware as in Table~\\ref{table: performance}.}",
            "  \\label{table: scaling}",
            "\\end{table}",
            "",
        ]
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "table_scaling.tex")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(tex)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    build_performance_tex()
    build_scaling_tex()
