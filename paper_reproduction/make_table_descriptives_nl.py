"""Generate output/tables/table_descriptives_nl_case.tex from the shipped NL dataset.

Reads data/NL_persons_headers_preprocessed_equal_weights.xlsx and writes the
Table S3 descriptives used in supplementary.tex. Column choices match the
Dutch case study loader in fig09_10_dutch_case_study.ipynb:
- income_before_tax, i_woz, i_assets, i_monthly_rent
- type_of_income for income-source counts
- fiscal_partner, k_not_wealthy, k_aow
- k_social_rent > 0 for social-housing tenants
"""

from __future__ import annotations

import os

import pandas as pd

DATA_PATH = os.path.join("data", "NL_persons_headers_preprocessed_equal_weights.xlsx")
OUT_PATH = os.path.join("output", "tables", "table_descriptives_nl_case.tex")
N_TAXPAYERS = 13_500
WEIGHT_DISPLAY_SCALE = 1_000_000  # data weights are 1e-3; table reports 1,000


def fmt_int(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", "{,}")


def fmt_pct(count: int, total: int, decimals: int = 1) -> str:
    return f"{100 * count / total:.{decimals}f}\\%"


def fmt_eu_decimal(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def cont_row(label: str, series: pd.Series) -> str:
    return (
        f"{label} & {N_TAXPAYERS:,} & {fmt_int(series.mean())} & "
        f"{fmt_int(series.std())} & {fmt_int(series.median())} & "
        f"{fmt_int(series.min())} & {fmt_int(series.max())} \\\\"
    )


def cat_row(label: str, count: int) -> str:
    return f"{label} & ${count:,}$ & {fmt_pct(count, N_TAXPAYERS)} \\\\"


def main() -> None:
    df = pd.read_excel(DATA_PATH)
    if len(df) != N_TAXPAYERS:
        raise ValueError(f"expected {N_TAXPAYERS} rows, found {len(df)}")

    income_counts = df["type_of_income"].value_counts()
    wealthy = int((df["k_not_wealthy"] == 0).sum())
    not_wealthy = int((df["k_not_wealthy"] == 1).sum())
    pension_yes = int((df["k_aow"] == 1).sum())
    pension_no = int((df["k_aow"] == 0).sum())
    fiscal_yes = int((df["fiscal_partner"] == "yes").sum())
    fiscal_no = int((df["fiscal_partner"] == "no").sum())
    social_rent = int((df["k_social_rent"] > 0).sum())
    kids = df["i_number_of_kids"]
    weight_display = df["weight"].iloc[0] * WEIGHT_DISPLAY_SCALE

    rows = [
        cont_row("Income before tax", df["income_before_tax"]),
        cont_row("Home value", df["i_woz"]),
        cont_row("Assets", df["i_assets"]),
        cont_row("Monthly rent", df["i_monthly_rent"]),
        f"Social rent  & {social_rent:,} & {fmt_eu_decimal(100 * social_rent / N_TAXPAYERS)}\\% \\\\",
        cat_row("Income: benefits", int(income_counts["benefits"])),
        cat_row("Income: employment", int(income_counts["employment"])),
        cat_row("Income: self-employed", int(income_counts["ZZP"])),
        cat_row("Wealth: wealthy$^\\dagger$", wealthy),
        cat_row("Wealth: not wealthy$^\\dagger$", not_wealthy),
        cat_row("Fiscal partner: yes", fiscal_yes),
        cat_row("Fiscal partner: no", fiscal_no),
        cat_row("Pension age: yes", pension_yes),
        cat_row("Pension age: no", pension_no),
        (
            f"Number of children & {N_TAXPAYERS:,} & "
            f"{fmt_eu_decimal(kids.mean(), 2)} & {fmt_eu_decimal(kids.std(), 2)} & "
            f"{fmt_int(kids.median())} & {fmt_int(kids.min())} & {fmt_int(kids.max())} \\\\"
        ),
        (
            f"Weight & {N_TAXPAYERS:,} & {fmt_int(weight_display)} & 0 & "
            f"{fmt_int(weight_display)} & {fmt_int(weight_display)} & "
            f"{fmt_int(weight_display)} \\\\"
        ),
    ]

    tex = "\n".join(
        [
            "",
            "\\begin{table}[!t] \\centering",
            "  \\footnotesize",
            "  \\caption{Descriptive Statistics: Simulated real-world case}",
            "  \\label{table: desc_case_4}",
            "\\begin{tabular}{@{\\extracolsep{5pt}}lcccccc}",
            "\\\\[-1.8ex]\\hline",
            "\\hline \\\\[-1.8ex]",
            "Statistic & \\multicolumn{1}{c}{N} & \\multicolumn{1}{c}{Mean} & "
            "\\multicolumn{1}{c}{St. Dev.} & \\multicolumn{1}{c}{Median} & "
            "\\multicolumn{1}{c}{Min} & \\multicolumn{1}{c}{Max} \\\\",
            "\\hline \\\\[-1.8ex]",
            *rows,
            "\\hline \\\\[-1.8ex]",
            "\\multicolumn{7}{l}{\\footnotesize{$^\\dagger$Wealth is defined as having assets above \\euro 57\\,000.}} \\\\",
            "\\end{tabular}",
            "\\end{table}",
            "",
        ]
    )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(tex)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
