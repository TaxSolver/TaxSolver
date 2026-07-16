"""Generate output/tables/table_reform_schedules.tex from the solved Dutch
reform rule tables (systems/case_nl_reform_{65,75}_5.xlsx).

Each rule family's bracket rows are run-length-encoded by rate (merging rows
with equal consecutive rates, regardless of the solver's own `b` activation
flag -- `b` marks only where a *new* segment begins for the solver's own
bookkeeping). The universal schedule shows every resulting segment, including
zero-rate ones; group-specific schedules and the benefit/legacy sections show
only the nonzero ones. This one-time rule-identifier -> manuscript-label
mapping is the only hand-authored part; every number is read from the solved
rule tables.
"""

import os
import re

import pandas as pd

OUT_DIR = os.path.join("output", "tables")
CAPS = [("65", "65\\% cap"), ("75", "75\\% cap")]

# Group-specific bracket families to report, in display order, and whether at
# least one cap actually uses them is decided from the data (see main()).
GROUP_LABELS = {
    "k_lowest_earner": "Lowest earner in fiscal partnership",
    "k_aow": "Retirees (AOW)",
    "k_zzp": "Self-employed",
}

# (rule_name, display label), in display order.
BENEFIT_ROWS = [
    ("inkomensonafhankelijke_zorgtoeslag_persoon", "Universal per-person benefit"),
    ("simpel_kb", "Household benefit per child"),
    ("young_handicapped_benefit", "Young-handicapped benefit"),
    (
        "inkomensonafhankelijke_zorgtoeslag_huishouden_single_topup",
        "Single-household benefit",
    ),
]

LEGACY_ROWS = [
    ("sq_kgb", "Child-related budget (kindgebonden budget)"),
    ("sq_rental_support", "Rental support (huurtoeslag)"),
]

BRACKET_VAR_RE = re.compile(r"^(?P<family>.+)_(?P<start>\d+)_(?P<end>\d+)$")


def euro(n):
    return f"\\euro{{}}{int(round(n)):,}".replace(",", "{,}")


def pct(rate):
    return f"{rate * 100:.1f}\\%"


def bracket_segments(df, family):
    """Run-length-encode a FlatTaxRule family's rows by rate, sorted by
    income start. Returns [(start, end_or_None, rate), ...]; end is None for
    the final (unbounded) segment."""
    rows = []
    for _, r in df[
        (df.rule_type == "FlatTaxRule") & df.var_name.str.startswith(family + "_")
    ].iterrows():
        m = BRACKET_VAR_RE.match(r.var_name)
        if not m or m.group("family") != family:
            continue
        rows.append((int(m.group("start")), int(m.group("end")), r.rate))
    rows.sort(key=lambda t: t[0])

    segments = []
    for start, end, rate in rows:
        if segments and abs(segments[-1][2] - rate) < 1e-9:
            segments[-1] = (segments[-1][0], end, rate)
        else:
            segments.append((start, end, rate))
    # Last segment is open-ended ("above X"), matching the manuscript's phrasing.
    if segments:
        s, _, r = segments[-1]
        segments[-1] = (s, None, r)
    return segments


def universal_rows(df65, df75):
    seg65 = bracket_segments(df65, "income_before_tax_k_everybody")
    seg75 = bracket_segments(df75, "income_before_tax_k_everybody")
    assert len(seg65) == len(seg75), "universal schedules have different segment counts"
    rows = []
    for (s65, e65, r65), (s75, e75, r75) in zip(seg65, seg75):
        left = f"above {euro(s65)}" if e65 is None else f"{euro(s65)}--{euro(e65)}"
        right = f"above {euro(s75)}" if e75 is None else f"{euro(s75)}--{euro(e75)}"
        rows.append(f"    \\quad & {left} & {pct(r65)} & {right} & {pct(r75)} \\\\")
    return rows


def group_nonzero_segment(df, family):
    """The family's single nonzero run-length segment, or None if every
    segment is zero (group deactivated at this cap)."""
    for start, end, rate in bracket_segments(df, family):
        if abs(rate) > 1e-9:
            return start, end, rate
    return None


def group_rows(df65, df75):
    rows = []
    for family, label in GROUP_LABELS.items():
        full_family = f"income_before_tax_{family}"
        seg65 = group_nonzero_segment(df65, full_family)
        seg75 = group_nonzero_segment(df75, full_family)
        if seg65 is None and seg75 is None:
            continue  # never used in either headline reform; omit the row
        left = (
            "--- & ---"
            if seg65 is None
            else (
                f"{'above ' + euro(seg65[0]) if seg65[1] is None else euro(seg65[0]) + '--' + euro(seg65[1])} & {pct(seg65[2])}"
            )
        )
        right = (
            "--- & ---"
            if seg75 is None
            else (
                f"{'above ' + euro(seg75[0]) if seg75[1] is None else euro(seg75[0]) + '--' + euro(seg75[1])} & {pct(seg75[2])}"
            )
        )
        rows.append(f"    \\quad {label} & {left} & {right} \\\\")
    return rows


def active_value(df, rule_name):
    r = df[(df.rule_name == rule_name) & (df.b == 1)]
    return float(r.iloc[0].rate) if not r.empty else None


def benefit_rows(df65, df75):
    rows = []
    for rule_name, label in BENEFIT_ROWS:
        v65, v75 = active_value(df65, rule_name), active_value(df75, rule_name)
        if v65 is None and v75 is None:
            continue
        left = "---" if v65 is None else euro(v65)
        right = "---" if v75 is None else euro(v75)
        rows.append(
            f"    \\quad {label} & \\multicolumn{{2}}{{c}}{{{left}}} & "
            f"\\multicolumn{{2}}{{c}}{{{right}}} \\\\"
        )
    return rows


def legacy_rows(df65, df75):
    rows = []
    for rule_name, label in LEGACY_ROWS:
        v65, v75 = active_value(df65, rule_name), active_value(df75, rule_name)
        if v65 is None and v75 is None:
            continue
        left = "---" if v65 is None else f"$\\times{v65:.2f}$"
        right = "---" if v75 is None else f"$\\times{v75:.2f}$"
        rows.append(
            f"    \\quad {label} & \\multicolumn{{2}}{{c}}{{{left}}} & "
            f"\\multicolumn{{2}}{{c}}{{{right}}} \\\\"
        )
    return rows


def main():
    df65 = pd.read_excel("systems/case_nl_reform_65_5.xlsx")
    df75 = pd.read_excel("systems/case_nl_reform_75_5.xlsx")

    tex = "\n".join(
        [
            "\\begin{table}[!t]",
            "  \\centering",
            "  \\footnotesize",
            "  \\resizebox{\\textwidth}{!}{%",
            "  \\begin{tabular}{lrrrr}",
            "    \\toprule",
            "    & \\multicolumn{2}{c}{Reform (65\\% cap)} & \\multicolumn{2}{c}{Reform (75\\% cap)} \\\\",
            "    \\cmidrule(lr){2-3}\\cmidrule(lr){4-5}",
            "    & Income range & Rate & Income range & Rate \\\\",
            "    \\midrule",
            "    \\multicolumn{5}{l}{\\emph{Universal income tax brackets (per person, income before tax)}} \\\\",
            *universal_rows(df65, df75),
            "    \\addlinespace",
            "    \\multicolumn{5}{l}{\\emph{Group-specific rates (per person, income before tax)}} \\\\",
            *group_rows(df65, df75),
            "    \\addlinespace",
            "    \\multicolumn{5}{l}{\\emph{Benefits (\\euro{} per year)}} \\\\",
            *benefit_rows(df65, df75),
            "    \\addlinespace",
            "    \\multicolumn{5}{l}{\\emph{Retained legacy rules (scaling of current statute)}} \\\\",
            *legacy_rows(df65, df75),
            "    \\bottomrule",
            "  \\end{tabular}%",
            "  }",
            "  \\caption{The two headline certified reforms of the Dutch case in full (65\\% and 75\\% marginal-pressure caps; both guarantee a 5\\% household income floor within a $\\pm$1.5\\% budget band). Group-specific rates are additive to the universal brackets and apply on the stated income range only (a negative rate is an income-dependent credit). Retained legacy rules keep the current statutory formula, scaled by the stated factor. All remaining candidate and current rules, including the healthcare allowance, child benefit, childcare allowance, labor tax credit, general tax credit, elderly discounts, and the own-home deductible, are deactivated (Table 2 of the main text). Extracted from the solved instances underlying Figure 10 of the main text.}",
            "  \\label{table: reform_schedules}",
            "\\end{table}",
            "",
        ]
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "table_reform_schedules.tex")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(tex)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
