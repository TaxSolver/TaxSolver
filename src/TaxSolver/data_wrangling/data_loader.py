import pandas as pd
from typing import Union, Dict, List
from TaxSolver.population.person import Person
from TaxSolver.population.household import Household


class DataLoader:
    """
    Loads and processes tabular input data for TaxSolver analysis.

    The DataLoader class is responsible for reading data from Excel, CSV, or pandas DataFrame sources,
    validating and renaming columns, handling special variables, and constructing person and household
    objects for TaxSolver analysis.

    TaxSolver requires households and persons to be defined in the input data. In addition, every person
    must have an income_before_tax, income_after_tax column, weight, and household ID. Column names for
    each have to be provided to DataLoader, which will rename them to standard names.

    In addition, the user can specify additional input variables and group variables to create tax groups.

    Parameters
    ----------
    path : str or pandas.DataFrame
        Path to the input data file ('.xlsx' or '.csv') or a pandas DataFrame.
    income_before_tax : str, optional
        Name of the column representing income before tax (default: "income_before_tax").
    income_after_tax : str, optional
        Name of the column representing income after tax (default: "income_after_tax").
    id : str, optional
        Name of the column representing the person ID (default: "id").
    weight : str, optional
        Name of the column representing the observation weight (default: "weight").
    hh_id : str, optional
        Name of the column representing the household ID (default: "hh_id").
    mirror_id : str, optional
        Name of the column representing the mirror household ID (default: "mirror_id").
    input_vars : list of str, optional
        List of additional input variable column names.
    group_vars : list of str, optional
        List of group variable column names to be one-hot encoded.
    tax_rules : dict or list, optional
        Tax rule mapping or list of tax rule column names.
    special_vars : list of str, optional
        List of required variables for TaxSolver to function correctly.
    prefixes : list of str, optional
        List of prefixes for variable selection (default: ["i_", "k_", "sq_a_", "sq_m_"]).
    ids : list of str, optional
        List of ID column names (default: ["id", "hh_id", "mirror_id", "weight"]).

    Attributes
    ----------
    df : pandas.DataFrame
        The processed DataFrame containing the selected and renamed columns.
    people : dict
        Dictionary mapping person IDs to Person objects.
    households : dict
        Dictionary mapping household IDs to Household objects.

    Methods
    -------
    from_multiple_files(paths, **kwargs)
        Class method to load and merge data from multiple files.
    _input_validation()
        Validates and processes input columns, renaming and filling as needed.
    _select_columns()
        Selects columns based on special variables, IDs, and prefixes.
    _create_people_and_households()
        Constructs Person and Household objects from the DataFrame.
    _set_mirror_households()
        Sets mirror household references for each household.
    _plot_inputs(input_dict, group, return_df, partwise)
        Plots or returns input/output variable relationships.
    _set_labor_effects_weight()
        Sets initial labor effect weights for each person.

    Examples
    --------
    >>> loader = DataLoader("data/input.csv", group_vars=["region", "gender"])
    >>> print(loader.df.head())
    >>> print(loader.households.keys())
    >>> loader._plot_inputs({"income_before_tax": "income_after_tax"}, group="region")
    """

    def __init__(
        self,
        path,
        income_before_tax: str = "income_before_tax",
        income_after_tax: str = "income_after_tax",
        id: str = "id",
        weight: str = "weight",
        hh_id: str = "hh_id",
        mirror_id: str = "mirror_id",
        input_vars: List[str] = None,
        group_vars: List[str] = None,
        tax_rules: Union[Dict, List] = None,
        special_vars: List[str] = None,
        prefixes: List[str] = None,
        ids: List[str] = None,
    ) -> None:
        # Assign settings
        self.income_before_tax = income_before_tax
        self.income_after_tax = income_after_tax
        self.id = id
        self.weight = weight
        self.hh_id = hh_id
        self.mirror_id = mirror_id
        self.input_vars = input_vars or []
        self.group_vars = group_vars or []
        self.tax_rules = tax_rules or []
        self.special_vars = special_vars or [
            "income_before_tax",
            "income_after_tax",
            "household_income_before_tax",
            "household_income_after_tax",
            "marginal_rate_current",
            "elasticity",
        ]
        self.prefixes = prefixes or ["i_", "k_", "sq_a_", "sq_m_"]
        self.ids = ids or ["id", "hh_id", "mirror_id", "weight"]
        self.df = self._load_data(path)

        self._input_validation()
        self._select_columns()
        self._create_people_and_households()
        self._set_mirror_households()
        self._set_labor_effects_weight()

    @staticmethod
    def _load_data(path: Union[str, pd.DataFrame]) -> pd.DataFrame:
        ## Load data from file or DataFrame
        if isinstance(path, str) and path.endswith(".xlsx"):
            print("Loading data from Excel file...")
            df = pd.read_excel(
                path, dtype={"id": str, "hh_id": str, "mirror_id": str}, na_filter=False
            )
            df = df.where(df != "", None)
        elif isinstance(path, str) and path.endswith(".csv"):
            print("Loading data from CSV file...")
            df = pd.read_csv(
                path, dtype={"id": str, "hh_id": str, "mirror_id": str}, na_filter=False
            )
            df = df.where(df != "", None)
        elif isinstance(path, pd.DataFrame):
            print("Directly loading from pd.DataFrame...")
            df = path
        else:
            raise ValueError(
                "data should be either a file path (str) pointing at a CSV/XLSX file or a pandas DataFrame"
            )
        return df

    @classmethod
    def from_multiple_files(cls, paths: list[str], **kwargs):
        """Loads input data for the scenario."""
        households = {}

        # Load households from datasets
        for path in paths:
            ipo_set = DataLoader(path, **kwargs)
            households.update(ipo_set.households)
            print(f"Loaded households from dataset: {path}")
        ipo_set.households = households
        return ipo_set

    def _input_validation(self):
        if self.income_before_tax:
            if self.income_before_tax in self.df.columns:
                self.df.rename(
                    columns={self.income_before_tax: "income_before_tax"}, inplace=True
                )
            else:
                print(
                    f"Warning: '{self.income_before_tax}' column specified as income before tax but not found in the dataframe."
                )
                if "income_before_tax" in self.df.columns:
                    print("Using 'income_before_tax' as the income before tax column.")

        assert (
            "income_before_tax" in self.df.columns
        ), "income_before_tax column not found in the dataframe. Aborting."

        if self.income_after_tax:
            if self.income_after_tax in self.df.columns:
                self.df.rename(
                    columns={self.income_after_tax: "income_after_tax"}, inplace=True
                )
            else:
                print(
                    f"Warning: '{self.income_after_tax}' column specified as income before tax but not found in the dataframe."
                )
                if "income_after_tax" in self.df.columns:
                    print("Using 'income_after_tax' as the income before tax column.")

        assert (
            "income_after_tax" in self.df.columns
        ), "income_after_tax column not in the dataframe. Aborting."

        if self.weight:
            if self.weight in self.df.columns:
                self.df.rename(columns={self.weight: "weight"}, inplace=True)
            else:
                print(
                    f"Warning: '{self.weight}' column specified as weight but not found in the dataframe. Variable 'weight' set to 1 as default."
                )
                if "weight" in self.df.columns:
                    print("Using 'weight' as the weight column.")
        if "weight" not in self.df.columns:
            self.df["weight"] = 1
            print("Setting 'weight' to 1 as default.")

        if self.id:
            if self.id in self.df.columns:
                self.df.rename(columns={self.id: "id"}, inplace=True)
            else:
                print(
                    f"Warning: '{self.id}' column specified as person ID but not found in the dataframe."
                )
                if "id" in self.df.columns:
                    print("Using 'id' as the person ID column.")

        if "id" not in self.df.columns:
            self.df["id"] = self.df.index.astype(str)
            print("Setting index as the person ID column.")

        if self.hh_id:
            if self.hh_id in self.df.columns:
                self.df.rename(columns={"hh_id": self.hh_id}, inplace=False)
            else:
                print(
                    f"Warning: '{self.hh_id}' column specified as household ID but not found in the dataframe."
                )
                if "hh_id" in self.df.columns:
                    print("Using 'hh_id' as the household ID column.")
        if "hh_id" not in self.df.columns:
            self.df["hh_id"] = self.df["id"] + "_0"
            print("Setting f'person_id_0' as the household ID column.")

        # Ensure input_vars have 'i_' prefix
        if self.input_vars:
            formatted_input_vars = []
            for var in self.input_vars:
                if var in self.df.columns:
                    if not var.startswith("i_"):
                        formatted_input_vars.append("i_" + var)
                    else:
                        formatted_input_vars.append(var)
                else:
                    print(
                        f"Warning: '{var}' column specified as input variable but not found in the dataframe."
                    )

            self.df.rename(
                columns=dict(zip(self.input_vars, formatted_input_vars)), inplace=True
            )

        # Add household_income_before_tax as the sum of income_before_tax per hh_id
        self.df = self.df.assign(
            household_income_before_tax=self.df.groupby("hh_id")[
                "income_before_tax"
            ].transform("sum")
        )
        self.df = self.df.assign(
            household_income_after_tax=self.df.groupby("hh_id")[
                "income_after_tax"
            ].transform("sum")
        )

        if self.group_vars:
            for var in self.group_vars:
                if var in self.df.columns:
                    unique_values = self.df[var].nunique()
                    if unique_values > 100:
                        print(
                            f"Warning: '{var}' column has more than 100 unique values, which may lead to a large number of columns after one-hot encoding."
                        )

                    one_hot_encoded = pd.get_dummies(self.df[var], prefix="k_" + var)
                    self.df = pd.concat([self.df, one_hot_encoded], axis=1)
                    self.df.drop(columns=[var], inplace=True)
                else:
                    print(
                        f"Warning: '{var}' column specified as group variable but not found in the dataframe."
                    )

        if "k_everybody" in self.df.columns:
            print(
                "Warning: 'k_everybody' column specified in dataframe but reserved as a special group variable. Overwritten with value 1 for all rows."
            )
        self.df.loc[:, "k_everybody"] = 1

        if self.tax_rules:
            tax_rule_dict = {}
            rules_without_marginal = []
            if isinstance(self.tax_rules, dict):
                for key, value in self.tax_rules.items():
                    if key in self.df.columns:
                        ## Add rule renaming for absolute pressure column for each rule
                        tax_rule_dict[key] = "sq_a_" + key
                    else:
                        print(
                            f"Warning: absolute tax rule '{key}' not found in the dataframe."
                        )
                    if value in self.df.columns:
                        ## Add rule renaming for marginal pressure column for each rule
                        tax_rule_dict[value] = "sq_m_" + value
                    else:
                        ## Collect rules missing marginal pressure column
                        print(
                            f"Warning: marginal tax rule '{value}' not found in the dataframe."
                        )
                        rules_without_marginal.append("sq_m_" + key)

            elif isinstance(self.tax_rules, list):
                for key in self.tax_rules:
                    ## Add rule renaming for absolute pressure column for each rule
                    tax_rule_dict[key] = "sq_a_" + key
                    rules_without_marginal.append("sq_m_" + key)

            # Create columns for rules without marginal and set to 0
            for rule in rules_without_marginal:
                if rule not in self.df.columns:
                    self.df[rule] = 0
                    print(
                        f"Warning: No marginal pressure column created for '{rule.replace('sq_m_', '')}'. Set to 0."
                    )
            self.df.rename(columns=tax_rule_dict, inplace=False)

        if self.mirror_id:
            if self.mirror_id in self.df.columns:
                self.df.rename(columns={"mirror_id": self.mirror_id}, inplace=True)
            else:
                print(
                    f"Warning: '{self.mirror_id}' column specified as mirror ID but not found in the dataframe."
                )

        if "marginal_rate_current" not in self.df.columns:
            print(
                "Warning: marginal_rate_current not found in the dataframe. Setting to 0 as default."
            )
            self.df["marginal_rate_current"] = 0

    def _select_columns(self) -> None:
        def is_valid_column(column):
            return (
                column in self.special_vars
                or column in self.ids
                or any(column.startswith(prefix) for prefix in self.prefixes)
            )

        return self.df[[col for col in self.df.columns if is_valid_column(col)]]

    def _create_people_and_households(self) -> None:
        self.people = {}
        self.households = {}
        for hh_id in self.df["hh_id"].unique():
            members = self.df.loc[self.df["hh_id"] == hh_id]
            hh_members = []

            for i, member in members.iterrows():
                self.people[member.id] = Person(dict(member))
                hh_members.append(self.people[member.id])

            # Use first member's weight as household weight
            # This assumes all members of the household have the same weight
            self.households[str(hh_id)] = Household(
                str(hh_id), hh_members, weight=hh_members[0]["weight"]
            )

    def _set_mirror_households(self) -> None:
        warning_hhs_set = 0
        for hh_id, hh in self.households.items():
            try:
                if hh.members[0].data["mirror_id"]:
                    if not pd.isna(hh.members[0].data["mirror_id"]):
                        hh.mirror_hh = self.households[hh.members[0].data["mirror_id"]]
            except KeyError:
                hh.members[0].data["mirror_id"] = hh_id
                hh.mirror_hh = self.households[hh.members[0].data["mirror_id"]]
                warning_hhs_set += 1
        if warning_hhs_set > 0:
            print(
                f"Mirror household were missing for {warning_hhs_set} households: set to own id"
            )

    def _set_labor_effects_weight(self) -> None:
        mirror_ids = [
            p.data["mirror_id"]
            for p in self.people.values()
            if p.data.get("mirror_id", None)
        ]

        for p_id, p in self.people.items():
            if p.data.get("init_labor_effect_weight", None):
                p.init_labor_effect_weight = p.data["labor_effect_weight"]
            elif p.data.get("mirror_id", False) and p.data.get("elasticity", None):
                print(
                    f"Warning: labor_effects_weight not found for person {p['id']}. Using 1 as the default."
                )
                p.init_labor_effect_weight = 1
            elif p.data["hh_id"] in mirror_ids and p.data.get("elasticity", False):
                p.init_labor_effect_weight = 0
            else:
                p.init_labor_effect_weight = None
