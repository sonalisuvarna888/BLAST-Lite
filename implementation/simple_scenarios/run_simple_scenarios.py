
import inspect
import json
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from blast.models import Nmc111_Gr_Kokam75Ah_Battery


BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "scenario_inputs"
RESULTS_DIR = BASE_DIR / "results"
LOG_DIR = BASE_DIR / "logs"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

SIMULATION_YEARS = 5

SCENARIOS = {
    "scenario_A": {
        "file": "scenario_A_constant_80pct.csv",
        "constant_input": True,
        "description": "Constant storage at 80% SOC and 45 C",
    },
    "scenario_B": {
        "file": "scenario_B_constant_50pct.csv",
        "constant_input": True,
        "description": "Constant storage at 50% SOC and 25 C",
    },
    "scenario_C": {
        "file": "scenario_C_daily_cycle.csv",
        "constant_input": False,
        "description": "One-day cycle from 30% to 80% SOC at 25 C",
    },
}


def build_duration_arguments(battery, years):
    signature = inspect.signature(
        battery.simulate_battery_life
    )
    parameter_names = signature.parameters.keys()

    if "threshold_time" in parameter_names:
        return {"threshold_time": years}, "threshold_time"

    if "simulation_years" in parameter_names:
        return {"simulation_years": years}, "simulation_years"

    raise RuntimeError(
        "No recognized duration argument in simulate_battery_life."
    )


def run_scenario(name, settings):
    input_path = INPUT_DIR / settings["file"]
    input_frame = pd.read_csv(input_path)

    required_columns = {
        "Time_s",
        "SOC",
        "Temperature_C",
    }

    if not required_columns.issubset(input_frame.columns):
        raise ValueError(
            f"{name}: missing required input columns."
        )

    input_data = {
        "Time_s": input_frame["Time_s"].to_numpy(dtype=float),
        "SOC": input_frame["SOC"].to_numpy(dtype=float),
        "Temperature_C": input_frame[
            "Temperature_C"
        ].to_numpy(dtype=float),
    }

    battery = Nmc111_Gr_Kokam75Ah_Battery()

    duration_kwargs, duration_name = build_duration_arguments(
        battery,
        SIMULATION_YEARS,
    )

    battery.simulate_battery_life(
        input_data,
        is_constant_input=settings["constant_input"],
        **duration_kwargs,
    )

    time_days = np.atleast_1d(
        np.asarray(
            battery.stressors["t_days"]
        ).squeeze()
    )
    time_years = time_days / 365.0

    q_values = np.atleast_1d(
        np.asarray(
            battery.outputs["q"]
        ).squeeze()
    )

    if len(time_years) != len(q_values):
        raise ValueError(
            f"{name}: time and q lengths do not match."
        )

    output_frame = pd.DataFrame({
        "Time_days": time_days,
        "Time_years": time_years,
        "q": q_values,
    })

    output_path = RESULTS_DIR / f"{name}_output.csv"
    output_frame.to_csv(output_path, index=False)

    return {
        "scenario": name,
        "description": settings["description"],
        "input_file": settings["file"],
        "constant_input": settings["constant_input"],
        "duration_argument": duration_name,
        "requested_years": SIMULATION_YEARS,
        "initial_q": float(q_values[0]),
        "final_q": float(q_values[-1]),
        "q_change": float(q_values[-1] - q_values[0]),
        "minimum_q": float(np.min(q_values)),
        "maximum_q": float(np.max(q_values)),
        "final_time_years": float(time_years[-1]),
        "output_points": int(len(q_values)),
        "output_file": str(output_path.relative_to(BASE_DIR)),
        "_time_years": time_years,
        "_q_values": q_values,
    }


def main():
    summary_rows = []
    plot_records = []
    errors = []

    for name, settings in SCENARIOS.items():
        print(f"Running {name}...")

        try:
            result = run_scenario(name, settings)
            plot_records.append(result)

            summary_rows.append({
                key: value
                for key, value in result.items()
                if not key.startswith("_")
            })

            print(f"  final q = {result['final_q']:.9f}")
            print(
                "  final time = "
                f"{result['final_time_years']:.6f} years"
            )

        except Exception as error:
            errors.append({
                "scenario": name,
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            })

            print(
                f"  FAILED: {type(error).__name__}: {error}"
            )

    summary = pd.DataFrame(summary_rows)
    summary_path = RESULTS_DIR / "scenario_summary.csv"
    summary.to_csv(summary_path, index=False)

    if plot_records:
        plt.figure(figsize=(10, 6))

        for result in plot_records:
            plt.plot(
                result["_time_years"],
                result["_q_values"],
                linewidth=2.2,
                label=result["scenario"],
            )

        plt.xlabel("Time (years)")
        plt.ylabel("q output")
        plt.title("BLAST-Lite Simple-Scenario Comparison")
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()

        comparison_path = (
            RESULTS_DIR / "scenario_comparison.png"
        )

        plt.savefig(
            comparison_path,
            dpi=220,
            bbox_inches="tight",
        )
        plt.close()
    else:
        comparison_path = None

    error_path = LOG_DIR / "scenario_errors.json"
    error_path.write_text(
        json.dumps(errors, indent=2),
        encoding="utf-8",
    )

    run_record = {
        "battery_model": "Nmc111_Gr_Kokam75Ah_Battery",
        "simulation_years_requested": SIMULATION_YEARS,
        "number_of_scenarios": len(SCENARIOS),
        "successful_scenarios": len(summary_rows),
        "failed_scenarios": len(errors),
        "summary_file": str(summary_path.relative_to(BASE_DIR)),
        "comparison_figure": (
            str(comparison_path.relative_to(BASE_DIR))
            if comparison_path
            else None
        ),
    }

    run_record_path = RESULTS_DIR / "run_record.json"
    run_record_path.write_text(
        json.dumps(run_record, indent=2),
        encoding="utf-8",
    )

    print("\nRun record:")
    print(json.dumps(run_record, indent=2))

    print("\nScenario summary:")
    if summary.empty:
        print("No scenarios succeeded.")
    else:
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
