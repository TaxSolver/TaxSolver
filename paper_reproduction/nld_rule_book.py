"""Dutch Rule Book for the new TaxSolver API.

This is a stand-alone rule-book implementation that mirrors the original
NLDRuleBook.

"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Callable

from TaxSolver.rule import (
    TaxRule,
    FlatTaxRule,
    BenefitRule,
    ExistingBenefit,
    HouseholdBenefit,
    BracketRule,
)
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.constraints.rule_constraints import MutuallyExclusiveRulesConstraint

if TYPE_CHECKING:
    import TaxSolver as tx


def tag(*tags):
    """Decorator that attaches an immutable `tags` tuple to a function."""

    def decorator(func):
        func.tags = tags
        return func

    return decorator


class NLDRuleBook:
    """Dutch rule-book implementation using the new object-returning API.

    This class provides:
    1. Static configuration methods (inflection points, k_groups, etc.)
    2. Rule factory methods that return lists of TaxRule objects
    3. Tag-based selection helpers

    Note: Bracket rules (alpha_b, add_brackets) require additional setup
    via BracketInput.add_split_variables_to_solver() in your notebook.
    """

    # ------------------------------------------------------------------
    # CONFIGURATION METHODS
    # ------------------------------------------------------------------

    @staticmethod
    def default_inflection_points() -> List[int]:
        """Return canonical break-points for progressive tax brackets.

        Base points [0, 10_000, 10_000_000] plus:
        - 20k-35k step 5k
        - 50k-110k step 20k
        - 150k-250k step 50k
        """
        base = [0, 10_000, 10_000_000]
        pts = base.copy()
        pts.extend(range(20_000, 40_000, 5_000))
        pts.extend(range(50_000, 120_000, 20_000))
        pts.extend(range(150_000, 250_001, 50_000))
        return sorted(pts)

    @staticmethod
    def k_b_inflection_points() -> List[int]:
        """Reduced inflection points for k-group brackets (every 2nd point)."""
        all_points = NLDRuleBook.default_inflection_points()
        return [ip for i, ip in enumerate(all_points) if i % 2 == 0]

    @staticmethod
    def default_rent_inflection_points() -> List[int]:
        """Inflection points for rent-based brackets."""
        return [i * 12 for i in range(0, 2000, 400)]

    @staticmethod
    def default_k_groups() -> List[str]:
        """Default k-groups for bracket rules."""
        return [
            "k_lowest_earner",
            "k_young_handicapped",
            "k_aow",
            "k_zzp",
            "k_employment",
        ]

    @staticmethod
    def all_k_groups() -> List[str]:
        """All available k-groups for comprehensive analysis."""
        return [
            "k_everybody",
            "k_lowest_earner",
            "k_young_handicapped",
            "k_aow",
            "k_zzp",
            "k_employment",
            "k_single",
            "k_single_earner",
            "k_double_earner",
            "k_single_working",
            "k_renter",
            "k_homeowner",
            "k_couple",
        ]

    @staticmethod
    def default_wealth_levels() -> List[str]:
        """Wealth level indicators for wealth-capped rules."""
        return ["k_not_wealthy"]

    @staticmethod
    def add_wealth_capped_variant(
        rules: List[TaxRule],
        wealth_levels: List[str] = None,
    ) -> List[TaxRule]:
        """Add wealth-capped variants of benefit rules.

        For each rule, creates a copy with the wealth_level variable appended
        to var_name and weight incremented by 1.

        Parameters
        ----------
        rules : List[TaxRule]
            Original rules to create wealth-capped variants for
        wealth_levels : List[str], optional
            Wealth level variables to cap with (default: ["k_not_wealthy"])

        Returns
        -------
        List[TaxRule]
            Original rules + their wealth-capped variants
        """
        if wealth_levels is None:
            wealth_levels = NLDRuleBook.default_wealth_levels()

        all_rules = list(rules)  # Start with original rules

        for rule in rules:
            for wealth_level in wealth_levels:
                # Get the original var_name as a list
                if isinstance(rule.var_name, list):
                    new_var_name = rule.var_name + [wealth_level]
                else:
                    new_var_name = [rule.var_name, wealth_level]

                # Create the capped variant with weight + 1
                # BenefitRule and HouseholdBenefit only have 'ub', not 'lb'
                capped_rule = rule.__class__(
                    name=f"{rule.name}_{wealth_level}",
                    var_name=new_var_name,
                    ub=rule.ub,
                    weight=rule.weight + 1,
                )
                all_rules.append(capped_rule)

        return all_rules

    # ------------------------------------------------------------------
    # BRACKET RULE HELPERS
    # These methods help set up brackets but require BracketInput in notebook
    # ------------------------------------------------------------------

    @staticmethod
    def setup_alpha_b(
        tax_solver: "tx.TaxSolver",
        inflection_points: List[int] = None,
        target: str = "income_before_tax",
        rate_ub: float = 0.8,
        rate_lb: float = -0.5,
        ascending: bool = True,
        weight: int = 1,
    ) -> BracketRule:
        """Set up main progressive income tax brackets.

        Usage in notebook:
            # First add split variables
            BracketInput.add_split_variables_to_solver(
                tx=tax_solver,
                target_var="income_before_tax",
                inflection_points=inflection_points,
                group_vars=["k_everybody"],
            )
            # Then get and add the bracket rule
            bracket_rule = NLDRuleBook.setup_alpha_b(tax_solver, inflection_points)
            tax_solver.add_rules([bracket_rule])
        """
        if inflection_points is None:
            inflection_points = NLDRuleBook.default_inflection_points()

        # Create bracket rule for main income tax
        bracket_rule = BracketRule(
            name=f"{target}_k_everybody",
            var_name=target,
            k_group_var="k_everybody",
            ub=rate_ub,
            lb=rate_lb,
            weight=weight,
        )

        return bracket_rule

    @staticmethod
    def setup_k_group_brackets(
        tax_solver: "tx.TaxSolver",
        k_groups: List[str] = None,
        inflection_points: List[int] = None,
        target: str = "income_before_tax",
        rate_ub: float = 0,
        rate_lb: float = -0.5,
        weight: int = 2,
    ) -> List[BracketRule]:
        """Set up brackets for multiple k-groups.

        Usage in notebook:
            for k_group in k_groups:
                BracketInput.add_split_variables_to_solver(
                    tx=tax_solver,
                    target_var="income_before_tax",
                    inflection_points=k_b_inflection_points,
                    group_vars=[k_group],
                )
            bracket_rules = NLDRuleBook.setup_k_group_brackets(tax_solver, k_groups)
            tax_solver.add_rules(bracket_rules)
        """
        if k_groups is None:
            k_groups = NLDRuleBook.default_k_groups()
        if inflection_points is None:
            inflection_points = NLDRuleBook.k_b_inflection_points()

        rules = []
        for k_group in k_groups:
            rule = BracketRule(
                name=f"{target}_{k_group}",
                var_name=target,
                k_group_var=k_group,
                ub=rate_ub,
                lb=rate_lb,
                weight=weight,
            )
            rules.append(rule)

        return rules

    # ------------------------------------------------------------------
    # EXISTING BENEFITS (Status Quo)
    # ------------------------------------------------------------------

    @staticmethod
    @tag("test", "basic", "sq", "toeslagen")
    def existing_benefits() -> List[TaxRule]:
        """Existing benefits: KB, KGB, rental_support, ZVW.

        ExistingBenefit weight: 10
        """
        benefits = ["kb", "kgb", "rental_support", "zvw_benefit"]
        return [
            ExistingBenefit(
                name=f"sq_{b}",
                var_name=b,
                lb=0.9,
                ub=1.1,
                weight=10,
            )
            for b in benefits
        ]

    @staticmethod
    @tag("basic", "enforce_kot", "test")
    def force_kot() -> List[TaxRule]:
        """KOT (kinderopvangtoeslag) forced at rate 1.

        ExistingBenefit weight: 10
        """
        return [
            ExistingBenefit(
                name="sq_kot",
                var_name="kot",
                lb=1.0,
                ub=1.0,  # Force to 1
                weight=10,
            )
        ]

    # ------------------------------------------------------------------
    # HOUSEHOLD RENT BENEFITS
    # ------------------------------------------------------------------

    @staticmethod
    @tag("household", "rent", "basic", "test")
    def household_rent_benefit() -> List[TaxRule]:
        """Rent benefit for households up to social limit.

        K-group HouseholdBenefit weight: 2
        """
        base_rules = [
            HouseholdBenefit(
                name="household_rent_benefit",
                var_name="k_rent_up_to_social_limit",
                ub=1,
                weight=2,
            ),
        ]
        return NLDRuleBook.add_wealth_capped_variant(base_rules)

    @staticmethod
    @tag("household", "rent", "basic")
    def household_rent_benefit_social() -> List[TaxRule]:
        """Rent benefits for social housing tenants.

        K-group HouseholdBenefit weight: 2
        """
        base_rules = [
            HouseholdBenefit(
                name="household_rent_benefit_sociaal",
                var_name="k_social_rent",
                ub=1,
                weight=2,
            ),
            HouseholdBenefit(
                name="vaste_toelage_huur_huishouden_sociaal_single_topup",
                var_name=["k_social_rent", "k_single"],
                ub=0.5,
                weight=2,
            ),
            HouseholdBenefit(
                name="vaste_toelage_huur_huishouden_single_topup",
                var_name=["k_rent_up_to_social_limit", "k_single"],
                ub=0.5,
                weight=2,
            ),
        ]
        return NLDRuleBook.add_wealth_capped_variant(base_rules)

    # ------------------------------------------------------------------
    # YOUNG HANDICAPPED BENEFIT
    # ------------------------------------------------------------------

    @staticmethod
    @tag("young_handicapped", "basic", "test")
    def young_handicapped_benefit() -> List[TaxRule]:
        """Benefit for young handicapped individuals.

        K-group BenefitRule weight: 2
        """
        base_rules = [
            BenefitRule(
                name="young_handicapped_benefit",
                var_name="k_young_handicapped",
                ub=5_000,
                weight=2,
            ),
        ]
        return NLDRuleBook.add_wealth_capped_variant(base_rules)

    # ------------------------------------------------------------------
    # HOUSEHOLD TYPE BENEFITS
    # ------------------------------------------------------------------

    @staticmethod
    @tag("household", "basic", "test")
    def household_type_benefit() -> List[TaxRule]:
        """Benefits based on household composition.

        K-group HouseholdBenefit weight: 2
        """
        return [
            HouseholdBenefit(
                name="single_benefit",
                var_name="k_single",
                ub=5_000,
                weight=2,
            ),
            HouseholdBenefit(
                name="double_earner_benefit",
                var_name="k_double_earner",
                ub=5_000,
                weight=2,
            ),
            HouseholdBenefit(
                name="single_earner_benefit",
                var_name="k_single_earner",
                ub=5_000,
                weight=2,
            ),
        ]

    # ------------------------------------------------------------------
    # BASISTOESLAG (Base Allowance)
    # ------------------------------------------------------------------

    @staticmethod
    @tag("basic", "minimal-test")
    def basistoeslag() -> List[TaxRule]:
        """Base allowance per person."""
        base_rules = [
            BenefitRule(
                name="inkomensonafhankelijke_zorgtoeslag_persoon",
                var_name="k_everybody",
                ub=5_000,
                weight=1,
            ),
        ]
        return NLDRuleBook.add_wealth_capped_variant(base_rules)

    @staticmethod
    @tag("basic", "household", "test", "test_single_household")
    def basistoeslag_huishouden() -> List[TaxRule]:
        """Base allowance per household.

        k_everybody HouseholdBenefit weight: 1
        """
        base_rules = [
            HouseholdBenefit(
                name="inkomensonafhankelijke_zorgtoeslag_huishouden",
                var_name="k_everybody",
                ub=10_000,
                weight=1,
            ),
        ]
        return NLDRuleBook.add_wealth_capped_variant(base_rules)

    @staticmethod
    @tag("basic", "test")
    def basistoeslag_huishouden_single_topup() -> List[TaxRule]:
        """Single household topup for base allowance.

        K-group HouseholdBenefit weight: 2
        """
        base_rules = [
            HouseholdBenefit(
                name="inkomensonafhankelijke_zorgtoeslag_huishouden_single_topup",
                var_name="k_single",
                ub=1_200,
                weight=2,
            ),
        ]
        return NLDRuleBook.add_wealth_capped_variant(base_rules)

    # ------------------------------------------------------------------
    # MORTGAGE INTEREST DEDUCTION
    # ------------------------------------------------------------------

    @staticmethod
    @tag("personal", "basic", "test")
    def mortgage_interest_deduction() -> List[TaxRule]:
        """Mortgage interest deduction (hypotheekrenteaftrek)."""
        return [
            BenefitRule(
                name="mortgage_interest_deduction",
                var_name="i_mortgage_interest",
                ub=0.375,
                weight=2,
            ),
        ]

    # ------------------------------------------------------------------
    # CHILD BENEFITS
    # ------------------------------------------------------------------

    @staticmethod
    @tag("basic", "child", "test")
    def household_benefit() -> List[TaxRule]:
        """Child benefits (kinderbijslag)."""
        # Main benefit with wealth cap
        main_rule = [
            HouseholdBenefit(
                name="simpel_kb",
                var_name="i_number_of_kids",
                ub=10_000,
                weight=1,
            ),
        ]
        rules_with_cap = NLDRuleBook.add_wealth_capped_variant(main_rule)

        # Age topups
        rules_with_cap.extend(
            [
                HouseholdBenefit(
                    name="simpel_kb_topup_0_5",
                    var_name="i_number_of_kids_0_5",
                    ub=2_500,
                    weight=1,
                ),
                HouseholdBenefit(
                    name="simpel_kb_topup_6_11",
                    var_name="i_number_of_kids_6_11",
                    ub=2_500,
                    weight=1,
                ),
                HouseholdBenefit(
                    name="simpel_kb_topup_12_15",
                    var_name="i_number_of_kids_12_15",
                    ub=2_500,
                    weight=1,
                ),
                HouseholdBenefit(
                    name="simpel_kb_topup_16_17",
                    var_name="i_number_of_kids_16_17",
                    ub=2_500,
                    weight=1,
                ),
            ]
        )
        return rules_with_cap

    @staticmethod
    @tag("basic", "household", "test")
    def household_benefit_single_topup() -> List[TaxRule]:
        """Single parent topup for child benefits.

        K-group (k_single) HouseholdBenefit weight: 2
        """
        base_rules = [
            HouseholdBenefit(
                name="simpel_kb_single_topup",
                var_name=["i_number_of_kids", "k_single"],
                ub=2_500,
                weight=2,
            ),
        ]
        return NLDRuleBook.add_wealth_capped_variant(base_rules)

    # ------------------------------------------------------------------
    # HOMEOWNER TAXES
    # ------------------------------------------------------------------

    @staticmethod
    @tag("basic", "homeowner", "test")
    def ewf() -> List[TaxRule]:
        """Eigen-woningforfait (imputed rent tax on home value)."""
        return [
            FlatTaxRule(
                name="ewf",
                var_name="i_woz",
                lb=0,
                ub=0.1,
                weight=2,
            ),
        ]

    # ------------------------------------------------------------------
    # CONDITIONAL BENEFITS (Verzilverbaar)
    # ------------------------------------------------------------------

    @staticmethod
    @tag("basic", "test", "verzilverbaar")
    def add_zeta_k() -> List[TaxRule]:
        """Conditional benefits per k_group (verzilverbaar).

        Creates a conditional benefit for each k_group.
        K-group BenefitRule weight: 2
        """
        k_groups = NLDRuleBook.default_k_groups()
        return [
            BenefitRule(
                name=f"conditional_benefit_{var}",
                var_name=var,
                ub=10_000,
                weight=2,
            )
            for var in k_groups
        ]

    # ------------------------------------------------------------------
    # TAG SELECTION HELPERS
    # ------------------------------------------------------------------

    @classmethod
    def get_methods_with_tags(
        cls,
        include_tags: List[str],
        exclude_tags: List[str],
    ) -> List[str]:
        """Get method names that match the tag criteria.

        A method is included if:
        - It has at least one tag from include_tags AND
        - It has no tags from exclude_tags
        """
        methods = []
        for name in dir(cls):
            if name.startswith("_"):
                continue
            method = getattr(cls, name)
            if callable(method) and hasattr(method, "tags"):
                method_tags = set(method.tags)
                if method_tags.intersection(
                    include_tags
                ) and not method_tags.intersection(exclude_tags):
                    methods.append(name)
        return methods

    @classmethod
    def rules_with_tags(
        cls,
        include_tags: List[str],
        exclude_tags: List[str],
    ) -> List[TaxRule]:
        """Get all rule objects matching the tag criteria."""
        rule_objects: List[TaxRule] = []
        method_names = cls.get_methods_with_tags(include_tags, exclude_tags)

        if not method_names:
            raise ValueError(
                f"No rules found with include tags {include_tags} / exclude {exclude_tags}"
            )

        for method_name in method_names:
            rules = getattr(cls, method_name)()
            rule_objects.extend(rules)

        return rule_objects

    @classmethod
    def list_available_tags(cls) -> set:
        """List all available tags across all methods."""
        all_tags = set()
        for name in dir(cls):
            if name.startswith("_"):
                continue
            method = getattr(cls, name)
            if callable(method) and hasattr(method, "tags"):
                all_tags.update(method.tags)
        return all_tags

    @classmethod
    def list_methods_and_tags(cls) -> dict:
        """List all methods and their associated tags."""
        result = {}
        for name in dir(cls):
            if name.startswith("_"):
                continue
            method = getattr(cls, name)
            if callable(method) and hasattr(method, "tags"):
                result[name] = list(method.tags)
        return result

    # ------------------------------------------------------------------
    # INCOME TYPE SELECTOR HELPER
    # ------------------------------------------------------------------

    @staticmethod
    def type_of_income_selector(type_of_income: str) -> Callable:
        """Create a filter function for households based on income type.

        Usage:
            filter_func = NLDRuleBook.type_of_income_selector("ZZP")
            zzp_households = [hh for hh in households if filter_func(hh)]
        """

        def func(household):
            if len(household.members) > 1:
                return (
                    household.members[0]["type_of_income"] == type_of_income
                    and household.members[1]["type_of_income"] == type_of_income
                )
            else:
                return household.members[0]["type_of_income"] == type_of_income

        return func


# ------------------------------------------------------------------
# CONVENIENCE FUNCTION FOR FULL SETUP
# ------------------------------------------------------------------


def setup_nl_optimization(
    tax_solver: "tx.TaxSolver",
    k_groups: List[str] = None,
    include_tags: List[str] = None,
    exclude_tags: List[str] = None,
    add_main_brackets: bool = True,
    add_k_group_brackets: bool = True,
    add_household_brackets: bool = True,
    ascending_main_brackets: bool = True,
    max_main_brackets: int = 5,
    min_gap_main_brackets: int = 3,
    max_k_group_brackets: int = 3,
    min_gap_k_group_brackets: int = 1,
    last_k_group_bracket_zero: bool = True,
) -> List[TaxRule]:
    """Convenience function to set up full NL tax optimization.

    This adds:
    1. Main income brackets (if add_main_brackets=True)
    2. K-group specific brackets (if add_k_group_brackets=True)
    3. Household income brackets (if add_household_brackets=True)
    4. All rules matching the tag criteria
    5. Bracket constraints (ascending, max_brackets, min_gap)

    Parameters
    ----------
    tax_solver : TaxSolver
        The tax solver instance to configure
    k_groups : List[str], optional
        K-groups to add brackets for (default: NLDRuleBook.default_k_groups())
    include_tags : List[str], optional
        Tags to include (default: ["basic"])
    exclude_tags : List[str], optional
        Tags to exclude (default: ["verzilverbaar", "toeslagen"])
    add_main_brackets : bool
        Whether to add main income brackets
    add_k_group_brackets : bool
        Whether to add k-group specific brackets
    add_household_brackets : bool
        Whether to add household income brackets
    ascending_main_brackets : bool
        Whether to enforce ascending rates for main brackets (default: True)
    max_main_brackets : int
        Maximum number of active main brackets (default: 5)
    min_gap_main_brackets : int
        Minimum gap between active main brackets (default: 3)
    max_k_group_brackets : int
        Maximum number of active k-group brackets (default: 3)
    min_gap_k_group_brackets : int
        Minimum gap between active k-group brackets (default: 1)
    last_k_group_bracket_zero : bool
        Whether to force last k-group bracket to have rate=0 (default: True)

    Returns
    -------
    List[TaxRule]
        All rules that were added
    """
    if k_groups is None:
        k_groups = NLDRuleBook.default_k_groups()
    if include_tags is None:
        include_tags = ["basic"]
    if exclude_tags is None:
        exclude_tags = ["verzilverbaar", "toeslagen"]

    all_rules = []
    inflection_points = NLDRuleBook.default_inflection_points()
    k_b_inflection_points = NLDRuleBook.k_b_inflection_points()

    # 1. Add main income brackets
    if add_main_brackets:
        BracketInput.add_split_variables_to_solver(
            tx=tax_solver,
            target_var="income_before_tax",
            inflection_points=inflection_points,
            group_vars=["k_everybody"],
        )
        main_bracket = NLDRuleBook.setup_alpha_b(tax_solver, inflection_points)
        all_rules.append(main_bracket)

    # 2. Add k-group brackets
    if add_k_group_brackets:
        for k_group in k_groups:
            try:
                BracketInput.add_split_variables_to_solver(
                    tx=tax_solver,
                    target_var="income_before_tax",
                    inflection_points=k_b_inflection_points,
                    group_vars=[k_group],
                )
            except Exception as e:
                print(f"Warning: Could not add bracket input for {k_group}: {e}")

        k_group_rules = NLDRuleBook.setup_k_group_brackets(
            tax_solver, k_groups, k_b_inflection_points
        )
        all_rules.extend(k_group_rules)

    # 3. Add household income brackets
    if add_household_brackets:
        try:
            BracketInput.add_split_variables_to_solver(
                tx=tax_solver,
                target_var="household_income_before_tax",
                inflection_points=inflection_points,
                group_vars=["k_everybody"],
            )
            hh_bracket = BracketRule(
                name="household_income_before_tax_k_everybody",
                var_name="household_income_before_tax",
                k_group_var="k_everybody",
                ub=0.8,
                lb=-0.5,
            )
            all_rules.append(hh_bracket)
        except Exception as e:
            print(f"Warning: Could not add household brackets: {e}")

    # 4. Add other rules based on tags
    try:
        tagged_rules = NLDRuleBook.rules_with_tags(include_tags, exclude_tags)
        all_rules.extend(tagged_rules)
    except ValueError as e:
        print(f"Warning: {e}")

    # Add all rules to solver
    tax_solver.add_rules(all_rules)

    # 5. Add bracket constraints (after rules are bound)
    backend = tax_solver.backend

    # Find main bracket rules
    main_bracket_flat_rules = []
    for rule in all_rules:
        if (
            isinstance(rule, BracketRule)
            and "k_everybody" in rule.name
            and "household" not in rule.name
        ):
            main_bracket_flat_rules = rule.flat_rules
            break

    # 5a. Ascending constraints for main brackets
    if add_main_brackets and ascending_main_brackets and main_bracket_flat_rules:
        for flat_rule in main_bracket_flat_rules:
            if flat_rule.prev_bracket is not None:
                backend.add_constr(
                    flat_rule.rate >= flat_rule.prev_bracket.rate,
                    name=f"ascending_{flat_rule.name}",
                )

    # 5b. Max brackets constraint for main brackets
    if add_main_brackets and max_main_brackets and main_bracket_flat_rules:
        active_brackets = backend.quicksum([r.b for r in main_bracket_flat_rules])
        backend.add_constr(
            active_brackets <= max_main_brackets,
            name="max_main_brackets",
        )

    # 5c. Min gap constraint for main brackets
    if add_main_brackets and min_gap_main_brackets > 0 and main_bracket_flat_rules:
        for i in range(len(main_bracket_flat_rules) - min_gap_main_brackets):
            neighbor_set = main_bracket_flat_rules[i : i + min_gap_main_brackets + 1]
            set_sum = backend.quicksum([r.b for r in neighbor_set])
            backend.add_constr(set_sum <= 1, name=f"main_min_gap_{i}")

    # 5d. K-group bracket constraints
    if add_k_group_brackets:
        for rule in all_rules:
            if (
                isinstance(rule, BracketRule)
                and "k_everybody" not in rule.name
                and "household" not in rule.name
            ):
                k_flat_rules = rule.flat_rules

                # Max brackets
                if max_k_group_brackets and k_flat_rules:
                    active_k_brackets = backend.quicksum([r.b for r in k_flat_rules])
                    backend.add_constr(
                        active_k_brackets <= max_k_group_brackets,
                        name=f"max_brackets_{rule.name}",
                    )

                # Min gap
                if min_gap_k_group_brackets > 0 and k_flat_rules:
                    for i in range(len(k_flat_rules) - min_gap_k_group_brackets):
                        neighbor_set = k_flat_rules[
                            i : i + min_gap_k_group_brackets + 1
                        ]
                        set_sum = backend.quicksum([r.b for r in neighbor_set])
                        backend.add_constr(
                            set_sum <= 1, name=f"kgroup_min_gap_{rule.name}_{i}"
                        )

                # Last bracket zero
                if last_k_group_bracket_zero and k_flat_rules:
                    backend.add_constr(
                        k_flat_rules[-1].rate == 0,
                        name=f"last_zero_{rule.name}",
                    )

    return all_rules


def get_mutually_exclusive_constraints() -> List[MutuallyExclusiveRulesConstraint]:
    """Get all mutually exclusive rule constraints for NL tax optimization.

    These constraints mirror the old codebase's MutuallyExclusive class.
    They ensure that certain rules cannot be active at the same time.

    Key constraints:
    - simpel_kb vs sq_kb: Can only use new OR existing child benefit
    - basistoeslag variants: Only one type of base allowance
    - basistoeslag vs sq_zvw_benefit: Can't have both
    - Rent benefit alternatives: Only one rent benefit type

    Returns
    -------
    List[MutuallyExclusiveRulesConstraint]
        List of mutually exclusive constraints to add to the solver
    """
    constraints = []

    # 1. simpel_kb vs sq_kb - can only use one child benefit system
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "simpel_kb",
                "sq_kb",
            ]
        )
    )

    # 2. basistoeslag variants - only one type of base allowance
    # (huishouden vs persoon, and their k_not_wealthy variants)
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "inkomensonafhankelijke_zorgtoeslag_huishouden",
                "inkomensonafhankelijke_zorgtoeslag_persoon",
                "inkomensonafhankelijke_zorgtoeslag_huishouden_k_not_wealthy",
                "inkomensonafhankelijke_zorgtoeslag_persoon_k_not_wealthy",
            ]
        )
    )

    # 3. Rent benefit alternatives - only one new rent benefit type
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "household_rent_benefit",
                "household_rent_benefit_k_not_wealthy",
                "household_rent_benefit_sociaal",
                "household_rent_benefit_sociaal_k_not_wealthy",
            ]
        )
    )

    # 4. Rent benefits including sq_rental_support
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "household_rent_benefit",
                "household_rent_benefit_k_not_wealthy",
                "household_rent_benefit_sociaal",
                "household_rent_benefit_sociaal_k_not_wealthy",
                "sq_rental_support",
            ]
        )
    )

    # 5. basistoeslag_huishouden vs sq_zvw_benefit
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "inkomensonafhankelijke_zorgtoeslag_huishouden",
                "sq_zvw_benefit",
            ]
        )
    )

    # 6. basistoeslag_persoon vs sq_zvw_benefit
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "inkomensonafhankelijke_zorgtoeslag_persoon",
                "sq_zvw_benefit",
            ]
        )
    )

    # 7. basistoeslag_huishouden_k_not_wealthy vs sq_zvw_benefit
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "inkomensonafhankelijke_zorgtoeslag_huishouden_k_not_wealthy",
                "sq_zvw_benefit",
            ]
        )
    )

    # 8. basistoeslag_persoon_k_not_wealthy vs sq_zvw_benefit
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "inkomensonafhankelijke_zorgtoeslag_persoon_k_not_wealthy",
                "sq_zvw_benefit",
            ]
        )
    )

    # 9. basistoeslag_huishouden_single_topup_k_not_wealthy vs sq_zvw_benefit
    constraints.append(
        MutuallyExclusiveRulesConstraint(
            [
                "inkomensonafhankelijke_zorgtoeslag_huishouden_single_topup_k_not_wealthy",
                "sq_zvw_benefit",
            ]
        )
    )

    return constraints
