# Real Household Load Dataset

## Purpose

This branch downloads, audits, selects, and cleans real residential
electricity data for use in the annual community-microgrid model.

## Source

Dataset:

`HUE: The Hourly Usage of Energy Dataset for Buildings in British Columbia`

Persistent identifier:

`doi:10.7910/DVN/N3HGRN`

Data article:

Stephen Makonin, “HUE: The Hourly Usage of Energy Dataset for Buildings
in British Columbia,” Data in Brief, vol. 23, article 103744, 2019.

License:

Creative Commons Attribution 4.0 (CC BY 4.0).

## Raw data

The Harvard Dataverse contains:

- 28 residential household files;
- one solar file;
- two weather files;
- a holiday/calendar file; and
- one residential documentation file.

The residential files contain:

- date;
- hour; and
- hourly interval energy in kWh.

Because the interval is one hour, hourly energy in kWh is numerically
equal to hourly-average power in kW.

## Dataverse download behavior

The Dataverse API returned tabular-export files with exact expected byte
sizes but checksums different from the original-file metadata.

The original expected and downloaded hashes are preserved.

Downloaded tabular files were validated using:

- file size;
- schema;
- row count;
- timestamp coverage;
- missingness;
- numeric values; and
- data ranges.

The documentation text file matched its original MD5 checksum.

## Analysis year

The selected analysis year is 2017.

2017 contains:

- 24 households with some data;
- 18 households above 98% nonmissing completeness;
- 14 households above 99% nonmissing completeness.

A non-leap year provides a canonical 8,760-hour analysis period.

## Household selection

Ten households were selected by:

1. requiring at least 99% nonmissing coverage;
2. requiring no negative energy values; and
3. selecting evenly spaced annual-energy ranks.

Selected source households:

- Residential_06
- Residential_22
- Residential_10
- Residential_07
- Residential_05
- Residential_20
- Residential_13
- Residential_04
- Residential_19
- Residential_14

Selection is based on data quality and annual-energy diversity, not
optimization performance.

## Timestamp handling

The source files use hour values from 0 to 23.

The canonical analysis index is:

`2017-01-01 00:00:00` through `2017-12-31 23:00:00`

Duplicate timestamps associated with clock changes were averaged before
reindexing.

## Missing-data treatment

For each household:

1. duplicate timestamps were averaged;
2. gaps of up to three hours were filled by time interpolation;
3. remaining gaps were filled using the household hour-of-week median;
4. an overall median fallback was available but was not needed.

Every selected household required less than 0.7% imputation.

## Processed dataset

The main processed file is:

`processed/real_household_loads_2017_hourly.csv`

It contains:

- 8,760 unique hourly timestamps;
- ten household load columns;
- imputation flags;
- community load;
- calendar fields; and
- weekend indicators.

## Real community summary

- Annual community energy: 77,603.75 kWh
- Mean community load: 8.86 kW
- Peak hourly-average load: 27.43 kW
- Household annual-energy range: approximately 2,956 to 13,612 kWh

## Controlled real-versus-synthetic input

The file:

`processed/real_annual_community_inputs_2017.csv`

replaces only the household-load layer of the validated annual model.

It preserves the same synthetic:

- shared-solar profile; and
- electricity-price profile.

This isolates the effect of replacing synthetic household demand with
real measured demand.

## Input comparison

| Metric | Real HUE data | Synthetic data |
|---|---:|---:|
| Annual energy | 77,603.75 kWh | 79,217.28 kWh |
| Mean load | 8.86 kW | 9.04 kW |
| Peak load | 27.43 kW | 21.43 kW |
| Solar/load ratio | 41.72% | 40.87% |

The annual energy is similar, but the real-data peak is substantially
higher.

## Figures

The branch includes:

- annual energy by household;
- one-day household profiles;
- one-week household profiles;
- daily household-energy heatmap;
- community load-duration curve; and
- weekday/weekend community profiles.

## Important limitations

- Household locations are in British Columbia, while solar and price
  profiles remain synthetic and are not site matched.
- The selected ten households are a quality-controlled sample, not a
  statistically representative population.
- Imputation is limited but still modifies the original data.
- The optimization results must be reported separately from data-cleaning
  results.

## Next milestone

Run the validated annual community-dispatch and battery-aging workflow
using the processed real household loads and compare the results with
the synthetic benchmark.
