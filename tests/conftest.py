import pytest
import pandas as pd
import os
import gurobipy as grb
from TaxSolver.backend import GurobiBackend, CvxpyBackend
from TaxSolver.population.person import Person
from TaxSolver.population.household import Household
from TaxSolver.data_wrangling.data_loader import DataLoader
from helpers.solved_system.solved_system import SolvedSystem


def pytest_addoption(parser):
    """Add the --gurobi command-line option."""
    parser.addoption(
        "--gurobi",
        action="store_true",
        default=False,
        help="run tests requiring gurobi backend",
    )


def pytest_configure(config):
    """Register the 'gurobi' marker."""
    config.addinivalue_line("markers", "gurobi: mark test as requiring gurobi backend")


def pytest_collection_modifyitems(config, items):
    """Skip gurobi tests by default unless --gurobi is given."""
    run_gurobi = config.getoption("--gurobi")

    skip_gurobi_marker = pytest.mark.skip(reason="need --gurobi option to run")

    for item in items:
        is_gurobi_test = "gurobi" in item.keywords
        if is_gurobi_test and not run_gurobi:
            item.add_marker(skip_gurobi_marker)


@pytest.fixture
def people_and_households():
    people_data = []
    for i in range(10):
        people_data.append(
            Person(
                {
                    "id": str(i),
                    "hh_id": "hh_" + str(i),
                    "kids": i % 3,
                    "children_ages": [5 for _ in range(i % 3)],
                    "k_test1": 1.0 if i % 4 > 2 else 0.0,
                    "test1": 1.0 if i % 4 > 2 else 0.0,
                    "k_test2": 1.0 if i % 7 > 3 else 0.0,
                    "test2": 1.0 if i % 7 > 3 else 0.0,
                    "bool_algemene_heffingskorting": 1.0,
                    "income_before_tax": 100.0 * (i + 1),
                    "income_after_tax": 90.0 * (i + 1) + i % 3 * 20.0,
                    "weight": 1,
                    # Tests fail without giving people and households all the necessary attributes in Solved System
                    "age": 30,
                    "marginal_rate_current": 0.5,
                    "type_of_income": "loon",
                    "fiscal_partner": False,
                    "partner_income": 0,
                    "i_woz": 0,
                    "i_number_of_kids": 3,
                    "poverty_line": 0,
                    "k_everybody": 1.0,
                }
            )
        )
    households = {}
    people = {}
    for person in people_data:
        people[person["id"]] = person
        if person["hh_id"] not in households:
            households[person["hh_id"]] = Household(person["hh_id"], [])
        households[person["hh_id"]].add_member(person)
        person.household = households[person["hh_id"]]

    return people, households


@pytest.fixture(scope="function")
def tax_system(people_and_households) -> SolvedSystem:
    _, households = people_and_households
    rules_and_rates = pd.read_csv("tests/solved_system/fixtures/fixture_r_and_r.csv")

    # Call the class method
    tax_system = SolvedSystem.from_rules_and_rates_table(rules_and_rates, households)
    return tax_system


@pytest.fixture(scope="session")
def gurobi_env():
    if os.getenv("BOOLEANGHA"):
        return grb.Env(
            params={
                "WLSACCESSID": os.getenv("WLSACCESSID"),
                "WLSSECRET": os.getenv("WLSSECRET"),
                "LICENSEID": int(os.getenv("LICENSEID")),
            }
        )

    # For local runs, create a default environment if possible
    try:
        return grb.Env()
    except grb.GurobiError:
        return None  # Could not create env (e.g., no license)


@pytest.fixture(scope="function")
def backend(request, gurobi_env):
    """Fixture to provide the solver backend based on the --gurobi command-line option."""
    use_gurobi = request.config.getoption("--gurobi")

    if use_gurobi and gurobi_env is not None:
        print("Using Gurobi backend")
        return GurobiBackend(env=gurobi_env)
    else:
        print("Using Cvxpy backend")
        return CvxpyBackend()

@pytest.fixture(scope="session")
def data_loader():
    return DataLoader(
            "tests/e2e/ipo_fixtures/df_employment_only_with_extreme_earners.xlsx",
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
        )
