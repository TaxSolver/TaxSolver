import numpy as np
from parameters import default_params
import random
import os
import pandas as pd

# Set seed for reproducibility
SEED = 1704
np.random.seed(SEED)
random.seed(SEED)


def include_rule(condition_attr):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if not getattr(self, condition_attr, True):
                return 0
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class DataSim:
    def __init__(
        self,
        income_before_tax,
        tax_group,
        household_size,
        id,
        hh_id,
        taxable_income_comb=0,
        partner=False,
        i_assets=0,
        i_assets_comb=0,
        i_children_ages=None,
        i_children=None,
        k_employment="all",
        k_single=0,
        k_couple=0,
        k_zzp=0,
        lowest_earner=False,
        precision=0,
        params=default_params,
    ):
        # system parameters
        self.params = params
        self.id = id
        self.hh_id = hh_id
        self.i_assets = i_assets
        self.i_assets_comb = i_assets_comb
        self.taxable_income_comb = taxable_income_comb
        self.i_children_ages = i_children_ages if i_children_ages else []
        self.i_children = i_children if i_children else 0
        self.k_employment = k_employment
        self.k_single = k_single
        self.k_couple = k_couple
        self.k_zzp = k_zzp
        self.lowest_earner = lowest_earner
        self.partner = partner
        self.precision = precision
        self.income_before_tax = income_before_tax
        self.tax_group = str(tax_group)
        self.household_size = household_size

    @property
    def taxable_income(self):
        return self.income_before_tax

    def calculate_progressive_tax(self):
        ib_rates = [i["rate"] for i in self.params["tax_brackets"][self.tax_group]]

        return round(
            self._progressive_tax(
                brackets=self.ib_brackets, rates=ib_rates, income=self.taxable_income
            ),
            self.precision,
        )

    def calculate_zvw_benefit(self, tax_group=False):
        if tax_group:
            if not self.partner:
                if self.i_assets > self.params["zvw_benefit"]["ztmaxv_a"]:
                    return 0

                single_max_benefit = self.params["zvw_benefit"]["zt_a"]
                income_related_deduction = max(
                    self.params["zvw_benefit"]["ztafb"]
                    * (self.taxable_income - self.params["zvw_benefit"]["wml"]),
                    0,
                )
                zt = single_max_benefit - income_related_deduction
            else:
                if self.i_assets_comb > self.params["zvw_benefit"]["ztmaxv_p"]:
                    return 0

                couple_max_benefit = self.params["zvw_benefit"]["zt_p"]
                income_related_deduction = max(
                    self.params["zvw_benefit"]["ztafb"]
                    * (
                        self.taxable_income_comb
                        - self.params["zvw_benefit"]["wml_couple"]
                    ),
                    0,
                )
                zt = (couple_max_benefit - income_related_deduction) / 2
        else:
            ## If not tax_group simply apply the non-partnered rules
            if self.i_assets > self.params["zvw_benefit"]["ztmaxv_a"]:
                return 0

            single_max_benefit = self.params["zvw_benefit"]["zt_a"]
            income_related_deduction = max(
                self.params["zvw_benefit"]["ztafb"]
                * (self.taxable_income - self.params["zvw_benefit"]["wml"]),
                0,
            )
            zt = single_max_benefit - income_related_deduction

        if zt < self.params["zvw_benefit"]["ztmin"]:
            return 0

        return round(zt, self.precision)

    def calculate_kb(self):
        if not self.lowest_earner:
            return 0

        if not self.i_children_ages:
            return 0

        cutoffs = [0] + [c["age_up_to"] for c in self.params["child_benefits"]]

        child_per_cutoff = [
            len([x for x in self.i_children_ages if cutoffs[i - 1] <= x < cutoffs[i]])
            for i in range(1, len(cutoffs))
        ]

        kb = sum(
            [
                child_per_cutoff[i] * self.params["child_benefits"][i]["benefit"]
                for i in range(len(child_per_cutoff))
            ]
        )

        return round(kb, self.precision)

    @property
    def ib_brackets(self):
        bracket_ends = [
            i["income_up_to"] for i in self.params["tax_brackets"][self.tax_group]
        ]
        return [(0, bracket_ends[0])] + [
            (bracket_ends[i], bracket_ends[i + 1])
            for i, b_e in enumerate(bracket_ends[:-1])
        ]

    def calculate_outcome(self, case="1"):
        if case == "1":
            self.net_income_pre_benefits = (
                self.income_before_tax - self.calculate_progressive_tax()
            )
        elif case == "2":
            self.net_income_pre_benefits = (
                self.income_before_tax
                - self.calculate_progressive_tax()
                + self.calculate_zvw_benefit()
                + self.calculate_kb()
            )
        elif case == "2_income_tax":
            self.net_income_pre_benefits = (
                self.calculate_progressive_tax() - self.calculate_zvw_benefit()
            )
        elif case == "2_children_tax":
            self.net_income_pre_benefits = self.calculate_kb()
        elif case == "3":
            self.net_income_pre_benefits = (
                self.income_before_tax
                - self.calculate_progressive_tax()
                + self.calculate_zvw_benefit(tax_group=True)
                + self.calculate_kb()
            )
        elif case == "3_income_tax":
            self.net_income_pre_benefits = (
                self.income_before_tax
                - self.calculate_progressive_tax()
                + self.calculate_zvw_benefit(tax_group=True)
            )
        elif case == "3":
            self.net_income_pre_benefits = (
                self.income_before_tax
                - self.calculate_progressive_tax()
                + self.calculate_zvw_benefit(tax_group=True)
                + self.calculate_kb()
            )

        self.net_income_post_benefits = self.net_income_pre_benefits

        self.taxes_paid = self.income_before_tax - self.net_income_post_benefits

        return self.net_income_post_benefits

    @staticmethod
    def _progressive_tax(
        brackets: list[tuple], rates: list[float], income: int, precision=0
    ):
        assert len(brackets) == len(rates)
        assert len(brackets) > 1

        tax_per_bracket = []
        for i, b in enumerate(brackets):
            if b[0] <= income < b[1]:
                income_in_bracket = income - b[0]
                tax_per_bracket.append(income_in_bracket * rates[i])
            elif income >= b[1]:
                income_in_bracket = b[1] - b[0]
                tax_per_bracket.append(income_in_bracket * rates[i])

        return round(sum(tax_per_bracket), precision)


class TaxpayerSimulator:
    def __init__(self, num_taxpayers):
        self.num_taxpayers = num_taxpayers
        self.households = self._generate_households()

    def _generate_households(self):
        taxpayers = [
            {
                "income_before_tax": round(np.random.uniform(10_000, 150_000)),
                "tax_group": random.randint(1, 4),
                "i_assets": round(np.random.uniform(0, 10_000)),
                "i_children_ages": [
                    random.randint(0, 17) for _ in range(random.randint(0, 3))
                ],
                "lowest_earner": True,
                "k_employment": random.choices(["zzp", "all"], weights=[0.4, 0.6])[0],
            }
            for _ in range(self.num_taxpayers)
        ]

        households = []
        i = 0

        while i < len(taxpayers):
            if i + 1 < len(taxpayers) and random.choice([True, False]):
                household = taxpayers[i : i + 2]
                i += 2
            else:
                household = [taxpayers[i]]
                i += 1
            households.append(household)

        return households

    def to_dataframe(self):
        data = []
        for hh_id, household in enumerate(self.households):
            id = 0
            for taxpayer in household:
                data.append(
                    {
                        "income_before_tax": taxpayer["income_before_tax"],
                        "tax_group": taxpayer["tax_group"],
                        "household_size": len(household),
                        "partner": len(household) > 1,
                        "i_assets": taxpayer["i_assets"],
                        "i_assets_comb": sum([t["i_assets"] for t in household]),
                        "k_single": len(household) == 1,
                        "k_couple": len(household) == 2,
                        "k_zzp": 1 if taxpayer["k_employment"] == "zzp" else 0,
                        "i_children_ages": taxpayer["i_children_ages"],
                        "i_children": len(taxpayer["i_children_ages"]),
                        "k_employment": taxpayer["k_employment"],
                        "lowest_earner": taxpayer["lowest_earner"],
                        "taxable_income_comb": sum(
                            [t["income_before_tax"] for t in household]
                        ),
                        "hh_id": hh_id,
                        "id": str(hh_id) + "_" + str(id),
                    }
                )
                id += 1

        return pd.DataFrame(data)


df_taxpayers = TaxpayerSimulator(1_000).to_dataframe()

## Add Jude and Laila
df_taxpayers.iloc[0, df_taxpayers.columns.get_loc("income_before_tax")] = 52_000
df_taxpayers.iloc[1, df_taxpayers.columns.get_loc("income_before_tax")] = 120_000

results_case_1 = []
results_case_2 = []
results_case_2_income = []
results_case_2_children = []
results_case_3 = []
results_case_3_income = []

row = df_taxpayers.iloc[0]

for _, row in df_taxpayers.iterrows():
    data_sim = DataSim(**row.to_dict())
    orig_group = data_sim.tax_group

    # results_group.append(data_sim.calculate_outcome())

    data_sim.tax_group = "all"
    results_case_1.append(data_sim.calculate_outcome(case="1"))
    results_case_2.append(data_sim.calculate_outcome(case="2"))
    results_case_2_income.append(data_sim.calculate_outcome(case="2_income_tax"))
    results_case_2_children.append(data_sim.calculate_outcome(case="2_children_tax"))

    data_sim.tax_group = data_sim.k_employment
    results_case_3_income.append(data_sim.calculate_outcome(case="3_income_tax"))
    results_case_3.append(data_sim.calculate_outcome(case="3"))

    # data_sim.tax_group = "reform_1_a"
    # results_reform_1_a.append(data_sim.calculate_outcome())

df_taxpayers["outcome_1"] = results_case_1
df_taxpayers["outcome_2"] = results_case_2
df_taxpayers["outcome_3"] = results_case_3
df_taxpayers["tax_2_income"] = results_case_2_income
df_taxpayers["tax_2_children"] = results_case_2_children
df_taxpayers["i_children_1"] = (df_taxpayers["i_children"] >= 1).astype(int)
df_taxpayers["i_children_2"] = (df_taxpayers["i_children"] >= 2).astype(int)
df_taxpayers["i_children_3"] = (df_taxpayers["i_children"] >= 3).astype(int)


df_taxpayers.loc[
    (df_taxpayers["outcome_2"] != df_taxpayers["outcome_3"])
    & (df_taxpayers["k_employment"] != "zzp")
]

# df_taxpayers['reform_1_a'] = results_reform_1_a

df_taxpayers.to_excel(os.path.join("data", "simple_simul_1000.xlsx"))
