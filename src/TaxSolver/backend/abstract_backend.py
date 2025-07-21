from __future__ import annotations
import abc
from typing import Any, List

# By using 'Any', we tell the type checker that the backend will return its own
# native variable and expression objects. As long as these objects support
# standard mathematical operations, the high-level code will work seamlessly.
Variable = Any
Expression = Any


class AbstractBackend(abc.ABC):
    """
    Defines the abstract interface for a solver backend.

    This interface provides a minimal, solver-agnostic set of methods
    for creating variables, constraints, and expressions required by the TaxSolver.
    """

    @abc.abstractmethod
    def add_var(
        self,
        name: str,
        lb: float = 0.0,
        ub: float = float("inf"),
        var_type: str = "continuous",
    ) -> Variable:
        """Adds a variable to the model."""
        pass

    @abc.abstractmethod
    def add_constr(self, expression: Expression, name: str = ""):
        """Adds a constraint to the model (e.g., backend.add_constr(x + y <= 5))."""
        pass

    @abc.abstractmethod
    def add_gen_constr_indicator(
        self, bin_var: Variable, bin_val: bool, expression: Expression, name: str = ""
    ):
        """Adds an indicator constraint: bin_var == bin_val IMPLIES expression is true."""
        pass

    @abc.abstractmethod
    def add_gen_constr_max(
        self, res_var: Variable, variables: List[Variable], name: str = ""
    ):
        """Adds a general constraint for max: res_var == max(variables)."""
        pass

    @abc.abstractmethod
    def quicksum(self, expressions: List[Expression]) -> Expression:
        """Sums a list of expressions, similar to gurobipy.quicksum."""
        pass

    @abc.abstractmethod
    def linear_expression(self, *args) -> Expression:
        """Creates a new, empty linear expression, similar to gurobipy.LinExpr()."""
        pass

    @abc.abstractmethod
    def set_objective(self, expression: Expression, sense: str = "maximize"):
        """Sets the model objective."""
        pass

    @abc.abstractmethod
    def set_objective_n(
        self,
        expression: Expression,
        index: int,
        priority: int,
        abstol: float,
        name: str = "",
    ):
        """Sets a multi-objective function at a specific index."""
        pass

    @abc.abstractmethod
    def solve(self, callback=None):
        """Solves the model, optionally using a callback."""
        pass

    @abc.abstractmethod
    def get_sol_count(self) -> int:
        """Returns the number of solutions found."""
        pass

    @abc.abstractmethod
    def close(self):
        """Closes the model and releases resources."""
        pass

    @abc.abstractmethod
    def get_var_by_name(self, name: str) -> Variable:
        """Gets a variable from the model by its name."""
        pass

    @abc.abstractmethod
    def get_value(self, expr: Expression) -> float:
        """Gets the value of an expression after solving."""
        pass

    @abc.abstractmethod
    def update(self):
        """Updates the model, if necessary for the backend."""
        pass

    @abc.abstractmethod
    def get_constraint_by_name(self, name: str) -> Any:
        """Gets a constraint from the model by its name."""
        pass
