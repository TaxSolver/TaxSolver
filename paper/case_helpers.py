"""Shared helper functions for paper notebooks.

This module contains common utilities used across case_1.ipynb, case_2.ipynb, and case_3.ipynb.
"""

from __future__ import annotations

import os
from typing import List, Dict, Tuple, Optional

import pandas as pd

# SHARED IMPORTS FOR NOTEBOOKS


# TEXT FORMATTING FUNCTIONS
def euro_format(x: float, pos: int) -> str:
    """Format numbers as euro amounts with K for thousands.

    Used as a matplotlib FuncFormatter callback.

    Args:
        x: The value to format
        pos: The tick position (required by FuncFormatter but not used)

    Returns:
        Formatted string like "€25K"
    """
    return f"€{x/1000:.0f}K"


def euro_format_full(x: float, pos: int) -> str:
    """Format numbers as full euro amounts (no K abbreviation).

    Used as a matplotlib FuncFormatter callback.

    Args:
        x: The value to format
        pos: The tick position (required by FuncFormatter but not used)

    Returns:
        Formatted string like "€25,000"
    """
    return f"€{x:,.0f}"


# BRACKET WRANGLING
def wrangle_intervals(
    df_intervals: pd.DataFrame,
    df_taxpayers: pd.DataFrame,
    filter_var: Optional[str] = None,
    filter_rule: Optional[str] = None,
    income_col: str = "income_before_tax",
) -> pd.DataFrame:
    """Prepare bracket intervals for plotting by setting max bracket to observed max income.

    Args:
        df_intervals: DataFrame with bracket definitions (bracket_start, bracket_end, rate)
        df_taxpayers: DataFrame with taxpayer data
        filter_var: Optional filter on 'target_var' or 'var_name' column
        filter_rule: Optional filter on 'rule_family' column
        income_col: Column name for income in df_taxpayers

    Returns:
        Processed DataFrame with last bracket_end set to max observed income
    """
    df_intervals = df_intervals.copy()

    if filter_var:  # Filter on target variable or variable name
        if "target_var" in df_intervals.columns:
            df_intervals = df_intervals.loc[df_intervals["target_var"] == filter_var]
        elif "var_name" in df_intervals.columns:
            df_intervals = df_intervals.loc[df_intervals["var_name"] == filter_var]

    if filter_rule:
        if "rule_family" in df_intervals.columns:
            df_intervals = df_intervals.loc[df_intervals["rule_family"] == filter_rule]

    # Reset index
    df_intervals = df_intervals.reset_index(drop=True)

    # Set last bracket end to max observed income
    if len(df_intervals) > 0:
        df_intervals.iloc[
            -1, df_intervals.columns.get_loc("bracket_end")
        ] = df_taxpayers[income_col].max()

    return df_intervals


def build_tax_line(
    df_intervals: pd.DataFrame,
    start_y: float = 0,
) -> Tuple[List[float], List[float], float]:
    """Build x,y values for a tax line from bracket intervals.

    Creates coordinates for plotting a piecewise linear tax function.

    Args:
        df_intervals: DataFrame with columns 'bracket_start', 'bracket_end', 'rate'
        start_y: Starting y value (usually 0 for tax amount)

    Returns:
        Tuple of (x_values, y_values, final_y) where:
        - x_values: List of x coordinates for plotting
        - y_values: List of y coordinates for plotting
        - final_y: The final y value after all brackets
    """
    x_values: List[float] = []
    y_values: List[float] = []
    current_y = start_y

    for _, row in df_intervals.iterrows():
        x_start = row["bracket_start"]
        x_end = row["bracket_end"]
        rate = row["rate"]

        x_interval = [x_start, x_end]
        y_interval = [current_y, current_y + (x_end - x_start) * rate]

        x_values.extend(x_interval)
        y_values.extend(y_interval)
        current_y = y_interval[1]

    return x_values, y_values, current_y


# TAX CALCULATION HELPERS
def get_marginal_rate(
    income: float,
    bracket_rates: Dict[Tuple[float, float], float],
) -> float:
    """Get the marginal tax rate for a given income level.

    Args:
        income: The income level to check
        bracket_rates: Dict mapping (lower_bound, upper_bound) tuples to rates

    Returns:
        The marginal tax rate for the given income
    """
    sorted_brackets = sorted(bracket_rates.items(), key=lambda x: x[0][0])
    for (lb, ub), rate in sorted_brackets:
        if lb <= income < ub:
            return rate
    # If income exceeds final cutoff, use the highest bracket rate
    return list(sorted_brackets)[-1][1]


def calculate_tax(
    income: float,
    bracket_rates: Dict[Tuple[float, float], float],
) -> float:
    """Calculate total tax for a given income using progressive brackets.

    Args:
        income: The income to calculate tax for
        bracket_rates: Dict mapping (lower_bound, upper_bound) tuples to rates

    Returns:
        The total tax amount
    """
    sorted_brackets = sorted(bracket_rates.items(), key=lambda x: x[0][0])
    tax = 0.0
    remaining_income = income

    for (lb, ub), rate in sorted_brackets:
        if remaining_income <= 0:
            break
        taxable_in_bracket = min(remaining_income, ub - lb)
        if taxable_in_bracket > 0:
            tax += taxable_in_bracket * rate
            remaining_income -= taxable_in_bracket

    return tax


def get_sq_marginal_rate_case1(income: float) -> float:
    """Get the status quo marginal rate for case 1 (outcome_1 tax system).

    This matches the tax brackets that generated outcome_1 in the simulation.

    Args:
        income: Income level

    Returns:
        Marginal tax rate
    """
    if income < 25_000:
        return 0.10
    elif income < 50_000:
        return 0.20
    elif income < 75_000:
        return 0.30
    elif income < 100_000:
        return 0.40
    else:
        return 0.50


# DATA LOADING HELPERS
def load_simple_simul_data(
    outcome_col: str,
    data_dir: str = "data",
    filename: str = "simple_simul_1000.xlsx",
    n_rows: Optional[int] = None,
) -> pd.DataFrame:
    """Load the simple simulation data with appropriate preprocessing.

    Args:
        outcome_col: Column name for the outcome (e.g., 'outcome_1', 'outcome_2', 'outcome_3')
        data_dir: Directory containing the data file
        filename: Name of the Excel file
        n_rows: Optional number of rows to load (None for all)

    Returns:
        DataFrame with 'tax' and 'hh_id' columns added
    """
    file_path = os.path.join(data_dir, filename)
    df = pd.read_excel(file_path)

    if n_rows is not None:
        df = df.iloc[:n_rows, :].copy()

    df["tax"] = df["income_before_tax"] - df[outcome_col]
    df["hh_id"] = df.index

    return df


def filter_low_income_households(
    households: dict,
    income_threshold: float = 70_000,
) -> list:
    """Filter households below an income threshold.

    Args:
        households: Dictionary of household objects from DataLoader
        income_threshold: Income threshold for filtering

    Returns:
        List of household objects below the threshold
    """
    return [
        hh
        for hh in households.values()
        if hh.members[0]["income_before_tax"] < income_threshold
    ]
