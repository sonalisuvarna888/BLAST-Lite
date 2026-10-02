# Stationary Application-Profile Comparison

## Purpose

This analysis compares four repository-provided stationary-storage SOC
profiles using the same BLAST-Lite battery model and a fixed temperature
of 25 degrees Celsius.

The analysis reports:

- mean and median SOC;
- modeled depth-of-discharge statistics;
- annualized equivalent full cycles;
- normalized capacity after five modeled years; and
- modeled time to q = 0.80, if reached within a 30-year cap.

## Branch

`analysis/stationary-application-comparison`

## Battery model

`Nmc111_Gr_Kokam75Ah_Battery`

## Applications

1. Residential PV-BESS — California mild
2. Residential PV-BESS — Germany aggressive
3. Commercial peak shaving
4. Frequency containment reserve

The source files are located in:

`examples/application profiles/`

## Common simulation settings

- Fixed temperature: 25 degrees Celsius
- Five-year comparison horizon
- `threshold_time=5`
- `is_constant_input=False`
- Repository-default energy-throughput conservation
- q = 0.80 threshold analysis capped at 30 modeled years

## Harmonization policy

The source profiles have different resolutions and boundary conditions.
To make annual repetition transparent:

1. each source time axis is normalized to begin at zero;
2. native time resolution is preserved;
3. each dataset is constructed to span one year;
4. a missing tail is filled by holding the last observed SOC;
5. if first-to-last SOC differs by more than 0.01, the final 24 hours are
   replaced by a linear return to the initial SOC; and
6. every correction is explicitly recorded.

## Harmonization outcomes

### Residential California mild

- Final-day correction applied
- Annual EFC changed from approximately 72.65 to 72.79
- Synthetic EFC change: approximately +0.146

### Residential Germany aggressive

- No boundary correction required
- Annual EFC: approximately 261.81

### Commercial peak shaving

- No boundary correction required
- Source covered approximately 357 days
- Eight-day constant-SOC tail extension added
- Annual EFC remained approximately 18.84

### Frequency containment reserve

- Final-day correction applied
- Annual EFC changed from approximately 233.25 to 232.59
- Synthetic EFC change: approximately -0.662

Tail extension and boundary correction are synthetic harmonization
steps. They are not measured operating behavior.

## Five-year results

| Application | Mean SOC | Annual EFC | Final q | Modeled capacity loss |
|---|---:|---:|---:|---:|
| Residential CA mild | 0.816 | 72.79 | 0.922811 | 7.72% |
| Residential Germany aggressive | 0.326 | 261.81 | 0.887713 | 11.23% |
| Commercial peak shaving | 0.990 | 18.84 | 0.907849 | 9.22% |
| Frequency containment reserve | 0.493 | 232.60 | 0.957165 | 4.28% |

All four five-year cases completed successfully and produced finite q
and stressor outputs.

## Main interpretation

Application degradation is not determined by equivalent full cycles
alone.

Commercial peak shaving has the lowest annual EFC, but its mean SOC is
approximately 99%. Its modeled five-year capacity loss is greater than
the frequency-containment case, even though frequency containment has
more than twelve times the annual EFC.

The results demonstrate that mean SOC, calendar exposure, depth-of-
discharge distribution, and cycling throughput interact in the model.

## q = 0.80 threshold analysis

| Application | Threshold result |
|---|---|
| Residential CA mild | Not reached by 30 modeled years; q = 0.837 |
| Residential Germany aggressive | Reached at 12.22 modeled years |
| Commercial peak shaving | Not reached by 30 modeled years; q = 0.819 |
| Frequency containment reserve | Reached at 28.28 modeled years |

These threshold values are long-horizon model extrapolations. They are
not validated service-life predictions, warranty estimates, or pack-
replacement recommendations.

## Important limitations

- The source application profiles are repository-provided examples.
- Profiles may be simulated or based on application-specific source data.
- Harmonization modifies the California and frequency-reserve final day.
- Commercial peak shaving includes a synthetic constant-SOC tail.
- Temperature is fixed at 25 degrees Celsius for experimental comparison.
- The NMC111 Kokam cell model is not a complete pack model.
- No second-life initial condition is applied.
- Long-horizon predictions extend beyond typical model calibration data.
- Results describe BLAST-Lite behavior under these inputs, not universal
  application lifetimes.

## Output evidence

The branch includes:

- source-profile audit data;
- harmonization policy and summary;
- four harmonized annual input CSVs;
- annual and representative-week SOC figures;
- reusable smoke/full/threshold runner;
- smoke-test results and logs;
- five-year q and EFC trajectories;
- q = 0.80 threshold results;
- presentation and machine-readable summary tables;
- publication-style figures; and
- JSON error records.

## Reproducibility

Smoke test:

`MPLBACKEND=Agg /content/blast_py311/bin/python analysis/stationary_application_comparison/run_application_comparison.py --mode smoke`

Full five-year and threshold experiment:

`MPLBACKEND=Agg /content/blast_py311/bin/python analysis/stationary_application_comparison/run_application_comparison.py --mode full --years 5 --max-threshold-years 30`

## Research value

The application comparison provides a more realistic basis for selecting
battery operating trajectories than constant-SOC examples.

It also shows why a simple throughput degradation penalty may be
insufficient for community-microgrid optimization: low-throughput,
high-SOC operation can produce substantial modeled degradation.

## Next milestone

Reproduce the official stationary-storage notebook as an auditable,
script-based benchmark on:

`reproduction/stationary-storage-example`

After that reproduction, inspect and define a consistent second-life
initial condition without modifying only q in isolation.
