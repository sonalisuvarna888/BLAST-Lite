
import argparse
import copy
import json
import pickle
import traceback
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd

# Compatibility for NumPy versions where
# np.trapz was removed in favor of np.trapezoid.
# This aliases the integration function without
# changing BLAST-Lite battery equations.
if not hasattr(np, "trapz"):
    np.trapz = np.trapezoid

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "inputs"
STATE_DIR = BASE_DIR / "states"
RESULTS_DIR = BASE_DIR / "results"
FIGURE_DIR = BASE_DIR / "figures"
LOG_DIR = BASE_DIR / "logs"

for directory in [
    RESULTS_DIR,
    FIGURE_DIR,
    LOG_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


N_HOUSES = 10
HOURS_PER_DAY = 24

ENTRY_Q = 0.80
ENTRY_CAPACITY_KWH = 42.0

SOC_MIN_FRACTION = 0.10
SOC_MAX_FRACTION = 0.90
INITIAL_SOC_FRACTION = 0.50

MAX_CHARGE_KW = 12.0
MAX_DISCHARGE_KW = 12.0

ROUND_TRIP_EFFICIENCY = 0.85
ETA_C = np.sqrt(
    ROUND_TRIP_EFFICIENCY
)
ETA_D = np.sqrt(
    ROUND_TRIP_EFFICIENCY
)

DR_LOWER = 0.85
DR_UPPER = 1.15
INCONVENIENCE_WEIGHT = 0.035

THROUGHPUT_COST = 0.015
TERMINAL_TARGET_WEIGHT = 0.10
PEAK_PENALTY_PER_KW = 0.50

MONTH_DAY_COUNTS = [
    31,
    28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
]


EXPERIMENTS = {
    "battery_only_fixed": {
        "demand_response":
            False,
        "capacity_treatment":
            "fixed",
    },
    "battery_only_dynamic": {
        "demand_response":
            False,
        "capacity_treatment":
            "dynamic",
    },
    "dr_plus_battery_fixed": {
        "demand_response":
            True,
        "capacity_treatment":
            "fixed",
    },
    "dr_plus_battery_dynamic": {
        "demand_response":
            True,
        "capacity_treatment":
            "dynamic",
    },
}


def load_aged_battery():
    path = (
        STATE_DIR
        / "second_life_entry_battery.pkl"
    )

    with path.open(
        "rb"
    ) as file:
        return pickle.load(
            file
        )


def battery_metrics(
    battery,
):
    return {
        "q":
            float(
                np.asarray(
                    battery.outputs[
                        "q"
                    ]
                )[-1]
            ),
        "r":
            float(
                np.asarray(
                    battery.outputs[
                        "r"
                    ]
                )[-1]
            ),
        "time_years":
            float(
                np.asarray(
                    battery.stressors[
                        "t_days"
                    ]
                )[-1]
                / 365.0
            ),
        "efc":
            float(
                np.asarray(
                    battery.stressors[
                        "efc"
                    ]
                )[-1]
            ),
    }


def capacity_from_q(
    q,
    treatment,
):
    if treatment == "fixed":
        return (
            ENTRY_CAPACITY_KWH
        )

    return (
        ENTRY_CAPACITY_KWH
        * q
        / ENTRY_Q
    )


def solve_day(
    baseline,
    solar,
    price,
    initial_soc_fraction,
    capacity_kwh,
    demand_response,
    final_day_of_period,
):
    horizon = len(price)

    constraints = []

    if demand_response:
        demand = cp.Variable(
            (
                N_HOUSES,
                horizon,
            ),
            nonneg=True,
        )

        constraints.extend([
            demand
            >= DR_LOWER
            * baseline,
            demand
            <= DR_UPPER
            * baseline,
        ])

        constraints.append(
            cp.sum(
                demand[
                    :,
                    :24,
                ],
                axis=1,
            )
            ==
            np.sum(
                baseline[
                    :,
                    :24,
                ],
                axis=1,
            )
        )

        if horizon > 24:
            constraints.append(
                cp.sum(
                    demand[
                        :,
                        24:,
                    ],
                    axis=1,
                )
                ==
                np.sum(
                    baseline[
                        :,
                        24:,
                    ],
                    axis=1,
                )
            )
    else:
        demand = baseline

    grid = cp.Variable(
        horizon,
        nonneg=True,
    )

    spill = cp.Variable(
        horizon,
        nonneg=True,
    )

    charge = cp.Variable(
        horizon,
        nonneg=True,
    )

    discharge = cp.Variable(
        horizon,
        nonneg=True,
    )

    soc = cp.Variable(
        horizon + 1,
    )

    soc_min_kwh = (
        SOC_MIN_FRACTION
        * capacity_kwh
    )

    soc_max_kwh = (
        SOC_MAX_FRACTION
        * capacity_kwh
    )

    initial_soc_kwh = (
        initial_soc_fraction
        * capacity_kwh
    )

    target_soc_kwh = (
        INITIAL_SOC_FRACTION
        * capacity_kwh
    )

    constraints.extend([
        charge
        <= MAX_CHARGE_KW,
        discharge
        <= MAX_DISCHARGE_KW,
        soc[0]
        == initial_soc_kwh,
        soc
        >= soc_min_kwh,
        soc
        <= soc_max_kwh,
    ])

    for hour in range(
        horizon
    ):
        constraints.append(
            soc[hour + 1]
            ==
            soc[hour]
            + ETA_C
            * charge[hour]
            - discharge[hour]
            / ETA_D
        )

    if final_day_of_period:
        constraints.append(
            soc[-1]
            == target_soc_kwh
        )

    aggregate_demand = (
        cp.sum(
            demand,
            axis=0,
        )
        if demand_response
        else np.sum(
            baseline,
            axis=0,
        )
    )

    constraints.append(
        grid
        + solar
        + discharge
        ==
        aggregate_demand
        + charge
        + spill
    )

    window_peak = cp.Variable(
        nonneg=True,
    )

    constraints.append(
        grid
        <= window_peak
    )

    energy_cost = cp.sum(
        cp.multiply(
            price,
            grid,
        )
    )

    if demand_response:
        inconvenience = (
            INCONVENIENCE_WEIGHT
            * cp.sum_squares(
                (
                    demand
                    - baseline
                )
                / (
                    baseline
                    + 0.25
                )
            )
        )
    else:
        inconvenience = 0.0

    throughput_cost = (
        THROUGHPUT_COST
        * 0.5
        * cp.sum(
            charge
            + discharge
        )
    )

    if final_day_of_period:
        terminal_penalty = 0.0
    else:
        terminal_penalty = (
            TERMINAL_TARGET_WEIGHT
            * cp.square(
                soc[-1]
                - target_soc_kwh
            )
        )

    peak_cost = (
        PEAK_PENALTY_PER_KW
        * window_peak
    )

    problem = cp.Problem(
        cp.Minimize(
            energy_cost
            + inconvenience
            + throughput_cost
            + terminal_penalty
            + peak_cost
        ),
        constraints,
    )

    problem.solve(
        solver="CLARABEL",
        verbose=False,
        max_iter=300,
    )

    if problem.status not in {
        cp.OPTIMAL,
        cp.OPTIMAL_INACCURATE,
    }:
        raise RuntimeError(
            problem.status
        )

    demand_value = (
        np.asarray(
            demand.value,
            dtype=float,
        )
        if demand_response
        else np.asarray(
            baseline,
            dtype=float,
        )
    )

    grid_value = np.asarray(
        grid.value,
        dtype=float,
    )

    spill_value = np.asarray(
        spill.value,
        dtype=float,
    )

    charge_value = np.asarray(
        charge.value,
        dtype=float,
    )

    discharge_value = np.asarray(
        discharge.value,
        dtype=float,
    )

    soc_value = np.asarray(
        soc.value,
        dtype=float,
    )

    residual = (
        grid_value
        + solar
        + discharge_value
        - demand_value.sum(
            axis=0
        )
        - charge_value
        - spill_value
    )

    return {
        "status":
            problem.status,
        "demand":
            demand_value,
        "grid":
            grid_value,
        "spill":
            spill_value,
        "charge":
            charge_value,
        "discharge":
            discharge_value,
        "soc_kwh":
            soc_value,
        "soc_fraction":
            soc_value
            / capacity_kwh,
        "residual":
            residual,
        "objective":
            float(
                problem.value
            ),
        "window_peak":
            float(
                window_peak.value
            ),
        "capacity_kwh":
            float(
                capacity_kwh
            ),
    }


def run_month_dispatch(
    annual,
    start_hour,
    days,
    capacity_kwh,
    initial_soc_fraction,
    demand_response,
    force_month_end_target,
):
    month_hours = (
        days
        * HOURS_PER_DAY
    )

    end_hour = (
        start_hour
        + month_hours
    )

    outputs = []
    records = []

    current_soc_fraction = (
        initial_soc_fraction
    )

    house_columns = [
        f"House_{number:02d}_kW"
        for number in range(
            1,
            11,
        )
    ]

    for day_offset in range(
        days
    ):
        day_start = (
            start_hour
            + day_offset
            * HOURS_PER_DAY
        )

        day_end = (
            day_start
            + HOURS_PER_DAY
        )

        lookahead_end = min(
            day_start + 48,
            end_hour,
        )

        window = annual.iloc[
            day_start:
            lookahead_end
        ]

        baseline = (
            window[
                house_columns
            ]
            .to_numpy(
                dtype=float
            )
            .T
        )

        solar = window[
            "Shared_Solar_kW"
        ].to_numpy(
            dtype=float
        )

        price = window[
            "Price_per_kWh"
        ].to_numpy(
            dtype=float
        )

        final_day = (
            force_month_end_target
            and day_offset
            == days - 1
        )

        result = solve_day(
            baseline=baseline,
            solar=solar,
            price=price,
            initial_soc_fraction=
                current_soc_fraction,
            capacity_kwh=
                capacity_kwh,
            demand_response=
                demand_response,
            final_day_of_period=
                final_day,
        )

        implemented = slice(
            0,
            24,
        )

        month_source = annual.iloc[
            day_start:
            day_end
        ]

        output = pd.DataFrame({
            "Timestamp":
                month_source[
                    "Timestamp"
                ].values,
            "Hour_Index":
                month_source[
                    "Hour_Index"
                ].values,
            "Day_Index":
                month_source[
                    "Day_Index"
                ].values,
            "Baseline_Load_kW":
                baseline[
                    :,
                    implemented,
                ].sum(
                    axis=0
                ),
            "Optimized_Load_kW":
                result[
                    "demand"
                ][
                    :,
                    implemented,
                ].sum(
                    axis=0
                ),
            "Solar_kW":
                solar[
                    implemented
                ],
            "Price_per_kWh":
                price[
                    implemented
                ],
            "Grid_Import_kW":
                result[
                    "grid"
                ][
                    implemented
                ],
            "Battery_Charge_kW":
                result[
                    "charge"
                ][
                    implemented
                ],
            "Battery_Discharge_kW":
                result[
                    "discharge"
                ][
                    implemented
                ],
            "SOC_Start_kWh":
                result[
                    "soc_kwh"
                ][
                    :24
                ],
            "SOC_End_kWh":
                result[
                    "soc_kwh"
                ][
                    1:25
                ],
            "SOC_Start_Fraction":
                result[
                    "soc_fraction"
                ][
                    :24
                ],
            "SOC_End_Fraction":
                result[
                    "soc_fraction"
                ][
                    1:25
                ],
            "Available_Capacity_kWh":
                capacity_kwh,
            "Solar_Spill_kW":
                result[
                    "spill"
                ][
                    implemented
                ],
            "Balance_Residual_kW":
                result[
                    "residual"
                ][
                    implemented
                ],
        })

        outputs.append(
            output
        )

        current_soc_fraction = float(
            result[
                "soc_fraction"
            ][24]
        )

        records.append({
            "day_offset":
                day_offset,
            "status":
                result["status"],
            "capacity_kwh":
                capacity_kwh,
            "start_soc_fraction":
                float(
                    result[
                        "soc_fraction"
                    ][0]
                ),
            "end_soc_fraction":
                current_soc_fraction,
            "window_peak_kw":
                result[
                    "window_peak"
                ],
            "maximum_residual":
                float(
                    np.max(
                        np.abs(
                            result[
                                "residual"
                            ][
                                implemented
                            ]
                        )
                    )
                ),
        })

    return {
        "output":
            pd.concat(
                outputs,
                ignore_index=True,
            ),
        "day_records":
            pd.DataFrame(
                records
            ),
        "ending_soc_fraction":
            current_soc_fraction,
    }


def continue_blast_month(
    battery,
    month_output,
):
    before = battery_metrics(
        battery
    )

    start_soc = (
        month_output[
            "SOC_Start_Fraction"
        ].to_numpy(
            dtype=float
        )
    )

    final_soc = float(
        month_output[
            "SOC_End_Fraction"
        ].iloc[-1]
    )

    soc = np.append(
        start_soc,
        final_soc,
    )

    time_s = (
        np.arange(
            len(soc),
            dtype=float,
        )
        * 3600.0
    )

    # Use the annual Miami profile already
    # embedded in the community source branch.
    day_of_year_hour = (
        month_output[
            "Hour_Index"
        ].to_numpy(
            dtype=int
        )
    )

    # Reconstruct temperature from source profile
    # copied separately in future if needed.
    # For the pilot, use 25 C constant to test
    # feedback mechanics independently.
    temperature = np.full(
        len(soc),
        25.0,
    )

    input_frame = pd.DataFrame({
        "Time_s":
            time_s,
        "SOC":
            soc,
        "Temperature_C":
            temperature,
    })

    target_time = (
        before[
            "time_years"
        ]
        + (
            time_s[-1]
            / (
                365.0
                * 24.0
                * 3600.0
            )
        )
    )

    battery.simulate_battery_life(
        input_frame,
        threshold_time=
            target_time,
        is_constant_input=False,
    )

    after = battery_metrics(
        battery
    )

    return {
        "before":
            before,
        "after":
            after,
        "input_rows":
            len(input_frame),
        "input_efc":
            float(
                0.5
                * np.abs(
                    np.diff(soc)
                ).sum()
            ),
        "temperature_C":
            25.0,
    }


def summarize_month(
    output,
):
    return {
        "grid_energy_kwh":
            float(
                output[
                    "Grid_Import_kW"
                ].sum()
            ),
        "grid_bill":
            float(
                np.sum(
                    output[
                        "Price_per_kWh"
                    ]
                    * output[
                        "Grid_Import_kW"
                    ]
                )
            ),
        "peak_grid_import_kw":
            float(
                output[
                    "Grid_Import_kW"
                ].max()
            ),
        "solar_spill_kwh":
            float(
                output[
                    "Solar_Spill_kW"
                ].sum()
            ),
        "battery_throughput_kwh":
            float(
                0.5
                * np.sum(
                    output[
                        "Battery_Charge_kW"
                    ]
                    + output[
                        "Battery_Discharge_kW"
                    ]
                )
            ),
        "minimum_soc_fraction":
            float(
                output[
                    "SOC_End_Fraction"
                ].min()
            ),
        "maximum_soc_fraction":
            float(
                output[
                    "SOC_End_Fraction"
                ].max()
            ),
        "maximum_balance_residual":
            float(
                output[
                    "Balance_Residual_kW"
                ].abs().max()
            ),
    }


def run_experiment(
    annual,
    experiment_name,
    settings,
    months_to_run,
):
    battery = load_aged_battery()

    initial_battery = (
        battery_metrics(
            battery
        )
    )

    current_soc_fraction = (
        INITIAL_SOC_FRACTION
    )

    start_hour = 0

    monthly_records = []
    dispatch_outputs = []

    for month_index in range(
        months_to_run
    ):
        days = MONTH_DAY_COUNTS[
            month_index
        ]

        before = battery_metrics(
            battery
        )

        capacity_kwh = (
            capacity_from_q(
                before["q"],
                settings[
                    "capacity_treatment"
                ],
            )
        )

        force_month_end_target = (
            month_index
            == months_to_run - 1
        )

        dispatch = run_month_dispatch(
            annual=annual,
            start_hour=
                start_hour,
            days=days,
            capacity_kwh=
                capacity_kwh,
            initial_soc_fraction=
                current_soc_fraction,
            demand_response=
                settings[
                    "demand_response"
                ],
            force_month_end_target=
                force_month_end_target,
        )

        month_output = dispatch[
            "output"
        ]

        aging = continue_blast_month(
            battery,
            month_output,
        )

        metrics = summarize_month(
            month_output
        )

        current_soc_fraction = (
            dispatch[
                "ending_soc_fraction"
            ]
        )

        month_output[
            "Experiment"
        ] = experiment_name

        month_output[
            "Month_Index"
        ] = month_index + 1

        dispatch_outputs.append(
            month_output
        )

        monthly_records.append({
            "experiment":
                experiment_name,
            "month_index":
                month_index + 1,
            "days":
                days,
            "start_hour":
                start_hour,
            "capacity_treatment":
                settings[
                    "capacity_treatment"
                ],
            "demand_response":
                settings[
                    "demand_response"
                ],
            "begin_q":
                aging[
                    "before"
                ][
                    "q"
                ],
            "end_q":
                aging[
                    "after"
                ][
                    "q"
                ],
            "begin_r":
                aging[
                    "before"
                ][
                    "r"
                ],
            "end_r":
                aging[
                    "after"
                ][
                    "r"
                ],
            "begin_time_years":
                aging[
                    "before"
                ][
                    "time_years"
                ],
            "end_time_years":
                aging[
                    "after"
                ][
                    "time_years"
                ],
            "begin_efc":
                aging[
                    "before"
                ][
                    "efc"
                ],
            "end_efc":
                aging[
                    "after"
                ][
                    "efc"
                ],
            "blast_input_efc":
                aging[
                    "input_efc"
                ],
            "available_capacity_kwh":
                capacity_kwh,
            "ending_soc_fraction":
                current_soc_fraction,
            "month_end_target_forced":
                force_month_end_target,
            **metrics,
        })

        start_hour += (
            days
            * 24
        )

    all_output = pd.concat(
        dispatch_outputs,
        ignore_index=True,
    )

    monthly = pd.DataFrame(
        monthly_records
    )

    output_path = (
        RESULTS_DIR
        / f"{experiment_name}_"
          f"{months_to_run}month_dispatch.csv"
    )

    monthly_path = (
        RESULTS_DIR
        / f"{experiment_name}_"
          f"{months_to_run}month_summary.csv"
    )

    state_path = (
        STATE_DIR
        / f"{experiment_name}_"
          f"after_{months_to_run}month.pkl"
    )

    all_output.to_csv(
        output_path,
        index=False,
    )

    monthly.to_csv(
        monthly_path,
        index=False,
    )

    with state_path.open(
        "wb"
    ) as file:
        pickle.dump(
            battery,
            file,
        )

    return {
        "experiment":
            experiment_name,
        "dispatch_output":
            all_output,
        "monthly_summary":
            monthly,
        "battery":
            battery,
        "initial_battery":
            initial_battery,
        "final_battery":
            battery_metrics(
                battery
            ),
        "output_file":
            str(
                output_path.relative_to(
                    BASE_DIR
                )
            ),
        "monthly_file":
            str(
                monthly_path.relative_to(
                    BASE_DIR
                )
            ),
        "state_file":
            str(
                state_path.relative_to(
                    BASE_DIR
                )
            ),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--months",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--experiments",
        nargs="*",
        default=list(
            EXPERIMENTS.keys()
        ),
    )

    args = parser.parse_args()

    if not (
        1
        <= args.months
        <= 12
    ):
        raise ValueError(
            "months must be 1 to 12"
        )

    annual = pd.read_csv(
        INPUT_DIR
        / "annual_community_inputs.csv"
    )

    results = []
    errors = []

    for experiment_name in (
        args.experiments
    ):
        if experiment_name not in (
            EXPERIMENTS
        ):
            raise ValueError(
                experiment_name
            )

        print(
            f"Running {experiment_name}..."
        )

        try:
            result = run_experiment(
                annual,
                experiment_name,
                EXPERIMENTS[
                    experiment_name
                ],
                args.months,
            )

            results.append(
                result
            )

            print(
                "  final q = "
                f"{result['final_battery']['q']:.9f}"
            )

            final_capacity = (
                capacity_from_q(
                    result[
                        "final_battery"
                    ][
                        "q"
                    ],
                    EXPERIMENTS[
                        experiment_name
                    ][
                        "capacity_treatment"
                    ],
                )
            )

            print(
                "  final capacity = "
                f"{final_capacity:.6f}"
            )

        except Exception as error:
            errors.append({
                "experiment":
                    experiment_name,
                "error_type":
                    type(error).__name__,
                "message":
                    str(error),
                "traceback":
                    traceback.format_exc(),
            })

            print(
                "  FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    overall_rows = []

    for result in results:
        output = result[
            "dispatch_output"
        ]

        monthly = result[
            "monthly_summary"
        ]

        overall_rows.append({
            "experiment":
                result[
                    "experiment"
                ],
            "months":
                args.months,
            "hours":
                len(output),
            "grid_energy_kwh":
                float(
                    output[
                        "Grid_Import_kW"
                    ].sum()
                ),
            "grid_bill":
                float(
                    np.sum(
                        output[
                            "Price_per_kWh"
                        ]
                        * output[
                            "Grid_Import_kW"
                        ]
                    )
                ),
            "peak_grid_import_kw":
                float(
                    output[
                        "Grid_Import_kW"
                    ].max()
                ),
            "solar_spill_kwh":
                float(
                    output[
                        "Solar_Spill_kW"
                    ].sum()
                ),
            "battery_throughput_kwh":
                float(
                    0.5
                    * np.sum(
                        output[
                            "Battery_Charge_kW"
                        ]
                        + output[
                            "Battery_Discharge_kW"
                        ]
                    )
                ),
            "initial_q":
                result[
                    "initial_battery"
                ][
                    "q"
                ],
            "final_q":
                result[
                    "final_battery"
                ][
                    "q"
                ],
            "q_change":
                result[
                    "final_battery"
                ][
                    "q"
                ]
                - result[
                    "initial_battery"
                ][
                    "q"
                ],
            "initial_r":
                result[
                    "initial_battery"
                ][
                    "r"
                ],
            "final_r":
                result[
                    "final_battery"
                ][
                    "r"
                ],
            "initial_capacity_kwh":
                float(
                    monthly[
                        "available_capacity_kwh"
                    ].iloc[0]
                ),
            "last_month_capacity_kwh":
                float(
                    monthly[
                        "available_capacity_kwh"
                    ].iloc[-1]
                ),
            "final_mapped_capacity_kwh":
                capacity_from_q(
                    result[
                        "final_battery"
                    ][
                        "q"
                    ],
                    EXPERIMENTS[
                        result[
                            "experiment"
                        ]
                    ][
                        "capacity_treatment"
                    ],
                ),
            "output_file":
                result[
                    "output_file"
                ],
            "monthly_file":
                result[
                    "monthly_file"
                ],
            "state_file":
                result[
                    "state_file"
                ],
        })

    overall = pd.DataFrame(
        overall_rows
    )

    overall_path = (
        RESULTS_DIR
        / f"dynamic_feedback_"
          f"{args.months}month_overall.csv"
    )

    overall.to_csv(
        overall_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"dynamic_feedback_"
          f"{args.months}month_errors.json"
    )

    error_path.write_text(
        json.dumps(
            errors,
            indent=2,
        ),
        encoding="utf-8",
    )

    record = {
        "months":
            args.months,
        "experiments":
            args.experiments,
        "successful_experiments":
            len(results),
        "failed_experiments":
            len(errors),
        "overall_file":
            str(overall_path),
        "error_file":
            str(error_path),
    }

    record_path = (
        RESULTS_DIR
        / f"dynamic_feedback_"
          f"{args.months}month_run_record.json"
    )

    record_path.write_text(
        json.dumps(
            record,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nRUN RECORD")
    print(
        json.dumps(
            record,
            indent=2,
        )
    )

    print("\nOVERALL")
    print(
        overall.to_string(
            index=False
        )
    )

    if errors:
        raise RuntimeError(
            f"{len(errors)} experiment(s) failed. "
            f"See {error_path}."
        )


if __name__ == "__main__":
    main()
