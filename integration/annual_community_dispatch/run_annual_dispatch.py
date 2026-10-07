
import argparse
import json
import traceback
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
LOG_DIR = BASE_DIR / "logs"

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


CASES = {
    "baseline": {
        "demand_response": False,
        "battery": False,
    },
    "demand_response_only": {
        "demand_response": True,
        "battery": False,
    },
    "battery_only": {
        "demand_response": False,
        "battery": True,
    },
    "demand_response_plus_battery": {
        "demand_response": True,
        "battery": True,
    },
}


N_HOUSES = 10
HOURS_PER_DAY = 24

DR_LOWER = 0.85
DR_UPPER = 1.15
INCONVENIENCE_WEIGHT = 0.035

CAPACITY_KWH = 42.0
SOC_MIN_KWH = 0.10 * CAPACITY_KWH
SOC_MAX_KWH = 0.90 * CAPACITY_KWH
INITIAL_SOC_KWH = 0.50 * CAPACITY_KWH
TARGET_SOC_KWH = INITIAL_SOC_KWH

MAX_CHARGE_KW = 12.0
MAX_DISCHARGE_KW = 12.0
ROUND_TRIP_EFFICIENCY = 0.85
ETA_C = np.sqrt(
    ROUND_TRIP_EFFICIENCY
)
ETA_D = np.sqrt(
    ROUND_TRIP_EFFICIENCY
)

THROUGHPUT_COST = 0.015
TERMINAL_TARGET_WEIGHT = 0.10

# Optional rolling-window peak penalty.
# Units: dollars per kW of maximum grid import
# in each solved look-ahead window.
DEFAULT_PEAK_PENALTY_PER_KW = 0.0

BALANCE_TOLERANCE = 2e-5


def select_solver():
    installed = set(
        cp.installed_solvers()
    )

    if "CLARABEL" in installed:
        return "CLARABEL"

    if "SCS" in installed:
        return "SCS"

    raise RuntimeError(
        "Neither CLARABEL nor SCS "
        "is installed."
    )


def solve_window(
    baseline,
    solar,
    price,
    initial_soc,
    settings,
    implemented_hours,
    force_terminal_target,
    solver,
    peak_penalty_per_kw,
):
    horizon = len(price)

    if baseline.shape != (
        N_HOUSES,
        horizon,
    ):
        raise ValueError(
            "Baseline shape does not match "
            "the expected household/horizon shape."
        )

    constraints = []

    if settings[
        "demand_response"
    ]:
        demand = cp.Variable(
            (
                N_HOUSES,
                horizon,
            ),
            nonneg=True,
        )

        constraints.extend([
            demand
            >= DR_LOWER * baseline,
            demand
            <= DR_UPPER * baseline,
        ])

        # Preserve each household's energy
        # over the implemented first day.
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

        # If a second day is available,
        # preserve its energy separately.
        if horizon > implemented_hours:
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

    if settings["battery"]:
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
                soc[hour + 1]
                ==
                soc[hour]
                + ETA_C
                * charge[hour]
                - discharge[hour]
                / ETA_D
            )

        if force_terminal_target:
            constraints.append(
                soc[-1]
                == TARGET_SOC_KWH
            )
    else:
        charge = np.zeros(horizon)
        discharge = np.zeros(horizon)
        soc = np.full(
            horizon + 1,
            initial_soc,
        )

    aggregate_demand = cp.sum(
        demand,
        axis=0,
    ) if settings[
        "demand_response"
    ] else np.sum(
        baseline,
        axis=0,
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

    energy_cost = cp.sum(
        cp.multiply(
            price,
            grid,
        )
    )

    if settings[
        "demand_response"
    ]:
        normalized_deviation = (
            demand - baseline
        ) / (
            baseline + 0.25
        )

        inconvenience_cost = (
            INCONVENIENCE_WEIGHT
            * cp.sum_squares(
                normalized_deviation
            )
        )
    else:
        inconvenience_cost = 0.0

    if settings["battery"]:
        throughput = (
            0.5
            * cp.sum(
                charge + discharge
            )
        )

        degradation_proxy = (
            THROUGHPUT_COST
            * throughput
        )

        terminal_penalty = (
            0.0
            if force_terminal_target
            else TERMINAL_TARGET_WEIGHT
            * cp.square(
                soc[-1]
                - TARGET_SOC_KWH
            )
        )
    else:
        degradation_proxy = 0.0
        terminal_penalty = 0.0

    if peak_penalty_per_kw > 0:
        window_peak = cp.Variable(
            nonneg=True,
        )

        constraints.append(
            grid <= window_peak
        )

        peak_cost = (
            peak_penalty_per_kw
            * window_peak
        )
    else:
        window_peak = None
        peak_cost = 0.0

    objective = cp.Minimize(
        energy_cost
        + inconvenience_cost
        + degradation_proxy
        + terminal_penalty
        + peak_cost
    )

    problem = cp.Problem(
        objective,
        constraints,
    )

    solve_kwargs = {
        "solver": solver,
        "verbose": False,
    }

    if solver == "CLARABEL":
        solve_kwargs.update({
            "max_iter": 300,
        })

    problem.solve(
        **solve_kwargs
    )

    if problem.status not in {
        cp.OPTIMAL,
        cp.OPTIMAL_INACCURATE,
    }:
        raise RuntimeError(
            f"Optimization status: "
            f"{problem.status}"
        )

    if settings[
        "demand_response"
    ]:
        demand_value = np.asarray(
            demand.value,
            dtype=float,
        )
    else:
        demand_value = np.asarray(
            baseline,
            dtype=float,
        )

    grid_value = np.asarray(
        grid.value,
        dtype=float,
    )

    spill_value = np.asarray(
        spill.value,
        dtype=float,
    )

    if settings["battery"]:
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
    else:
        charge_value = np.zeros(
            horizon
        )

        discharge_value = np.zeros(
            horizon
        )

        soc_value = np.full(
            horizon + 1,
            initial_soc,
        )

    residual = (
        grid_value
        + solar
        + discharge_value
        - demand_value.sum(axis=0)
        - charge_value
        - spill_value
    )

    return {
        "status": problem.status,
        "objective":
            float(problem.value),
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
        "soc":
            soc_value,
        "residual":
            residual,
        "maximum_absolute_residual":
            float(
                np.max(
                    np.abs(residual)
                )
            ),
        "optimized_window_peak_kw":
            (
                float(window_peak.value)
                if window_peak is not None
                else float(
                    np.max(grid_value)
                )
            ),
    }


def run_case(
    annual,
    case_name,
    settings,
    days_to_run,
    solver,
    peak_penalty_per_kw,
):
    house_columns = [
        f"House_{number:02d}_kW"
        for number in range(
            1,
            N_HOUSES + 1,
        )
    ]

    total_hours = (
        days_to_run
        * HOURS_PER_DAY
    )

    outputs = []
    day_records = []
    errors = []

    current_soc = (
        INITIAL_SOC_KWH
    )

    for day in range(
        days_to_run
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
            start:lookahead_end
        ]

        horizon = len(window)

        implemented_hours = min(
            HOURS_PER_DAY,
            horizon,
        )

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

        force_terminal = bool(
            day
            == days_to_run - 1
            and settings["battery"]
        )

        try:
            result = solve_window(
                baseline=baseline,
                solar=solar,
                price=price,
                initial_soc=current_soc,
                settings=settings,
                implemented_hours=
                    implemented_hours,
                force_terminal_target=
                    force_terminal,
                solver=solver,
                peak_penalty_per_kw=
                    peak_penalty_per_kw,
            )

            implemented_slice = slice(
                0,
                implemented_hours,
            )

            implemented_demand = (
                result["demand"][
                    :,
                    implemented_slice,
                ]
            )

            implemented_soc_start = (
                result["soc"][
                    :implemented_hours
                ]
            )

            implemented_soc_end = (
                result["soc"][
                    1:
                    implemented_hours + 1
                ]
            )

            day_output = pd.DataFrame({
                "Case": case_name,
                "Timestamp":
                    annual.iloc[
                        start:
                        implemented_end
                    ][
                        "Timestamp"
                    ].values,
                "Hour_Index":
                    annual.iloc[
                        start:
                        implemented_end
                    ][
                        "Hour_Index"
                    ].values,
                "Day_Index": day,
                "Hour_of_Day":
                    annual.iloc[
                        start:
                        implemented_end
                    ][
                        "Hour_of_Day"
                    ].values,
                "Baseline_Load_kW":
                    baseline[
                        :,
                        implemented_slice,
                    ].sum(axis=0),
                "Optimized_Load_kW":
                    implemented_demand.sum(
                        axis=0
                    ),
                "Solar_kW":
                    solar[
                        implemented_slice
                    ],
                "Price_per_kWh":
                    price[
                        implemented_slice
                    ],
                "Grid_Import_kW":
                    result["grid"][
                        implemented_slice
                    ],
                "Battery_Charge_kW":
                    result["charge"][
                        implemented_slice
                    ],
                "Battery_Discharge_kW":
                    result["discharge"][
                        implemented_slice
                    ],
                "SOC_Start_kWh":
                    implemented_soc_start,
                "SOC_End_kWh":
                    implemented_soc_end,
                "Solar_Spill_kW":
                    result["spill"][
                        implemented_slice
                    ],
                "Balance_Residual_kW":
                    result["residual"][
                        implemented_slice
                    ],
            })

            for house_index, column in enumerate(
                house_columns
            ):
                day_output[
                    column.replace(
                        "_kW",
                        "_Optimized_kW",
                    )
                ] = (
                    implemented_demand[
                        house_index,
                        :,
                    ]
                )

            outputs.append(
                day_output
            )

            current_soc = float(
                result["soc"][
                    implemented_hours
                ]
            )

            day_records.append({
                "case": case_name,
                "day": day,
                "status":
                    result["status"],
                "objective":
                    result["objective"],
                "start_soc_kwh":
                    float(
                        result["soc"][0]
                    ),
                "end_soc_kwh":
                    current_soc,
                "maximum_absolute_residual":
                    float(
                        np.max(
                            np.abs(
                                result[
                                    "residual"
                                ][
                                    implemented_slice
                                ]
                            )
                        )
                    ),
                "optimized_window_peak_kw":
                    result[
                        "optimized_window_peak_kw"
                    ],
            })

        except Exception as error:
            errors.append({
                "case": case_name,
                "day": day,
                "error_type":
                    type(error).__name__,
                "message":
                    str(error),
                "traceback":
                    traceback.format_exc(),
            })

            break

    if outputs:
        annual_output = pd.concat(
            outputs,
            ignore_index=True,
        )
    else:
        annual_output = (
            pd.DataFrame()
        )

    return {
        "output": annual_output,
        "day_records":
            pd.DataFrame(
                day_records
            ),
        "errors": errors,
    }


def summarize_case(
    output,
    case_name,
):
    if output.empty:
        raise ValueError(
            f"{case_name}: empty output"
        )

    bill = float(
        np.sum(
            output[
                "Price_per_kWh"
            ]
            * output[
                "Grid_Import_kW"
            ]
        )
    )

    throughput = float(
        0.5
        * np.sum(
            output[
                "Battery_Charge_kW"
            ]
            + output[
                "Battery_Discharge_kW"
            ]
        )
    )

    return {
        "case": case_name,
        "hours":
            int(len(output)),
        "grid_energy_kwh":
            float(
                output[
                    "Grid_Import_kW"
                ].sum()
            ),
        "grid_energy_bill":
            bill,
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
            throughput,
        "battery_charge_kwh":
            float(
                output[
                    "Battery_Charge_kW"
                ].sum()
            ),
        "battery_discharge_kwh":
            float(
                output[
                    "Battery_Discharge_kW"
                ].sum()
            ),
        "minimum_soc_kwh":
            float(
                output[
                    "SOC_End_kWh"
                ].min()
            ),
        "maximum_soc_kwh":
            float(
                output[
                    "SOC_End_kWh"
                ].max()
            ),
        "initial_soc_kwh":
            float(
                output[
                    "SOC_Start_kWh"
                ].iloc[0]
            ),
        "final_soc_kwh":
            float(
                output[
                    "SOC_End_kWh"
                ].iloc[-1]
            ),
        "maximum_absolute_balance_residual":
            float(
                output[
                    "Balance_Residual_kW"
                ].abs().max()
            ),
        "maximum_load_shift_kw":
            float(
                np.max(
                    np.abs(
                        output[
                            "Optimized_Load_kW"
                        ]
                        - output[
                            "Baseline_Load_kW"
                        ]
                    )
                )
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
        "--cases",
        nargs="*",
        default=list(
            CASES.keys()
        ),
    )

    parser.add_argument(
        "--peak-penalty-per-kw",
        type=float,
        default=DEFAULT_PEAK_PENALTY_PER_KW,
    )

    args = parser.parse_args()

    annual = pd.read_csv(
        DATA_DIR
        / "annual_community_inputs.csv"
    )

    total_hours = (
        args.days
        * HOURS_PER_DAY
    )

    annual = annual.iloc[
        :total_hours
    ].copy()

    solver = select_solver()

    print("Solver:", solver)
    print("Days:", args.days)
    print("Cases:", args.cases)
    print(
        "Peak penalty ($/kW-window):",
        args.peak_penalty_per_kw,
    )

    summaries = []
    all_errors = []

    for case_name in args.cases:
        if case_name not in CASES:
            raise ValueError(
                f"Unknown case: "
                f"{case_name}"
            )

        print(
            f"\nRunning {case_name}..."
        )

        case_result = run_case(
            annual=annual,
            case_name=case_name,
            settings=CASES[
                case_name
            ],
            days_to_run=
                args.days,
            solver=solver,
            peak_penalty_per_kw=
                args.peak_penalty_per_kw,
        )

        output = case_result[
            "output"
        ]

        day_records = case_result[
            "day_records"
        ]

        errors = case_result[
            "errors"
        ]

        all_errors.extend(errors)

        output_path = (
            RESULTS_DIR
            / f"{case_name}_"
              f"{args.days}day_output.csv"
        )

        records_path = (
            RESULTS_DIR
            / f"{case_name}_"
              f"{args.days}day_day_records.csv"
        )

        output.to_csv(
            output_path,
            index=False,
        )

        day_records.to_csv(
            records_path,
            index=False,
        )

        if not output.empty:
            summary = summarize_case(
                output,
                case_name,
            )

            summary[
                "successful_days"
            ] = len(
                day_records
            )

            summary[
                "failed_days"
            ] = len(errors)

            summaries.append(
                summary
            )

            print(
                json.dumps(
                    summary,
                    indent=2,
                )
            )

        if errors:
            print(
                "Errors:",
                json.dumps(
                    errors,
                    indent=2,
                )
            )

    summary_frame = pd.DataFrame(
        summaries
    )

    summary_path = (
        RESULTS_DIR
        / f"dispatch_summary_"
          f"{args.days}day.csv"
    )

    summary_frame.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"dispatch_errors_"
          f"{args.days}day.json"
    )

    error_path.write_text(
        json.dumps(
            all_errors,
            indent=2,
        ),
        encoding="utf-8",
    )

    run_record = {
        "days":
            args.days,
        "solver":
            solver,
        "peak_penalty_per_kw":
            args.peak_penalty_per_kw,
        "requested_cases":
            args.cases,
        "successful_cases":
            len(summaries),
        "failed_case_days":
            len(all_errors),
        "summary_file":
            str(summary_path),
        "error_file":
            str(error_path),
    }

    record_path = (
        RESULTS_DIR
        / f"run_record_"
          f"{args.days}day.json"
    )

    record_path.write_text(
        json.dumps(
            run_record,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nRUN RECORD")
    print(
        json.dumps(
            run_record,
            indent=2,
        )
    )

    print("\nSUMMARY")
    print(
        summary_frame.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
