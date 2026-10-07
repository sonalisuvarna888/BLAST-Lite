# Official Stationary-Storage Example Reproduction

## Purpose

This branch provides a script-based, auditable reproduction of:

`examples/example_stationary_storage_life.ipynb`

The official notebook compares eight stationary-storage application
profiles across four BLAST-Lite battery models.

## Branch

`reproduction/stationary-storage-example`

## Reproduction scope

The primary reproduction includes:

- eight official application profiles;
- four battery models;
- application SOC, EFC, and DOD statistics;
- q versus modeled time;
- q versus equivalent full cycles;
- q = 0.70 capacity threshold;
- 30-year modeled-time cap;
- complete execution logs and compact trajectory CSVs.

The battery-sizing derating and cost-factor section is deferred until
the main stationary-lifetime figures are fully documented.

## Battery models

- `Nmc111_Gr_Kokam75Ah_Battery`
- `Lfp_Gr_250AhPrismatic`
- `Nca_Gr_Panasonic3Ah_Battery`
- `Nmc622_Gr_DENSO50Ah_Battery`

## Applications

- Commercial peak shaving
- Residential PV-BESS — California mild
- Telecom backup power and peak shaving
- EV charging support — rental-car depot
- Commercial PV-BESS — NREL
- Frequency containment reserve
- Residential PV-BESS — Germany aggressive
- EV charging support — corner charging station

## Reproduction environment

- Isolated Python 3.11 environment
- BLAST-Lite installed from the checked-out repository
- Noninteractive Matplotlib Agg backend
- Current API duration argument: `threshold_time`
- Original BLAST-Lite battery equations unchanged

## Preserved evidence

The branch contains:

- an exact copy of the official notebook;
- a human-readable cell extract;
- a code-only extract;
- the notebook SHA256 hash;
- source-file hashes;
- battery-model source inventory;
- API signatures;
- source-profile inventory; and
- run records, logs, figures, and numerical summaries.

## Important temperature inconsistency

The official notebook markdown states:

> All simulations assume a stable temperature of 30 degrees Celsius.

However:

- every official application CSV contains `Temperature_C = 20`;
- the notebook code loads the CSV files directly;
- the code does not overwrite temperature; and
- BLAST-Lite uses the source dataframe temperature values.

Therefore, the literal notebook-code execution uses 20°C rather than
the stated 30°C.

This branch treats:

- source 20°C execution as the primary literal reproduction; and
- explicit 30°C override as a separate markdown-intent sensitivity.

## Literal source-temperature reproduction

All 32 battery/application combinations completed successfully.

| Battery model | Applications reaching q = 0.70 before 30 years |
|---|---:|
| NMC111-Gr | 4 of 8 |
| LFP-Gr | 1 of 8 |
| NCA-Gr | 6 of 8 |
| NMC622-Gr | 3 of 8 |

The reproduction supports the official qualitative conclusion:

> Battery chemistry and stationary application duty cycle produce widely
> different modeled capacity trajectories and threshold times.

## Application stress characteristics

The official application profiles span a wide range:

| Application | Annual EFC | Mean SOC | RMS modeled DOD |
|---|---:|---:|---:|
| Commercial peak shaving | 19.26 | 0.990 | 0.131 |
| Residential CA PV-BESS | 72.65 | 0.817 | 0.341 |
| Telecom backup | 91.33 | 0.742 | 0.369 |
| EV rental-car depot | 155.56 | 0.304 | 0.551 |
| Commercial NREL PV-BESS | 213.39 | 0.955 | 0.791 |
| Frequency reserve | 233.26 | 0.493 | 0.347 |
| Germany PV-BESS | 261.81 | 0.326 | 0.826 |
| EV corner station | 366.86 | 0.335 | 0.827 |

These statistics reinforce that application stress is not represented
by equivalent full cycles alone.

## Explicit 30-degree sensitivity

All 32 explicit-30°C cases also completed successfully.

Temperature comparison classes:

- 12 pairs reached q = 0.70 at both temperatures;
- 16 pairs reached neither threshold by 30 years;
- 2 pairs reached only at source 20°C; and
- 2 pairs reached only at explicit 30°C.

For pairs reaching q = 0.70 at both temperatures:

- mean threshold-time change at 30°C: approximately -4.96 years;
- median threshold-time change: approximately -5.07 years.

For pairs reaching neither threshold:

- 15 of 16 had lower final q at 30°C;
- mean final-q change was approximately -0.0514.

The effect is material but model- and application-dependent. The results
should not be summarized as a universal monotonic lifetime rule.

## Interpretation rule

Threshold time and capped final q must be interpreted separately.

- If both runs reach q = 0.70, compare threshold times.
- If neither reaches q = 0.70, compare final q at the 30-year cap.
- If only one reaches q = 0.70, report the status transition explicitly.

## Important limitations

- Stationary-storage horizons of 20 to 30 years extend beyond much of
  the degradation-model calibration data.
- The source profiles may not represent all systems with the same
  application label.
- The models estimate cell-level expected behavior, not complete
  battery-pack reliability or safety.
- q is normalized capacity output, not a full SOH definition.
- The source temperature inconsistency materially affects results.
- Long-horizon outputs are model extrapolations, not validated service-
  life or warranty predictions.

## Reproducibility

Literal notebook-code reproduction:

`MPLBACKEND=Agg /content/blast_py311/bin/python reproduction/stationary_storage_example/run_stationary_storage_reproduction.py --temperature-mode literal_source_20C --threshold-capacity 0.70 --threshold-time 30`

Explicit markdown-intent sensitivity:

`MPLBACKEND=Agg /content/blast_py311/bin/python reproduction/stationary_storage_example/run_stationary_storage_reproduction.py --temperature-mode override_30C --threshold-capacity 0.70 --threshold-time 30`

## Main conclusion

The official stationary-storage analysis is reproducible as a script
and confirms that battery chemistry and application profile strongly
change modeled degradation.

The notebook also contains a material documentation inconsistency:
prose states 30°C, while literal code execution uses source data at 20°C.

For publication, the literal 20°C execution should be reported as the
primary reproduction and the explicit 30°C run should be presented as a
separate sensitivity.

## Next milestone

Generate a physically consistent second-life starting state by aging a
fresh battery through a documented first-life profile.

Do not modify only q. Preserve the full battery state, including capacity
and resistance-related degradation variables, before continuing into
stationary service.
