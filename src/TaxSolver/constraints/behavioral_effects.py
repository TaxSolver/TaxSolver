"""
Behavioral Effects Constraint

Models the income change due to behavioral responses to marginal tax rate changes.

Assumed elasticity formula:
    behavioral_income_change = elasticity × (old_marginal_rate - new_marginal_rate) × income

The elasticity represents how much income increases (as a fraction) for a 
1 percentage point decrease in marginal tax pressure.

This changed income is then taxed at the new marginal rate:
    behavioral_tax_effect = behavioral_income_change × new_marginal_rate

The net effect on the person's income is:
    net_behavioral_effect = behavioral_income_change × (1 - new_marginal_rate)

This net effect is added directly to the person's new_net_income, and the tax effect
is added to their tax_balance. This ensures behavioral effects flow through to both
the income constraint and budget constraint automatically.

Backend support:
- Gurobi: Full quadratic constraint support (exact calculations)
- CVXPY/HiGHS: Uses linear approximation (tax at old marginal rate)
  HiGHS supports QP (quadratic objective) but not QCQP (quadratic constraints)
"""

from TaxSolver.constraints.constraint import Constraint
from TaxSolver.population.person import Person


class BehavioralEffects(Constraint):
    """
    Constraint that models behavioral responses to marginal tax rate changes.

    When marginal tax rates change, individuals may adjust their labor supply,
    affecting their income. This constraint captures that effect using an
    elasticity parameter.

    The behavioral effects are integrated directly into each person's new_net_income
    and tax_balance, so they automatically flow through to income constraints
    and budget constraints.

    Parameters
    ----------
    elasticity : float, optional
        The labor supply elasticity. If None, uses per-person elasticity from data.
        A value of 0.25 means a 1 percentage point DECREASE in marginal rate
        leads to a 0.25% INCREASE in income. Default is None.

    Attributes
    ----------
    elasticity : float or None
        Global elasticity override, or None to use per-person values.
    """

    def __init__(self, elasticity: float = None):
        self.elasticity = elasticity

    def _is_gurobi_backend(self, backend) -> bool:
        """Check if the backend is Gurobi (supports quadratic constraints)."""
        return backend.__class__.__name__ == "GurobiBackend"

    def apply(self, tx) -> None:
        """
        Apply behavioral effects to person incomes in the tax solver.

        For each person, this:
        1. Calculates the behavioral income change (gross)
        2. Calculates the tax on the behavioral income change
        3. Updates the person's new_net_income to include the net behavioral effect
        4. Updates the person's tax_balance to include the behavioral tax
        5. Updates household incomes to reflect the changes

        For Gurobi backend, uses exact quadratic constraints.
        For other backends, uses linear approximation.

        Parameters
        ----------
        tx : TaxSolver
            The tax solver instance to apply behavioral effects to.
        """
        backend = tx.backend
        use_quadratic = self._is_gurobi_backend(backend)

        if use_quadratic:
            print("Behavioral effects: Using exact quadratic constraints (Gurobi)")
        else:
            print("Behavioral effects: Using linear approximation (non-Gurobi backend)")

        for person in tx.people.values():
            person: Person

            # Get elasticity - use global override or per-person value
            if self.elasticity is not None:
                elasticity = self.elasticity
            else:
                # Try to get per-person elasticity, default to 0 if not available
                try:
                    elasticity = person["elasticity"]
                    if elasticity is None:
                        elasticity = 0
                except KeyError:
                    elasticity = 0

            # Skip if no behavioral effect (elasticity = 0)
            if elasticity == 0:
                person.behavioral_income_change = 0
                person.behavioral_tax_effect = 0
                person.net_behavioral_effect = 0
                continue

            income = person["income_before_tax"]
            old_marginal_rate = person["marginal_rate_current"]

            # Gross income change due to behavioral response
            person.behavioral_income_change = (
                elasticity * (old_marginal_rate - person.new_marginal_rate) * income
            )

            # Create variable for behavioral tax effect
            behavioral_tax_var = backend.add_var(
                name=f'behavioral_tax_effect_{person["id"]}',
                lb=-float("inf"),
                ub=float("inf"),
                var_type="continuous",
            )

            # Create variable for net behavioral effect (after-tax income change)
            net_behavioral_var = backend.add_var(
                name=f'net_behavioral_effect_{person["id"]}',
                lb=-float("inf"),
                ub=float("inf"),
                var_type="continuous",
            )

            if use_quadratic:
                # Gurobi: Use exact quadratic constraints
                backend.add_constr(
                    behavioral_tax_var
                    == person.behavioral_income_change * person.new_marginal_rate,
                    name=f'behavioral_tax_quadratic_{person["id"]}',
                )
                # net_behavioral_effect = behavioral_income_change × (1 - new_marginal_rate)
                backend.add_constr(
                    net_behavioral_var
                    == person.behavioral_income_change * (1 - person.new_marginal_rate),
                    name=f'net_behavioral_quadratic_{person["id"]}',
                )
            else:
                # Non-Gurobi: Use linear approximation at old marginal rate (= data)
                backend.add_constr(
                    behavioral_tax_var
                    == person.behavioral_income_change * old_marginal_rate,
                    name=f'behavioral_tax_linear_approx_{person["id"]}',
                )
                backend.add_constr(
                    net_behavioral_var
                    == person.behavioral_income_change * (1 - old_marginal_rate),
                    name=f'net_behavioral_linear_approx_{person["id"]}',
                )

            person.behavioral_tax_effect = behavioral_tax_var
            person.net_behavioral_effect = net_behavioral_var

            # Update person's new_net_income to include net behavioral effect
            person.new_net_income = person.new_net_income + net_behavioral_var

            # Update person's tax_balance to include behavioral tax
            person.tax_balance = person.tax_balance - behavioral_tax_var
            person.weighted_tax_balance = person.tax_balance * person["weight"]

        # Update household incomes to reflect behavioral effects
        for hh in tx.households.values():
            person_new_net_incomes = backend.quicksum(
                [person.new_net_income for person in hh.members]
            )
            hh.new_net_household_income = person_new_net_incomes + hh.household_benefits

        tx.behavioral_effects_constraint = self
        print(f"Behavioral effects applied to {len(tx.people)} persons")

    def __repr__(self) -> str:
        if self.elasticity is not None:
            return f"BehavioralEffects(elasticity={self.elasticity})"
        return "BehavioralEffects(per-person elasticity)"
