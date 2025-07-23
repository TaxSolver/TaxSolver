import pandas as pd
from TaxSolver.backend.abstract_backend import AbstractBackend
from TaxSolver.population.household import Household
from TaxSolver.population.person import Person
from TaxSolver.rule import TaxRule
from TaxSolver.brackets import Brackets

# from TaxSolver.solved_system import SolvedSystem
from typing import Optional
from TaxSolver.constraints.constraint import Constraint
from TaxSolver.objective import Objective
from TaxSolver.backend import CvxpyBackend


class TaxSolver:
    def __init__(
        self,
        households: dict[str, Household],
        backend: AbstractBackend = CvxpyBackend(),
        name: str = "TaxModel",
    ):
        assert self._check_unique_ids(households), "Not all ids are unique strings!"
        self.objective: Optional[Objective] = None
        self.constraints: list[Constraint] = []
        self.backend = backend

        self.rules: list[TaxRule] = []
        self.households: dict[str, Household] = households
        self.name = name

        self.solved = False

        for hh in self.households.values():
            hh.assign_to_system(self)

    def add_objective(self, objective: Objective):
        """
        Define objective of the solver
        """
        self.objective = objective

    def add_rules(self, rules: list[TaxRule]) -> None:
        """
        Bind every rule to solver.
        If a rule is Brackets it may spawn child FlatTaxRules.
        """
        for rule in rules:
            if isinstance(rule, Brackets):
                rule.bind_and_initialize(self)
                self.rules.extend(rule.flat_rules)
            else:
                rule.bind_and_initialize(self)
                self.rules.append(rule)

    def add_constraints(self, constraints: list[Constraint]):
        self.constraints.extend(constraints)

    def solve(self):
        if not self.objective:
            raise ValueError("Objective not set, please add an objective first.")

        # Set rules on person level
        [p.update_solver_variables(self.rules) for p in self.people.values()]

        # Set rules on household level
        [hh.update_solver_variables(self.rules) for hh in self.households.values()]

        # Apply all constraints now that the model is fully built
        for constraint in self.constraints:
            constraint.apply(self)

        # Bind and set the objective now that all variables are created
        self.objective.bind_solver_and_set_objective(self)

        # Solve the problem
        print("Going to solve!")
        self.backend.solve()

        if self.backend.get_sol_count() > 0:
            print("Found at least one feasible solution!")
            self.solved = True
        else:
            raise ValueError("No feasible solution found :-(")

    def close(self):
        self.backend.close()

    def rules_and_rates_table(self):
        if self.solved:
            return pd.DataFrame(
                [
                    {
                        "rule_name": rule.name,
                        "rule_type": rule.__class__.__name__,
                        "var_name": ":".join(rule.var_name),
                        "rate": float(self.backend.get_value(rule.rate)),
                        "b": int(self.backend.get_value(rule.b)),
                        "weight": rule.weight,
                    }
                    for rule in self.rules
                ]
            )
        else:
            ValueError("System not solved yet")

    def __repr__(self) -> str:
        if self.name:
            return self.name
        else:
            return "Anonymous TaxSolver"

    def get_rule(self, rule_name: str) -> TaxRule:
        rule = [r for r in self.rules if r.name == rule_name]
        if len(rule) == 0:
            raise ValueError(f"Rule {rule_name} not found")
        elif len(rule) > 1:
            raise ValueError(f"Multiple rules found for {rule_name}")
        return rule[0]

    def _check_unique_ids(self, households: dict[str, Household]):
        hh_ids = [hh.id for hh in households.values()]
        person_ids = [
            person["id"] for hh in households.values() for person in hh.members
        ]
        ids = hh_ids + person_ids
        return len(ids) == len(set(ids)) and all(
            [isinstance(i, str) for i in ids]
        )  # Check if all ids are unique strings and are type string

    @property
    def rule_weight(self):
        return self.backend.quicksum([rule.b for rule in self.rules])

    @property
    def people(self) -> dict[str, Person]:
        return {
            person["id"]: person
            for hh in self.households.values()
            for person in hh.members
        }

    @property
    def people_with_labor_effects(self) -> dict[str, Person]:
        return {
            person["id"]: person
            for hh in self.households.values()
            for person in hh.members
            if person.init_labor_effect_weight is not None
        }

    @property
    def inputs(self):
        # Returns a list of input variable names from the first person in the first household
        first_household = next(iter(self.households.values()))
        first_person = first_household.members[0]
        return [
            i
            for i in first_person.data
            if i.startswith("income_before_tax")
            or i.startswith("household_income_before_tax")
            or i.startswith("i_")
        ]

    @property
    def groups(self):
        # Returns a list of input variable names from the first person in the first household
        first_household = next(iter(self.households.values()))
        first_person = first_household.members[0]
        return [i for i in first_person.data if i.startswith("k_")]
