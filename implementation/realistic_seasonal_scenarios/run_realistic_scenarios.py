
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
LOG_DIR = BASE_DIR / "logs"
FIGURE_DIR = BASE_DIR / "figures"

for directory in [
    RESULTS_DIR,
    LOG_DIR,
    FIGURE_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)


SCENARIOS = {
    "T25": {
        "file":
            "scenario_T25_annual.csv",
        "description":
            "Residential PV-BESS SOC at constant 25 C",
        "temperature_type":
            "constant",
    },
    "T30": {
        "file":
            "scenario_T30_annual.csv",
        "description":
            "Residential PV-BESS SOC at constant 30 C",
        "temperature_type":
            "constant",
    },
    "T40": {
        "file":
            "scenario_T40_annual.csv",
        "description":
            "Residential PV-BESS SOC at constant 40 C",
        "temperature_type":
            "constant",
    },
    "Miami_variable": {
        "file":
            "scenario_Miami_variable_annual.csv",
        "description":
            "Residential PV-BESS SOC with variable Miami temperature",
        "temperature_type":
            "climate-informed",
    },
}


def validate_input(frame, scenario_name):
    required = {
        "Time_s",
        "SOC",
        "Temperature_C",
    }

    if not required.issubset(
        frame.columns
    ):
        missing = sorted(
            required - set(frame.columns)
        )
        raise ValueError(
            f"{scenario_name}: missing columns "
            f"{missing}"
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
            f"{scenario_name}: fewer than "
            "two input rows"
        )

    if not np.all(
        np.diff(time_s) > 0
    ):
        raise ValueError(
            f"{scenario_name}: time is not "
            "strictly increasing"
        )

    if not np.isfinite(
        time_s
    ).all():
        raise ValueError(
            f"{scenario_name}: nonfinite time"
        )

    if not np.isfinite(
        soc
    ).all():
        raise ValueError(
            f"{scenario_name}: nonfinite SOC"
        )

    if not np.isfinite(
        temperature
    ).all():
        raise ValueError(
            f"{scenario_name}: nonfinite "
            "temperature"
        )

    if not np.all(
        (soc >= 0) & (soc <= 1)
    ):
        raise ValueError(
            f"{scenario_name}: SOC is outside "
            "[0, 1]"
        )

    return time_s, soc, temperature


def choose_duration_argument(
    battery,
    years,
):
    signature = inspect.signature(
        battery.simulate_battery_life
    )

    parameter_names = (
        signature.parameters.keys()
    )

    if "threshold_time" in parameter_names:
        return (
            {"threshold_time": years},
            "threshold_time",
        )

    if "simulation_years" in parameter_names:
        return (
            {"simulation_years": years},
            "simulation_years",
        )

    raise RuntimeError(
        "No recognized duration argument."
    )


def prepare_frame(
    frame,
    mode,
):
    if mode == "smoke":
        smoke_duration_seconds = (
            30 * 24 * 3600
        )

        prepared = frame.loc[
            frame["Time_s"]
            <= smoke_duration_seconds
        ].copy()

        if len(prepared) < 2:
            raise ValueError(
                "Smoke-test subset contains "
                "fewer than two rows."
            )

        prepared["Time_s"] = (
            prepared["Time_s"]
            - prepared["Time_s"].iloc[0]
        )

        return prepared

    return frame.copy()


def run_scenario(
    scenario_name,
    settings,
    mode,
    simulation_years,
):
    input_path = (
        INPUT_DIR / settings["file"]
    )

    source_frame = pd.read_csv(
        input_path
    )

    frame = prepare_frame(
        source_frame,
        mode,
    )

    time_s, soc, temperature = (
        validate_input(
            frame,
            scenario_name,
        )
    )

    input_data = {
        "Time_s": time_s,
        "SOC": soc,
        "Temperature_C": temperature,
    }

    battery = (
        Nmc111_Gr_Kokam75Ah_Battery()
    )

    simulate_kwargs = {
        "is_constant_input": False,
    }

    if mode == "full":
        duration_kwargs, duration_name = (
            choose_duration_argument(
                battery,
                simulation_years,
            )
        )

        simulate_kwargs.update(
            duration_kwargs
        )
    else:
        duration_name = (
            "none_one_input_pass"
        )

    battery.simulate_battery_life(
        input_data,
        **simulate_kwargs,
    )

    time_days = np.atleast_1d(
        np.asarray(
            battery.stressors["t_days"]
        ).squeeze()
    )

    time_years = (
        time_days / 365.0
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

    if not (
        len(time_days)
        == len(q)
        == len(efc)
    ):
        raise ValueError(
            f"{scenario_name}: output lengths "
            "do not match"
        )

    if not np.isfinite(q).all():
        raise ValueError(
            f"{scenario_name}: q contains "
            "nonfinite values"
        )

    output = pd.DataFrame({
        "Time_days": time_days,
        "Time_years": time_years,
        "EFC": efc,
        "q": q,
    })

    output_path = (
        RESULTS_DIR
        / f"{mode}_{scenario_name}_output.csv"
    )

    output.to_csv(
        output_path,
        index=False,
    )

    return {
        "scenario": scenario_name,
        "mode": mode,
        "description":
            settings["description"],
        "input_file":
            settings["file"],
        "input_rows":
            int(len(frame)),
        "input_duration_days":
            float(
                (
                    time_s[-1]
                    - time_s[0]
                )
                / 86400.0
            ),
        "temperature_type":
            settings[
                "temperature_type"
            ],
        "temperature_min_C":
            float(np.min(temperature)),
        "temperature_mean_C":
            float(np.mean(temperature)),
        "temperature_max_C":
            float(np.max(temperature)),
        "soc_min":
            float(np.min(soc)),
        "soc_mean":
            float(np.mean(soc)),
        "soc_max":
            float(np.max(soc)),
        "duration_argument":
            duration_name,
        "requested_years":
            (
                simulation_years
                if mode == "full"
                else None
            ),
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
            float(time_years[-1]),
        "final_efc":
            float(efc[-1]),
        "output_points":
            int(len(q)),
        "output_file":
            str(
                output_path.relative_to(
                    BASE_DIR
                )
            ),
        "_time_years":
            time_years,
        "_q":
            q,
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

    summary_rows = []
    plot_records = []
    errors = []

    for scenario_name, settings in (
        SCENARIOS.items()
    ):
        print(
            f"Running {scenario_name} "
            f"in {args.mode} mode..."
        )

        try:
            result = run_scenario(
                scenario_name,
                settings,
                args.mode,
                args.years,
            )

            plot_records.append(result)

            summary_rows.append({
                key: value
                for key, value
                in result.items()
                if not key.startswith("_")
            })

            print(
                "  final q = "
                f"{result['final_q']:.9f}"
            )

            print(
                "  final time = "
                f"{result['final_time_days']:.4f} "
                "days"
            )

            print(
                "  final EFC = "
                f"{result['final_efc']:.6f}"
            )

        except Exception as error:
            errors.append({
                "scenario":
                    scenario_name,
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

    summary = pd.DataFrame(
        summary_rows
    )

    summary_path = (
        RESULTS_DIR
        / f"{args.mode}_scenario_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"{args.mode}_scenario_errors.json"
    )

    error_path.write_text(
        json.dumps(
            errors,
            indent=2,
        ),
        encoding="utf-8",
    )

    if plot_records:
        plt.figure(
            figsize=(10, 6)
        )

        colors = {
            "T25": "#2D8C5A",
            "T30": "#E6A500",
            "T40": "#B52D30",
            "Miami_variable": "#0072CE",
        }

        for result in plot_records:
            plt.plot(
                result["_time_years"],
                result["_q"],
                label=result["scenario"],
                color=colors[
                    result["scenario"]
                ],
                linewidth=2.4,
            )

        plt.xlabel("Time (years)")
        plt.ylabel(
            "Normalized capacity output, q"
        )

        title_mode = (
            "30-Day Smoke Test"
            if args.mode == "smoke"
            else (
                f"{args.years:g}-Year "
                "Temperature Comparison"
            )
        )

        plt.title(
            "Residential PV-BESS "
            + title_mode
        )

        plt.grid(alpha=0.25)
        plt.legend(frameon=False)
        plt.tight_layout()

        figure_path = (
            FIGURE_DIR
            / f"{args.mode}_q_comparison.png"
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
        "requested_years":
            (
                args.years
                if args.mode == "full"
                else None
            ),
        "successful_scenarios":
            len(summary_rows),
        "failed_scenarios":
            len(errors),
        "summary_file":
            str(summary_path),
        "error_file":
            str(error_path),
        "comparison_figure":
            (
                str(figure_path)
                if figure_path
                else None
            ),
    }

    run_record_path = (
        RESULTS_DIR
        / f"{args.mode}_run_record.json"
    )

    run_record_path.write_text(
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
        print(
            "No scenarios succeeded."
        )
    else:
        print(
            summary.to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
