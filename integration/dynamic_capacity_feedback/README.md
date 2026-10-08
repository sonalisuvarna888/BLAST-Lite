# Monthly Dynamic Capacity Feedback

## Purpose

This branch completes the feedback loop between annual community
microgrid dispatch and BLAST-Lite battery aging.

A documented second-life NMC111 battery state at q approximately 0.80
is used as the stationary-service entry condition.

The model compares fixed-capacity and dynamically updated monthly
capacity for:

- battery-only operation; and
- demand-response-plus-battery operation.

## Branch

`integration/dynamic-capacity-feedback`

## Starting second-life state

- Battery model: `Nmc111_Gr_Kokam75Ah_Battery`
- First-life profile: combined personal EV
- Entry q: approximately 0.80
- Entry normalized resistance r: approximately 27.1363
- Entry modeled time: approximately 12.8179 years
- Entry EFC: approximately 1,156.61
- Entry dispatch capacity: 42 kWh

The complete battery object is loaded from the documented
second-life initial-condition branch.

## Capacity mapping

The second-life entry point defines 42 kWh at q = 0.80:

`C_m = 42 * q_m / 0.80`

The dynamic treatment updates capacity at the beginning of each month.

The fixed treatment retains 42 kWh for dispatch while still continuing
the same BLAST-Lite q and resistance states for comparison.

## Experiment matrix

1. Battery only — fixed capacity
2. Battery only — dynamic monthly capacity
3. DR plus battery — fixed capacity
4. DR plus battery — dynamic monthly capacity

## Dispatch assumptions

- 10 synthetic households
- 8,760 annual hourly intervals
- 48-hour daily rolling look-ahead
- 24 implemented hours per solve
- 85%–115% demand-response bounds
- Daily household energy preservation
- 10%–90% SOC window
- Fixed 12-kW charge/discharge power
- 85% round-trip efficiency
- $0.50/kW-window synthetic peak penalty
- No grid export
- Solar curtailment allowed

## Feedback loop

For each month:

1. read beginning-of-month q;
2. map q to available capacity;
3. update SOC energy bounds;
4. solve each day in the month;
5. convert monthly SOC from kWh to fractional SOC;
6. continue the same BLAST-Lite battery object;
7. record updated q, resistance, time, and EFC; and
8. pass updated capacity into the next month.

Only the final month is forced to return to 50% SOC. Earlier months
continue naturally using a terminal penalty.

## Validation

The implementation verifies:

- all four experiment paths;
- 12 monthly feedback updates;
- 8,760 dispatch hours per experiment;
- q, resistance, time, and EFC continuity;
- monthly capacity mapping;
- SOC bounds;
- daily energy balance;
- no material simultaneous charging and discharging;
- final annual SOC target; and
- successful serialization of final battery states.

## Annual results

The fixed-versus-dynamic comparison is stored in:

`results/annual_fixed_vs_dynamic_comparison.csv`

The full experiment output is stored in:

`results/dynamic_feedback_12month_overall.csv`

## Main finding

Dynamic capacity feedback allows degradation to change subsequent
dispatch constraints rather than evaluating aging only after dispatch.

The magnitude and operational effect of that feedback are reported
separately for battery-only and DR-plus-battery strategies.

## Interpretation boundaries

- All household, solar, and price profiles are synthetic.
- Monthly feedback approximates continuous degradation.
- The power limit remains fixed at 12 kW.
- BLAST-Lite is a cell-level model rather than a complete pack model.
- q is not a complete SOH, safety, or warranty metric.
- The Miami temperature profile is not geographically matched.
- Results are model-based and not empirical validation.

## Reproducibility

Run a one-month pilot:

`MPLBACKEND=Agg /content/blast_py311/bin/python integration/dynamic_capacity_feedback/run_dynamic_feedback.py --months 1`

Run a two-month continuity pilot:

`MPLBACKEND=Agg /content/blast_py311/bin/python integration/dynamic_capacity_feedback/run_dynamic_feedback.py --months 2`

Run the full annual study:

`MPLBACKEND=Agg /content/blast_py311/bin/python integration/dynamic_capacity_feedback/run_dynamic_feedback.py --months 12`

## Next work

- add capacity-scaled power limits as a sensitivity;
- repeat across multiple household random seeds;
- test multiple temperatures and battery chemistries;
- compare fresh and second-life starting states; and
- evaluate an SOH surrogate for faster iterative optimization.
