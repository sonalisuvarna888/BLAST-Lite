# Annual Community Dispatch and BLAST-Lite Aging

## Purpose

This implementation extends the community-microgrid model from a
24-hour study to one synthetic year and evaluates the resulting battery
SOC trajectories with BLAST-Lite.

The analysis links:

1. ten heterogeneous household demand profiles;
2. shared solar generation;
3. a synthetic time-of-use price;
4. demand response;
5. shared-battery dispatch; and
6. post-processing battery-aging evaluation.

## Branch

`integration/annual-community-dispatch`

## Research status

This is a reproducible synthetic operational prototype.

It is not:

- an empirical household-savings study;
- a utility tariff analysis;
- a distribution power-flow model;
- a fully coupled degradation-feedback optimization; or
- a validated second-life battery-pack lifetime prediction.

## Annual synthetic dataset

The annual dataset contains:

- 365 days;
- 8,760 hourly intervals;
- 10 heterogeneous households;
- 79,217.28 kWh annual community load;
- 9.04 kW mean community load;
- 21.43 kW peak hourly-average community load;
- 18 kW shared PV capacity;
- 32,375.37 kWh annual shared-solar energy;
- a 40.9% solar-to-load energy ratio; and
- a synthetic price range from $0.092 to $0.367 per kWh.

A fixed random seed makes the household and weather profiles
reproducible.

## Household demand construction

Each household includes:

- a background load;
- morning, daytime, and evening components;
- household-specific scale and peak timing;
- seasonal variation;
- weekend effects;
- day-level and hour-level random variation; and
- occasional evening events.

All profiles are synthetic and should not be interpreted as measured
customer data.

## Optimization structure

The model solves 365 sequential daily optimization problems with a
48-hour rolling look-ahead whenever the next day is available.

Only the first 24 hours are implemented. The ending battery SOC becomes
the next day's initial SOC.

The four operating cases are:

- baseline;
- demand response only;
- battery only; and
- demand response plus battery.

## Demand response

For each household:

- hourly load can vary from 85% to 115% of baseline;
- daily household energy is preserved; and
- a normalized quadratic inconvenience penalty discourages large shifts.

## Battery assumptions

- Nominal capacity: 60 kWh
- Initial assumed SOH: 70%
- Fixed available capacity during dispatch: 42 kWh
- SOC window: 10% to 90%
- Charge/discharge power: 12 kW
- Round-trip efficiency: 85%
- Initial and final annual SOC: 21 kWh
- Throughput proxy: $0.015 per kWh
- Selected synthetic rolling-window peak penalty: $0.50 per kW

The peak penalty is a planning sensitivity, not a documented utility
demand charge.

## Annual dispatch results

| Case | Annual bill | Bill savings | Peak reduction | Solar spill |
|---|---:|---:|---:|---:|
| Baseline | $12,970.89 | 0.00% | 0.00% | 9,446.55 kWh |
| DR only | $11,831.02 | 8.79% | 15.00% | 7,588.77 kWh |
| Battery only | $9,573.16 | 26.20% | 34.26% | 1,510.31 kWh |
| DR + battery | $8,556.15 | 34.04% | 41.92% | 807.92 kWh |

The combined case produces the lowest modeled grid-energy bill, the
largest peak reduction, and the lowest solar curtailment.

Battery cases increase conversion losses but enable greater use of local
solar and lower-priced grid energy.

## Annual validation

All 1,460 daily case-solves completed successfully.

Validation confirmed:

- 8,760 output hours for every case;
- no failed daily optimization;
- negligible energy-balance residuals;
- battery SOC within bounds;
- continuous SOC across daily boundaries;
- final annual SOC returned to its initial target;
- household daily energy preserved in DR cases; and
- no material simultaneous charging and discharging.

## BLAST-ready annual inputs

Hourly battery SOC histories were converted to BLAST-Lite inputs for:

- battery only; and
- demand response plus battery.

Each file contains 8,761 points, including the final annual endpoint.

SOC is normalized by the fixed 42-kWh available capacity used in the
dispatch model.

A Miami annual temperature profile was attached:

- minimum: 5.0 degrees Celsius;
- annual mean: approximately 24.51 degrees Celsius;
- maximum: 35.6 degrees Celsius.

The Miami climate is not geographically matched to the synthetic
community and is used only as a climate-informed trajectory.

## Five-year BLAST-Lite post-processing

| Case | Mean SOC | Annual input EFC | Final q | Modeled capacity loss |
|---|---:|---:|---:|---:|
| Battery only | 0.5134 | 406.75 | 0.893096 | 10.69% |
| DR + battery | 0.5338 | 392.59 | 0.890412 | 10.96% |

The DR-plus-battery trajectory has approximately 3.48% fewer annual EFC
but a mean SOC that is 0.0204 higher.

Its modeled five-year capacity loss is approximately 0.27 percentage
points greater.

This modest difference supports a multi-stressor interpretation:
reduced cycling does not necessarily imply reduced degradation when SOC
exposure also changes.

## Interpretation boundaries

- All load, solar, price, and weather-matching assumptions are synthetic.
- The dispatch uses a fixed 42-kWh available capacity for the full year.
- BLAST-Lite degradation is evaluated after dispatch, not fed back into
  the dispatch model.
- The battery model is cell-level and does not represent all pack-level
  effects.
- q is normalized capacity output, not a complete SOH, safety, or
  warranty metric.
- The five-year result is model behavior under selected inputs, not an
  empirical lifetime prediction.

## Reproducibility

Annual dispatch:

`python integration/annual_community_dispatch/run_annual_dispatch.py --days 365 --peak-penalty-per-kw 0.5`

BLAST-Lite post-processing:

`MPLBACKEND=Agg /content/blast_py311/bin/python integration/annual_community_dispatch/run_annual_blast_aging.py --mode full --years 5`

## Output evidence

The branch includes:

- annual household, solar, and price datasets;
- household-generation parameters;
- annual dispatch outputs for four cases;
- daily optimization records;
- operational audits;
- pilot and annual sensitivity analyses;
- BLAST-ready annual SOC inputs;
- five-year BLAST trajectories;
- integrated dispatch-aging metrics;
- figures, logs, and structured JSON records.

## Main conclusion

Demand response plus battery operation provides greater modeled
operational value than battery-only operation, including larger bill and
peak reductions.

However, the combined trajectory has slightly greater modeled capacity
loss despite fewer equivalent full cycles because it operates at a
higher mean SOC.

The result shows why throughput alone is insufficient for representing
battery degradation in community-microgrid optimization.

## Next milestone

1. Reproduce the official stationary-storage notebook.
2. Define a consistent aged second-life initial condition.
3. Introduce degradation feedback into annual dispatch.
4. Compare fixed-capacity dispatch with dynamically updated capacity.
5. Evaluate an SOH surrogate model for repeated optimization.
