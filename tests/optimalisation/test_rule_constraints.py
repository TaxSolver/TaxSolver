import pytest
from TaxSolver.tax_solver import TaxSolver
from TaxSolver.rule import FlatTaxRule
from TaxSolver.constraints.rule_constraints import (
    ForceRulesOnConstraint,
    ForceRateConstraint,
    ForceRuleFamilyOnConstraint,
    MutuallyExclusiveRulesConstraint,
)


@pytest.fixture
def tax_solver_with_rules():
    solver = TaxSolver(households={})
    rules = [
        FlatTaxRule(name="rule1", var_name=["var1"], metadata={"family": "fam1"}),
        FlatTaxRule(name="rule2", var_name=["var2"], metadata={"family": "fam1"}),
        FlatTaxRule(name="rule3", var_name=["var3"], metadata={"family": "fam2"}),
    ]
    solver.add_rules(rules)
    return solver


def test_force_rules_on_constraint(tax_solver_with_rules):
    solver = tax_solver_with_rules
    constraint = ForceRulesOnConstraint(rule_names=["rule1", "rule3"])
    constraint.apply(solver)
    solver.backend.update()

    assert solver.backend.get_constraint_by_name("force_on_rule1") is not None
    assert solver.backend.get_constraint_by_name("force_on_rule3") is not None
    assert solver.backend.get_constraint_by_name("force_on_rule2") is None


def test_force_rate_constraint(tax_solver_with_rules):
    solver = tax_solver_with_rules
    constraint = ForceRateConstraint(rule_names=["rule1"], rate=0.5)
    constraint.apply(solver)
    solver.backend.update()

    assert solver.backend.get_constraint_by_name("force_rate_rule1") is not None


def test_force_one_of_rules_on_constraint(tax_solver_with_rules):
    solver = tax_solver_with_rules
    constraint = ForceRuleFamilyOnConstraint(rule_names=["rule1", "rule3"])
    constraint.apply(solver)
    solver.backend.update()

    assert (
        solver.backend.get_constraint_by_name("force_on_one_of_rule1:rule3") is not None
    )


def test_mutually_exclusive_rules_constraint(tax_solver_with_rules):
    solver = tax_solver_with_rules
    constraint = MutuallyExclusiveRulesConstraint(rule_names=["rule1", "rule2"])
    constraint.apply(solver)
    solver.backend.update()

    assert (
        solver.backend.get_constraint_by_name("mutually_exclusive_rule1:rule2")
        is not None
    )
