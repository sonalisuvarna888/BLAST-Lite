# BLAST-Lite Simple-Scenario Implementation

## Purpose

This implementation validates that BLAST-Lite can accept controlled
state-of-charge (SOC) and temperature inputs and generate reproducible
numerical battery-degradation outputs.

This is a validation study. It is not yet the final second-life battery
case and is not yet connected to the community-microgrid optimization
model.

## Branches

Implementation branch:

`implementation/simple-blast-scenarios`

Preserved reproduction branch:

`reproduction/original-example`

## Battery model

`Nmc111_Gr_Kokam75Ah_Battery`

## Simulation settings

- Requested horizon: five years
- Duration argument: `threshold_time=5`
- Main output: `q`
- Temperature units: degrees Celsius
- Time input units: seconds
- Final simulated time: approximately 5.0027 years

## Scenarios

### Scenario A — Constant high-SOC storage

- SOC: 80%
- Temperature: 45 degrees Celsius
- Input duration: one day
- `is_constant_input`: `True`
- Final `q`: approximately 0.735478

This scenario reproduces the physical inputs of the official
fast-calculation example.

### Scenario B — Constant moderate-SOC storage

- SOC: 50%
- Temperature: 25 degrees Celsius
- Input duration: one day
- `is_constant_input`: `True`
- Final `q`: approximately 0.981995

This scenario demonstrates that the interface accepts another controlled
storage condition.

### Scenario C — Daily stationary cycle

- SOC range: 30% to 80%
- Temperature: 25 degrees Celsius
- Input duration: one day
- `is_constant_input`: `False`
- Final `q`: approximately 0.945890

For this checked-out API and input, the nonconstant one-day profile
continued to the requested five-year stopping time.

This validates charging and discharging behavior, but it does not yet
represent a community-microgrid dispatch trajectory.

## Inputs

The `scenario_inputs` directory contains:

- `scenario_A_constant_80pct.csv`
- `scenario_B_constant_50pct.csv`
- `scenario_C_daily_cycle.csv`

Each input contains `Time_s`, `SOC`, and `Temperature_C`.

## Outputs

The `results` directory contains:

- one numerical CSV trajectory for each scenario;
- `scenario_summary.csv`;
- `scenario_comparison.png`; and
- `run_record.json`.

The `logs` directory contains:

- `execution_log.txt`; and
- `scenario_errors.json`.

The error record is an empty JSON list when no scenario fails.

## Results summary

| Scenario | Operating condition | Final q |
|---|---|---:|
| A | Constant 80% SOC at 45 degrees Celsius | 0.735478 |
| B | Constant 50% SOC at 25 degrees Celsius | 0.981995 |
| C | Daily 30%-80% SOC cycle at 25 degrees Celsius | 0.945890 |

These are controlled validation cases, not final second-life claims.

## Reproduction instructions

Use an isolated Python 3.11 environment with BLAST-Lite installed from
this repository. From the repository root, run:

`MPLBACKEND=Agg /content/blast_py311/bin/python implementation/simple_scenarios/run_simple_scenarios.py`

The runner detects whether the API uses `threshold_time` or
`simulation_years`.

## Interpretation

The high-temperature, high-SOC case produced the lowest final `q`.
The moderate-temperature, moderate-SOC case produced the highest final
`q`. The daily cycling case produced an intermediate final `q`.

This comparison demonstrates interface functionality. It does not
isolate the causal contribution of SOC, temperature, or cycling because
more than one operating variable differs across scenarios.

## Planned community-microgrid integration

1. CVXPY generates an hourly battery SOC and dispatch trajectory.
2. The trajectory and a temperature profile are converted to the
   BLAST-Lite input format.
3. BLAST-Lite evaluates degradation.
4. Updated battery condition is passed to the next optimization period.

## Next milestone

Before full CVXPY integration:

1. reproduce the official stationary-storage example;
2. compare its assumptions with these controlled scenarios; and
3. define a documented aged initial condition.
