class BracketInput:
    """A class for distributing a variable over brackets.

    Raises:
        KeyError: _description_

    Returns:
        _type_: _description_
    """

    @staticmethod
    def _create_bracket_tuples(brackets):
        bracket_tuples = []
        for i in range(len(brackets) - 1):
            lower_limit = brackets[i]
            upper_limit = brackets[i + 1]
            bracket_tuples.append((lower_limit, upper_limit))
        return bracket_tuples

    @staticmethod
    def _amount_in_bracket(value: float, lower: float, upper: float) -> float:
        """Return the part of *value* that lies within the bracket [lower, upper)."""
        if value == lower:
            return 0.000001
        elif value <= lower:
            return 0
        return min(value, upper) - lower

    @staticmethod
    def _is_marginal_bracket(value: float, lower: float, upper: float) -> bool:
        """Return True if *value* lies within the bracket [lower, upper)."""
        return value >= lower and value < upper

    @staticmethod
    def add_split_variables_to_solver(
        tx,
        target_var: str,
        inflection_points: list[float],
        group_vars: list[str] | None = None,
        overwrite: bool = False,
    ) -> None:
        """Add bracket-level versions of *target_var* to every person in *tx*.

        For every bracket defined by *inflection_points* and for every *group_var*
        (or for all persons if *group_vars* is ``None``) a new attribute is added
        to each :class:`~TaxSolver.household.person.Person` instance.  The name of
        the attribute follows the convention::

            f"{target_var}_{lower}_{upper}_{group_var}"

        where *lower* and *upper* are the bracket limits.  The value equals the
        amount of *target_var* that falls inside the bracket, multiplied by the
        value of *group_var* (assumed to be 0/1) if *group_var* is provided.

        Parameters
        ----------
        tx
            A :class:`TaxSolver` instance.
        target_var
            The name of the variable to split (e.g. ``"income_before_tax"``).
        inflection_points
            A monotonic list of numeric break points (e.g. ``[0, 25_000, 50_000]``).
        group_vars
            List of group indicator variables (e.g. ``["k_everybody", "k_children"]``).
            If ``None`` the split is performed for all persons irrespective of
            group membership.
        overwrite
            If *True*, existing attributes with the same name will be overwritten.

        Returns
        -------
        None
        """

        if group_vars is None or len(group_vars) == 0:
            group_vars = ["k_everybody"]

        # Prepare bracket tuples
        brackets = BracketInput._create_bracket_tuples(inflection_points)

        created_vars: set[str] = set()

        for person in tx.people.values():
            try:
                base_value = person[target_var]
            except KeyError:
                raise KeyError(
                    f"Target variable '{target_var}' not found for person {person['id']}."
                )

            for lower, upper in brackets:
                in_bracket = BracketInput._amount_in_bracket(base_value, lower, upper)
                bracket_is_marginal_bracket = BracketInput._is_marginal_bracket(
                    base_value, lower, upper
                )

                for g in group_vars:
                    if g is None:
                        group_multiplier = 1
                        var_suffix = ""
                    else:
                        group_multiplier = person.data.get(g, 0)
                        var_suffix = f"_{g}"

                    new_var_name = f"{target_var}{var_suffix}_{lower}_{upper}"

                    # Skip if the variable exists and overwrite is False
                    if not overwrite and new_var_name in person.data:
                        continue

                    person[new_var_name] = in_bracket * group_multiplier
                    person[new_var_name + "_is_marginal"] = (
                        1 if bracket_is_marginal_bracket else 0
                    )
                    created_vars.add(new_var_name)
