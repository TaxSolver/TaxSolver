import pytest
from TaxSolver.objective import ComplexityObjective
from TaxSolver.tax_solver import TaxSolver
from TaxSolver.rule import (
    BenefitRule,
    HouseholdBenefit,
    PreTaxBenefit,
    ExistingBenefit,
    FlatTaxRule,
)
from TaxSolver.brackets import Brackets
from TaxSolver.constraints.rule_constraints import ForceRateConstraint
from TaxSolver.population.person import Person
from TaxSolver.population.household import Household
from TaxSolver.backend import CvxpyBackend


@pytest.fixture
def simple_person():
    person_data = {
        "id": "p_1",
        "hh_id": "hh_1",
        "weight": 100,
        "income_before_tax": 50000,
        "income_after_tax": 50000,
        "sq_a_some_benefit": 1000,
        "sq_m_some_benefit": 0.1,
        "some_variable": 1,
    }
    person = Person(person_data)
    return person


@pytest.fixture
def simple_household(simple_person):
    hh = Household(id="hh_1", members=[simple_person])
    return hh


@pytest.fixture
def tax_solver(simple_household):
    households = {"hh_1": simple_household}
    backend = CvxpyBackend()
    solver = TaxSolver(households, backend=backend)
    solver.add_objective(ComplexityObjective())
    return solver


@pytest.fixture
def multi_person_household():
    person1_data = {
        "id": "p_1",
        "hh_id": "hh_1",
        "weight": 100,
        "income_before_tax": 50000,
        "income_after_tax": 50000,
        "some_variable": 1,
    }
    person2_data = {
        "id": "p_2",
        "hh_id": "hh_1",
        "weight": 100,
        "income_before_tax": 30000,
        "income_after_tax": 30000,
        "some_variable": 1,
    }
    p1 = Person(person1_data)
    p2 = Person(person2_data)
    hh = Household(id="hh_1", members=[p1, p2])
    return hh


@pytest.fixture
def tax_solver_multi_person(multi_person_household):
    households = {"hh_1": multi_person_household}
    backend = CvxpyBackend()
    solver = TaxSolver(households, backend=backend)
    solver.add_objective(ComplexityObjective())
    return solver


def test_tax_rule(tax_solver):
    """Test that a TaxRule with a positive rate leads to a negative tax."""
    tax_rule = FlatTaxRule(
        name="test_tax",
        var_name="income_before_tax",
    )
    tax_solver.add_rules([tax_rule])
    tax_solver.add_constraints(
        [ForceRateConstraint(rule_names=["test_tax"], rate=0.25)]
    )
    tax_solver.solve()

    person = tax_solver.households["hh_1"].members[0]

    expected_tax = -50000 * 0.25

    expected_net_income = 50000 + expected_tax
    assert tax_solver.backend.get_value(person.new_net_income) == pytest.approx(
        expected_net_income
    )


def test_benefit_rule(tax_solver):
    """Test that a BenefitRule leads to a positive number."""
    benefit_rule = BenefitRule(
        name="test_benefit",
        var_name="income_before_tax",
    )
    tax_solver.add_rules([benefit_rule])
    tax_solver.add_constraints(
        [ForceRateConstraint(rule_names=["test_benefit"], rate=0.1)]
    )
    tax_solver.solve()

    person = tax_solver.households["hh_1"].members[0]

    expected_benefit = 50000 * 0.1

    expected_net_income = 50000 + expected_benefit
    assert tax_solver.backend.get_value(person.new_net_income) == pytest.approx(
        expected_net_income
    )


def test_household_benefit(tax_solver_multi_person):
    """Test that HouseholdBenefit is applied once per household."""
    hh_benefit = HouseholdBenefit(
        name="test_hh_benefit",
        var_name="some_variable",
    )
    tax_solver_multi_person.add_rules([hh_benefit])
    tax_solver_multi_person.add_constraints(
        [ForceRateConstraint(rule_names=["test_hh_benefit"], rate=500)]
    )
    tax_solver_multi_person.solve()

    hh = tax_solver_multi_person.households["hh_1"]
    expected_net_income = (50000 + 30000) + 500
    assert tax_solver_multi_person.backend.get_value(
        hh.new_net_household_income
    ) == pytest.approx(expected_net_income)


def test_flat_tax_rule_active_and_tax_calculation(tax_solver):
    """Test FlatTaxRule constraints and tax calculation."""
    person = tax_solver.households["hh_1"].first_member
    person["income_before_tax_bracket_1"] = 30_000
    person["income_before_tax_bracket_1_is_marginal"] = 0
    person["income_before_tax_bracket_2"] = 20_000
    person["income_before_tax_bracket_2_is_marginal"] = 1

    bracket1 = FlatTaxRule(
        name="bracket1",
        var_name="income_before_tax_bracket_1",
        marginal_pressure="income_before_tax_bracket_1_is_marginal",
        rule_considered_inactive_at=0,
    )
    bracket2 = FlatTaxRule(
        name="bracket2",
        var_name="income_before_tax_bracket_2",
        marginal_pressure="income_before_tax_bracket_2_is_marginal",
        rule_considered_inactive_at=bracket1,
    )

    tax_solver.add_rules([bracket1, bracket2])
    tax_solver.add_constraints([ForceRateConstraint(rule_names=["bracket1"], rate=0.2)])
    tax_solver.add_constraints([ForceRateConstraint(rule_names=["bracket2"], rate=0.3)])
    tax_solver.solve()

    assert tax_solver.backend.get_value(bracket1.b) == 1
    assert tax_solver.backend.get_value(bracket2.b) == 1

    total_tax = -(30_000 * 0.2 + 20_000 * 0.3)
    expected_net_income = 50_000 + total_tax
    assert tax_solver.backend.get_value(person.new_net_income) == expected_net_income


def test_bracket_rule_active_and_tax_calculation(tax_solver):
    """Test Brackets constraints and tax calculation."""
    person = tax_solver.households["hh_1"].first_member
    person["income_before_tax_0_30000"] = 30_000
    person["income_before_tax_0_30000_is_marginal"] = 0
    person["income_before_tax_30000_50000"] = 20_000
    person["income_before_tax_30000_50000_is_marginal"] = 1

    brackets = Brackets(
        name="brackets",
        var_name="income_before_tax",
    )

    tax_solver.add_rules([brackets])
    tax_solver.add_constraints(
        [
            ForceRateConstraint(
                rule_names=["brackets__income_before_tax_0_30000"], rate=0.2
            )
        ]
    )
    tax_solver.add_constraints(
        [
            ForceRateConstraint(
                rule_names=["brackets__income_before_tax_30000_50000"], rate=0.3
            )
        ]
    )
    tax_solver.solve()


def test_flat_tax_rule_inactive_when_rate_is_same(tax_solver):
    """Test FlatTaxRule is inactive when its rate is the same as previous bracket."""
    person = tax_solver.households["hh_1"].members[0]
    person["income_before_tax_bracket_1"] = 30_000
    person["income_before_tax_bracket_1_is_marginal"] = 0
    person["income_before_tax_bracket_2"] = 20_000
    person["income_before_tax_bracket_2_is_marginal"] = 1

    bracket1 = FlatTaxRule(
        name="bracket1",
        var_name="income_before_tax_bracket_1",
        rule_considered_inactive_at=0,
    )
    bracket2 = FlatTaxRule(
        name="bracket2",
        var_name="income_before_tax_bracket_2",
        rule_considered_inactive_at=bracket1,
    )

    tax_solver.add_rules([bracket1, bracket2])
    tax_solver.add_constraints([ForceRateConstraint(rule_names=["bracket1"], rate=0.2)])
    tax_solver.add_constraints([ForceRateConstraint(rule_names=["bracket2"], rate=0.2)])
    tax_solver.solve()

    assert tax_solver.backend.get_value(bracket1.rate) == tax_solver.backend.get_value(
        bracket2.rate
    )

    assert tax_solver.backend.get_value(bracket1.b) == 1
    assert tax_solver.backend.get_value(bracket2.b) == 0


def test_bracket_rule_inactive_when_rate_is_same(tax_solver):
    person = tax_solver.households["hh_1"].first_member
    person["income_before_tax_0_30000"] = 30_000
    person["income_before_tax_0_30000_is_marginal"] = 0
    person["income_before_tax_30000_50000"] = 20_000
    person["income_before_tax_30000_50000_is_marginal"] = 1

    brackets = Brackets(
        name="brackets",
        var_name="income_before_tax",
    )

    tax_solver.add_rules([brackets])
    tax_solver.add_constraints(
        [
            ForceRateConstraint(
                rule_names=["brackets__income_before_tax_0_30000"], rate=0.2
            )
        ]
    )
    tax_solver.add_constraints(
        [
            ForceRateConstraint(
                rule_names=["brackets__income_before_tax_30000_50000"], rate=0.2
            )
        ]
    )
    tax_solver.solve()

    bracket1 = brackets.flat_rules[0]
    bracket2 = brackets.flat_rules[1]

    assert tax_solver.backend.get_value(bracket1.b) == 1
    assert tax_solver.backend.get_value(bracket2.b) == 0


def test_pre_tax_benefit(tax_solver):
    """Test that PreTaxBenefit is discounted by marginal rate."""
    person = tax_solver.households["hh_1"].members[0]

    tax_rule = FlatTaxRule(
        name="income_tax",
        var_name="income_before_tax",
        marginal_pressure=True,
    )

    pre_tax_benefit = PreTaxBenefit(
        name="test_pre_tax_benefit",
        var_name="income_before_tax",
        lb=0,
        ub=1,
    )

    tax_solver.add_rules([tax_rule, pre_tax_benefit])
    tax_solver.add_constraints(
        [ForceRateConstraint(rule_names=["income_tax"], rate=0.4)]
    )
    tax_solver.add_constraints(
        [ForceRateConstraint(rule_names=["test_pre_tax_benefit"], rate=0.1)]
    )
    tax_solver.solve()

    tax_from_tax_rule = -(50000 * 0.4)
    benefit_from_pre_tax = 50000 * 0.1 * (1 - 0.4)
    total_tax = tax_from_tax_rule + benefit_from_pre_tax

    expected_net_income = 50000 + total_tax
    assert tax_solver.backend.get_value(person.new_net_income) == pytest.approx(
        expected_net_income
    )


def test_existing_benefit(tax_solver):
    """Test ExistingBenefit."""
    person: Person = tax_solver.households["hh_1"].members[0]

    existing_benefit = ExistingBenefit(
        name="test_existing_benefit",
        var_name="some_benefit",
        lb=0,
        ub=2,
    )

    tax_solver.add_rules([existing_benefit])
    tax_solver.add_constraints(
        [ForceRateConstraint(rule_names=["test_existing_benefit"], rate=0.5)]
    )
    tax_solver.solve()

    benefit_amount = 1000 * 0.5
    expected_net_income = 50000 + benefit_amount
    assert tax_solver.backend.get_value(person.new_net_income) == pytest.approx(
        expected_net_income
    )
    assert tax_solver.backend.get_value(person.new_marginal_rate) == pytest.approx(0.05)
