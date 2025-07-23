from TaxSolver.rule import TaxRule, FlatTaxRule
from TaxSolver.tax_solver import TaxSolver
from typing import Optional

class Brackets(TaxRule):
    """
    A progressive tax rule that expands into multiple flat tax brackets.

    This rule is a wrapper that can be used to assign progressive tax brackets
    to an input. It automatically creates child FlatTaxRule objects for each bracket
    based on input data columns.

    Parameters
    ----------
    name : str
        Base name for the bracket rule and its children.
    var_name : list[str] or str
        Base variable name(s) that will be used to identify bracket columns.
    k_group_var : Optional[str], optional
        Grouping variable for bracket identification, by default None.
    lb : Optional[float], optional
        Lower bound for bracket rates, by default None (uses 0.0).
    ub : Optional[float], optional
        Upper bound for bracket rates, by default None (uses 1.0).
    weight : Optional[float], optional
        Weight for each bracket rule in complexity calculations, by default None.
    metadata : dict, optional
        Additional metadata passed to child rules, by default {}.

    Attributes
    ----------
    _flat_rules : list[FlatTaxRule]
        List of child FlatTaxRule objects created for each bracket.

    Notes
    -----
    This is a "container" rule that doesn't directly calculate taxes but instead
    creates and manages multiple FlatTaxRule children. Each bracket is linked
    to the previous one through the rule_considered_inactive_at mechanism to
    ensure proper progressive behavior.

    The rule automatically identifies bracket columns in the input data based
    on the naming pattern: "{base_var}_{k_group_var}_*" or "{base_var}_*".
    """

    def __init__(
        self,
        name: str,
        var_name: list[str] | str,
        k_group_var: Optional[str] = None,
        lb: Optional[float] = None,
        ub: Optional[float] = None,
        weight: Optional[float] = None,
        metadata: dict = {},
        max_brackets: Optional[int] = None,
        ascending: bool = False,
        start_from_first_inflection: bool = False,
        last_bracket_zero: bool = False,
        min_gap: int = 0,
    ) -> None:
        self.name = name
        self.var_name = var_name if isinstance(var_name, list) else [var_name]
        self.k_group_var = k_group_var
        self.lb = 0.0 if lb is None else lb
        self.ub = 1.0 if ub is None else ub
        self.weight = weight
        self.metadata = metadata or {}
        self.max_brackets = max_brackets
        self.ascending = ascending
        self.start_from_first_inflection = start_from_first_inflection
        self.last_bracket_zero = last_bracket_zero
        self.min_gap = min_gap

        self._flat_rules: list[FlatTaxRule] = []  # will hold the children

    def bind_and_initialize(self, tx: "TaxSolver") -> None:
        """
        Create and bind child FlatTaxRule objects for each tax bracket.

        This method identifies bracket columns in the input data and creates
        a FlatTaxRule for each bracket, linking them together to ensure
        proper progressive tax behavior.

        Parameters
        ----------
        tx : TaxSolver
            The tax solver instance to bind bracket rules to.

        Raises
        ------
        ValueError
            If no input columns match the expected bracket naming pattern.

        Notes
        -----
        The method searches for columns matching the pattern:
        - "{base_var}_{k_group_var}_*" if k_group_var is specified
        - "{base_var}_*" otherwise

        Each bracket rule is linked to the previous one to ensure that
        higher brackets only activate when lower brackets are fully utilized.
        """
        base = self.var_name[0]
        prefix = f"{base}_{self.k_group_var}_" if self.k_group_var else f"{base}_"

        cols = [
            c
            for c in tx.inputs
            if c.startswith(prefix) and not c.endswith("_is_marginal")
        ]
        if not cols:
            raise ValueError(f"No input columns start with '{prefix}'")

        prev_rule: float | FlatTaxRule = 0.0
        for col in cols:
            child = FlatTaxRule(
                name=f"{self.name}__{col}",
                var_name=col,
                lb=self.lb,
                ub=self.ub,
                marginal_pressure=col + "_is_marginal",
                rule_considered_inactive_at=prev_rule,
                weight=self.weight,
                metadata={**self.metadata, "bracket_source": col},
            )
            child.bind_and_initialize(tx)  # adds vars/constraints
            self._flat_rules.append(child)
            prev_rule = child
        
        self._constrain_brackets(tx)

    def _constrain_brackets(self, tx):
        backend = tx.backend

        if self.max_brackets:
            active_brackets = backend.quicksum([rule.b for rule in self.flat_rules])
            backend.add_constr(
                active_brackets <= self.max_brackets,
                name=f"max_brackets_{self.name}",
            )

        # Force ascending brackets if necessary
        if self.ascending is True:
            for rule in self.flat_rules:
                if isinstance(rule.rule_considered_inactive_at, FlatTaxRule):
                    backend.add_constr(
                        rule.rate >= rule.rule_considered_inactive_at.rate,
                        name=f"ascending_{rule.name}",
                    )

        if self.start_from_first_inflection:
            first_rule = self.flat_rules[0]
            for r in self.flat_rules[1:]:
                backend.add_constr(
                    r.b <= first_rule.b, name=f"start_from_first_inflection_{r.name}"
                )

        if self.last_bracket_zero is True:
            backend.add_constr(
                self.flat_rules[-1].rate == 0,
                name=f"last_bracket_zero_{self.name}",
            )

        if self.min_gap == 0:
            return

        # Make sure neighboring brackets are not both considered
        neighbor_sets = []
        for i in range(len(self.flat_rules) - self.min_gap - 1):
            neighbor_sets.append(self.flat_rules[i : i + self.min_gap])

        set_sums = [backend.quicksum([rule.b for rule in set]) for set in neighbor_sets]
        backend.add_constrs((set_sums[i] <= 1) for i in range(len(set_sums)))

    @property
    def flat_rules(self) -> list[FlatTaxRule]:
        """
        Get the list of child FlatTaxRule objects.

        Returns
        -------
        list[FlatTaxRule]
            List of FlatTaxRule objects representing individual tax brackets.
        """
        return self._flat_rules