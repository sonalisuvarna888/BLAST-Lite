# Consistent Second-Life Battery Initial Condition

## Purpose

This branch defines and validates an internally consistent second-life
starting state for the NMC111 Kokam BLAST-Lite model.

The battery is not initialized by manually changing q.

Instead, a fresh battery is aged through a documented first-life EV
profile until q reaches 0.80. The complete battery object, including
capacity states, resistance states, outputs, rates, stressors, elapsed
time, and equivalent full cycles, is preserved and continued into
stationary service.

## Branch

`extension/second-life-initial-condition`

## Battery model

`Nmc111_Gr_Kokam75Ah_Battery`

## Transition threshold

The analytical second-life transition occurs when:

`q <= 0.80`

This is a scenario definition and not a universal EV retirement rule.

## Official EV source

The official EV-life notebook is preserved on this branch:

`examples/example_EV_life.ipynb`

Notebook SHA256:

`625b0491b5b1da2cc084c64eecb174c0a311441bca9f5db0df44fe5e5732d805`

The notebook states that its EV driving profiles are illustrative and
not representative of real-world vehicles.

## First-life candidate profiles

Five annual profiles were evaluated:

- combined personal EV, unscaled;
- personal EV, large battery;
- personal EV, small battery;
- commercial EV; and
- combined personal EV scaled toward 55 EFC/year.

All profiles use constant 25 degrees Celsius and the NMC111 Kokam model
with `degradation_scalar=2.75`, following the notebook's VMT-based
NMC111 example.

## Annual harmonization

The repository's `assemble_one_year_input` utility creates 8,640 hourly
points, corresponding to approximately 360 days.

For repeatable first-life simulations, each candidate was extended to:

- 365 days;
- 8,760 hourly intervals;
- 8,761 points including the final endpoint; and
- a continuous annual SOC boundary.

If the first-to-last SOC difference exceeded 0.01, the final 24 hours
were replaced with a documented linear transition.

The selected profile did not require a synthetic boundary correction.

## Candidate results

| Candidate | Annual EFC | Years to q=0.80 | EFC at transition | Final r |
|---|---:|---:|---:|---:|
| Combined unscaled | 90.90 | 12.82 | 1,156.61 | 27.14 |
| Personal large | 64.38 | 25.92 | 1,608.46 | 48.19 |
| Personal small | 132.63 | 14.52 | 1,895.46 | 28.98 |
| Commercial | 657.00 | 2.11 | 1,268.16 | 3.09 |
| Combined scaled 55 EFC | 53.76 | 20.91 | 1,084.47 | 51.14 |

Resistance `r` is a normalized model output, not direct ohmic
resistance.

## Selected first-life history

The selected profile is:

`combined_unscaled`

Selection reasons:

- it is an official combined personal-EV profile;
- it is naturally continuous after 365-day tiling;
- it requires no synthetic final-day correction;
- it has moderate annual use of approximately 90.90 EFC;
- it reaches q=0.80 in 12.82 modeled years; and
- it avoids the commercial profile's extreme annual throughput.

## Selected transition state

At the second-life transition:

- q: approximately 0.800000;
- normalized resistance r: approximately 27.1363;
- modeled first-life time: approximately 12.8179 years;
- cumulative EFC: approximately 1,156.61;
- all internal degradation states are finite; and
- the full battery object is saved as a pickle and JSON state record.

## Serialization validation

Python `deepcopy` and pickle serialization are supported.

The saved-state audit confirmed:

- q matches the pre-serialization value;
- resistance matches;
- modeled time matches;
- EFC matches;
- all final states, outputs, stressors, and rates are finite; and
- expected initial NaN entries occur only in historical stressor and
  rate arrays.

## Stationary service profile

The selected aged battery is continued using the annual community
demand-response-plus-battery SOC trajectory from:

`integration/annual-community-dispatch`

Source commit:

`114193eedee56340403d390fce7431ceb09e9e4c`

The profile uses Miami temperature and was generated under a fixed
42-kWh dispatch-capacity assumption.

## One-year stationary continuation

The internally consistent aged state was continued for one full modeled
year.

| Metric | At transition | After one stationary year | Change |
|---|---:|---:|---:|
| q | 0.800000 | 0.765158 | -0.034842 |
| normalized r | 27.1363 | 29.5417 | +2.4055 |
| modeled time | 12.8179 years | 13.8183 years | +1.0003 years |
| EFC | 1,156.61 | 1,512.10 | +355.49 |

A fresh reference battery under the same one-year stationary profile
ended at q = 0.927448.

The fresh and aged results should not be interpreted as a simple
age-only causal comparison because their internal histories and
effective model behavior differ.

## Continuation equivalence

Three continuation paths were tested:

1. directly loaded aged state;
2. deep copy of the loaded aged state; and
3. independently reloaded pickle.

All three produced identical final:

- q;
- resistance;
- modeled time; and
- EFC.

The test also confirmed that:

- q did not reset;
- resistance did not reset;
- elapsed time continued;
- EFC continued; and
- history arrays were appended.

## Reproducibility

Generate candidate aged states:

`MPLBACKEND=Agg /content/blast_py311/bin/python extension/second_life_initial_condition/run_first_life_candidates.py`

Test continuation:

`MPLBACKEND=Agg /content/blast_py311/bin/python extension/second_life_initial_condition/test_second_life_continuation.py`

## Important limitations

- q=0.80 is an analytical transition threshold.
- First-life profiles are illustrative repository profiles.
- The degradation scalar of 2.75 is scenario-specific.
- The battery model is cell-level rather than a complete pack model.
- The stationary service profile uses synthetic community dispatch.
- The Miami climate is not geographically matched to the community.
- State continuity does not establish second-life safety or warranty
  suitability.

## Main conclusion

A consistent second-life state can be created by aging the full battery
model through a documented first-life history and preserving all model
states.

Manually changing only q is unnecessary and would risk internal
inconsistency.

## Next milestone

Use the selected aged state in a monthly dynamic-capacity feedback loop:

1. solve one month of community dispatch;
2. evaluate monthly aging;
3. update available capacity and SOC limits;
4. solve the next month; and
5. compare fixed-capacity and dynamically updated operation.
