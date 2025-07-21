from TaxSolver.constraints.constraint import Constraint
from TaxSolver.population.household import Household
from TaxSolver.population.person import Person


class LaborEffects(Constraint):
    def apply(self, tx):
        backend = tx.backend
        self.sq_wage_output = sum(
            [
                p["income_before_tax"] * p.init_labor_effect_weight
                for p in tx.people_with_labor_effects.values()
            ]
        )

        # Prepare macro variables for labor participation effects
        self.new_wage_output = backend.add_var(
            name="new_wage_output",
            lb=self.sq_wage_output * 0,
            ub=self.sq_wage_output * 2,
            var_type="continuous",
        )
        self.wage_output_change = backend.add_var(
            name="wage_output_change",
            lb=-1,
            ub=1,
            var_type="continuous",
        )

        backend.add_constr(
            self.new_wage_output == (1 + self.wage_output_change) * self.sq_wage_output,
            name="calc_wage_output_change",
        )

        for hh in tx.households.values():
            # If there is no mirror household, we can skip this household.
            # Adjusted weight does have to be set for the budget constraint to work.
            # As there are no labour effects, the adjusted weight is the same as the original weight.
            hh: Household
            mirror: Household = hh.mirror_hh

            if mirror is None:
                continue

            sq_hh_income = hh.old_household_income
            sq_hh_income += (
                10_000  # To prevent division by zero and very high elasticity effects.
            )

            for person, mirror_p in zip(hh.members, mirror.members):
                person: Person
                mirror_p: Person

                person.create_labor_effects_variables()
                mirror_p.create_labor_effects_variables()

                # First we need to check if the person is flexible.
                if person.init_labor_effect_weight is None:
                    person.new_labor_effects_weight = 0
                    mirror_p.new_labor_effects_weight = 0
                    continue

                elasticity = person["elasticity"]

                # First get the income jump in the status quo: how much does the household income increase if a person chooses to participate?
                sq_income_increase = (
                    mirror_p["income_after_tax"] - person["income_after_tax"]
                )

                person.old_income_increase_factor = (
                    sq_hh_income + sq_income_increase
                ) / sq_hh_income

                if person.old_income_increase_factor > 10:
                    print(
                        "Warning: old_income_increase_factor > 10 for person: ",
                        person["id"],
                    )

                # Then get the income jump in the new situation: how much does the household income increase if a person chooses to participate?
                backend.add_constr(
                    person.new_income_increase
                    == mirror_p.new_net_income - person.new_net_income
                )
                # Line below is following line rewritten:
                # new_income_increase_factor = (10_000 + hh.new_net_household_income + new_income_increase) / (10_000 + hh.new_net_household_income)
                # Add the 10_000 to prevent division by zero and very high elasticity effects.
                backend.add_constr(
                    (10_000 + hh.new_net_household_income)
                    * person.new_income_increase_factor
                    == (
                        10_000
                        + hh.new_net_household_income
                        + person.new_income_increase
                    ),
                    name=f'new_income_increase_factor_{person["id"]}',
                )

                # Now the crucial bit: with how many more % of extra income is working recommended in the new situation?
                backend.add_constr(
                    person.new_income_increase_factor
                    - person.old_income_increase_factor
                    == person.change_in_income_increase_factor,
                    name=f'new_participation_benefit_{person["id"]}',
                )

                backend.add_constr(
                    person.weight_percentage_change
                    == person.change_in_income_increase_factor * elasticity
                )

                backend.add_constr(
                    person.new_labor_effects_weight
                    == person.init_labor_effect_weight
                    - person.init_labor_effect_weight * person.weight_percentage_change,
                    name=f'calc_adjusted_labor_effects_weight_{person["id"]}',
                )
                backend.add_constr(
                    mirror_p.new_labor_effects_weight
                    == 0
                    + person.init_labor_effect_weight * person.weight_percentage_change,
                    name=f'calc_adjusted_labor_effects_weight_{mirror_p["id"]}',
                )

                self.extra_pretax_income = backend.add_var(
                    name=f'additional_pretax_income_{person["id"]}',
                    lb=-float("inf"),
                    ub=float("inf"),
                    var_type="continuous",
                )

                backend.add_constr(
                    self.extra_pretax_income
                    == mirror_p["income_before_tax"] * mirror_p.new_labor_effects_weight
                    - person["income_before_tax"] * person.new_labor_effects_weight
                )

        backend.add_constr(
            self.new_wage_output
            == backend.quicksum(
                [
                    p["income_before_tax"] * p.new_labor_effects_weight
                    for p in tx.people_with_labor_effects.values()
                ]
            )
        )
