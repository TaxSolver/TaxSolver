"""Unit tests for DataLoader.from_multiple_files."""
import tempfile
import pandas as pd
from TaxSolver.data_wrangling.data_loader import DataLoader


def _create_temp_csv(df: pd.DataFrame):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    df.to_csv(tmp.name, index=False)
    return tmp.name


def test_from_multiple_files_combines_households():
    # Create two small data sets with disjoint household IDs
    df1 = pd.DataFrame(
        {
            "id": ["1"],
            "hh_id": ["A"],
            "mirror_id": [None],
            "income_before_tax": [10],
            "income_after_tax": [9],
        }
    )
    df2 = pd.DataFrame(
        {
            "id": ["2"],
            "hh_id": ["B"],
            "mirror_id": [None],
            "income_before_tax": [20],
            "income_after_tax": [18],
        }
    )

    path1 = _create_temp_csv(df1)
    path2 = _create_temp_csv(df2)

    dl = DataLoader.from_multiple_files(
        [path1, path2],
        income_before_tax="income_before_tax",
        income_after_tax="income_after_tax",
        id="id",
        hh_id="hh_id",
        mirror_id="mirror_id",
    )

    households = dl.households
    assert len(households) == 2
    assert "A" in households and "B" in households

    # Clean up temp files
    import os

    os.unlink(path1)
    os.unlink(path2)
