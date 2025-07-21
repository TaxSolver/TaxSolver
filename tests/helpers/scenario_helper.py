from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.marginal_pressure_constraint import (
    MarginalPressureConstraint,
)
from tests.helpers.nld_rule_book import NLDRuleBook
from TaxSolver.objective import BudgetObjective
from TaxSolver.backend.cvxpy_backend import CvxpyBackend
from TaxSolver.tax_solver import TaxSolver
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.rule import BracketRule
from TaxSolver.backend.abstract_backend import AbstractBackend


class ScenarioHelper:
    def __init__(
        self,
        data_path: str,
        include_tags: list[str],
        exclude_tags: list[str],
        overall_income_constraint: float = 0.01,
        backend: AbstractBackend = CvxpyBackend(),
    ):
        self.households = DataLoader(
            data_path,
            income_before_tax="income_before_tax",
            income_after_tax="income_after_tax",
            weight="weight",
            id="id",
            hh_id="hh_id",
            mirror_id="mirror_id",
            input_vars=[
                "number_of_kids_0_5",
                "number_of_kids_6_11",
                "number_of_kids_12_15",
                "number_of_kids_16_17",
                "number_of_kids",
                "monthly_rent",
                "assets",
                "partner_income",
                "other_income",
                "woz",
                "mortgage_interest",
            ],
            group_vars=["fiscal_partner", "partner_type_of_income"],
        ).households

        tax_solver = TaxSolver(households=self.households, backend=backend)
        # Split input along inflection points to construct brackets
        for k_group in [
            "k_everybody",
            "k_single_working",
            "k_single_earner",
            "k_double_earner",
            "k_lowest_earner",
            "k_young_handicapped",
            "k_aow",
            "k_zzp",
            "k_employment",
            "k_renter",
            "k_homeowner",
            "k_couple",
            "k_single",
        ]:
            BracketInput.add_split_variables_to_solver(
                tx=tax_solver,
                target_var="income_before_tax",
                inflection_points=NLDRuleBook.default_inflection_points(),
                group_vars=[k_group],
            )

            # Define solver variables for the optimization
            group_brackets = BracketRule(
                name=f"brackets_{k_group}",
                var_name="income_before_tax",
                k_group_var=k_group,
                ub=1,
                lb=-1,
            )
            tax_solver.add_rules([group_brackets])

        BracketInput.add_split_variables_to_solver(
            tx=tax_solver,
            target_var="household_income_before_tax",
            inflection_points=NLDRuleBook.default_inflection_points(),
            group_vars=["k_everybody"],
        )

        # Define solver variables for the optimization
        household_income_brackets = BracketRule(
            name="household_income_brackets",
            var_name="household_income_before_tax",
            k_group_var="k_everybody",
            ub=1,
            lb=-1,
        )
        tax_solver.add_rules([household_income_brackets])

        self.marginal_pressure_constraint = MarginalPressureConstraint(0.9)

        self.budget_constraint = BudgetConstraint(
            "all_households",
            list(self.households.values()),
            0,
        )

        self.income_constraint = IncomeConstraint(
            overall_income_constraint,
            list(self.households.values()),
        )

        tax_solver.add_constraints(
            [
                self.marginal_pressure_constraint,
                self.budget_constraint,
                self.income_constraint,
            ]
        )

        rules = NLDRuleBook.rules_with_tags(include_tags, exclude_tags)
        tax_solver.add_rules(rules)

        self.objective = BudgetObjective(self.budget_constraint)

        tax_solver.add_objective(self.objective)

        self.opt_sys = tax_solver

    def solve(self):
        self.opt_sys.solve()
