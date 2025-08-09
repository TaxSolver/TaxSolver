# TaxSolver: A Design Tool for Optimal Income Tax Reform

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![arXiv](https://img.shields.io/badge/arXiv-DOI_10_48550-b31b1b.svg)](https://arxiv.org/abs/2508.03708)

**TaxSolver** is a constrained optimization-based tool that enables policymakers to design optimal income tax reforms by focusing on the desired outcomes of a reform in conjunction with fiscal guarantees that a reform has to abide by rather than ad-hoc rule adjustments.

## Abstract

Across the developed world, there are growing calls to streamline and improve ever more complex income tax codes. Executing reform has proven difficult. Even when the desired outcomes of a reform are clear, the tools to design fitting reforms are lacking. To remedy this, we developed **TaxSolver**: a design tool for optimal income tax reform. TaxSolver allows policymakers to focus solely on what they aim to achieve with a tax reform — e.g. wealth redistribution, incentivizing work, reducing complexity etc. — and the guarantees within which reform can take place — e.g. limiting fluctuations in taxpayer incomes or overall tax revenues. Given these goals and guarantees, TaxSolver finds the optimal set of tax rules that satisfies all the criteria, often in a matter of minutes. We illustrate TaxSolver by reforming various examples, including one based on a real-world system.

## Key Features & Evidence for Practice

1. **Mathematical Foundation**: Most tax codes can be defined as a simple system of equations that make it possible to solve tax reform as (linear) optimization problem.

2. **Policy-Aligned Design**: Linear optimization allows policymakers to formulate both hard guarantees that the reform has to adhere to, as well as objectives that are maximized within these set constraints. This makes optimization a practical tool that is aligned with the reality of policy work.

3. **Systematic Approach**: Our approach allows for a tax reform process that does not consist of ad-hoc tweaking of existing rules but reasons over the entire system and returns an optimal solution.

4. **Real-World Application**: We illustrate our approach by reforming various example systems, as well as a system representing the complexity and scale of a real-world income tax code.

## Installation

### Prerequisites
- Python 3.8 or higher
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

### Example
Here is an example of a simple tax reform:

```python
import os
import TaxSolver as tx
from TaxSolver.constraints.income_constraint import IncomeConstraint
from TaxSolver.constraints.budget_constraint import BudgetConstraint
from TaxSolver.data_wrangling.data_loader import DataLoader
from TaxSolver.data_wrangling.bracket_input import BracketInput
from TaxSolver.objective import BudgetObjective

# Load taxpayer data from a system with 6 brackets into TaxSolver format
dl = DataLoader(path=os.path.join("data", "example", "simple_simul_1000.xlsx"), 
                income_before_tax="income_before_tax", 
                income_after_tax="income_after_tax")

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

# Solve the optimization problem
tax_solver.solve()

# Add an objective to the optimization
tax_solver.add_objective(BudgetObjective(budget_constraint))

# View results
print(tax_solver.rules_and_rates_table())
```
### Numerical solver
We are using Gurobi as the numerical solver to solve the underlying optimization problem. You can request a free license for academic research [here](https://www.gurobi.com/features/academic-named-user-license/). We also support other LP/MILP solvers via our [cvxpy backend](https://www.cvxpy.org/tutorial/solvers/index.html#choosing-a-solver). For smaller toy systems, we found that the open source solver [SCIP](https://www.scipopt.org/) showed adequate performance.

## Project Structure

```
TaxSolver/
├── src/TaxSolver/           # Main package
│   ├── tax_solver.py        # Main class
│   ├── backend/             # interaction with numerical solver (gurobi or others via cvxpy)
│   ├── constraints/         # Constraint definitions
│   ├── data_wrangling/      # Loading and transforming the input dataset
│   ├── objective.py         # Reform objectives
│   ├── rule.py              # Tax rule definitions
├── tests/                   # Test suite
├── notebooks/               # Example Notebooks
└── data/                    # Example datasets
```

## Core Concepts

- **Tax Rules**: Define how income is taxed (flat, progressive, benefits)
- **Constraints**: Hard limits the reform must satisfy (budget neutrality, income bounds)
- **Objectives**: Goals to optimize (redistribution, efficiency, simplicity)
- **Households**: Units of analysis with income, demographics, and tax liabilities

## Citation

**Academic Paper**: A preprint version is available [here](https://arxiv.org/abs/2508.03708).

If you use TaxSolver in your research, please cite:

```bibtex
@article{taxsolver_2025,
  title={TaxSolver: A Design Tool for Optimal Income Tax Reform},
  author={Mark Donald Verhagen and Menno Schellekens and Michael Garstka},
  journal={arXiv pre-print: 2508.03708},
  year={2025},
  note={Software available at: https://github.com/Tax-Lab/TaxSolver.git},
  url={https://arxiv.org/abs/2508.03708}
}
```

## License

This project is licensed under the MIT License.

## Contributing and Support

We welcome contributions! Please use [GitHub Issues](https://github.com/Tax-Lab/TaxSolver/issues) to submit pull requests, report issues, and suggest improvements.



## Authors

- [Mark Verhagen](https://markverhagen.me/)
- Menno Schellekens
- [Michael Garstka](https://migarstka.github.io/)
