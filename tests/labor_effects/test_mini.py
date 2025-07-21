from tests.helpers.scenario_helper import ScenarioHelper
from TaxSolver.constraints.labor_effects import LaborEffects
import pytest


@pytest.mark.gurobi
def test_labor_effects_mini_single(backend):
    scenario = ScenarioHelper(
        data_path="tests/labor_effects/ipo_fixtures/mini_single.xlsx",
        include_tags=["test"],
        exclude_tags=["enforce_progressive_tax", "pretax"],
        backend=backend,
    )

    scenario.opt_sys.add_constraints([LaborEffects()])

    scenario.opt_sys.solve()

    assert scenario.opt_sys.solved
