# Realistic Seasonal BLAST-Lite Scenarios

## Purpose

This implementation responds to the need for more realistic battery-aging
inputs than constant state-of-charge (SOC) storage cases.

It evaluates one annual residential photovoltaic–battery energy storage
system (PV-BESS) SOC profile under three controlled constant temperatures
and one variable climate profile.

The primary research question is:

> How does the BLAST-Lite modeled capacity trajectory change when the SOC
> input is held identical and temperature exposure is varied?

## Research status

This is a controlled temperature-sensitivity and climate-informed
simulation study.

It is not:

- an empirical battery lifetime validation;
- a pack-level reliability or safety analysis;
- a final second-life battery claim; or
- a completed CVXPY–BLAST integration.

## Branch

`implementation/realistic-seasonal-scenarios`

The previous controlled-interface implementation remains preserved on:

`implementation/simple-blast-scenarios`

The original compatibility reproduction remains preserved on:

`reproduction/original-example`

## Battery model

`Nmc111_Gr_Kokam75Ah_Battery`

## Source SOC profile

The shared SOC input comes from:

`examples/application profiles/Residential PV-BESS (CA, mild).csv`

The repository describes this as a simulated residential PV-BESS profile.

Source-profile characteristics:

- approximately one year;
- 15-minute resolution;
- SOC range: approximately 30% to 95%;
- mean SOC before correction: approximately 81.65%;
- approximately 72.65 equivalent full cycles per year.

This profile is more operationally realistic than holding the battery at
one constant SOC for five years.

## Annual boundary correction

The source profile begins at SOC 0.50 and ends at SOC 0.792004. Repeating
the source directly would create an artificial 29.2-percentage-point SOC
drop at each annual boundary.

To avoid hiding this discontinuity, the final 24 hours were replaced with
a synthetic linear transition from the original final-day starting SOC of
0.949987 to the initial SOC of 0.50.

The correction:

- preserves the annual row count;
- preserves 15-minute resolution;
- makes the first and last SOC equal;
- adds approximately 0.146 equivalent full cycles per year; and
- is explicitly flagged using `Boundary_Correction=True`.

The corrected annual profile has approximately 72.79 equivalent full
cycles.

## Temperature cases

All four cases use exactly the same corrected SOC values and timestamps.

### T25

- Constant temperature: 25 degrees Celsius
- Purpose: controlled reference case

### T30

- Constant temperature: 30 degrees Celsius
- Purpose: isolate the modeled effect of a 5-degree increase from T25

### T40

- Constant temperature: 40 degrees Celsius
- Purpose: evaluate sustained high-temperature exposure

### Miami_variable

- Variable temperature: 5.0 to 35.6 degrees Celsius
- Annual mean: approximately 24.51 degrees Celsius
- Source: `examples/climates/hourly_temperature_miami.csv`
- Hourly data were linearly interpolated to 15-minute timestamps

The Miami climate is not geographically matched to the California SOC
profile. It is included as a climate-informed variable-temperature case,
not as a site-specific empirical simulation.

## Validation workflow

1. Load the annual SOC source profile.
2. Replace the final day with a documented SOC boundary transition.
3. Create four datasets with identical SOC and different temperatures.
4. Validate columns, time ordering, SOC ranges, and temperatures.
5. Run a 30-day smoke test.
6. Run all four scenarios for five simulated years.
7. Save trajectories, figures, logs, and structured records.

## Input schema

Every final scenario CSV contains:

- `Time_s`
- `SOC`
- `Temperature_C`
- `Boundary_Correction`

The runner passes only the required physical input columns to the
BLAST-Lite API.

## Simulation settings

- Requested horizon: five years
- Duration argument: `threshold_time=5`
- `is_constant_input=False`
- Energy-throughput conservation: repository default
- Main output: normalized capacity `q`
- Additional reported stressor: equivalent full cycles (EFC)

## Five-year results

| Case | Temperature exposure | Final q | Modeled capacity loss |
|---|---|---:|---:|
| T25 | Constant 25 degrees Celsius | 0.922811 | 7.72% |
| T30 | Constant 30 degrees Celsius | 0.888971 | 11.10% |
| T40 | Constant 40 degrees Celsius | 0.778546 | 22.15% |
| Miami_variable | 5.0–35.6 degrees Celsius; mean 24.51 | 0.916880 | 8.31% |

All four cases completed successfully, reached approximately 5.0004
years, and produced 1,830 q-output points.

## Controlled temperature finding

For an identical annual SOC input, final q decreased as constant
temperature increased:

`T25 final q >= T30 final q >= T40 final q`

The modeled five-year capacity loss at 40 degrees Celsius was
approximately 2.87 times the modeled loss at 25 degrees Celsius.

This is a BLAST-Lite result under controlled inputs. It is not an
empirical claim that every battery will experience the same loss.

## Variable-temperature finding

The Miami-variable case had a mean annual temperature close to 25
degrees Celsius but included cooler and warmer periods. Its final q was
0.916880, compared with 0.922811 for constant 25 degrees Celsius.

This demonstrates that a variable temperature trajectory can produce a
different result from constant temperature near the same mean. It does
not establish a universal climate-variability effect.

## Equivalent-full-cycle interpretation

The input SOC was identical across temperature cases, but final model
EFC values were not exactly identical:

- T25: 363.69
- T30: 363.25
- T40: 354.95
- Miami_variable: 363.67

The model used its default energy-throughput conservation behavior.
As modeled capacity changed, internal SOC stress and accumulated EFC
could diverge endogenously.

## Important limitations

- The SOC profile is repository-provided and simulated.
- The final-day SOC correction is synthetic.
- Miami temperature is not site-matched to the California SOC profile.
- The NMC111 Kokam model represents a cell model, not a complete pack.
- The runs do not begin from a documented aged second-life state.
- Results describe model behavior, not universal battery performance.

## Reproducibility

Use an isolated Python 3.11 environment with BLAST-Lite installed from
this repository.

Smoke-test command:

`MPLBACKEND=Agg /content/blast_py311/bin/python implementation/realistic_seasonal_scenarios/run_realistic_scenarios.py --mode smoke`

Full-experiment command:

`MPLBACKEND=Agg /content/blast_py311/bin/python implementation/realistic_seasonal_scenarios/run_realistic_scenarios.py --mode full --years 5`

## Output evidence

The implementation includes:

- corrected annual SOC data and correction metadata;
- four annual temperature-case CSV files;
- smoke-test outputs and logs;
- five-year q and EFC trajectory CSV files;
- scenario and presentation summary CSV files;
- input quality-control figures;
- five-year comparison figures;
- error records; and
- structured run records.

## Planned CVXPY integration

1. CVXPY generates an hourly community-battery SOC history.
2. Time is converted to cumulative seconds.
3. Stored energy is normalized by available capacity.
4. A documented battery-temperature profile is attached.
5. BLAST-Lite evaluates degradation.
6. Updated capacity and limits are passed to the next dispatch period.

## Next experiment

Before full integration:

1. reproduce the official stationary-storage example;
2. compare other repository application profiles;
3. define a documented aged second-life initial condition; and
4. test one-factor-at-a-time SOC depth and temperature experiments.
