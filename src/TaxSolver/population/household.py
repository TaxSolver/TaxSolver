from typing import List, Optional

from TaxSolver.population.person import Person


class Household:
    """
    Represents a household consisting of one or more persons in the tax system.

    A household is a collection of persons who are considered together for tax
    calculations and benefit determinations. It manages optimization variables
    and constraints related to household-level benefits and income calculations.

    Parameters
    ----------
    id : str
        Unique identifier for the household.
    members : List[Person]
        List of Person objects that belong to this household.
    weight : int or float, optional
        Weight factor for the household in optimization calculations, by default 1.

    Attributes
    ----------
    id : str
        Unique identifier for the household.
    members : List[Person]
        List of Person objects in the household.
    size : int
        Number of members in the household.
    weight : int or float
        Weight factor for optimization calculations.
    mirror_hh : Optional[Household]
        Reference to a mirror household for comparison purposes.
    model : grb.Model
        Gurobi optimization model (assigned when household is added to system).
    household_benefits : grb.Var
        Optimization variable representing total household benefits.
    weighted_household_benefits : grb.Var
        Optimization variable for weighted household benefits.
    new_net_household_income : grb.Var
        Optimization variable for new net household income after optimization.
    """

    def __init__(self, id: str, members: List[Person], weight=1) -> None:
        self.id = id
        self.members = members
        self.size = len(members)
        self.weight = weight
        self.mirror_hh: Optional[Household] = None

        for m in members:
            m.household = self

    def assign_to_system(self, sys) -> None:
        """
        Assign the household to an optimization system and create solver variables.

        This method creates the necessary Gurobi optimization variables for the
        household and also assigns solver variables to all household members.

        Parameters
        ----------
        sys : object
            The tax system object containing the Gurobi model to which this
            household will be assigned.

        Notes
        -----
        This method must be called before running optimization to ensure all
        necessary variables are created in the Gurobi model.
        """
        self.tx = sys
        [m.create_solver_variables() for m in self.members]

    def add_member(self, member: Person) -> None:
        """
        Add a new member to the household.

        Parameters
        ----------
        member : Person
            The Person object to add to the household.

        Notes
        -----
        This method updates the household size and sets the member's household
        reference to this household.
        """
        self.members.append(member)
        member.household = self
        self.size = len(self.members)

    def update_solver_variables(self, rules):
        """
        Calculate household-level benefits based on provided tax rules.

        This method computes the total household benefits by applying all
        household-level tax rules and creates the necessary optimization
        constraints for household income calculations.

        Parameters
        ----------
        rules : list
            List of tax rule objects that may apply at the household level.

        Raises
        ------
        AssertionError
            If no optimization model has been assigned to the household.
        AssertionError
            If member new net incomes have not been calculated.

        Notes
        -----
        This method defines three solver variables in the optimization model:
        1. Total household benefits from applicable rules (sum over household_benefits)
        2. Weighted household benefits (benefits * weight)
        3. New net household income (sum of member incomes + benefits)
        """
        assert self.tx, "No system assigned for household"
        backend = self.tx.backend
        assert self.members[0].new_net_income, "Person new net income not calculated"

        household_benefits = []
        for rule in rules:
            if rule.household_level:
                household_benefits.append(rule.calculate_tax(self))

        self.household_benefits = backend.quicksum(household_benefits)
        self.weighted_household_benefits = self.household_benefits * self.weight

        person_new_net_incomes = backend.quicksum(
            [person.new_net_income for person in self.members]
        )
        self.new_net_household_income = person_new_net_incomes + self.household_benefits

    def __repr__(self) -> str:
        """
        Return string representation of the household.

        Returns
        -------
        str
            A string describing the household ID and number of members.
        """
        return f"Household {self.id} with {self.size} members"

    @property
    def old_household_income(self):
        """
        Calculate the total old (pre-optimization) household income.

        Returns
        -------
        float
            Sum of after-tax income for all household members before optimization (can be accessed anytime).
        """
        return sum([m["income_after_tax"] for m in self.members])

    @property
    def first_member(self) -> Person:
        """
        Get the first member of the household.

        Returns
        -------
        Person
            The first Person object in the household members list.

        Notes
        -----
        This property is commonly used when household-level calculations need
        a reference member.
        """
        return self.members[0]
