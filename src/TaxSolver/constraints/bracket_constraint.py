from TaxSolver.constraints.constraint import Constraint
import gurobipy as grb


class BracketConstraint(Constraint):
    def __init__(
        self,
        rule_family: str,
        max_brackets: int,
        ascending: bool,
        start_from_first_inflection: bool,
        last_bracket_zero: bool,
        min_gap: int = 0,
    ) -> None:
        self.rule_family = rule_family
        self.max_brackets = max_brackets
        self.ascending = ascending
        self.start_from_first_inflection = start_from_first_inflection
        self.last_bracket_zero = last_bracket_zero
        self.min_gap = min_gap

    def apply(self, tx) -> None:
        ## Get rules from the tx
        ## Only return rules in line with the rule family
        # rules = [r for r in tx.rules if r.family == self.rule_family]
        # Set limit for active brackets
        if self.max_brackets:
            active_brackets = grb.quicksum([rule.b for rule in self.brackets])
            tx.model.addConstr(
                active_brackets <= self.max_brackets,
                name=f"max_brackets_{self.brackets[0].family}",
            )

        # Force ascending brackets if necessary
        if self.ascending is True:
            for rule in self.brackets:
                if rule.prev_bracket:
                    tx.model.addConstr(
                        rule.rate >= rule.prev_bracket.rate,
                        name=f"ascending_{rule.name}",
                    )

        if self.start_from_first_inflection:
            first_rule = self.brackets[0]
            for r in self.brackets[1:]:
                tx.model.addConstr(
                    r.b <= first_rule.b, name=f"start_from_first_inflection_{r.name}"
                )

        if self.last_bracket_zero is True:
            tx.model.addConstr(
                self.brackets[-1].rate == 0,
                name=f"last_bracket_zero_{self.brackets[-1].family}",
            )

        if self.min_gap == 0:
            return

        # Make sure neighboring brackets are not both considered
        neighbor_sets = []
        for i in range(len(self.brackets) - self.min_gap - 1):
            neighbor_sets.append(self.brackets[i : i + self.min_gap])

        set_sums = [grb.quicksum([rule.b for rule in set]) for set in neighbor_sets]
        tx.model.addConstrs((set_sums[i] <= 1) for i in range(len(set_sums)))

    def __repr__(self) -> str:
        return self.key

    @property
    def key(self):
        return f"limit_{int(self.income_loss_limit * 100)}_loss"
