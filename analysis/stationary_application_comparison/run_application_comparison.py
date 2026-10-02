
import argparse
import inspect
import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from blast.models import (
    Nmc111_Gr_Kokam75Ah_Battery
)


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "scenario_inputs"
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
    "residential_CA_mild": {
        "file":
            "residential_CA_mild_annual_25C.csv",
        "label":
            "Residential PV-BESS — CA mild",
        "color":
            "#0072CE",
    },
    "residential_Germany_aggressive": {
        "file":
            "residential_Germany_aggressive_annual_25C.csv",
        "label":
            "Residential PV-BESS — Germany aggressive",
        "color":
            "#B52D30",
    },
    "commercial_peak_shaving": {
        "file":
            "commercial_peak_shaving_annual_25C.csv",
        "label":
            "Commercial peak shaving",
        "color":
            "#2D8C5A",
    },
    "frequency_containment_reserve": {
        "file":
            "frequency_containment_reserve_annual_25C.csv",
        "label":
            "Frequency containment reserve",
        "color":
            "#E67300",
    },
}


def validate(frame, case):
    required = {
        "Time_s",
        "SOC",
        "Temperature_C",
    }

    if not required.issubset(frame.columns):
        raise ValueError(
            f"{case}: missing required columns"
        )

    time_s = frame[
        "Time_s"
    ].to_numpy(dtype=float)

    soc = frame[
        "SOC"
    ].to_numpy(dtype=float)

    temperature = frame[
        "Temperature_C"
    ].to_numpy(dtype=float)

    if len(frame) < 2:
        raise ValueError(
            f"{case}: fewer than two rows"
        )

    if not np.all(
        np.diff(time_s) > 0
    ):
        raise ValueError(
            f"{case}: time is not increasing"
        )

    if not np.all(
        (soc >= 0) & (soc <= 1)
    ):
        raise ValueError(
            f"{case}: SOC outside [0, 1]"
        )

    if not np.isfinite(
        np.column_stack([
            time_s,
            soc,
            temperature,
        ])
    ).all():
        raise ValueError(
            f"{case}: nonfinite inputs"
        )

    if not np.allclose(
        temperature,
        25.0,
    ):
        raise ValueError(
            f"{case}: temperature not 25 C"
        )

    return time_s, soc, temperature


def prepare(frame, mode):
    if mode == "smoke":
        duration_s = (
            30 * 24 * 3600
        )

        frame = frame.loc[
            frame["Time_s"]
            <= duration_s
        ].copy()

        frame["Time_s"] = (
            frame["Time_s"]
            - frame["Time_s"].iloc[0]
        )

    return frame


def method_parameters(battery):
    return inspect.signature(
        battery.simulate_battery_life
    ).parameters


def run_battery(
    input_data,
    mode,
    years,
    threshold_capacity=None,
    max_years=None,
):
    battery = (
        Nmc111_Gr_Kokam75Ah_Battery()
    )

    parameters = method_parameters(
        battery
    )

    kwargs = {
        "is_constant_input": False,
    }

    duration_name = "one_input_pass"

    if mode == "full":
        if "threshold_time" in parameters:
            kwargs["threshold_time"] = years
            duration_name = "threshold_time"
        elif "simulation_years" in parameters:
            kwargs["simulation_years"] = years
            duration_name = "simulation_years"
        else:
            raise RuntimeError(
                "No recognized duration argument"
            )

    elif mode == "threshold":
        kwargs[
            "threshold_capacity"
        ] = threshold_capacity

        if "threshold_time" in parameters:
            kwargs["threshold_time"] = max_years
            duration_name = (
                "threshold_capacity+threshold_time"
            )
        elif "simulation_years" in parameters:
            kwargs["simulation_years"] = max_years
            duration_name = (
                "threshold_capacity+simulation_years"
            )
        else:
            raise RuntimeError(
                "No recognized duration argument"
            )

    battery.simulate_battery_life(
        input_data,
        **kwargs,
    )

    return battery, duration_name


def extract_outputs(battery):
    time_days = np.atleast_1d(
        np.asarray(
            battery.stressors["t_days"]
        ).squeeze()
    )

    q = np.atleast_1d(
        np.asarray(
            battery.outputs["q"]
        ).squeeze()
    )

    efc = np.atleast_1d(
        np.asarray(
            battery.stressors["efc"]
        ).squeeze()
    )

    dod = np.atleast_1d(
        np.asarray(
            battery.stressors["dod"]
        ).squeeze()
    )

    stress_soc = np.atleast_1d(
        np.asarray(
            battery.stressors["soc"]
        ).squeeze()
    )

    return {
        "time_days": time_days,
        "time_years":
            time_days / 365.0,
        "q": q,
        "efc": efc,
        "dod": dod,
        "stress_soc": stress_soc,
    }


def run_case(
    case,
    settings,
    mode,
    years,
    max_threshold_years,
):
    frame = pd.read_csv(
        INPUT_DIR / settings["file"]
    )

    frame = prepare(
        frame,
        mode,
    )

    time_s, soc, temperature = (
        validate(
            frame,
            case,
        )
    )

    input_data = {
        "Time_s": time_s,
        "SOC": soc,
        "Temperature_C": temperature,
    }

    battery, duration_name = (
        run_battery(
            input_data,
            mode=mode,
            years=years,
        )
    )

    outputs = extract_outputs(
        battery
    )

    output_frame = pd.DataFrame({
        "Time_days":
            outputs["time_days"],
        "Time_years":
            outputs["time_years"],
        "EFC":
            outputs["efc"],
        "q":
            outputs["q"],
    })

    output_path = (
        RESULTS_DIR
        / f"{mode}_{case}_output.csv"
    )

    output_frame.to_csv(
        output_path,
        index=False,
    )

    input_duration_days = float(
        (
            time_s[-1] - time_s[0]
        )
        / 86400.0
    )

    input_efc = float(
        0.5
        * np.abs(np.diff(soc)).sum()
    )

    annualized_input_efc = float(
        input_efc
        * 365.0
        / input_duration_days
    )

    result = {
        "case": case,
        "label": settings["label"],
        "mode": mode,
        "input_file": settings["file"],
        "input_rows": int(len(frame)),
        "input_duration_days":
            input_duration_days,
        "temperature_C": 25.0,
        "input_soc_min":
            float(np.min(soc)),
        "input_soc_mean":
            float(np.mean(soc)),
        "input_soc_median":
            float(np.median(soc)),
        "input_soc_max":
            float(np.max(soc)),
        "input_annualized_efc":
            annualized_input_efc,
        "duration_argument":
            duration_name,
        "requested_years":
            years if mode == "full" else None,
        "initial_q":
            float(outputs["q"][0]),
        "final_q":
            float(outputs["q"][-1]),
        "q_change":
            float(
                outputs["q"][-1]
                - outputs["q"][0]
            ),
        "final_time_years":
            float(
                outputs["time_years"][-1]
            ),
        "final_efc":
            float(outputs["efc"][-1]),
        "mean_model_soc":
            float(np.nanmean(
                outputs["stress_soc"]
            )),
        "mean_model_dod":
            float(np.nanmean(
                outputs["dod"]
            )),
        "rms_model_dod":
            float(np.sqrt(
                np.nanmean(
                    outputs["dod"] ** 2
                )
            )),
        "output_points":
            int(len(outputs["q"])),
        "output_file":
            str(output_path.relative_to(
                BASE_DIR
            )),
        "_time_years":
            outputs["time_years"],
        "_q":
            outputs["q"],
        "_color":
            settings["color"],
    }

    if mode == "full":
        threshold_battery, threshold_name = (
            run_battery(
                input_data,
                mode="threshold",
                years=None,
                threshold_capacity=0.80,
                max_years=max_threshold_years,
            )
        )

        threshold_outputs = (
            extract_outputs(
                threshold_battery
            )
        )

        threshold_final_q = float(
            threshold_outputs["q"][-1]
        )

        threshold_reached = bool(
            threshold_final_q <= 0.800001
        )

        result.update({
            "q80_threshold_argument":
                threshold_name,
            "q80_reached":
                threshold_reached,
            "time_to_q80_years":
                (
                    float(
                        threshold_outputs[
                            "time_years"
                        ][-1]
                    )
                    if threshold_reached
                    else None
                ),
            "q80_run_final_q":
                threshold_final_q,
            "q80_run_final_time_years":
                float(
                    threshold_outputs[
                        "time_years"
                    ][-1]
                ),
            "q80_run_final_efc":
                float(
                    threshold_outputs[
                        "efc"
                    ][-1]
                ),
            "q80_cap_years":
                max_threshold_years,
        })

    return result


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=["smoke", "full"],
        default="smoke",
    )

    parser.add_argument(
        "--years",
        type=float,
        default=5.0,
    )

    parser.add_argument(
        "--max-threshold-years",
        type=float,
        default=30.0,
    )

    args = parser.parse_args()

    summaries = []
    plots = []
    errors = []

    for case, settings in (
        APPLICATIONS.items()
    ):
        print(
            f"Running {case} in "
            f"{args.mode} mode..."
        )

        try:
            result = run_case(
                case,
                settings,
                args.mode,
                args.years,
                args.max_threshold_years,
            )

            plots.append(result)

            summaries.append({
                key: value
                for key, value
                in result.items()
                if not key.startswith("_")
            })

            print(
                f"  final q = "
                f"{result['final_q']:.9f}"
            )
            print(
                f"  annualized input EFC = "
                f"{result['input_annualized_efc']:.3f}"
            )

            if args.mode == "full":
                print(
                    "  q=0.80 reached = "
                    f"{result['q80_reached']}"
                )
                print(
                    "  q=0.80 time = "
                    f"{result['time_to_q80_years']}"
                )

        except Exception as error:
            errors.append({
                "case": case,
                "error_type":
                    type(error).__name__,
                "message": str(error),
                "traceback":
                    traceback.format_exc(),
            })

            print(
                f"  FAILED: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    summary = pd.DataFrame(
        summaries
    )

    summary_path = (
        RESULTS_DIR
        / f"{args.mode}_application_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"{args.mode}_application_errors.json"
    )

    error_path.write_text(
        json.dumps(
            errors,
            indent=2,
        ),
        encoding="utf-8",
    )

    if plots:
        plt.figure(
            figsize=(11, 6.5)
        )

        for result in plots:
            plt.plot(
                result["_time_years"],
                result["_q"],
                label=result["label"],
                color=result["_color"],
                linewidth=2.5,
            )

        plt.xlabel("Time (years)")
        plt.ylabel(
            "Normalized capacity output, q"
        )
        plt.title(
            "Stationary Application Comparison "
            "at 25°C"
        )
        plt.grid(alpha=0.22)
        plt.legend(frameon=False)
        plt.tight_layout()

        figure_path = (
            FIGURE_DIR
            / f"{args.mode}_application_q_comparison.png"
        )

        plt.savefig(
            figure_path,
            dpi=220,
            bbox_inches="tight",
        )

        plt.close()
    else:
        figure_path = None

    run_record = {
        "mode": args.mode,
        "battery_model":
            "Nmc111_Gr_Kokam75Ah_Battery",
        "fixed_temperature_C": 25.0,
        "requested_years":
            args.years
            if args.mode == "full"
            else None,
        "q80_threshold": 0.80,
        "q80_cap_years":
            args.max_threshold_years,
        "successful_cases":
            len(summaries),
        "failed_cases":
            len(errors),
        "summary_file":
            str(summary_path),
        "error_file":
            str(error_path),
        "comparison_figure":
            str(figure_path)
            if figure_path
            else None,
    }

    record_path = (
        RESULTS_DIR
        / f"{args.mode}_run_record.json"
    )

    record_path.write_text(
        json.dumps(
            run_record,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nRun record:")
    print(
        json.dumps(
            run_record,
            indent=2,
        )
    )

    print("\nSummary:")
    if summary.empty:
        print("No successful cases.")
    else:
        print(
            summary.to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
