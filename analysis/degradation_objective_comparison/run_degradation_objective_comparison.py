
import argparse
import copy
import json
import pickle
import time
import traceback
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd

if not hasattr(
    np,
    "trapz",
):
    np.trapz = (
        np.trapezoid
    )

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "inputs"
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

CAPACITY_KWH = 42.0
SOC_MIN_KWH = 4.2
SOC_MAX_KWH = 37.8
INITIAL_SOC_KWH = 21.0

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

PEAK_PENALTY_PER_KW = 0.50
TERMINAL_TARGET_WEIGHT = 0.10

ENTRY_Q = 0.80
ENTRY_CAPACITY_KWH = 42.0

CASES = {
    "battery_only": {
        "demand_response":
            False,
    },
    "dr_plus_battery": {
        "demand_response":
            True,
    },
}


def load_aged_battery():
    path = (
        INPUT_DIR
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


def solve_window(
    baseline,
    solar,
    price,
    initial_soc,
    demand_response,
    implemented_hours,
    final_window,
    c_deg,
):
    horizon = len(
        price
    )

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
                    :implemented_hours,
                ],
                axis=1,
            )
            ==
            np.sum(
                baseline[
                    :,
                    :implemented_hours,
                ],
                axis=1,
            )
        )

        if horizon > (
            implemented_hours
        ):
            constraints.append(
                cp.sum(
                    demand[
                        :,
                        implemented_hours:,
                    ],
                    axis=1,
                )
                ==
                np.sum(
                    baseline[
                        :,
                        implemented_hours:,
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
        horizon + 1
    )

    constraints.extend([
        charge
        <= MAX_CHARGE_KW,

        discharge
        <= MAX_DISCHARGE_KW,

        soc[0]
        == initial_soc,

        soc
        >= SOC_MIN_KWH,

        soc
        <= SOC_MAX_KWH,
    ])

    for hour in range(
        horizon
    ):
        constraints.append(
            soc[
                hour + 1
            ]
            ==
            soc[hour]
            + ETA_C
            * charge[hour]
            - discharge[hour]
            / ETA_D
        )

    if final_window:
        constraints.append(
            soc[-1]
            == INITIAL_SOC_KWH
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
        nonneg=True
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
        inconvenience_cost = (
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
        inconvenience_cost = 0.0

    throughput = (
        0.5
        * cp.sum(
            charge
            + discharge
        )
    )

    degradation_proxy = (
        c_deg
        * throughput
    )

    peak_cost = (
        PEAK_PENALTY_PER_KW
        * window_peak
    )

    if final_window:
        terminal_penalty = 0.0
    else:
        terminal_penalty = (
            TERMINAL_TARGET_WEIGHT
            * cp.square(
                soc[-1]
                - INITIAL_SOC_KWH
            )
        )

    problem = cp.Problem(
        cp.Minimize(
            energy_cost
            + inconvenience_cost
            + degradation_proxy
            + peak_cost
            + terminal_penalty
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

    return {
        "status":
            problem.status,

        "objective":
            float(
                problem.value
            ),

        "demand":
            demand_value,

        "grid":
            np.asarray(
                grid.value,
                dtype=float,
            ),

        "spill":
            np.asarray(
                spill.value,
                dtype=float,
            ),

        "charge":
            np.asarray(
                charge.value,
                dtype=float,
            ),

        "discharge":
            np.asarray(
                discharge.value,
                dtype=float,
            ),

        "soc":
            np.asarray(
                soc.value,
                dtype=float,
            ),

        "window_peak":
            float(
                window_peak.value
            ),
    }


def run_dispatch(
    annual,
    case_name,
    settings,
    days,
    c_deg,
):
    total_hours = (
        days
        * HOURS_PER_DAY
    )

    annual = annual.iloc[
        :total_hours
    ].copy()

    house_columns = [
        f"House_{number:02d}_kW"
        for number in range(
            1,
            11,
        )
    ]

    outputs = []
    day_records = []

    current_soc = (
        INITIAL_SOC_KWH
    )

    for day in range(
        days
    ):
        start = (
            day
            * HOURS_PER_DAY
        )

        implemented_end = (
            start
            + HOURS_PER_DAY
        )

        lookahead_end = min(
            start + 48,
            total_hours,
        )

        window = annual.iloc[
            start:
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

        final_window = (
            day
            == days - 1
        )

        result = solve_window(
            baseline=baseline,
            solar=solar,
            price=price,
            initial_soc=current_soc,
            demand_response=
                settings[
                    "demand_response"
                ],
            implemented_hours=24,
            final_window=
                final_window,
            c_deg=c_deg,
        )

        implemented = slice(
            0,
            24,
        )

        source = annual.iloc[
            start:
            implemented_end
        ]

        optimized_demand = (
            result[
                "demand"
            ][
                :,
                implemented,
            ]
        )

        residual = (
            result[
                "grid"
            ][
                implemented
            ]
            + solar[
                implemented
            ]
            + result[
                "discharge"
            ][
                implemented
            ]
            - optimized_demand.sum(
                axis=0
            )
            - result[
                "charge"
            ][
                implemented
            ]
            - result[
                "spill"
            ][
                implemented
            ]
        )

        frame = pd.DataFrame({
            "Case":
                case_name,

            "c_deg":
                c_deg,

            "Timestamp":
                source[
                    "Timestamp"
                ].values,

            "Hour_Index":
                source[
                    "Hour_Index"
                ].values,

            "Day_Index":
                source[
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
                optimized_demand.sum(
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
                    "soc"
                ][
                    :24
                ],

            "SOC_End_kWh":
                result[
                    "soc"
                ][
                    1:25
                ],

            "Solar_Spill_kW":
                result[
                    "spill"
                ][
                    implemented
                ],

            "Balance_Residual_kW":
                residual,
        })

        outputs.append(
            frame
        )

        current_soc = float(
            result[
                "soc"
            ][24]
        )

        day_records.append({
            "day":
                day,

            "status":
                result[
                    "status"
                ],

            "objective":
                result[
                    "objective"
                ],

            "start_soc_kwh":
                float(
                    result[
                        "soc"
                    ][0]
                ),

            "end_soc_kwh":
                current_soc,

            "window_peak_kw":
                result[
                    "window_peak"
                ],
        })

    output = pd.concat(
        outputs,
        ignore_index=True,
    )

    records = pd.DataFrame(
        day_records
    )

    return output, records


def make_blast_input(
    dispatch,
):
    soc_start = (
        dispatch[
            "SOC_Start_kWh"
        ].to_numpy(
            dtype=float
        )
        / CAPACITY_KWH
    )

    final_soc = float(
        dispatch[
            "SOC_End_kWh"
        ].iloc[-1]
        / CAPACITY_KWH
    )

    soc = np.append(
        soc_start,
        final_soc,
    )

    time_s = (
        np.arange(
            len(soc),
            dtype=float,
        )
        * 3600.0
    )

    temperature = np.full(
        len(soc),
        25.0,
    )

    return pd.DataFrame({
        "Time_s":
            time_s,

        "SOC":
            soc,

        "Temperature_C":
            temperature,
    })


def evaluate_blast(
    blast_input,
):
    battery = (
        load_aged_battery()
    )

    before = battery_metrics(
        battery
    )

    duration_years = (
        blast_input[
            "Time_s"
        ].iloc[-1]
        / (
            365.0
            * 24.0
            * 3600.0
        )
    )

    target_years = (
        before[
            "time_years"
        ]
        + duration_years
    )

    battery.simulate_battery_life(
        blast_input,
        threshold_time=
            target_years,
        is_constant_input=False,
    )

    after = battery_metrics(
        battery
    )

    return (
        battery,
        before,
        after,
    )


def summarize(
    case_name,
    c_deg,
    dispatch,
    day_records,
    before,
    after,
):
    throughput = float(
        0.5
        * np.sum(
            dispatch[
                "Battery_Charge_kW"
            ]
            + dispatch[
                "Battery_Discharge_kW"
            ]
        )
    )

    bill = float(
        np.sum(
            dispatch[
                "Price_per_kWh"
            ]
            * dispatch[
                "Grid_Import_kW"
            ]
        )
    )

    input_soc = (
        dispatch[
            "SOC_Start_kWh"
        ]
        / CAPACITY_KWH
    )

    input_efc = float(
        0.5
        * np.abs(
            np.diff(
                np.append(
                    input_soc.to_numpy(),
                    dispatch[
                        "SOC_End_kWh"
                    ].iloc[-1]
                    / CAPACITY_KWH,
                )
            )
        ).sum()
    )

    remaining_capacity = (
        ENTRY_CAPACITY_KWH
        * after["q"]
        / ENTRY_Q
    )

    return {
        "case":
            case_name,

        "c_deg":
            c_deg,

        "hours":
            len(dispatch),

        "successful_days":
            len(day_records),

        "grid_energy_kwh":
            float(
                dispatch[
                    "Grid_Import_kW"
                ].sum()
            ),

        "grid_bill":
            bill,

        "peak_grid_import_kw":
            float(
                dispatch[
                    "Grid_Import_kW"
                ].max()
            ),

        "solar_spill_kwh":
            float(
                dispatch[
                    "Solar_Spill_kW"
                ].sum()
            ),

        "battery_throughput_kwh":
            throughput,

        "charge_energy_kwh":
            float(
                dispatch[
                    "Battery_Charge_kW"
                ].sum()
            ),

        "discharge_energy_kwh":
            float(
                dispatch[
                    "Battery_Discharge_kW"
                ].sum()
            ),

        "dispatch_objective_sum":
            float(
                day_records[
                    "objective"
                ].sum()
            ),

        "input_mean_soc":
            float(
                input_soc.mean()
            ),

        "input_annual_efc":
            input_efc,

        "initial_q":
            before["q"],

        "final_q":
            after["q"],

        "q_change":
            after["q"]
            - before["q"],

        "initial_r":
            before["r"],

        "final_r":
            after["r"],

        "final_remaining_capacity_kwh":
            remaining_capacity,

        "maximum_balance_residual":
            float(
                dispatch[
                    "Balance_Residual_kW"
                ].abs().max()
            ),

        "minimum_soc_kwh":
            float(
                dispatch[
                    "SOC_End_kWh"
                ].min()
            ),

        "maximum_soc_kwh":
            float(
                dispatch[
                    "SOC_End_kWh"
                ].max()
            ),

        "final_soc_kwh":
            float(
                dispatch[
                    "SOC_End_kWh"
                ].iloc[-1]
            ),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--days",
        type=int,
        default=7,
    )

    parser.add_argument(
        "--coefficients",
        nargs="*",
        type=float,
        default=[
            0.0,
            0.015,
        ],
    )

    parser.add_argument(
        "--cases",
        nargs="*",
        default=list(
            CASES.keys()
        ),
    )

    args = parser.parse_args()

    annual = pd.read_csv(
        INPUT_DIR
        / "annual_community_inputs.csv"
    )

    results = []
    errors = []

    for case_name in args.cases:
        for c_deg in (
            args.coefficients
        ):
            label = (
                f"{case_name}_"
                f"cdeg_"
                f"{str(c_deg).replace('.', 'p')}"
            )

            print(
                f"Running {label}..."
            )

            try:
                start_time = time.time()

                dispatch, day_records = (
                    run_dispatch(
                        annual=annual,
                        case_name=case_name,
                        settings=
                            CASES[
                                case_name
                            ],
                        days=args.days,
                        c_deg=c_deg,
                    )
                )

                blast_input = (
                    make_blast_input(
                        dispatch
                    )
                )

                battery, before, after = (
                    evaluate_blast(
                        blast_input
                    )
                )

                summary = summarize(
                    case_name,
                    c_deg,
                    dispatch,
                    day_records,
                    before,
                    after,
                )

                summary[
                    "execution_seconds"
                ] = (
                    time.time()
                    - start_time
                )

                summary[
                    "experiment_label"
                ] = label

                results.append(
                    summary
                )

                dispatch.to_csv(
                    RESULTS_DIR
                    / f"{label}_"
                      f"{args.days}day_"
                      "dispatch.csv",
                    index=False,
                )

                day_records.to_csv(
                    RESULTS_DIR
                    / f"{label}_"
                      f"{args.days}day_"
                      "day_records.csv",
                    index=False,
                )

                blast_input.to_csv(
                    RESULTS_DIR
                    / f"{label}_"
                      f"{args.days}day_"
                      "blast_input.csv",
                    index=False,
                )

                with (
                    RESULTS_DIR
                    / f"{label}_"
                      f"{args.days}day_"
                      "final_battery.pkl"
                ).open(
                    "wb"
                ) as file:
                    pickle.dump(
                        battery,
                        file,
                    )

                print(
                    "  bill = "
                    f"{summary['grid_bill']:.4f}"
                )

                print(
                    "  throughput = "
                    f"{summary['battery_throughput_kwh']:.4f}"
                )

                print(
                    "  final q = "
                    f"{summary['final_q']:.9f}"
                )

            except Exception as error:
                errors.append({
                    "case":
                        case_name,

                    "c_deg":
                        c_deg,

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

    summary_frame = pd.DataFrame(
        results
    )

    summary_path = (
        RESULTS_DIR
        / f"degradation_objective_"
          f"{args.days}day_summary.csv"
    )

    summary_frame.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"degradation_objective_"
          f"{args.days}day_errors.json"
    )

    error_path.write_text(
        json.dumps(
            errors,
            indent=2,
        ),
        encoding="utf-8",
    )

    record = {
        "days":
            args.days,

        "cases":
            args.cases,

        "coefficients":
            args.coefficients,

        "successful_runs":
            len(results),

        "failed_runs":
            len(errors),

        "summary_file":
            str(
                summary_path
            ),

        "error_file":
            str(
                error_path
            ),
    }

    record_path = (
        RESULTS_DIR
        / f"degradation_objective_"
          f"{args.days}day_"
          "run_record.json"
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

    print("\nSUMMARY")
    print(
        summary_frame.to_string(
            index=False
        )
    )

    if errors:
        raise RuntimeError(
            f"{len(errors)} run(s) failed."
        )


if __name__ == "__main__":
    main()
