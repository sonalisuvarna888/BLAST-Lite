# SOC Operating-Window Sensitivity

## Purpose

This experiment evaluates how BLAST-Lite modeled degradation changes
when an annual residential photovoltaic–battery energy storage system
(PV-BESS) SOC trajectory is transformed to different operating windows.

Temperature is fixed at 25 degrees Celsius and the annual timing pattern
is preserved.

## Branch

`implementation/soc-depth-sensitivity`

## Battery model

`Nmc111_Gr_Kokam75Ah_Battery`

## Source profile

The timing template is the corrected annual residential PV-BESS profile
from:

`implementation/realistic_seasonal_scenarios/scenario_inputs/annual_soc_residential_pvbess_CA_corrected.csv`

The source profile is repository-provided and simulated. Its final day
was previously corrected to remove an artificial annual repeat jump.

## Transformation

Each new SOC profile is produced using min-max scaling:

`SOC_new = target_min + normalized_source_shape * (target_max - target_min)`

This preserves:

- timestamps;
- relative charging and discharging shape;
- turning-point directions;
- annual profile length; and
- annual boundary continuity.

## Scenarios

### Shallow

- SOC window: 50% to 70%
- Annual input EFC: approximately 22.40

### Moderate

- SOC window: 30% to 80%
- Annual input EFC: approximately 55.99

### Deep

- SOC window: 10% to 90%
- Annual input EFC: approximately 89.59

All scenarios use constant 25 degrees Celsius.

## Experimental interpretation

This is a controlled SOC operating-window experiment because temperature
and timing are fixed while the SOC range is transformed.

It is not a pure causal isolation of depth of discharge. As the operating
window widens, mean SOC, equivalent full cycles, depth of discharge, and
energy throughput also change.

## Five-year results

| Scenario | SOC window | Final q | Modeled capacity loss | Final EFC |
|---|---:|---:|---:|---:|
| Shallow | 50%–70% | 0.967781 | 3.22% | 111.91 |
| Moderate | 30%–80% | 0.946073 | 5.39% | 279.77 |
| Deep | 10%–90% | 0.927532 | 7.25% | 447.64 |

All three scenarios:

- completed successfully;
- reached approximately 5.0004 years;
- produced 1,830 output points;
- had finite q and stressor statistics; and
- generated no error records.

## Main finding

At fixed 25 degrees Celsius and identical annual timing, wider SOC
operating windows produced:

- higher equivalent full cycles;
- higher root-mean-square modeled depth of discharge;
- lower final q; and
- greater modeled capacity loss.

The deep-window modeled capacity loss was approximately 2.25 times the
shallow-window modeled loss.

## Research boundaries

- The transformed profiles are synthetic controlled scenarios.
- The source SOC profile is repository-provided and simulated.
- Mean SOC changes across the operating windows.
- Throughput and equivalent full cycles change across the windows.
- The experiment does not independently isolate depth of discharge.
- The cell model is not a complete battery-pack model.
- No documented aged second-life initial condition is applied.
- Results describe BLAST-Lite model behavior, not empirical validation.

## Output evidence

The implementation contains:

- three annual scenario-input CSV files;
- scenario-design metadata;
- input quality-control figures;
- a reusable smoke/full simulation runner;
- smoke-test outputs and logs;
- five-year q and EFC trajectories;
- result summaries and metrics;
- publication-style figures; and
- JSON error records.

## Reproducibility

Smoke test:

`MPLBACKEND=Agg /content/blast_py311/bin/python implementation/soc_depth_sensitivity/run_soc_depth_sensitivity.py --mode smoke`

Full five-year experiment:

`MPLBACKEND=Agg /content/blast_py311/bin/python implementation/soc_depth_sensitivity/run_soc_depth_sensitivity.py --mode full --years 5`

## Next milestone

Compare realistic repository stationary-storage application profiles at
a common 25-degree-Celsius temperature using the same battery model.

The comparison should report mean SOC, modeled depth of discharge,
equivalent full cycles per year, final q, and time to q = 0.80 if reached.
