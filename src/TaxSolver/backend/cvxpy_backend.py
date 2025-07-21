from __future__ import annotations
from typing import List, Optional
import cvxpy as cp  # type: ignore
import numpy as np

from .abstract_backend import AbstractBackend, Variable, Expression


class CvxpyBackend(AbstractBackend):
    """CVXPY implementation of the solver backend."""

    def __init__(
        self,
        solver: Optional[str] = "SCIP",
        suppress_output: bool = False,
        solver_params: Optional[dict] = None,
    ):
        self.problem: Optional[cp.Problem] = None
        self.variables: dict[str, cp.Variable] = {}
        self.constraints: list[cp.Constraint] = []
        self.named_constraints: dict[str, cp.Constraint] = {}
        self.objective: cp.Objective = cp.Minimize(0)  # Default placeholder
        self.suppress_output = suppress_output
        self.solver = solver
        self.solver_params = solver_params or {}

        self._VAR_TYPE_MAP = {
            "continuous": {"integer": False, "boolean": False},
            "c": {"integer": False, "boolean": False},
            "binary": {"integer": False, "boolean": True},
            "b": {"integer": False, "boolean": True},
            "integer": {"integer": True, "boolean": False},
            "i": {"integer": True, "boolean": False},
        }
        self._SENSE_MAP = {
            "minimize": cp.Minimize,
            "maximize": cp.Maximize,
        }

    def add_var(
        self,
        name: str,
        lb: float = 0.0,
        ub: float = float("inf"),
        var_type: str = "continuous",
    ) -> Variable:
        var_opts = self._VAR_TYPE_MAP.get(var_type.lower())
        if var_opts is None:
            raise ValueError(f"Unsupported variable type: {var_type}")

        var = cp.Variable(name=name, **var_opts)

        if lb != -np.inf:
            self.constraints.append(var >= lb)
        if ub != np.inf:
            self.constraints.append(var <= ub)

        self.variables[name] = var
        return var

    def add_constr(self, expression: Expression, name: str = ""):
        self.constraints.append(expression)
        if name:
            # CVXPY constraints don't have a name property, so we store them separately.
            self.named_constraints[name] = expression

    def add_gen_constr_indicator(
        self, bin_var: Variable, bin_val: bool, expression: Expression, name: str = ""
    ):
        # CVXPY's implication operator `>>` can cause a TypeError with equality constraints.
        # We use a big-M formulation for equality constraints as a workaround.
        # For inequality constraints, `>>` should work fine.
        M = 1e5  # A large number, should be chosen carefully based on problem scaling.

        if not isinstance(expression, cp.constraints.Equality):
            if bin_val:
                self.constraints.append((bin_var == 1) >> expression)
            else:
                self.constraints.append((bin_var == 0) >> expression)
            return

        # It's an equality constraint, e.g., lhs == rhs.
        # We rewrite it as e = lhs - rhs, and enforce e == 0.
        e = expression.args[0] - expression.args[1]

        if bin_val:  # bin_var == 1 => e == 0
            # This is equivalent to:
            # e <= M * (1 - bin_var)
            # e >= -M * (1 - bin_var)
            self.constraints.append(e <= M * (1 - bin_var))
            self.constraints.append(e >= -M * (1 - bin_var))
        else:  # bin_var == 0 => e == 0
            # This is equivalent to:
            # e <= M * bin_var
            # e >= -M * bin_var
            self.constraints.append(e <= M * bin_var)
            self.constraints.append(e >= -M * bin_var)

    def add_gen_constr_max(
        self, res_var: Variable, variables: List[Variable], name: str = ""
    ):
        # res_var == cp.maximum(*variables) is not DCP compliant because cp.maximum is convex.
        # We reformulate the constraint using the big-M method.
        # y = max(x_1, ..., x_n) is equivalent to:
        # 1. y >= x_i for all i
        # 2. y <= x_i + M * (1 - b_i) for all i
        # 3. sum(b_i) == 1
        # where b_i are binary variables.
        M = 1e6  # A large number, should be chosen carefully based on problem scaling.

        # Create binary variables to select the max
        num_vars = len(variables)
        # Using a unique name prefix to avoid collisions
        if name:
            prefix = f"{name}_b"
        else:
            # Fallback to a unique name based on object id
            prefix = f"max_b_{id(variables)}"

        binary_vars = []
        for i in range(num_vars):
            var_name = f"{prefix}_{i}"
            b_var = cp.Variable(name=var_name, boolean=True)
            binary_vars.append(b_var)
            self.variables[var_name] = b_var

        # Add constraint: sum(binary_vars) == 1
        self.constraints.append(cp.sum(binary_vars) == 1)

        for i, var in enumerate(variables):
            # Add constraint: res_var >= var
            self.constraints.append(res_var >= var)
            # Add constraint: res_var <= var + M * (1 - binary_var)
            self.constraints.append(res_var <= var + M * (1 - binary_vars[i]))

    def quicksum(self, expressions: List[Expression]) -> Expression:
        return sum(expressions)

    def linear_expression(self, *args) -> Expression:
        # CVXPY builds expressions naturally, so we can start with 0
        return 0

    def set_objective(self, expression: Expression, sense: str = "maximize"):
        sense_func = self._SENSE_MAP.get(sense.lower())
        if sense_func is None:
            raise ValueError(f"Unsupported objective sense: {sense}")
        self.objective = sense_func(expression)

    def set_objective_n(
        self,
        expression: Expression,
        index: int,
        priority: int,
        abstol: float,
        name: str = "",
    ):
        raise NotImplementedError(
            "CVXPY does not support multi-objective optimization with priorities in the same way as Gurobi."
        )

    def solve(self, callback=None):
        self.problem = cp.Problem(self.objective, self.constraints)
        self.problem.solve(
            solver=self.solver, verbose=not self.suppress_output, **self.solver_params
        )

    def get_sol_count(self) -> int:
        return (
            1
            if self.problem
            and self.problem.status in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]
            else 0
        )

    def close(self):
        # CVXPY does not require explicit resource disposal
        pass

    def get_var_by_name(self, name: str) -> Variable:
        return self.variables.get(name)

    def update(self):
        # CVXPY does not require an explicit update step.
        pass

    def get_constraint_by_name(self, name: str):
        return self.named_constraints.get(name)

    def get_value(self, expr: Expression) -> float:
        """Gets the value of a solved expression.

        Handles CVXPY variables, expressions, and constants.
        """
        if hasattr(expr, "value") and expr.value is not None:
            return expr.value
        elif isinstance(expr, (int, float)):
            return expr
        else:
            # Return 0 for expressions that don't have a value, which can happen
            # with inactive parts of the model.
            return 0.0
