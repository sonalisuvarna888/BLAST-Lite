# BLAST-Lite Fast-Calculation Example Reproduction

## Purpose

This folder documents a clean reproduction of the BLAST-Lite
fast-calculation example before creating a second-life battery extension.

## Source repositories

- Fork: https://github.com/sonalisuvarna888/BLAST-Lite.git
- Upstream: https://github.com/NatLabRockies/BLAST-Lite.git
- Commit: `b093495b47dc40dd96dba865d91f553619501e94`
- Branch: `reproduction/original-example`

## Official example

`examples/example_fast_calculations.ipynb`

The official example represents constant storage at:

- State of charge: 80%
- Temperature: 45 degrees Celsius
- Repeated period: one day
- Simulation duration: five years
- Battery model: `Nmc111_Gr_Kokam75Ah_Battery`

## Environment

The reproduction was run in an isolated Python 3.11 environment.
The Colab host environment was not used to execute the battery model.

## API compatibility

The official notebook used simulation_years=5, while the checked-out source used threshold_time=5. The current source docstring defines threshold_time as the stopping time in years.

The compatibility handling did not modify:

- the battery class,
- the degradation equations,
- the SOC input,
- the temperature input, or
- the five-year simulation duration.

## Reproduction result

- Initial q: 1.0
- Final q: 0.7354776618956259
- Output points: 1827
- Final simulated time: 5.00268182394733 years
- Tests: No tests collected

## Evidence

The `artifacts` directory contains:

- repository metadata,
- repository inventory,
- documentation extracts,
- installation logs,
- API inspection,
- smoke-test log,
- five-year execution log,
- environment package list,
- numerical results,
- generated figure, and
- structured reproduction record.

## Reproduction boundary

No original BLAST-Lite source file or battery equation was modified.

This work is classified as a script-based compatibility reproduction of
the official example, not yet as an independent reimplementation.

## Next step

The next repository example to investigate is:

`examples/example_stationary_storage_life.ipynb`

Only after an appropriate stationary-storage baseline is reproduced will
a separate branch be created for a second-life battery scenario.