from __future__ import annotations
from typing import List
import gurobipy as gp

from .abstract_backend import AbstractBackend, Variable, Expression


class GurobiBackend(AbstractBackend):
    """Gurobi implementation of the solver backend."""

    def __init__(self, suppress_output: bool = False, env=None):
        if env:
            self.model = gp.Model("tax_optimization", env=env)
        else:
            self.model = gp.Model("tax_optimization")

        # if suppress_output:
        #     self.model.setParam("OutputFlag", 0)

        self._VAR_TYPE_MAP = {
            "continuous": gp.GRB.CONTINUOUS,
            "c": gp.GRB.CONTINUOUS,
            "binary": gp.GRB.BINARY,
            "b": gp.GRB.BINARY,
            "integer": gp.GRB.INTEGER,
            "i": gp.GRB.INTEGER,
        }
        self._SENSE_MAP = {
            "minimize": gp.GRB.MINIMIZE,
            "maximize": gp.GRB.MAXIMIZE,
        }

    def add_var(
        self,
        name: str,
        lb: float = 0.0,
        ub: float = float("inf"),
        var_type: str = "continuous",
    ) -> Variable:
        gurobi_vtype = self._VAR_TYPE_MAP.get(var_type.lower())
        if gurobi_vtype is None:
            raise ValueError(f"Unsupported variable type: {var_type}")
        return self.model.addVar(lb=lb, ub=ub, vtype=gurobi_vtype, name=name)

    def add_constr(self, expression: Expression, name: str = ""):
        return self.model.addConstr(expression, name=name)

    def add_gen_constr_indicator(
        self, bin_var: Variable, bin_val: bool, expression: Expression, name: str = ""
    ):
        # Gurobi's indicator requires the expression to be in the form of
        # linear_expr sense constant (e.g., x + y <= 5)
        return self.model.addGenConstrIndicator(bin_var, bin_val, expression, name=name)

    def add_gen_constr_max(
        self, res_var: Variable, variables: List[Variable], name: str = ""
    ):
        # We need to create auxiliary variables that store the marginal pressure values
        # for each person.
        aux_vars = self.model.addVars(
            len(variables), name="aux", vtype=gp.GRB.CONTINUOUS
        )
        for i in range(len(variables)):
            self.model.addConstr(aux_vars[i] == variables[i])

        return self.model.addGenConstrMax(res_var, aux_vars, name=name)

    def quicksum(self, expressions: List[Expression]) -> Expression:
        return gp.quicksum(expressions)

    def linear_expression(self, *args) -> Expression:
        return gp.LinExpr(*args)

    def set_objective(self, expression: Expression, sense: str = "maximize"):
        gurobi_sense = self._SENSE_MAP.get(sense.lower())
        if gurobi_sense is None:
            raise ValueError(f"Unsupported objective sense: {sense}")
        self.model.setObjective(expression, sense=gurobi_sense)

    def set_objective_n(
        self,
        expression: Expression,
        index: int,
        priority: int,
        abstol: float,
        name: str = "",
    ):
        return self.model.setObjectiveN(
            expression, index, priority=priority, abstol=abstol, name=name
        )

    def solve(self, callback=None):
        self.model.optimize(callback)

    def get_sol_count(self) -> int:
        return self.model.SolCount

    def close(self):
        self.model.dispose()

    def get_var_by_name(self, name: str) -> Variable:
        return self.model.getVarByName(name)

    def update(self):
        return self.model.update()

    def get_constraint_by_name(self, name: str):
        return self.model.getConstrByName(name)

    def get_value(self, expr: Expression) -> float:
        """Gets the value of a solved expression.

        Handles Gurobi variables, linear expressions, and quadratic expressions.
        """
        if isinstance(expr, (gp.LinExpr, gp.QuadExpr)):
            return expr.getValue()
        elif isinstance(expr, gp.Var):
            return expr.X
        elif isinstance(expr, (int, float)):
            return expr
        else:
            raise TypeError(f"Unhandled type in get_value: {type(expr)}")

    def get_all_variable_names(self) -> list[str]:
        """Gets the names of all variables in the model."""
        return [v.VarName for v in self.model.getVars()]
