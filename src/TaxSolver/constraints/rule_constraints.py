from TaxSolver.constraints.constraint import Constraint
from typing import List


class ForceRulesOnConstraint(Constraint):
    def __init__(self, rule_names: List[str]):
        self.rule_names = rule_names

    def apply(self, solver) -> None:
        backend = solver.backend
        for rule in solver.rules:
            if rule.name in self.rule_names:
                backend.add_constr(rule.b == 1, name=f"force_on_{rule.name}")


class ForceRateConstraint(Constraint):
    def __init__(self, rule_names: List[str], rate: float):
        self.rule_names = rule_names
        self.rate = rate

    def apply(self, solver) -> None:
        backend = solver.backend
        for rule in solver.rules:
            if rule.name in self.rule_names:
                backend.add_constr(
                    rule.rate == self.rate, name=f"force_rate_{rule.name}"
                )


class ForceRuleFamilyOnConstraint(Constraint):
    def __init__(self, rule_names: list[str]):
        self.rule_names = rule_names

    def apply(self, solver) -> None:
        backend = solver.backend
        rules = [solver.get_rule(rule_name) for rule_name in self.rule_names]
        bool_sum = backend.quicksum(r.b for r in rules)
        backend.add_constr(
            bool_sum >= 1, name=f"force_on_one_of_{':'.join(self.rule_names)}"
        )


class MutuallyExclusiveRulesConstraint(Constraint):
    def __init__(self, rule_names: List[str]):
        self.rule_names = rule_names

    def apply(self, solver) -> None:
        backend = solver.backend
        bool_sum = backend.quicksum(
            solver.get_rule(rule_name).b for rule_name in self.rule_names
        )
        backend.add_constr(
            bool_sum <= 1, name=f"mutually_exclusive_{':'.join(self.rule_names)}"
        )
