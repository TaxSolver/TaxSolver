import pandas as pd
from dataclasses import dataclass
import operator
from functools import reduce
from .rule_record import RuleRecord
from TaxSolver.population.household import Household
from TaxSolver.population.person import Person
from TaxSolver.rule import TaxRule


@dataclass
class RuleOutcome:
    entity_id: str
    rule: RuleRecord
    amount: float
    marginal_pressure: float
    weighted_amount: float

    def __repr__(self) -> str:
        return f"{self.person} - {self.rule}: {self.tax}"

    def _to_dict(self):
        return {
            "entity_id": self.entity_id,
            "rule_name": self.rule.name,
            "rule_type": self.rule.type,
            "amount": self.amount,
            "marginal_pressure": self.marginal_pressure,
            "weighted_amount": self.weighted_amount,
        }


class SolvedSystem:
    def __init__(
        self, rule_records: list[RuleRecord], households: dict[str:Household]
    ) -> None:
        self.rules = rule_records

        self.households: dict[str:Household] = households
        self.people: list[Person] = [
            person
            for household in self.households.values()
            for person in household.members
        ]

        self._check_necessary_keys_present()

        self.rule_outcomes: pd.DataFrame = self._calculate_rule_outcomes(self.rules)

    @classmethod
    def from_solved_system(cls, system):
        rule_records = []
        for rule in system.rules:
            rule: TaxRule
            record = RuleRecord.from_rule(rule)
            rule_records.append(record)
        return cls(rule_records, system.households)

    @classmethod
    def from_rules_and_rates_table(
        cls, rules_and_rates: pd.DataFrame, households: dict[str:Household]
    ):
        rule_records = list(RuleRecord.from_rules_and_rates_table(rules_and_rates))
        return cls(rule_records, households)

    def _calculate_rule_outcomes(self, rules):
        outcomes: list[RuleOutcome] = []
        for person in self.people:
            for rule in rules:
                rule: RuleRecord
                if rule.type in [
                    "TaxRule",
                    "FlatTaxRule",
                    "BenefitRule",
                    "BracketRule",
                    "ExistingBenefit",
                ]:
                    outcomes.append(self._calculate_outcome(person, rule))
                elif not rule.type == "HouseholdBenefit":
                    raise ValueError(f"Rule {rule.type} is not a valid rule type")
        for household in self.households.values():
            household: Household
            for rule in rules:
                if rule.type == "HouseholdBenefit":
                    outcome = self._calculate_outcome(
                        household.first_member, rule, entity_type="household"
                    )
                    outcomes.append(outcome)

        return pd.DataFrame([outcome._to_dict() for outcome in outcomes])

    def _calculate_outcome(
        self, person: Person, rule: RuleRecord, entity_type: str = "person"
    ):
        # There might be one or more variable names passed that the rule responds to
        if rule.type != "ExistingBenefit":
            vals: list[float] = [
                person[v] for v in rule.var_name
            ]  # Get variable values
            product: float = reduce(
                operator.mul, vals, 1
            )  # Get product of all the variables
        else:
            product = 1

        if product == 0:
            amount = 0
            marginal_pressure = 0
        elif rule.type == "TaxRule" or rule.type == "FlatTaxRule":
            amount = -1 * product * rule.rate
            marginal_pressure = 0
            if rule.name in [r.name for r in person.marginal_rate_rules]:
                marginal_pressure = rule.rate
        elif rule.type == "BenefitRule" or rule.type == "HouseholdBenefit":
            amount = product * rule.rate
            marginal_pressure = 0
        elif rule.type == "BracketRule":
            amount = -1 * product * rule.rate
            marginal_pressure = 0
            if rule.name in [r.name for r in person.marginal_rate_rules]:
                marginal_pressure = rule.rate
        elif rule.type == "ExistingBenefit":
            amount = person["sq_a_" + rule.name] * rule.rate
            marginal_pressure = person["sq_m_" + rule.name] * rule.rate
        else:
            raise ValueError(f"Rule type {rule.type} not recognized")

        weighted_amount = amount * person.weight

        return RuleOutcome(
            entity_id=person["id"] if entity_type == "person" else person.household.id,
            rule=rule,
            amount=amount,
            marginal_pressure=marginal_pressure,
            weighted_amount=weighted_amount,
        )

    def calculate_net_incomes(self):
        tax_balance: pd.DataFrame = (
            self.rule_outcomes[["entity_id", "amount"]]
            .groupby("entity_id")
            .aggregate("sum")
        )
        net_incomes = []
        for hh in self.households.values():
            hh: Household
            gross_income = sum(person["income_before_tax"] for person in hh.members)
            p_balance = sum(
                tax_balance.loc[person["id"]]["amount"] for person in hh.members
            )

            if hh.id not in tax_balance.index:
                hh_balance = 0
            else:
                hh_balance = tax_balance.loc[hh.id]["amount"]

            net_income = gross_income + p_balance + hh_balance
            net_incomes.append(
                {
                    "hh_id": hh.id,
                    "household_income_before_tax": gross_income,
                    "new_household_benefits": hh_balance,
                    "new_net_income": net_income,
                }
            )

        return pd.DataFrame(net_incomes)

    def calculate_marginal_pressure(self):
        people_ids = [person["id"] for person in self.people]
        marginal_pressures: pd.DataFrame = (
            self.rule_outcomes[["entity_id", "marginal_pressure"]]
            .groupby("entity_id")
            .aggregate("sum")
        )
        marginal_pressures.rename(
            columns={"marginal_pressure": "new_marginal_pressure"}, inplace=True
        )
        return marginal_pressures.loc[people_ids]

    def get_max_marginal_pressure_in_hh(self):
        marginal_pressures = self.calculate_marginal_pressure()
        marginal_pressures = pd.merge(
            left=marginal_pressures,
            right=self.get_hh_person_join_table(),
            left_index=True,
            right_on="person_id",
        )
        return (
            marginal_pressures.drop("person_id", axis=1)
            .groupby("hh_id")
            .aggregate("max")
        )

    def get_hh_person_join_table(self):
        df_list = []
        for hh in self.households.values():
            for person in hh.members:
                df_list.append({"hh_id": hh.id, "person_id": person["id"]})
        return pd.DataFrame(df_list)

    def get_household_characteristics(self):
        df_list = []
        for household in self.households.values():
            household: Household = household

            # Add all k_ group variables from household's first member
            k_group_items = {
                k: v
                for k, v in household.first_member.data.items()
                if k.startswith("k_")
            }
            df_list.append(
                {
                    "hh_id": household.id,
                    "weight": household.weight,
                    "marginal_rate_current": max(
                        [
                            m.data.get("marginal_rate_current", None)
                            for m in household.members
                        ]
                    ),
                    "employment_type": household.first_member.data.get(
                        "type_of_income", None
                    ),
                    "aow": household.first_member.data.get("k_aow", None),
                    "fiscal_partner": household.first_member.data.get(
                        "fiscal_partner", None
                    ),
                    "partner_income": household.first_member.data.get(
                        "partner_income", None
                    ),
                    "i_woz": household.first_member.data.get("i_woz", None),
                    "i_number_of_kids": household.first_member.data.get(
                        "i_number_of_kids", None
                    ),
                    "sq_net_income": sum(
                        [m.data["income_after_tax"] for m in household.members]
                    ),
                    "poverty_line": household.first_member.data.get("poverty_line", 0),
                    # Fixtures do not have poverty lines, if not there, there is no poverty line
                    "alleenverdiener": household.first_member.data.get(
                        "k_single_earner", None
                    ),
                    **k_group_items,
                }
            )

        return pd.DataFrame(df_list)

    def get_household_table(self):
        characteristics = self.get_household_characteristics()
        incomes = self.calculate_net_incomes()
        marginal_pressuress = self.get_max_marginal_pressure_in_hh()

        return pd.merge(
            left=pd.merge(incomes, characteristics, on="hh_id"),
            right=marginal_pressuress,
            left_on="hh_id",
            right_index=True,
        )

    def _check_necessary_keys_present(self):
        all_var_keys = []
        for rule in self.rules:
            if rule.type == "ExistingBenefit":
                all_var_keys.extend(rule.var_name)
            elif isinstance(rule.var_name, str):
                all_var_keys.extend(rule.var_name)
            else:
                all_var_keys.extend(rule.var_name)
        all_var_keys = set(all_var_keys)

        for person in self.people:
            for key in all_var_keys:
                person[key]  # Just check they don't throw a key error

    def calculate_tax_balance(self):
        incomes = self.get_household_table()
        old_balance = sum(
            (incomes["sq_net_income"] - incomes["household_income_before_tax"])
            * incomes["weight"]
        )
        new_balance = sum(self.rule_outcomes["weighted_amount"])
        return {
            "old_balance": old_balance,
            "new_balance": new_balance,
            "diff_balance": new_balance - old_balance,
        }

    def calculate_max_marginal_pressure(self):
        old_max_marginal_pressure = max(
            self.get_household_characteristics()["marginal_rate_current"]
        )
        new_max_marginal_pressure = max(
            self.get_household_table()["new_marginal_pressure"]
        )
        return {
            "old_max_marginal_pressure": old_max_marginal_pressure,
            "new_max_marginal_pressure": new_max_marginal_pressure,
        }

    def calculate_complexity_score(self):
        return sum([r.b * r.weight for r in self.rules])

    def calculate_poverty_rate(self):
        hh_table = self.get_household_table()
        hh_table["b_poverty_old"] = hh_table["sq_net_income"] < hh_table["poverty_line"]
        hh_table["b_poverty_new"] = (
            hh_table["new_net_income"] < hh_table["poverty_line"]
        )

        return {
            "poverty_rate_old": sum(hh_table["b_poverty_old"] * hh_table["weight"]),
            "poverty_rate_new": sum(hh_table["b_poverty_new"] * hh_table["weight"]),
        }

    def get_new_cashflows_for_household(self, hh_id):
        ids = self.get_hh_person_join_table().query(f"hh_id == '{hh_id}'")[
            "person_id"
        ].to_list() + [hh_id]
        household_outcomes = self.rule_outcomes[
            self.rule_outcomes["entity_id"].isin(ids)
        ]
        household_outcomes = household_outcomes[household_outcomes["amount"] != 0]
        household_outcomes = household_outcomes.groupby(["entity_id", "rule_name"]).sum(
            "amount"
        )
        return household_outcomes
