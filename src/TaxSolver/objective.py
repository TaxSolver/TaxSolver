from __future__ import annotations
from TaxSolver.backend.abstract_backend import Variable

from TaxSolver.constraints.budget_constraint import BudgetConstraint


class Objective:
    """
    Base class for optimization objectives in the tax solver system.

    This abstract class defines the interface for different types of objectives
    that can be used to guide the optimization process in tax reform.
    All concrete objective classes should inherit from this base class.

    Attributes
    ----------
    _tx : TaxSolver or None
        Reference to the bound tax solver instance.
    """

    def __init__(
        self,
    ):
        self._tx = None

    def bind_solver(self, tx):
        """
        Bind this objective to a tax solver instance.

        Parameters
        ----------
        tx : TaxSolver
            The tax solver instance to bind to this objective.
        """
        self._tx = tx

    def set_objective(self) -> None:
        """
        Set the optimization objective in the Gurobi model.

        This method must be implemented by all concrete objective classes
        to define the specific optimization goal.

        Raises
        ------
        NotImplementedError
            This is an abstract method that must be implemented by subclasses.
        """
        raise NotImplementedError

    def bind_solver_and_set_objective(self, tx):
        """
        Convenience method to bind solver and set objective in one call.

        Parameters
        ----------
        tx : TaxSolver
            The tax solver instance to bind and configure with this objective.
        """
        self.bind_solver(tx)
        self.set_objective()

    @property
    def tx(self):
        """
        Get the bound tax solver instance.

        Returns
        -------
        TaxSolver
            The tax solver instance bound to this objective.

        Raises
        ------
        ValueError
            If no solver has been bound to this objective.
        """
        if self._tx is None:
            raise ValueError("Solver not bound to objective")
        return self._tx

    def _rule_weight(self) -> Variable:
        """
        Get the rule weight variable from the tax solver.

        Returns
        -------
        Variable
            Gurobi variable representing the total weight of active tax rules,
            used to measure system complexity.
        """
        return self.tx.rule_weight

    def _highest_marginal_pressure(self) -> Variable:
        """
        Get the highest marginal pressure variable from the tax solver.

        Returns
        -------
        Variable
            Gurobi variable representing the highest marginal tax pressure
            in the system, used to minimize tax burden concentration.
        """
        return self.marginal_pressure_constraint.highest_marginal_pressure


class NullObjective(Objective):
    """
    A null objective that sets the optimization target to zero.

    This objective is used when no specific optimization goal is desired,
    effectively making the solver focus solely on satisfying the set constraints.
    """

    def set_objective(self) -> None:
        """
        Set the objective to minimize zero (no optimization goal).

        This effectively turns the optimization problem into a feasibility
        problem, where the solver only needs to find a solution that
        satisfies all constraints.
        """
        self.tx.backend.set_objective(0, "minimize")


class BudgetObjective(Objective):
    """
    Objective that minimizes total budget expenditures.

    This objective focuses on finding tax system configurations that
    minimize the total cost or expenditures as defined by the budget
    constraint.

    Parameters
    ----------
    budget_constraint : BudgetConstraint
        The budget constraint that defines expenditures to be minimized.

    Attributes
    ----------
    budget_constraint : BudgetConstraint
        The budget constraint used to calculate expenditures.
    """

    def __init__(self, budget_constraint: BudgetConstraint):
        super().__init__()
        self.budget_constraint = budget_constraint

    def set_objective(self) -> None:
        """
        Set the objective to minimize total expenditures.

        The objective minimizes the new_expenditures variable from the
        budget constraint, encouraging solutions with lower fiscal cost.
        """
        self.tx.backend.set_objective(self._spend(), "minimize")

    def _spend(self) -> Variable:
        """
        Get the expenditures variable from the budget constraint.

        Returns
        -------
        Variable
            Gurobi variable representing total new expenditures.
        """
        return self.budget_constraint.new_expenditures


class ComplexityObjective(Objective):
    """
    Objective that minimizes tax system complexity.

    This objective focuses on finding simpler tax systems by minimizing
    the total weight of active tax rules, encouraging solutions with
    fewer or simpler rules.
    """

    def set_objective(self) -> None:
        """
        Set the objective to minimize rule complexity.

        The objective minimizes the total weight of active tax rules,
        encouraging simpler tax system configurations.
        """
        self.tx.backend.set_objective(self._rule_weight(), "minimize")


class SequentialMixedObjective(BudgetObjective):
    """
    Multi-objective optimization using hierarchical priorities.

    This objective combines multiple goals with different priority levels,
    optimizing them sequentially in order of importance. Budget has the
    highest priority, followed by complexity, then marginal pressure.

    Parameters
    ----------
    budget_constraint : BudgetConstraint
        The budget constraint that defines expenditures.
    budget_tolerance : int, optional
        Absolute tolerance for budget objective, by default 100.
    complexity_tolerance : int, optional
        Absolute tolerance for complexity objective, by default 15.

    Attributes
    ----------
    budget_tolerance : int
        Tolerance level for budget optimization.
    complexity_tolerance : int
        Tolerance level for complexity optimization.
    """

    def __init__(
        self,
        budget_constraint: BudgetConstraint,
        budget_tolerance: int = 100,
        complexity_tolerance: int = 15,
    ):
        super().__init__(budget_constraint)
        self.budget_tolerance = budget_tolerance
        self.complexity_tolerance = complexity_tolerance

    def set_objective(self) -> None:
        """
        Set up hierarchical multi-objective optimization.

        Configures three objectives with different priorities:
        1. Budget (priority 3, highest): Minimize expenditures
        2. Complexity (priority 2): Minimize rule weight
        3. Marginal Pressure (priority 1, lowest): Minimize highest marginal rate

        The solver will optimize objectives in priority order, using the
        specified tolerances to determine when each objective is satisfied.
        """
        self.tx.backend.set_objective_n(
            self._spend(),
            index=0,
            priority=3,
            name="Budget",
            abstol=self.budget_tolerance,
        )
        self.tx.backend.set_objective_n(
            self._rule_weight(),
            index=1,
            priority=2,
            name="Complexity",
            abstol=self.complexity_tolerance,
        )
        self.tx.backend.set_objective_n(
            self._highest_marginal_pressure(),
            index=2,
            priority=1,
            name="Marginal Pressure",
        )


class WeightedMixedObjective(BudgetObjective):
    """
    Multi-objective optimization using weighted combination.

    This objective combines multiple goals into a single weighted objective
    function, allowing simultaneous optimization of budget, complexity,
    and marginal pressure concerns.

    Parameters
    ----------
    budget_constraint : BudgetConstraint
        The budget constraint that defines expenditures.
    complexity_penalty : int, optional
        Weight for complexity penalty in the objective, by default 15.
    marginal_pressure_penalty : int, optional
        Weight for marginal pressure penalty in the objective, by default 1.

    Attributes
    ----------
    complexity_penalty : int
        Penalty weight for tax system complexity.
    marginal_pressure_penalty : int
        Penalty weight for high marginal tax rates.
    """

    def __init__(
        self,
        budget_constraint: BudgetConstraint,
        marginal_pressure_constraint: MarginalPressureConstraint,
        complexity_penalty: int = 15,
        marginal_pressure_penalty: int = 1,
    ):
        super().__init__(budget_constraint)
        self.marginal_pressure_constraint = marginal_pressure_constraint
        self.complexity_penalty = complexity_penalty
        self.marginal_pressure_penalty = marginal_pressure_penalty

    def set_objective(self) -> None:
        """
        Set up weighted multi-objective optimization.

        Creates a single objective function that combines:
        - Budget expenditures (weight = 1)
        - Rule complexity (weight = complexity_penalty)
        - Marginal pressure (weight = marginal_pressure_penalty)

        All components are minimized simultaneously with their respective weights.
        """
        self.tx.backend.set_objective(
            self._spend()
            + self._rule_weight() * self.complexity_penalty
            + self._highest_marginal_pressure() * self.marginal_pressure_penalty,
            "minimize",
        )


class WeightedMixedLabourEffectsObjective(BudgetObjective):
    """
    Multi-objective optimization including labor effects considerations.

    This objective extends weighted optimization to include labor supply effects,
    accounting for how tax changes might affect work incentives and overall
    economic output through behavioral responses.

    Parameters
    ----------
    budget_constraint : BudgetConstraint
        The budget constraint that defines expenditures.
    complexity_penalty : int, optional
        Weight for complexity penalty in the objective, by default 15.
    marginal_pressure_penalty : int, optional
        Weight for marginal pressure penalty in the objective, by default 1.
    labor_effects_penalty : float, optional
        Weight for labor effects penalty in the objective, by default 100 * 5_000 * 0.4.

    Attributes
    ----------
    complexity_penalty : int
        Penalty weight for tax system complexity.
    marginal_pressure_penalty : int
        Penalty weight for high marginal tax rates.
    labor_effects_penalty : float
        Penalty weight for negative labor supply effects.

    Notes
    -----
    The labor effects penalty is applied with a negative sign to encourage
    policies that increase labor supply and economic output. The default
    value represents an economic calibration based on expected wage and
    employment effects.
    """

    def __init__(
        self,
        budget_constraint: BudgetConstraint,
        complexity_penalty: int = 15,
        marginal_pressure_penalty: int = 1,
        labor_effects_penalty: float = 100 * 5_000 * 0.4,
    ):
        super().__init__(budget_constraint)
        self.complexity_penalty = complexity_penalty
        self.marginal_pressure_penalty = marginal_pressure_penalty
        self.labor_effects_penalty = labor_effects_penalty

    def set_objective(self) -> None:
        """
        Set up weighted multi-objective optimization with labor effects.

        Creates a single objective function that combines:
        - Budget expenditures (weight = 1)
        - Rule complexity (weight = complexity_penalty)
        - Marginal pressure (weight = marginal_pressure_penalty)
        - Labor effects (weight = -labor_effects_penalty, negative to encourage growth)

        The labor effects component uses the wage_output_change variable from
        the tax solver to account for behavioral responses to tax changes.
        """
        self.tx.backend.set_objective(
            self._spend()
            + self._rule_weight() * self.complexity_penalty
            + self._highest_marginal_pressure() * self.marginal_pressure_penalty
            + -1 * self.tx.wage_output_change * self.labor_effects_penalty,
            "minimize",
        )
