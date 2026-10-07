
import argparse
import json
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from blast.models import (
    Lfp_Gr_250AhPrismatic,
    Nmc111_Gr_Kokam75Ah_Battery,
    Nca_Gr_Panasonic3Ah_Battery,
    Nmc622_Gr_DENSO50Ah_Battery,
)


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parents[1]
PROFILE_DIR = (
    REPO_DIR
    / "examples"
    / "application profiles"
)
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


APPLICATIONS = {
    "commercial_peak_shaving":
        "Commercial peak shaving.csv",
    "residential_pvbess_CA_mild":
        "Residential PV-BESS (CA, mild).csv",
    "telecom_backup_power":
        "Telecom backup power and peak shaving.csv",
    "ev_support_rental_car_depot":
        "EV charging support rental car depot.csv",
    "commercial_pvbess_NREL":
        "Commercial PV-BESS (NREL).csv",
    "frequency_containment_reserve":
        "Frequency containment reserve.csv",
    "residential_pvbess_Germany_aggressive":
        "Residential PV-BESS (Germany, aggressive).csv",
    "ev_support_corner_charging_station":
        "EV charging support corner charging station.csv",
}


BATTERIES = {
    "NMC111-Gr":
        Nmc111_Gr_Kokam75Ah_Battery,
    "LFP-Gr":
        Lfp_Gr_250AhPrismatic,
    "NCA-Gr":
        Nca_Gr_Panasonic3Ah_Battery,
    "NMC622-Gr":
        Nmc622_Gr_DENSO50Ah_Battery,
}


COLORS = {
    "commercial_peak_shaving":
        "#1f77b4",
    "residential_pvbess_CA_mild":
        "#ff7f0e",
    "telecom_backup_power":
        "#2ca02c",
    "ev_support_rental_car_depot":
        "#d62728",
    "commercial_pvbess_NREL":
        "#9467bd",
    "frequency_containment_reserve":
        "#8c564b",
    "residential_pvbess_Germany_aggressive":
        "#e377c2",
    "ev_support_corner_charging_station":
        "#7f7f7f",
}


def load_profile(
    filename,
    temperature_mode,
):
    path = PROFILE_DIR / filename

    frame = pd.read_csv(path)

    required = {
        "Time_s",
        "SOC",
        "Temperature_C",
    }

    if not required.issubset(
        frame.columns
    ):
        raise ValueError(
            f"{filename}: missing required columns"
        )

    input_frame = frame[
        [
            "Time_s",
            "SOC",
            "Temperature_C",
        ]
    ].copy()

    if temperature_mode == "override_30C":
        input_frame[
            "Temperature_C"
        ] = 30.0

    return input_frame


def input_statistics(
    frame,
):
    time_s = frame[
        "Time_s"
    ].to_numpy(
        dtype=float
    )

    soc = frame[
        "SOC"
    ].to_numpy(
        dtype=float
    )

    temperature = frame[
        "Temperature_C"
    ].to_numpy(
        dtype=float
    )

    duration_days = (
        time_s[-1]
        - time_s[0]
    ) / 86400.0

    profile_efc = (
        0.5
        * np.abs(
            np.diff(soc)
        ).sum()
    )

    annualized_efc = (
        profile_efc
        * 365.0
        / duration_days
    )

    return {
        "input_rows":
            int(len(frame)),
        "input_duration_days":
            float(duration_days),
        "input_soc_min":
            float(soc.min()),
        "input_soc_mean":
            float(soc.mean()),
        "input_soc_median":
            float(
                np.median(soc)
            ),
        "input_soc_max":
            float(soc.max()),
        "input_profile_efc":
            float(profile_efc),
        "input_annualized_efc":
            float(annualized_efc),
        "input_temperature_min_C":
            float(temperature.min()),
        "input_temperature_mean_C":
            float(temperature.mean()),
        "input_temperature_max_C":
            float(temperature.max()),
    }


def compact_trajectory(
    time_years,
    efc,
    q,
):
    # Preserve first, last, and approximately
    # monthly points to keep evidence compact.
    target_step_years = (
        30.0 / 365.0
    )

    selected = [0]

    last_time = float(
        time_years[0]
    )

    for index in range(
        1,
        len(time_years) - 1,
    ):
        current = float(
            time_years[index]
        )

        if (
            current - last_time
            >= target_step_years
        ):
            selected.append(
                index
            )
            last_time = current

    if len(time_years) > 1:
        selected.append(
            len(time_years) - 1
        )

    selected = sorted(
        set(selected)
    )

    return pd.DataFrame({
        "Time_years":
            time_years[selected],
        "EFC":
            efc[selected],
        "q":
            q[selected],
    })


def run_case(
    battery_label,
    battery_class,
    application,
    filename,
    temperature_mode,
    threshold_capacity,
    threshold_time,
):
    input_frame = load_profile(
        filename,
        temperature_mode,
    )

    stats = input_statistics(
        input_frame
    )

    battery = battery_class()

    start = time.time()

    battery.simulate_battery_life(
        input_frame,
        threshold_capacity=
            threshold_capacity,
        threshold_time=
            threshold_time,
        is_constant_input=False,
    )

    elapsed = (
        time.time() - start
    )

    time_days = np.atleast_1d(
        np.asarray(
            battery.stressors[
                "t_days"
            ]
        ).squeeze()
    )

    time_years = (
        time_days / 365.0
    )

    efc = np.atleast_1d(
        np.asarray(
            battery.stressors[
                "efc"
            ]
        ).squeeze()
    )

    q = np.atleast_1d(
        np.asarray(
            battery.outputs[
                "q"
            ]
        ).squeeze()
    )

    dod = np.atleast_1d(
        np.asarray(
            battery.stressors[
                "dod"
            ]
        ).squeeze()
    )

    stress_soc = np.atleast_1d(
        np.asarray(
            battery.stressors[
                "soc"
            ]
        ).squeeze()
    )

    stress_temperature_C = (
        np.atleast_1d(
            np.asarray(
                battery.stressors[
                    "TdegK"
                ]
            ).squeeze()
        )
        - 273.15
    )

    if not (
        len(time_years)
        == len(efc)
        == len(q)
    ):
        raise ValueError(
            "Output lengths differ."
        )

    trajectory = compact_trajectory(
        time_years,
        efc,
        q,
    )

    safe_battery = (
        battery_label
        .replace("-", "_")
        .replace(" ", "_")
    )

    output_path = (
        RESULTS_DIR
        / f"{temperature_mode}_"
          f"{safe_battery}_"
          f"{application}_trajectory.csv"
    )

    trajectory.to_csv(
        output_path,
        index=False,
    )

    threshold_reached = bool(
        q[-1]
        <= threshold_capacity
        + 1e-6
    )

    summary = {
        "temperature_mode":
            temperature_mode,
        "battery_label":
            battery_label,
        "battery_class":
            battery_class.__name__,
        "application":
            application,
        "source_file":
            filename,
        **stats,
        "threshold_capacity":
            threshold_capacity,
        "threshold_time_years":
            threshold_time,
        "threshold_capacity_reached":
            threshold_reached,
        "final_q":
            float(q[-1]),
        "final_time_years":
            float(
                time_years[-1]
            ),
        "final_efc":
            float(efc[-1]),
        "output_points":
            int(len(q)),
        "mean_model_soc":
            float(
                np.nanmean(
                    stress_soc
                )
            ),
        "mean_model_dod":
            float(
                np.nanmean(
                    dod
                )
            ),
        "rms_model_dod":
            float(
                np.sqrt(
                    np.nanmean(
                        dod ** 2
                    )
                )
            ),
        "mean_model_temperature_C":
            float(
                np.nanmean(
                    stress_temperature_C
                )
            ),
        "execution_seconds":
            float(elapsed),
        "trajectory_file":
            str(
                output_path.relative_to(
                    BASE_DIR
                )
            ),
        "_time_years":
            time_years,
        "_efc":
            efc,
        "_q":
            q,
    }

    return summary


def make_figures(
    results,
    temperature_mode,
):
    fig_time, axes_time = plt.subplots(
        1,
        4,
        figsize=(16, 4.5),
        sharey=True,
    )

    fig_efc, axes_efc = plt.subplots(
        1,
        4,
        figsize=(16, 4.5),
        sharey=True,
    )

    battery_order = list(
        BATTERIES.keys()
    )

    for axis_index, battery_label in enumerate(
        battery_order
    ):
        axis_time = axes_time[
            axis_index
        ]

        axis_efc = axes_efc[
            axis_index
        ]

        subset = [
            item
            for item in results
            if item[
                "battery_label"
            ]
            == battery_label
        ]

        for item in subset:
            application = item[
                "application"
            ]

            axis_time.plot(
                item[
                    "_time_years"
                ],
                item["_q"],
                label=application,
                color=COLORS[
                    application
                ],
                linewidth=1.4,
            )

            axis_efc.plot(
                item["_efc"],
                item["_q"],
                label=application,
                color=COLORS[
                    application
                ],
                linewidth=1.4,
            )

        axis_time.set_title(
            battery_label
        )

        axis_time.set_xlabel(
            "Time (years)"
        )

        axis_time.set_ylim(
            0.69,
            1.01,
        )

        axis_time.set_xlim(
            0,
            30,
        )

        axis_time.grid(
            alpha=0.18
        )

        axis_efc.set_title(
            battery_label
        )

        axis_efc.set_xlabel(
            "Equivalent full cycles"
        )

        axis_efc.set_ylim(
            0.69,
            1.01,
        )

        axis_efc.grid(
            alpha=0.18
        )

        if axis_index == 0:
            axis_time.set_ylabel(
                "Relative discharge capacity, q"
            )

            axis_efc.set_ylabel(
                "Relative discharge capacity, q"
            )

        # Place the application legend on the
        # rightmost populated battery panel.
        populated_indices = [
            index
            for index, label
            in enumerate(battery_order)
            if any(
                item["battery_label"] == label
                for item in results
            )
        ]

        legend_index = (
            max(populated_indices)
            if populated_indices
            else None
        )

        if (
            legend_index is not None
            and axis_index == legend_index
            and subset
        ):
            axis_time.legend(
                loc="upper left",
                bbox_to_anchor=(
                    1.02,
                    1.0,
                ),
                fontsize=7,
                frameon=False,
            )

            axis_efc.legend(
                loc="upper left",
                bbox_to_anchor=(
                    1.02,
                    1.0,
                ),
                fontsize=7,
                frameon=False,
            )

    fig_time.suptitle(
        f"Stationary Storage Reproduction: "
        f"q vs Time — {temperature_mode}",
        fontsize=15,
        fontweight="bold",
    )

    fig_time.tight_layout()

    time_path = (
        FIGURE_DIR
        / f"{temperature_mode}_q_vs_time.png"
    )

    fig_time.savefig(
        time_path,
        dpi=220,
        bbox_inches="tight",
    )

    plt.close(
        fig_time
    )

    fig_efc.suptitle(
        f"Stationary Storage Reproduction: "
        f"q vs EFC — {temperature_mode}",
        fontsize=15,
        fontweight="bold",
    )

    fig_efc.tight_layout()

    efc_path = (
        FIGURE_DIR
        / f"{temperature_mode}_q_vs_efc.png"
    )

    fig_efc.savefig(
        efc_path,
        dpi=220,
        bbox_inches="tight",
    )

    plt.close(
        fig_efc
    )

    return (
        time_path,
        efc_path,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--temperature-mode",
        choices=[
            "literal_source_20C",
            "override_30C",
        ],
        default="literal_source_20C",
    )

    parser.add_argument(
        "--threshold-capacity",
        type=float,
        default=0.70,
    )

    parser.add_argument(
        "--threshold-time",
        type=float,
        default=30.0,
    )

    parser.add_argument(
        "--smoke",
        action="store_true",
    )

    args = parser.parse_args()

    if args.smoke:
        selected_batteries = {
            "NMC111-Gr":
                Nmc111_Gr_Kokam75Ah_Battery,
        }

        selected_applications = {
            "residential_pvbess_CA_mild":
                APPLICATIONS[
                    "residential_pvbess_CA_mild"
                ],
        }

        threshold_time = 2.0
    else:
        selected_batteries = BATTERIES
        selected_applications = APPLICATIONS
        threshold_time = (
            args.threshold_time
        )

    results = []
    errors = []

    for battery_label, battery_class in (
        selected_batteries.items()
    ):
        for application, filename in (
            selected_applications.items()
        ):
            print(
                f"Running {battery_label} | "
                f"{application} | "
                f"{args.temperature_mode}..."
            )

            try:
                result = run_case(
                    battery_label,
                    battery_class,
                    application,
                    filename,
                    args.temperature_mode,
                    args.threshold_capacity,
                    threshold_time,
                )

                results.append(
                    result
                )

                print(
                    "  final q = "
                    f"{result['final_q']:.6f}"
                )

                print(
                    "  final years = "
                    f"{result['final_time_years']:.3f}"
                )

            except Exception as error:
                errors.append({
                    "battery_label":
                        battery_label,
                    "application":
                        application,
                    "temperature_mode":
                        args.temperature_mode,
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

    summary_rows = []

    for result in results:
        summary_rows.append({
            key: value
            for key, value
            in result.items()
            if not key.startswith("_")
        })

    summary = pd.DataFrame(
        summary_rows
    )

    suffix = (
        "smoke"
        if args.smoke
        else "full"
    )

    summary_path = (
        RESULTS_DIR
        / f"{args.temperature_mode}_"
          f"{suffix}_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"{args.temperature_mode}_"
          f"{suffix}_errors.json"
    )

    error_path.write_text(
        json.dumps(
            errors,
            indent=2,
        ),
        encoding="utf-8",
    )

    if results:
        time_path, efc_path = (
            make_figures(
                results,
                args.temperature_mode,
            )
        )
    else:
        time_path = None
        efc_path = None

    record = {
        "temperature_mode":
            args.temperature_mode,
        "smoke":
            args.smoke,
        "threshold_capacity":
            args.threshold_capacity,
        "threshold_time_years":
            threshold_time,
        "successful_cases":
            len(results),
        "failed_cases":
            len(errors),
        "summary_file":
            str(summary_path),
        "error_file":
            str(error_path),
        "q_vs_time_figure":
            (
                str(time_path)
                if time_path
                else None
            ),
        "q_vs_efc_figure":
            (
                str(efc_path)
                if efc_path
                else None
            ),
    }

    record_path = (
        RESULTS_DIR
        / f"{args.temperature_mode}_"
          f"{suffix}_run_record.json"
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
    if summary.empty:
        print(
            "No successful cases."
        )
    else:
        print(
            summary.to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
