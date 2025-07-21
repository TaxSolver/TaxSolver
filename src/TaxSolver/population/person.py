from typing import Optional

from TaxSolver.rule import TaxRule


class Person:
    """
    Represents an individual person within a household in the tax system.

    A person contains personal data and manages optimization variables related to
    income, taxes, and labor effects. Each person belongs to exactly one household
    and has access to that household's optimization model. Solver variables are
    created through the create_solver_variables method and updated with rules
    trough the update_solver_variables method.

    Parameters
    ----------
    data : dict
        Dictionary containing person-specific data including income, demographics,
        and other relevant information for tax calculations.

    Attributes
    ----------
    data : dict
        Dictionary storing all person-specific data.
    household : Household or None
        Reference to the household this person belongs to.
    init_labor_effect_weight : Optional[float]
        Initial weight for labor effect calculations.
    new_marginal_rate : grb.LinExpr or None
        Optimization variable representing the individual's marginal tax rate.
    marginal_rate_rules : list
        List of tax rules that affect the marginal rate calculation.
    new_net_income : grb.Var or None
        Optimization variable for new net income after tax optimization.
    weighted_tax_balance : grb.Var or None
        Optimization variable for weighted tax balance.
    new_income_increase : grb.Var or None
        Optimization variable for income increase due to labor effects.
    new_income_increase_factor : grb.Var or None
        Optimization variable for income increase factor.
    old_income_increase_factor : float or None
        Original income increase factor before optimization.
    change_in_income_increase_factor : grb.Var or None
        Optimization variable for change in income increase factor.
    weight_percentage_change : grb.Var or None
        Optimization variable for percentage change in weight.
    new_labor_effects_weight : grb.Var or None
        Optimization variable for adjusted labor effects weight.
    tax_balance : grb.Var or None
        Optimization variable for total tax balance (taxes minus benefits).
    """

    def __init__(self, data):
        self.data: dict = data
        self.household = None

        self.init_labor_effect_weight: Optional[float] = None

        self.new_marginal_rate = None
        self.marginal_rate_rules = []

        self.new_net_income = None
        self.weighted_tax_balance = None
        self.new_income_increase = None
        self.new_income_increase_factor = None
        self.old_income_increase_factor = None
        self.change_in_income_increase_factor = None
        self.weight_percentage_change = None

    def create_solver_variables(self):
        """
        Create basic optimization variables for the person in the Gurobi model.

        This method creates the fundamental optimization variables needed for
        tax and income calculations, including net income, tax balance, weighted
        tax balance, marginal rate, and labor effects weight. It is called when
        the household the person belongs to is assigned to the optimization.

        Notes
        -----
        This method must be called after the person is assigned to a household
        that has been added to an optimization system, as the model is obtained from
        the household. The variables created are:

        - new_net_income: Non-negative continuous variable for optimized net income
        - tax_balance: Continuous variable for total taxes minus benefits
        - weighted_tax_balance: Weighted version of tax_balance for macro purposes
        - new_marginal_rate: Taxpayer's effective marginal rate bounded between 0 and 1
        - new_labor_effects_weight: Continuous variable for labor effect adjustments

        Raises
        ------
        AttributeError
            If the person has not been assigned to a household with a model.
        """
        backend = self.household.tx.backend

        self.new_marginal_rate = backend.linear_expression()
        backend.add_constr(
            self.new_marginal_rate <= 1,
            name=f'upper_bound_new marginal_rate_{self["id"]}',
        )
        backend.add_constr(
            self.new_marginal_rate >= 0,
            name=f'lower_bound_new marginal_rate_{self["id"]}',
        )

    def create_labor_effects_variables(self):
        """
        Create optimization variables specifically for labor effects calculations.

        This method creates additional variables needed for modeling how tax changes
        affect labor supply and income generation behavior. The intuition is that the
        relative increase in real income by working more hours might increase or
        decrease due to reform.

        Notes
        -----
        The variables created are:

        - new_income_increase: Change in income due to labor supply effects
        - new_income_increase_factor: Factor representing income elasticity
        - change_in_income_increase_factor: Change in the income increase factor
        - weight_percentage_change: Percentage change in person's weight

        All variables have appropriate bounds to ensure realistic economic behavior.

        Raises
        ------
        AttributeError
            If the person has not been assigned to a household with a model.
        """
        backend = self.household.tx.backend
        self.new_income_increase = backend.add_var(
            name=f'new_income_increase_{self["id"]}',
            lb=-100_000,
            ub=100_000,
            var_type="continuous",
        )
        self.new_income_increase_factor = backend.add_var(
            name=f'new_income_increase_factor_{self["id"]}',
            lb=0,
            ub=10,
            var_type="continuous",
        )
        self.change_in_income_increase_factor = backend.add_var(
            name=f'change_in_income_increase_factor_{self["id"]}',
            lb=-10,
            ub=10,
            var_type="continuous",
        )
        self.weight_percentage_change = backend.add_var(
            name=f'weight_percentage_change_{self["id"]}',
            lb=-10,
            ub=10,
            var_type="continuous",
        )
        self.new_labor_effects_weight = backend.add_var(
            name=f'new_labor_effects_weight_{self["id"]}',
            lb=0,
            ub=100_000,
            var_type="continuous",
        )

    def update_solver_variables(self, rules: list[TaxRule]):
        """
        Calculate new net income by applying individual-level tax rules.

        This method computes the person's tax balance by applying all non-household
        level tax rules and creates optimization constraints for net income calculation.
        It is used to update the empty solver variables through the rules.

        Parameters
        ----------
        rules : list[TaxRule]
            List of tax rule objects to apply to this person. Only rules where
            `household_level` is False will be applied.

        Notes
        -----
        This method updates three solver variables to the optimization model:

        1. tax_balance: Sum of all applicable individual-level taxes and benefits
        2. weighted_tax_balance: Tax balance multiplied by person's weight for macro purposes
        3. new_net_income: Income before tax plus tax balance (benefits are negative taxes)

        Raises
        ------
        AttributeError
            If the person has not been assigned to a household with a model.
        """
        backend = self.household.tx.backend

        taxes_and_benefits = []
        for rule in rules:
            if not rule.household_level:
                taxes_and_benefits.append(rule.calculate_tax(self))

        self.tax_balance = backend.quicksum(taxes_and_benefits)
        self.weighted_tax_balance = self.tax_balance * self["weight"]
        self.new_net_income = self["income_before_tax"] + self.tax_balance

    @property
    def weight(self) -> int:
        """
        Get the weight of the person from their household.

        Returns
        -------
        int
            The weight factor from the household this person belongs to.

        Notes
        -----
        This property provides access to the household's weight, which is used
        in optimization calculations to represent the relative importance or
        frequency of this person's household type in the population.
        """
        return self.household.weight

    def __getitem__(self, key: str):
        """
        Get a data value for the person using dictionary-style access.

        Parameters
        ----------
        key : str
            The key to look up in the person's data dictionary.

        Returns
        -------
        Any
            The value associated with the given key in the person's data.

        Raises
        ------
        KeyError
            If the key is not found in the person's data dictionary.
        """
        if key in self.data:
            return self.data[key]
        else:
            raise KeyError(f"Invalid Key: {key}")

    def __setitem__(self, key, value):
        """
        Set a data value for the person using dictionary-style access.

        Parameters
        ----------
        key : str
            The key to set in the person's data dictionary.
        value : Any
            The value to associate with the given key.
        """
        self.data[key] = value

    def __repr__(self) -> str:
        """
        Return string representation of the person.

        Returns
        -------
        str
            A string describing the person's ID and household ID.
        """
        return f'Person {self.data["id"]} in household {self.data["hh_id"]}'
