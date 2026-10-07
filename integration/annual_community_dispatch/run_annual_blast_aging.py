
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
DATA_DIR = BASE_DIR / "data"
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


CASES = {
    "battery_only": {
        "file":
            "blast_input_battery_only_annual.csv",
        "label":
            "Battery only",
        "color":
            "#E67300",
    },
    "demand_response_plus_battery": {
        "file":
            "blast_input_demand_response_plus_battery_annual.csv",
        "label":
            "DR + battery",
        "color":
            "#0072CE",
    },
}


def validate_input(
    frame,
    case,
):
    required = {
        "Time_s",
        "SOC",
        "Temperature_C",
    }

    if not required.issubset(
        frame.columns
    ):
        raise ValueError(
            f"{case}: missing input columns"
        )

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

    if not np.all(
        np.diff(time_s) > 0
    ):
        raise ValueError(
            f"{case}: time not increasing"
        )

    if not np.all(
        (soc >= 0)
        & (soc <= 1)
    ):
        raise ValueError(
            f"{case}: SOC outside [0,1]"
        )

    if not np.isfinite(
        np.column_stack([
            time_s,
            soc,
            temperature,
        ])
    ).all():
        raise ValueError(
            f"{case}: nonfinite values"
        )

    if not np.isclose(
        soc[0],
        soc[-1],
        atol=1e-8,
    ):
        raise ValueError(
            f"{case}: annual SOC boundary "
            "is not continuous"
        )

    return (
        time_s,
        soc,
        temperature,
    )


def duration_arguments(
    battery,
    years,
):
    parameters = inspect.signature(
        battery.simulate_battery_life
    ).parameters

    if "threshold_time" in parameters:
        return (
            {
                "threshold_time":
                    years,
            },
            "threshold_time",
        )

    if "simulation_years" in parameters:
        return (
            {
                "simulation_years":
                    years,
            },
            "simulation_years",
        )

    raise RuntimeError(
        "No recognized duration argument."
    )


def extract_outputs(
    battery,
):
    time_days = np.atleast_1d(
        np.asarray(
            battery.stressors[
                "t_days"
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

    efc = np.atleast_1d(
        np.asarray(
            battery.stressors[
                "efc"
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

    temperature_k = np.atleast_1d(
        np.asarray(
            battery.stressors[
                "TdegK"
            ]
        ).squeeze()
    )

    return {
        "time_days":
            time_days,
        "time_years":
            time_days / 365.0,
        "q":
            q,
        "efc":
            efc,
        "dod":
            dod,
        "stress_soc":
            stress_soc,
        "temperature_C":
            temperature_k - 273.15,
    }


def run_case(
    case,
    settings,
    mode,
    years,
):
    frame = pd.read_csv(
        DATA_DIR
        / settings["file"]
    )

    time_s, soc, temperature = (
        validate_input(
            frame,
            case,
        )
    )

    battery = (
        Nmc111_Gr_Kokam75Ah_Battery()
    )

    kwargs = {
        "is_constant_input":
            False,
    }

    if mode == "full":
        duration_kwargs, duration_name = (
            duration_arguments(
                battery,
                years,
            )
        )

        kwargs.update(
            duration_kwargs
        )
    else:
        duration_name = (
            "one_input_pass"
        )

    battery.simulate_battery_life(
        {
            "Time_s":
                time_s,
            "SOC":
                soc,
            "Temperature_C":
                temperature,
        },
        **kwargs,
    )

    outputs = extract_outputs(
        battery
    )

    if not (
        len(outputs["time_days"])
        == len(outputs["q"])
        == len(outputs["efc"])
    ):
        raise ValueError(
            f"{case}: output lengths differ"
        )

    output = pd.DataFrame({
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
        / f"blast_{mode}_{case}_output.csv"
    )

    output.to_csv(
        output_path,
        index=False,
    )

    input_efc = float(
        0.5
        * np.abs(
            np.diff(soc)
        ).sum()
    )

    return {
        "case":
            case,
        "label":
            settings["label"],
        "mode":
            mode,
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
        "input_soc_min":
            float(soc.min()),
        "input_soc_mean":
            float(soc.mean()),
        "input_soc_max":
            float(soc.max()),
        "input_annual_efc":
            input_efc,
        "input_temperature_min_C":
            float(
                temperature.min()
            ),
        "input_temperature_mean_C":
            float(
                temperature.mean()
            ),
        "input_temperature_max_C":
            float(
                temperature.max()
            ),
        "duration_argument":
            duration_name,
        "requested_years":
            (
                years
                if mode == "full"
                else None
            ),
        "initial_q":
            float(
                outputs["q"][0]
            ),
        "final_q":
            float(
                outputs["q"][-1]
            ),
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
            float(
                outputs["efc"][-1]
            ),
        "mean_model_soc":
            float(
                np.nanmean(
                    outputs[
                        "stress_soc"
                    ]
                )
            ),
        "mean_model_dod":
            float(
                np.nanmean(
                    outputs["dod"]
                )
            ),
        "rms_model_dod":
            float(
                np.sqrt(
                    np.nanmean(
                        outputs["dod"]
                        ** 2
                    )
                )
            ),
        "mean_model_temperature_C":
            float(
                np.nanmean(
                    outputs[
                        "temperature_C"
                    ]
                )
            ),
        "output_points":
            int(
                len(
                    outputs["q"]
                )
            ),
        "output_file":
            str(
                output_path.relative_to(
                    BASE_DIR
                )
            ),
        "_time_years":
            outputs["time_years"],
        "_q":
            outputs["q"],
        "_color":
            settings["color"],
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=[
            "smoke",
            "full",
        ],
        default="smoke",
    )

    parser.add_argument(
        "--years",
        type=float,
        default=5.0,
    )

    args = parser.parse_args()

    summaries = []
    plots = []
    errors = []

    for case, settings in (
        CASES.items()
    ):
        print(
            f"Running {case} "
            f"in {args.mode} mode..."
        )

        try:
            result = run_case(
                case,
                settings,
                args.mode,
                args.years,
            )

            plots.append(result)

            summaries.append({
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
                "  final EFC = "
                f"{result['final_efc']:.6f}"
            )

        except Exception as error:
            errors.append({
                "case":
                    case,
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
        summaries
    )

    summary_path = (
        RESULTS_DIR
        / f"blast_{args.mode}_"
          "community_aging_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / f"blast_{args.mode}_"
          "community_aging_errors.json"
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
            figsize=(10, 6)
        )

        for result in plots:
            plt.plot(
                result[
                    "_time_years"
                ],
                result["_q"],
                label=result["label"],
                color=result["_color"],
                linewidth=2.6,
            )

        plt.xlabel(
            "Time (years)"
        )

        plt.ylabel(
            "Normalized capacity output, q"
        )

        plt.title(
            "Community Dispatch "
            "Battery-Aging Comparison"
        )

        plt.grid(
            alpha=0.22
        )

        plt.legend(
            frameon=False
        )

        plt.tight_layout()

        figure_path = (
            FIGURE_DIR
            / f"blast_{args.mode}_"
              "community_aging.png"
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
        "mode":
            args.mode,
        "battery_model":
            "Nmc111_Gr_Kokam75Ah_Battery",
        "requested_years":
            (
                args.years
                if args.mode == "full"
                else None
            ),
        "successful_cases":
            len(summaries),
        "failed_cases":
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
        "classification":
            (
                "Post-processing aging "
                "evaluation with fixed "
                "dispatch capacity"
            ),
    }

    record_path = (
        RESULTS_DIR
        / f"blast_{args.mode}_"
          "community_aging_run_record.json"
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
