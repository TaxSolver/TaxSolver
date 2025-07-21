from TaxSolver.population.household import Household
from TaxSolver.constraints.constraint import Constraint


class IncomeConstraint(Constraint):
    def __init__(self, income_loss_limit: float, households: list[Household]) -> None:
        self.income_loss_limit = income_loss_limit
        self.households = households

    def apply(self, solver) -> None:
        backend = solver.backend
        for hh in self.households:
            backend.add_constr(
                hh.new_net_household_income
                >= hh.old_household_income * (1 - self.income_loss_limit),
                name=f"income_constraint_{hh.id}",
            )

    def __repr__(self) -> str:
        return self.key

    @property
    def key(self):
        return f"limit_{int(self.income_loss_limit * 100)}_loss"
