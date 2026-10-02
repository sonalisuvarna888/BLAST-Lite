
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


SCENARIOS = {
    "shallow_50_70": {
        "file":
            "scenario_shallow_50_70_annual.csv",
        "label":
            "Shallow 50–70% SOC",
        "color":
            "#2D8C5A",
    },
    "moderate_30_80": {
        "file":
            "scenario_moderate_30_80_annual.csv",
        "label":
            "Moderate 30–80% SOC",
        "color":
            "#0072CE",
    },
    "deep_10_90": {
        "file":
            "scenario_deep_10_90_annual.csv",
        "label":
            "Deep 10–90% SOC",
        "color":
            "#B52D30",
    },
}


def validate(frame, scenario):
    required = {
        "Time_s",
        "SOC",
        "Temperature_C",
    }

    if not required.issubset(frame.columns):
        raise ValueError(
            f"{scenario}: missing required columns"
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
            f"{scenario}: fewer than two rows"
        )

    if not np.all(np.diff(time_s) > 0):
        raise ValueError(
            f"{scenario}: time not strictly increasing"
        )

    if not np.all((soc >= 0) & (soc <= 1)):
        raise ValueError(
            f"{scenario}: SOC outside [0, 1]"
        )

    if not np.isfinite(
        np.column_stack([
            time_s,
            soc,
            temperature,
        ])
    ).all():
        raise ValueError(
            f"{scenario}: nonfinite inputs"
        )

    if not np.allclose(
        temperature,
        25.0,
    ):
        raise ValueError(
            f"{scenario}: temperature is not fixed at 25 C"
        )

    return time_s, soc, temperature


def duration_arguments(
    battery,
    years,
):
    parameters = inspect.signature(
        battery.simulate_battery_life
    ).parameters

    if "threshold_time" in parameters:
        return (
            {"threshold_time": years},
            "threshold_time",
        )

    if "simulation_years" in parameters:
        return (
            {"simulation_years": years},
            "simulation_years",
        )

    raise RuntimeError(
        "No recognized duration argument."
    )


def prepare(frame, mode):
    if mode == "smoke":
        seconds = 30 * 24 * 3600

        frame = frame.loc[
            frame["Time_s"] <= seconds
        ].copy()

        frame["Time_s"] = (
            frame["Time_s"]
            - frame["Time_s"].iloc[0]
        )

    return frame


def run_case(
    scenario,
    settings,
    mode,
    years,
):
    frame = pd.read_csv(
        INPUT_DIR / settings["file"]
    )

    frame = prepare(frame, mode)

    time_s, soc, temperature = validate(
        frame,
        scenario,
    )

    battery = (
        Nmc111_Gr_Kokam75Ah_Battery()
    )

    kwargs = {
        "is_constant_input": False,
    }

    if mode == "full":
        duration_kwargs, duration_name = (
            duration_arguments(
                battery,
                years,
            )
        )
        kwargs.update(duration_kwargs)
    else:
        duration_name = "one_input_pass"

    battery.simulate_battery_life(
        {
            "Time_s": time_s,
            "SOC": soc,
            "Temperature_C": temperature,
        },
        **kwargs,
    )

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

    if not (
        len(time_days)
        == len(q)
        == len(efc)
    ):
        raise ValueError(
            f"{scenario}: output lengths differ"
        )

    output = pd.DataFrame({
        "Time_days": time_days,
        "Time_years":
            time_days / 365.0,
        "EFC": efc,
        "q": q,
    })

    output_path = (
        RESULTS_DIR
        / f"{mode}_{scenario}_output.csv"
    )

    output.to_csv(
        output_path,
        index=False,
    )

    return {
        "scenario": scenario,
        "label": settings["label"],
        "mode": mode,
        "input_file": settings["file"],
        "input_rows": int(len(frame)),
        "temperature_C": 25.0,
        "input_soc_min":
            float(np.min(soc)),
        "input_soc_mean":
            float(np.mean(soc)),
        "input_soc_max":
            float(np.max(soc)),
        "input_soc_range":
            float(np.max(soc) - np.min(soc)),
        "input_profile_efc":
            float(
                0.5
                * np.abs(np.diff(soc)).sum()
            ),
        "duration_argument":
            duration_name,
        "requested_years":
            years if mode == "full" else None,
        "initial_q":
            float(q[0]),
        "final_q":
            float(q[-1]),
        "q_change":
            float(q[-1] - q[0]),
        "minimum_q":
            float(np.min(q)),
        "final_time_days":
            float(time_days[-1]),
        "final_time_years":
            float(time_days[-1] / 365.0),
        "final_efc":
            float(efc[-1]),
        "mean_model_dod":
            float(np.nanmean(dod)),
        "rms_model_dod":
            float(np.sqrt(np.nanmean(dod ** 2))),
        "mean_model_soc":
            float(np.nanmean(stress_soc)),
        "output_points":
            int(len(q)),
        "output_file":
            str(output_path.relative_to(BASE_DIR)),
        "_time_years":
            time_days / 365.0,
        "_q": q,
        "_color": settings["color"],
    }


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

    args = parser.parse_args()

    summaries = []
    plot_records = []
    errors = []

    for scenario, settings in SCENARIOS.items():
        print(
            f"Running {scenario} in "
            f"{args.mode} mode..."
        )

        try:
            result = run_case(
                scenario,
                settings,
                args.mode,
                args.years,
            )

            plot_records.append(result)

            summaries.append({
                key: value
                for key, value in result.items()
                if not key.startswith("_")
            })

            print(
                f"  final q = "
                f"{result['final_q']:.9f}"
            )
            print(
                f"  final EFC = "
                f"{result['final_efc']:.6f}"
            )
            print(
                f"  mean DOD = "
                f"{result['mean_model_dod']:.6f}"
            )

        except Exception as error:
            errors.append({
                "scenario": scenario,
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

    summary = pd.DataFrame(summaries)

    summary_path = (
        RESULTS_DIR
        / f"{args.mode}_soc_depth_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"{args.mode}_soc_depth_errors.json"
    )

    error_path.write_text(
        json.dumps(errors, indent=2),
        encoding="utf-8",
    )

    if plot_records:
        plt.figure(figsize=(10, 6))

        for result in plot_records:
            plt.plot(
                result["_time_years"],
                result["_q"],
                label=result["label"],
                color=result["_color"],
                linewidth=2.6,
            )

        plt.xlabel("Time (years)")
        plt.ylabel(
            "Normalized capacity output, q"
        )
        plt.title(
            "SOC-Depth Sensitivity at 25°C"
        )
        plt.grid(alpha=0.23)
        plt.legend(frameon=False)
        plt.tight_layout()

        figure_path = (
            FIGURE_DIR
            / f"{args.mode}_soc_depth_q_comparison.png"
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
        "successful_scenarios":
            len(summaries),
        "failed_scenarios":
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
            summary.to_string(index=False)
        )


if __name__ == "__main__":
    main()
