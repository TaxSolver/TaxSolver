# Paper reproduction package

Everything needed to regenerate the results reported in *"Tax reform as a
constrained optimization problem: a piecewise-linear framework and software
implementation"*, **from code and raw data only**: there are
no pre-saved solver outputs. Every notebook solves its own optimization
problems and builds its figures from those solves. Run the notebooks from
**this folder** so the relative paths (`./data/`, `./systems/`, `./output/`)
resolve; `./systems/` and `./output/` start empty and are populated by the
runs.

`output/figs/` and `output/tables/` hold every script-generated manuscript
figure and table, under the same filenames used in the manuscript. To update
the paper after a rerun, copy those two folders wholesale:

```
cp output/figs/*.png   ../../figs/
cp output/tables/*.tex ../../tables/
```

## Environment

- Python: the repository's `uv`-managed venv (`../.venv`), with the
  `TaxSolver` package importable (installed from `../src`).
- Solver: Gurobi (academic license required). LP-only parts also run on
  CVXPY/HiGHS.
- All figures use the shared palette in `case_helpers.py` (`OKABE_ITO` for
  categorical series, viridis for sequential/density encodings).

## Inputs (raw data only)

- `data/simple_simul_1000.xlsx`: 1,000 simulated taxpayers for the
  illustrative cases. Regenerable from scratch with
  `python data_simulator.py` (seed 1704; rows 0 and 1 are the manuscript's
  Jude and Laila).
- `data/NL_persons_headers_preprocessed_equal_weights.xlsx`: the simulated
  Dutch population (8,400 households / 13,500 taxpayers, weighted to
  8.4M / 13.5M). Each record carries `weight = 0.001` (the weights sum to
  13.5 and represent 13.5 million taxpayers).

## Figure map

| Manuscript figure | Notebook | Output |
|---|---|---|
| Figure 5 (`fig: case_1_combined`) | `fig05_case1_single_rule.ipynb` | `output/figs/case_1a_combined.png` |
| Figure 6 (`fig: case_2`) | `fig06_case2_multi_rule.ipynb` | `output/figs/case_1b_combined.png` |
| Figure 7 (`fig: case_3_reform`) | `fig07_case3_multi_group.ipynb` | `output/figs/case_2_reform.png` |
| Figure 8 (`fig: case_3_behavioral`) | `fig08_behavioral_effects.ipynb` | `output/figs/case_3_pareto_schedules.png` |
| Figure 9 (`fig: case_4_intro_comp`) | `fig09_10_dutch_case_study.ipynb` | `output/figs/case_nl_combined_figure.png` |
| Figure 10 (`fig: case_4_reform`) | `fig09_10_dutch_case_study.ipynb` (same run) | `output/figs/case_nl_65_75_comparison.png` |
| Figure 11 (`fig: case_nl_incidence`) | `fig09_10_dutch_case_study.ipynb` (last cell) | `output/figs/case_nl_incidence.png` |
| Figure 12 (`fig: frontier`) | `fig12_guarantee_frontier.ipynb` | `output/figs/case_frontier_caps.png` |

Notes:
- The notebook names are prefixed with the manuscript figure number they
  produce, so the mapping above is redundant with the filename itself.
- `fig09_10_dutch_case_study.ipynb` writes its solved systems to `./systems/`
  (per-cap rate and household tables, plus the system-comparison summary) and
  its figure cells read those same files, so the notebook must be run top to
  bottom once; the figure cells can then be re-run standalone.
- The Figure 11 cell computes each household's percentage change in net
  income against the same status-quo baseline the solver's own income
  guarantee uses.
- `fig12_guarantee_frontier.ipynb` likewise saves its sweep tables to
  `./systems/` incrementally (safe to interrupt) and re-plots from them.
- All income guarantees on the low-income group use the manuscript's 5%
  floor (`IncomeConstraint(-0.05)`) consistently.

## Table map

| Manuscript table | Script | Output |
|---|---|---|
| Table `desc_case_4` (NL descriptives) | `make_table_descriptives_nl.py` | `output/tables/table_descriptives_nl_case.tex` |
| Table `performance` | `make_table_rows.py` | `output/tables/table_performance.tex` |
| Table `scaling` | `make_table_rows.py` | `output/tables/table_scaling.tex` |
| Table `behavioral_convergence` | `fig08_behavioral_effects.ipynb` (last cell) | `output/tables/table_behavioral_convergence.tex` |
| Table `reform_schedules` | `make_table_reform_schedules.py` | `output/tables/table_reform_schedules.tex` |

## Computational reporting (appendix tables)

The instrumented run scripts behind `table_performance.tex` and
`table_scaling.tex`:

- `solve_stats.py`: shared instrumentation; reads model dimensions
  (continuous/binary variables, linear/general/quadratic constraints),
  wall-clock runtime, termination status, and terminal MIP gap off the Gurobi
  model after each solve, plus hardware/solver metadata
  (`python solve_stats.py` prints the hardware summary).
- `run_stats_small.py`: recovery/reform solves of the illustrative cases and
  the dynamic-bracketing demo.
- `run_stats_behavioral.py`: direct MIQP vs Algorithm 1 fixed point per
  elasticity -> `systems/computational_stats_behavioral.csv` (~1 min).
- `run_stats_nl.py`: the Dutch reform at every cap gamma, solved both as the
  stand-alone stage-1 MILP and as the two-stage sequential procedure ->
  `systems/computational_stats_nl.csv`.
- `run_stats_nl_gamma65_extended.py`: reruns just that one gamma=0.65
  cardinality stage with the time limit relaxed to 4 hours -> confirms proven
  optimality (gap 0) after 2,252s; appends a `_4h`-suffixed row to the same
  CSV. The reform reported in the paper at gamma=0.65 is therefore a
  certified global optimum, not merely a feasible, gap-bounded solution.
- `run_iis_demo.py`: IIS readout for the infeasible Dutch point (55% cap,
  96% floor) -> `systems/iis_cap55_floor096.ilp` (~2 min).
- `run_stats_scaling.py <factor> [mode]`: the scaling experiment
  (`factor` in `{1, 10, 100}`, replicating the sample with weights divided by
  the factor; `mode` in `{sequential, budget_only, both}`, default
  `sequential`) -> `systems/computational_stats_scaling.csv` (30 min limit
  for 1x/10x, 4 h for 100x). `table_scaling.tex` uses both modes per factor
  (the reported "Two-stage" reproduces the two-stage `sequential` runs; the
  x100 "Stage 1" time is read from inside that same sequential run's log,
  since the stand-alone `budget_only` attempt at that size timed out without
  finding an incumbent).
- `make_table_rows.py`: writes `output/tables/table_performance.tex` and
  `output/tables/table_scaling.tex`.
- `make_table_descriptives_nl.py`: regenerates
  `output/tables/table_descriptives_nl_case.tex` (Table S3) from
  `data/NL_persons_headers_preprocessed_equal_weights.xlsx`.
- `make_table_reform_schedules.py`: regenerates
  `output/tables/table_reform_schedules.tex` from the solved rule tables
  `systems/case_nl_reform_{65,75}_5.xlsx`, merging consecutive equal-rate
  bracket rows and translating internal rule identifiers to manuscript labels
  via a one-time lookup table in the script.

Figure 12's per-instance statistics (grid points from the income-floor and
budget-band sweeps, at the main 65% cap and the two extra caps) are recorded
by `fig12_guarantee_frontier.ipynb` itself in `systems/case_frontier_*.xlsx`
(`runtime_s`, `mip_gap`, `status` columns), plus one file per grid point in
`systems/frontier_runs/` as a fuller audit trail of each individual solve.

## Support modules

- `case_helpers.py`: shared imports, plotting helpers (including
  `rates_to_intervals`, which converts solver output into plotting intervals),
  and the paper palette.
- `nld_rule_book.py`: the Dutch rule book, complexity weights, and
  `setup_nl_optimization`.
- `parameters.py` / `data_simulator.py`: the data-generating tax systems and
  simulator for the illustrative cases; `fig06_case2_multi_rule.ipynb` also
  constructs its "current system" line directly from these parameters.