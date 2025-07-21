from TaxSolver.constraints.constraint import Constraint


class MarginalPressureConstraint(Constraint):
    def __init__(self, marginal_pressure_limit: float) -> None:
        self.marginal_pressure_limit = marginal_pressure_limit

    def apply(self, solver) -> None:
        backend = solver.backend

        # This variable will be used to store the maximum marginal pressure for later inspection
        self.highest_marginal_pressure = backend.add_var(
            name="highest_marginal_pressure", lb=0, ub=1, var_type="continuous"
        )

        # Get all marginal pressure expressions, filtering for valid variables
        mps = [person.new_marginal_rate for person in solver.people.values()]

        # If there are no marginal pressure variables, there's nothing to constrain.
        if not mps:
            backend.add_constr(self.highest_marginal_pressure == 0)
            return

        # Use the backend's generic max constraint.
        # This abstracts away the need for auxiliary variables for some backends.
        backend.add_gen_constr_max(
            self.highest_marginal_pressure, mps, name="set_max_marginal_pressure"
        )

        # And constraint the max as well
        backend.add_constr(
            self.highest_marginal_pressure <= self.marginal_pressure_limit,
            name="set_marginal_pressure_below_max",
        )

    def __repr__(self) -> str:
        return self.key

    @property
    def key(self):
        return f"marginal_pressure_constraint_limit_{int(self.marginal_pressure_limit * 100)}"
