from __future__ import annotations
from typing import TYPE_CHECKING
from functools import reduce
import operator
import gurobipy as grb
from typing import Optional
from TaxSolver.backend.abstract_backend import Variable

if TYPE_CHECKING:
    from TaxSolver.population.person import Person
    from TaxSolver import TaxSolver


class TaxRule:
    """
    Base class for defining tax rules in the optimization system.

    A tax rule represents a specific tax or benefit policy that can be applied
    to individuals or households. Each rule has an associated rate that is
    optimized by the solver, along with constraints and metadata that define
    its behavior and scope. Tax rules are the main vehicle to provide TaxSolver
    with solver variables to optimize.

    Parameters
    ----------
    name : str
        Unique name identifier for the tax rule.
    var_name : list[str] or str
        Variable name(s) from person data that this rule applies to.
        If string, will be converted to single-element list.
    lb : float
        Lower bound for the rule's rate parameter.
    ub : float
        Upper bound for the rule's rate parameter.
    pretax : bool
        Whether this rule applies to pre-tax income (affects marginal rate calculation).
    benefit : bool
        Whether this rule represents a benefit or tax.
    household_level : bool
        Whether this rule applies at household level (True) or individual level (False).
    marginal_pressure : bool or str
        Whether this rule contributes to marginal tax pressure. Can be boolean
        or string referencing a person data field.
    marginal_pressure_scaler_var : Optional[str], optional
        Variable name for scaling marginal pressure contribution, by default None.
    rule_considered_inactive_at : float or TaxRule, optional
        Value or rule at which this rule is considered inactive, by default 0.
    weight : float, optional
        Weight of this rule for complexity calculations, by default 1.
    metadata : dict, optional
        Additional metadata for the rule, by default {}.

    Attributes
    ----------
    name : str
        Rule identifier.
    var_name : list[str]
        List of variable names this rule applies to.
    lb : float
        Lower bound for rule rate.
    ub : float
        Upper bound for rule rate.
    weight : float
        Rule weight for optimization.
    pretax : bool
        Whether rule applies pre-tax.
    benefit : bool
        Whether rule is a benefit.
    household_level : bool
        Whether rule applies at household level.
    marginal_pressure : bool or str
        Marginal pressure configuration.
    marginal_pressure_scaler_var : Optional[str]
        Scaler variable for marginal pressure.
    rule_considered_inactive_at : float or TaxRule
        Inactivity threshold.
    metadata : dict
        Additional rule metadata.
    tx : TaxSolver
        Bound tax solver instance (set during initialization).
    rate : grb.Var
        Gurobi variable representing the rule's rate (created during binding).
    b : grb.Var
        Binary variable indicating rule activity (created during binding).
    """

    def __init__(
        self,
        name: str,
        var_name: list[str] | str,
        lb: float,
        ub: float,
        pretax: bool,
        benefit: bool,
        household_level: bool,
        marginal_pressure: bool | str,
        marginal_pressure_scaler_var: Optional[str] = None,
        rule_considered_inactive_at: float | TaxRule = 0,
        weight: float = 1,
        metadata: dict = {},
    ) -> None:
        self.name = name
        self.var_name: list[str] = (
            var_name if isinstance(var_name, list) else [var_name]
        )
        self.lb = lb
        self.ub = ub
        self.weight = weight
        self.pretax = pretax
        self.benefit = benefit
        self.household_level = household_level
        self.marginal_pressure = marginal_pressure
        self.marginal_pressure_scaler_var = marginal_pressure_scaler_var
        self.rule_considered_inactive_at = rule_considered_inactive_at
        self.metadata = metadata

    def bind_and_initialize(self, tx: TaxSolver) -> None:
        """
        Bind the rule to a tax solver model and create optimization variables.

        This method creates the necessary Gurobi variables for the rule's rate
        and activity status, and sets up constraints for rule inactivity conditions.

        Parameters
        ----------
        tx : TaxSolver
            The tax solver instance to bind this rule to.

        Notes
        -----
        Creates two Gurobi variables:
        - rate: Continuous variable with bounds
        - b: Binary variable indicating whether the rule is active

        Also adds indicator constraints to handle rule inactivity based on
        the rule_considered_inactive_at parameter, and to enforce the true
        lower bound when the rule is active.

        When b=1 (active), additional indicator constraints enforce lb <= rate <= ub.
        """
        self.tx = tx

        # Determine the inactive value for this rule
        if isinstance(self.rule_considered_inactive_at, TaxRule):
            inactive_val = None  # Will be linked to another rule's rate
        else:
            inactive_val = self.rule_considered_inactive_at

        # Set variable bounds to include both active range AND inactive value
        if inactive_val is not None:
            var_lb = min(self.lb, inactive_val)
            var_ub = max(self.ub, inactive_val)
        else:
            var_lb = self.lb
            var_ub = self.ub

        self.rate: Variable = self.tx.backend.add_var(
            name=f"{self.name}_rate",
            lb=var_lb,
            ub=var_ub,
            var_type="continuous",
        )
        self.b: Variable = self.tx.backend.add_var(
            name=f"{self.name}_b", lb=0, ub=1, var_type="binary"
        )

        # When b=0 (inactive), set rate to inactive value
        if isinstance(self.rule_considered_inactive_at, TaxRule):
            self.tx.backend.add_gen_constr_indicator(
                self.b,
                False,
                self.rate == self.rule_considered_inactive_at.rate,
                name=f"{self.name}_b_indicator_inactive",
            )
        else:
            self.tx.backend.add_gen_constr_indicator(
                self.b,
                False,
                self.rate == self.rule_considered_inactive_at,
                name=f"{self.name}_b_indicator_inactive",
            )

        # When b=1 (active), enforce the true bounds: lb <= rate <= ub
        if inactive_val is not None and (
            inactive_val < self.lb or inactive_val > self.ub
        ):
            if inactive_val < self.lb:
                self.tx.backend.add_gen_constr_indicator(
                    self.b,
                    True,
                    self.rate >= self.lb,
                    name=f"{self.name}_b_indicator_active_lb",
                )
            if inactive_val > self.ub:
                self.tx.backend.add_gen_constr_indicator(
                    self.b,
                    True,
                    self.rate <= self.ub,
                    name=f"{self.name}_b_indicator_active_ub",
                )

    @property
    def prev_bracket(self) -> "TaxRule | None":
        """
        Get the previous bracket rule if this rule is linked to one.

        This property returns the rule that this bracket inherits from when
        inactive (b=0). It's used by BracketConstraint to enforce ascending
        rate constraints.

        Returns
        -------
        TaxRule or None
            The previous bracket rule, or None if rule_considered_inactive_at
            is not a TaxRule (e.g., it's a numeric value like 0).
        """
        if isinstance(self.rule_considered_inactive_at, TaxRule):
            return self.rule_considered_inactive_at
        return None

    def calculate_tax(self, p: Person) -> grb.Var | grb.LinExpr:
        """
        Calculate the tax amount for a person from this specific rule.

        This method computes the tax or benefit amount by applying the rule's
        rate to the relevant variables from the person's data, accounting for
        pre-tax adjustments and marginal pressure effects.

        Parameters
        ----------
        p : Person
            The person to calculate tax for. If this is a household-level rule,
            the first member of the household will be used.

        Returns
        -------
        grb.Var or grb.LinExpr
            Gurobi variable or expression representing the tax amount.
            Positive values for benefits, negative values for taxes.

        Notes
        -----
        The calculation process:
        1. Extracts relevant variable values from person data
        2. Computes product of all variables
        3. Applies rule rate, adjusting for pre-tax effects if applicable
        4. Updates marginal pressure if the rule contributes to it
        5. Returns tax amount with appropriate sign (benefit vs tax)
        """
        if self.household_level:
            p = p.first_member

        vals = [p[v] for v in self.var_name]
        product = reduce(operator.mul, vals, 1)

        tax_i = (
            product * self.rate * (1 - p.new_marginal_rate)
            if self.pretax
            else product * self.rate
        )

        if isinstance(self.marginal_pressure, bool):
            bool_marginal_pressure: int = int(self.marginal_pressure)
        else:
            bool_marginal_pressure: int = p[self.marginal_pressure]

        if bool_marginal_pressure:
            if product > 0 or product < 0:
                self._update_marginal_pressure(p)
                p.marginal_rate_rules.append(self)

        return tax_i if self.benefit else -tax_i

    def _update_marginal_pressure(self, p: Person):
        """
        Update the person's marginal tax rate based on this rule.

        Parameters
        ----------
        p : Person
            The person whose marginal rate should be updated.

        Notes
        -----
        If a marginal_pressure_scaler_var is specified, the rate is scaled
        by that variable's value. Otherwise, the rate is added directly
        to the person's new_marginal_rate.

        Status quo marginal pressure values (sq_m_*) outside [-0.5, 1] are
        treated as data errors and set to 0 with a warning.
        """
        if self.marginal_pressure_scaler_var:
            mp_scaler = p[self.marginal_pressure_scaler_var]
            # Safeguard: Check if sq_m_ values are within reasonable bounds
            # Values outside [-0.5, 1] are likely data errors
            if mp_scaler < -0.5 or mp_scaler > 1:
                print(
                    f"WARNING: sq_marginal_pressure ({self.marginal_pressure_scaler_var}={mp_scaler}) "
                    f"is extremely positive or negative for person {p['id']}. Setting to 0."
                )
                mp_scaler = 0
            p.new_marginal_rate += self.rate * mp_scaler
        else:
            p.new_marginal_rate += self.rate

    def __repr__(self) -> str:
        """
        Return string representation of the tax rule.

        Returns
        -------
        str
            The name of the tax rule.
        """
        return self.name


class FlatTaxRule(TaxRule):
    """
    A flat tax rule with a constant rate applied to specified variables.

    This is a simplified tax rule that applies a flat rate to one or more
    variables. It's commonly used for basic income taxes, flat benefits,
    or simple proportional adjustments. The BracketRule class is a wrapper
    that automatically creates multiple FlatTaxRule objects for brackets of
    an input.

    Parameters
    ----------
    name : str
        Unique name identifier for the tax rule.
    var_name : list[str] or str
        Variable name(s) from person data that this rule applies to.
    lb : float, optional
        Lower bound for the rule's rate parameter, by default 0.
    ub : float, optional
        Upper bound for the rule's rate parameter, by default 1.
    rule_considered_inactive_at : float or TaxRule, optional
        Value or rule at which this rule is considered inactive, by default 0.
    marginal_pressure : bool, optional
        Whether this rule contributes to marginal tax pressure, by default False.
    weight : Optional[float], optional
        Weight of this rule for complexity calculations, by default None (uses 1).
    metadata : dict, optional
        Additional metadata for the rule, by default {}.

    Notes
    -----
    This rule is configured as:
    - Individual-level (not household_level)
    - Post-tax application (not pretax)
    - Tax (not benefit)
    - No marginal pressure scaling
    """

    def __init__(
        self,
        name: str,
        var_name: list[str] | str,
        lb: float = 0,
        ub: float = 1,
        rule_considered_inactive_at: float | TaxRule = 0,
        marginal_pressure: bool = False,
        weight: Optional[float] = None,
        metadata: dict = {},
    ) -> None:
        super().__init__(
            name=name,
            var_name=var_name,
            lb=lb,
            ub=ub,
            pretax=False,
            benefit=False,
            household_level=False,
            marginal_pressure=marginal_pressure,
            marginal_pressure_scaler_var=None,
            rule_considered_inactive_at=rule_considered_inactive_at,
            weight=weight if weight is not None else 1,
            metadata=metadata,
        )


class BenefitRule(TaxRule):
    """
    A rule representing a benefit payment to individuals.

    This rule type is used for benefits, subsidies, or other positive transfers
    to individuals. The rate represents the benefit amount per unit of the
    specified variables.

    Parameters
    ----------
    name : str
        Unique name identifier for the benefit rule.
    var_name : list[str] or str
        Variable name(s) from person data that this benefit applies to.
    ub : float, optional
        Upper bound for the benefit rate, by default inf (unlimited).
    weight : Optional[float], optional
        Weight of this rule for complexity calculations, by default None (uses 1).
    metadata : dict, optional
        Additional metadata for the rule, by default {}.

    Notes
    -----
    This rule is configured as:
    - Individual-level (not household_level)
    - Benefit (positive transfer)
    - Post-tax application (not pretax)
    - No marginal pressure contribution
    - Lower bound of 0 (benefits cannot be negative)
    """

    def __init__(
        self,
        name: str,
        var_name: list[str] | str,
        ub: float = float("inf"),
        weight: Optional[float] = None,
        metadata: dict = {},
    ) -> None:
        super().__init__(
            name=name,
            var_name=var_name,
            lb=0,
            ub=ub,
            pretax=False,
            benefit=True,
            household_level=False,
            marginal_pressure=False,
            marginal_pressure_scaler_var=None,
            weight=weight if weight else 1,
            metadata=metadata,
        )


class HouseholdBenefit(TaxRule):
    """
    A rule representing a benefit payment at the household level.

    This rule type is used for household-level benefits that are determined
    based on household characteristics rather than individual characteristics.
    Examples include housing benefits, family allowances, or household-based
    social assistance.

    Parameters
    ----------
    name : str
        Unique name identifier for the household benefit rule.
    var_name : list[str] or str
        Variable name(s) from household data that this benefit applies to.
    ub : float, optional
        Upper bound for the benefit rate, by default inf (unlimited).
    weight : Optional[float], optional
        Weight of this rule for complexity calculations, by default None (uses 1).
    metadata : dict, optional
        Additional metadata for the rule, by default {}.

    Notes
    -----
    This rule is configured as:
    - Household-level (applies to entire household)
    - Benefit (positive transfer)
    - Post-tax application (not pretax)
    - No marginal pressure contribution
    - Lower bound of 0 (benefits cannot be negative)
    """

    def __init__(
        self,
        name: str,
        var_name: list[str] | str,
        ub: float = float("inf"),
        weight: Optional[float] = None,
        metadata: dict = {},
    ) -> None:
        super().__init__(
            name=name,
            var_name=var_name,
            lb=0,
            ub=ub,
            pretax=False,
            benefit=True,
            household_level=True,
            marginal_pressure=False,
            marginal_pressure_scaler_var=None,
            weight=weight if weight else 1,
            metadata=metadata,
        )


class BracketRule(TaxRule):
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
    ) -> None:
        self.name = name
        self.var_name = var_name if isinstance(var_name, list) else [var_name]
        self.k_group_var = k_group_var
        self.lb = 0.0 if lb is None else lb
        self.ub = 1.0 if ub is None else ub
        self.weight = weight
        self.metadata = metadata or {}

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


class PreTaxBenefit(TaxRule):
    """
    A benefit rule that applies to pre-tax income.

    This rule represents benefits that are applied before other taxes are
    calculated, effectively reducing the taxable income base. This is commonly
    used for tax deductions, pre-tax savings contributions, or other income
    adjustments that should be applied before marginal rates.

    Parameters
    ----------
    name : str
        Unique name identifier for the pre-tax benefit rule.
    var_name : list[str] or str
        Variable name(s) from person data that this benefit applies to.
    lb : float
        Lower bound for the benefit rate.
    ub : float
        Upper bound for the benefit rate.
    weight : Optional[float], optional
        Weight of this rule for complexity calculations, by default None (uses 1).
    metadata : dict, optional
        Additional metadata for the rule, by default {}.

    Notes
    -----
    This rule is configured as:
    - Individual-level (not household_level)
    - Benefit (positive for the taxpayer)
    - Pre-tax application (affects marginal rate calculation)
    - No marginal pressure contribution
    """

    def __init__(
        self,
        name: str,
        var_name: list[str] | str,
        lb: float,
        ub: float,
        weight: Optional[float] = None,
        metadata: dict = {},
    ) -> None:
        super().__init__(
            name=name,
            var_name=var_name,
            lb=lb,
            ub=ub,
            pretax=True,
            benefit=True,
            household_level=False,
            marginal_pressure=False,
            weight=weight if weight else 1,
            metadata=metadata,
        )


class ExistingBenefit(TaxRule):
    """
    A rule representing an existing benefit with status quo scaling.

    This rule type is used to model existing benefits in the tax system,
    allowing for adjustments while maintaining connection to the current
    system design. It includes marginal pressure effects and uses special
    status quo variable naming conventions to determine both the absolute
    and marginal tax pressure due to the benefit.

    Parameters
    ----------
    name : str
        Unique name identifier for the existing benefit rule.
    var_name : str
        Base variable name (will be prefixed with "sq_a_" for amount).
    lb : float
        Lower bound for the benefit scaling factor.
    ub : float
        Upper bound for the benefit scaling factor.
    weight : Optional[float], optional
        Weight of this rule for complexity calculations, by default None (uses 1).
    metadata : dict, optional
        Additional metadata for the rule, by default {}.

    Notes
    -----
    This rule is configured as:
    - Individual-level (not household_level)
    - Benefit (positive transfer)
    - Post-tax application (not pretax)
    - Contributes to marginal pressure
    - Uses "sq_a_" prefix for amount variable
    - Uses "sq_m_" prefix for marginal scaler variable
    - Considered inactive at rate 0
    """

    def __init__(
        self,
        name: str,
        var_name: str,
        lb: float,
        ub: float,
        weight: Optional[float] = None,
        metadata: dict = {},
    ) -> None:
        super().__init__(
            name=name,
            var_name="sq_a_" + var_name,
            lb=lb,
            ub=ub,
            pretax=False,
            benefit=True,
            household_level=False,
            marginal_pressure=True,
            marginal_pressure_scaler_var="sq_m_" + var_name,
            rule_considered_inactive_at=0,
            weight=weight if weight else 1,
            metadata=metadata,
        )
