# TaxSolver: A Design Tool for Optimal Income Tax Reform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![arXiv](https://img.shields.io/badge/arXiv-2508.03708-b31b1b.svg)](https://arxiv.org/abs/2508.03708)
[![DOI](https://zenodo.org/badge/1023689283.svg)](https://doi.org/10.5281/zenodo.21320272)

**TaxSolver** is a constrained optimization-based tool that enables policymakers to design optimal income tax reforms by focusing on the desired outcomes of a reform in conjunction with fiscal guarantees that a reform has to abide by rather than ad-hoc rule adjustments. Read our accompanying paper [Implementing Optimal Taxation: A Constrained Optimization Framework for Tax Reform](https://arxiv.org/abs/2508.03708).

## Abstract

Governments must regularly redesign income tax codes that have grown into complex tangles of interacting brackets, benefits, and deductions, while any politically viable reform must satisfy hard guarantees on household incomes, marginal rates, and budgetary cost. Existing microsimulation tools can evaluate a reform proposal but cannot generate one by themselves. We develop a framework that casts tax reform as a constrained optimization problem. We show that any statutory tax code satisfying four mild assumptions reduces to a finite-dimensional piecewise-linear function for each taxpayer group, so reform becomes a linear or mixed-integer linear program whose decision variables are legislatable parameters: rates, bracket cutoffs, and lump-sum transfers. Recovering the current system is an inverse-optimization feasibility problem, and we give conditions under which the recovered parameters are unique. Relaxing the recovery constraints yields reforms that are provably optimal within the modeled space, or a certificate that no reform satisfying the stated policy design constraints exists. Behavioral effects can also be incorporated, producing a nonconvex mixed-integer formulation. We demonstrate the framework through a near-complete reconstruction of the Dutch income tax code with fifteen rules and 13,500 simulated, weighted taxpayers, generating reforms that smooth marginal-rate spikes, cap household income losses, and roughly halve the number of active rules through a lexicographic procedure. Sweeping the guarantees shows that tighter guarantees are priced in tax-code complexity, not revenue. Developed in close collaboration with the Dutch Ministry of Finance, the methodology is currently in active use there. An open-source software implementation is available as `TaxSolver`.

## Key Features & Evidence for Practice

1. **A modeling result**: Under four mild assumptions (additivity, scalar inputs, piecewise linearity, group heterogeneity), any statutory income tax code reduces to a single piecewise-linear function per tax group whose breakpoints are the union of all rule cutoffs. The function's parameters (rates, cutoffs, lump sums) are exactly the quantities legislation specifies.

2. **Inverse recovery with identifiability conditions**: Recovering the status-quo parameters from observed liabilities is a feasibility problem of inverse-optimization type, with a rank condition under which recovery is unique.

3. **A reform-optimization framework**: A library of constraints (two-sided income guarantees, marginal-rate caps, budget bands, protected rules), objectives (revenue loss, weighted rule-count cardinality), and a dynamic-bracketing formulation that makes the support itself a decision variable, each classified as a linear program (LP), mixed-integer linear program (MILP), or nonconvex mixed-integer quadratically constrained program (MIQCP) on first appearance, with infeasibility certificates.

4. **A representative case study**: A reconstruction of the Dutch income tax code (15 rules, 13,500 weighted taxpayers representing 13.5 million): a family of certified reforms that cap marginal pressure at 55-80%, guarantee no household falls below 95% of current net income within a ±1.5% budget band, and roughly halve the number of active rules via a lexicographic two-stage procedure, with every formulation remaining tractable at national scale.

5. **An open-source software implementation**: `TaxSolver`, a solver-agnostic Python package with a full reproducibility package, developed in close collaboration with the Dutch Ministry of Finance and currently in active use there.

## Installation

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Install from source

```bash
pip install git+https://github.com/Tax-Lab/TaxSolver.git
```

### Install for development

```bash
git clone https://github.com/Tax-Lab/TaxSolver.git
cd TaxSolver
pip install -e .
```

## Quick Start

```python
import os
import TaxSolver as tx
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.objective import BudgetObjective

# Load taxpayer data from a system with 6 brackets into TaxSolver format.
# In the bundled example file the after-tax income column is named "outcome_1".
dl = DataLoader(path=os.path.join("data", "example", "simple_simul_1000.xlsx"), 
                income_before_tax="income_before_tax", 
                income_after_tax="outcome_1")

# Initialize the solver
tax_solver = tx.TaxSolver(dl.households)

# Split input along inflection points to construct brackets
BracketInput.add_split_variables_to_solver(
    tx=tax_solver,
    target_var="income_before_tax",
    inflection_points=[0, 25_000, 50_000, 75_000, 100_000, 125_000, 150_000],
    group_vars=["k_everybody"]
)

# Define solver variables for the optimization
income_tax = tx.BracketRule(
    name="income_before_tax_k_everybody",
    var_name="income_before_tax",
    k_group_var="k_everybody",
    ub=1,
    lb=0,
)

# Add solver variables to the solver
tax_solver.add_rules([income_tax])

# Define constraints for the optimization
income_constraint = IncomeConstraint(0.0001, dl.households.values()) # No one can experience income shocks of more than 0.01%
budget_constraint = BudgetConstraint(
    "All_households", dl.households.values(), 0, 0 # The total tax revenue cannot decrease or increase
)

# Add constraints to the solver
tax_solver.add_constraints([income_constraint, budget_constraint])

# Add an objective to the optimization (required before solving)
tax_solver.add_objective(BudgetObjective(budget_constraint))

# Solve the optimization problem
tax_solver.solve()

# View results
print(tax_solver.rules_and_rates_table())
```

## Documentation

- **Tutorial**: See `notebooks/example_notebook.ipynb` and
  `notebooks/readme_notebook.ipynb` for walkthroughs.
- **Methods**: See `paper/methods.md` for the methodology underlying `TaxSolver`.

## Project Structure

```
TaxSolver/
├── src/TaxSolver/           # Main package
│   ├── tax_solver.py        # Core solver orchestration
│   ├── rule.py              # Tax/benefit rule definitions
│   ├── objective.py         # Optimization objectives
│   ├── backend/             # Solver backends (CVXPY/HiGHS, Gurobi)
│   ├── constraints/         # Constraint definitions
│   ├── data_wrangling/      # Data loading and bracket inputs
│   └── population/          # Household and person models
├── paper/                   # Academic paper and examples
├── tests/                   # Test suite
├── notebooks/               # Notebooks
└── data/                    # Example datasets
```

## Core Concepts

- **Tax Rules**: Define how income is taxed (flat, progressive, benefits)
- **Constraints**: Hard limits the reform must satisfy (budget neutrality, income bounds)
- **Objectives**: Goals to optimize (redistribution, efficiency, simplicity)
- **Households**: Units of analysis with income, demographics, and tax liabilities

## Citation

If you use TaxSolver in your research, please cite:

```bibtex
@article{taxsolver2025,
  title={Implementing Optimal Taxation: A Constrained Optimization Framework for Tax Reform},
  author={Verhagen, M.D. and Schellekens, M. and Garstka, M.},
  year={2025},
  eprint={2508.03708},
  archivePrefix={arXiv},
  note={Software available at: https://github.com/Tax-Lab/TaxSolver.git}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and suggest improvements.

## Support

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/Tax-Lab/TaxSolver/issues)
- **Documentation**: Full documentation available at [project website] TODO
- **Academic Paper**: [Link to published paper] TODO

## Authors

Mark Verhagen
Menno Schellekens
Michael Garstka
