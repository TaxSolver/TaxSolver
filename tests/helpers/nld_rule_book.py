"""Object-based rule book.

This is the *new* rule-book implementation where every rulebook method
**returns** a *list of rule objects* (``TaxRule``, ``BenefitRule`` …) rather
than mutating a running ``TaxSolver`` instance.  That makes it compatible
with the modern flow used in ``tests/test_basic_small.py`` where rules are
collected first and the solver is constructed afterwards.

Only a subset of rules has been ported so far (those tagged with
``"test"``).  The remaining methods are left as *TODO* stubs so that the
module can be imported while we migrate incrementally.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from TaxSolver.rule import TaxRule
from TaxSolver.rule import FlatTaxRule
from TaxSolver.rule import BenefitRule
from TaxSolver.rule import ExistingBenefit
from TaxSolver.rule import HouseholdBenefit

if TYPE_CHECKING:  # pragma: no cover
    pass


def tag(*tags):
    """Decorator that attaches an immutable ``tags`` tuple to a function."""

    def decorator(func):
        func.tags = tags  # type: ignore[attr-defined]
        return func

    return decorator


class NLDRuleBook:
    """New object-returning implementation of the Dutch rule-book."""

    # ---------------------------------------------------------------------
    # Helper utilities
    # ---------------------------------------------------------------------
    @classmethod
    def _return(cls, *rules: "TaxRule") -> list["TaxRule"]:
        """Convenience: wrap arbitrary rule objects in a list, flattening
        nested lists.
        """
        flat: list["TaxRule"] = []
        for r in rules:
            if isinstance(r, list):
                flat.extend(r)
            else:
                flat.append(r)  # type: ignore[arg-type]
        return flat

    # ------------------------------------------------------------------
    # PORTED RULES (test/basic/sq tags)
    # ------------------------------------------------------------------

    @staticmethod
    @tag("basic", "homeowner", "test")
    def ewf() -> list["TaxRule"]:
        """Eigen-woningforfait (imputed rent)."""
        rule = FlatTaxRule(
            name="ewf",
            var_name="i_woz",
            lb=0,
            ub=0.03,
            weight=1,
        )
        return [rule]

    @staticmethod
    @tag("basic", "household", "test")
    def household_benefit_single_topup() -> list["TaxRule"]:
        rule = HouseholdBenefit(
            name="simpel_kb_single_topup",
            var_name=["i_number_of_kids", "k_single"],
            ub=2_500,
            weight=10,
        )
        return [rule]

    # ------------------------------------------------------------------
    # Simple benefits/taxes copied verbatim

    # ------------------------------------------------------------------
    # Progressive income-tax bracket helpers
    # ------------------------------------------------------------------

    @staticmethod
    @tag("personal", "basic", "sq", "test")
    def mortgage_interest_deduction() -> list["TaxRule"]:
        rule = BenefitRule(
            name="hra",
            var_name="i_mortgage_interest",
            ub=1,
            weight=1,
        )
        return [rule]

    @staticmethod
    @tag("young_handicapped", "basic", "test")
    def young_handicapped_benefit() -> list["TaxRule"]:
        rule = BenefitRule(
            name="young_handicapped_benefit",
            var_name="k_young_handicapped",
            ub=10_000,
            weight=1,
        )
        return [rule]

    @staticmethod
    @tag("basic", "household", "test")
    def household_benefit() -> list["TaxRule"]:
        rules: list["TaxRule"] = [
            HouseholdBenefit(
                name="simpel_kb",
                var_name="i_number_of_kids",
                ub=3_000,
                weight=1,
            ),
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
        return rules

    @staticmethod
    @tag("household", "rent", "basic", "test")
    def household_rent_benefit() -> list["TaxRule"]:
        rule = HouseholdBenefit(
            name="rent_benefit",
            var_name="k_renter",
            ub=5_000,
            weight=1,
        )
        return [rule]

    @staticmethod
    @tag("household_type_benefit", "household", "basic", "test")
    def household_type_benefit() -> list["TaxRule"]:
        rules = [
            HouseholdBenefit(
                name="double_earner_benefit",
                var_name="k_double_earner",
                ub=5_000,
                weight=10,
            ),
            HouseholdBenefit(
                name="single_benefit",
                var_name="k_single",
                ub=5_000,
                weight=10,
            ),
            HouseholdBenefit(
                name="single_earner_benefit",
                var_name="k_single_earner",
                ub=5_000,
                weight=10,
            ),
        ]
        return rules

    @staticmethod
    @tag("basic", "test", "verzilverbaar")
    def add_zeta_k() -> list["TaxRule"]:
        # Conditional benefits per k_group variable
        rules: list["TaxRule"] = []
        for var in [
            "k_lowest_earner",
            "k_double_earner",
            "k_single",
            "k_single_earner",
        ]:
            rules.append(
                BenefitRule(
                    name=f"conditional_benefit_{var}",
                    var_name=[var],
                    ub=10_000,
                )
            )
        return rules

    @staticmethod
    @tag("test", "basic", "sq", "toeslagen")
    def existing_benefits() -> list["TaxRule"]:
        benefits = ["kb", "kgb", "rental_support", "kot", "zvw_benefit"]
        return [
            ExistingBenefit(name=b, var_name=b, lb=0.9, ub=1.1, weight=10)
            for b in benefits
        ]

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def default_inflection_points() -> list[int]:
        """Return canonical break-points used across progressive rules.

        Maintains the historical specification:
        base points [0, 10 000, 10 000 000] plus three ranges –
        20k–35k step 5k, 50k–110k step 20k, 150k–250k step 50k.
        """
        base = [0, 10_000, 10_000_000]
        ranges = (
            range(20_000, 40_000, 5_000),
            range(50_000, 120_000, 20_000),
            range(150_000, 250_001, 50_000),
        )
        pts: list[int] = base.copy()
        for r in ranges:
            pts.extend(r)
        return sorted(pts)

    @staticmethod
    def default_rent_inflection_points() -> list[int]:
        return [i * 12 for i in range(0, 2000, 400)]

    # ------------------------------------------------------------------
    # TODO: the remaining methods still need porting.  They currently
    # return an empty list so that code importing the class does not fail.
    # ------------------------------------------------------------------

    @staticmethod  # noqa: D401 – simple wrappers are fine
    @tag("basic")
    def _placeholder() -> list["TaxRule"]:  # pragma: no cover
        """Temporary stub for not-yet-ported rules."""
        return []

    # ------------------------------------------------------------------
    # Tag selection helpers (equivalent to the old implementation)
    # ------------------------------------------------------------------

    @classmethod
    def get_methods_with_tags(cls, include_tags, exclude_tags):
        methods = []
        for name in dir(cls):
            method = getattr(cls, name)
            if callable(method) and hasattr(method, "tags"):
                method_tags = set(method.tags)  # type: ignore[attr-defined]
                if method_tags.intersection(
                    include_tags
                ) and not method_tags.intersection(exclude_tags):
                    methods.append(name)
        return methods

    @classmethod
    def rules_with_tags(cls, include_tags, exclude_tags):
        rule_objects: list["TaxRule"] = []
        for method_name in cls.get_methods_with_tags(include_tags, exclude_tags):
            rule_objects.extend(getattr(cls, method_name)())
        if not rule_objects:
            raise ValueError(
                f"No rules found with include tags {include_tags} / exclude {exclude_tags}"
            )
        return rule_objects
