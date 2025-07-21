from typing import Optional
from TaxSolver.population.household import Household
from TaxSolver.population.person import Person
from TaxSolver.constraints.constraint import Constraint


class BudgetConstraint(Constraint):
    def __init__(
        self,
        name: str,
        households: list[Household],
        max_bln_mut_expenditure: int,
        min_bln_mut_expenditure: Optional[int] = None,
    ) -> None:
        self.name = name
        self.max_bln_mut_expenditure = max_bln_mut_expenditure
        self.min_bln_mut_expenditure = min_bln_mut_expenditure
        self.households = households

    def apply(self, solver) -> None:
        backend = solver.backend
        current_expenditures = -sum(
            [
                p.weight * (p["income_before_tax"] - p["income_after_tax"])
                for p in self.people
            ]
        )
        print(f"Current tax balance {self.name}:", current_expenditures)
        self.current_expenditures = current_expenditures

        new_person_expenditures = [p.weighted_tax_balance for p in self.people]
        new_household_benefits = [
            hh.weighted_household_benefits for hh in self.households
        ]

        self.new_expenditures = backend.quicksum(
            new_person_expenditures + new_household_benefits
        )

        self.spend = self.new_expenditures - current_expenditures

        print(
            "New Maximum:",
            current_expenditures + self.max_bln_mut_expenditure,
        )

        backend.add_constr(
            self.new_expenditures
            <= current_expenditures + self.max_bln_mut_expenditure,
            name=f"{self.name} max budget constraint",
        )

        if self.min_bln_mut_expenditure is not None:
            print(
                "New Minimum:",
                current_expenditures + self.min_bln_mut_expenditure,
            )
            backend.add_constr(
                self.new_expenditures
                >= current_expenditures + self.min_bln_mut_expenditure,
                name=f"{self.name} min budget constraint",
            )

    @property
    def people(self) -> list[Person]:
        return [person for hh in self.households for person in hh.members]

    def __repr__(self) -> str:
        return f"{self.name}: {self.max_bln_mut_expenditure} budget slack"
