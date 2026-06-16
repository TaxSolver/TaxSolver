from TaxSolver.constraints.constraint import Constraint


class BracketConstraint(Constraint):
    """Constrain the family of bracket rules created by a :class:`BracketRule`.

    ``rule_family`` must match the ``name`` passed to the originating
    :class:`~TaxSolver.rule.BracketRule`. Its child :class:`FlatTaxRule`
    objects are named ``f"{rule_family}__{column}"``; this constraint resolves
    them from the solver in their creation order when applied.
    """

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
        self.brackets: list = []

    def apply(self, tx) -> None:
        backend = tx.backend

        # Resolve the bracket rules belonging to this family, preserving the
        # order in which the BracketRule created them.
        prefix = f"{self.rule_family}__"
        self.brackets = [r for r in tx.rules if r.name.startswith(prefix)]
        if not self.brackets:
            raise ValueError(
                f"No bracket rules found for family '{self.rule_family}'. "
                "Make sure a BracketRule with this name was added to the solver."
            )

        # Set limit for active brackets
        if self.max_brackets:
            active_brackets = backend.quicksum([rule.b for rule in self.brackets])
            backend.add_constr(
                active_brackets <= self.max_brackets,
                name=f"max_brackets_{self.rule_family}",
            )

        # Force ascending brackets if necessary
        if self.ascending is True:
            for rule in self.brackets:
                if rule.prev_bracket:
                    backend.add_constr(
                        rule.rate >= rule.prev_bracket.rate,
                        name=f"ascending_{rule.name}",
                    )

        if self.start_from_first_inflection:
            first_rule = self.brackets[0]
            for r in self.brackets[1:]:
                backend.add_constr(
                    r.b <= first_rule.b, name=f"start_from_first_inflection_{r.name}"
                )

        if self.last_bracket_zero is True:
            backend.add_constr(
                self.brackets[-1].rate == 0,
                name=f"last_bracket_zero_{self.rule_family}",
            )

        if self.min_gap == 0:
            return

        # Make sure neighboring brackets are not both considered
        neighbor_sets = []
        for i in range(len(self.brackets) - self.min_gap - 1):
            neighbor_sets.append(self.brackets[i : i + self.min_gap])

        set_sums = [backend.quicksum([rule.b for rule in s]) for s in neighbor_sets]
        for i, set_sum in enumerate(set_sums):
            backend.add_constr(set_sum <= 1, name=f"min_gap_{i}")

    def __repr__(self) -> str:
        return self.key

    @property
    def key(self):
        return f"bracket_constraint_{self.rule_family}"
