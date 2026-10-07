
import json
import pickle
import time
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
SOURCE_DIR = BASE_DIR / "source_profiles"
STATE_DIR = BASE_DIR / "saved_states"
RESULTS_DIR = BASE_DIR / "results"
FIGURE_DIR = BASE_DIR / "figures"
LOG_DIR = BASE_DIR / "logs"

for directory in [
    STATE_DIR,
    RESULTS_DIR,
    FIGURE_DIR,
    LOG_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )


CANDIDATES = {
    "combined_unscaled":
        "first_life_combined_unscaled_365day.csv",
    "personal_large":
        "first_life_personal_large_365day.csv",
    "personal_small":
        "first_life_personal_small_365day.csv",
    "commercial":
        "first_life_commercial_365day.csv",
    "combined_scaled_55efc":
        "first_life_combined_scaled_55efc_365day.csv",
}


TARGET_Q = 0.80
MAX_YEARS = 30.0
DEGRADATION_SCALAR = 2.75


def json_safe(
    value,
):
    if isinstance(
        value,
        np.ndarray,
    ):
        return value.tolist()

    if isinstance(
        value,
        (
            np.floating,
            np.integer,
        ),
    ):
        return value.item()

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key):
                json_safe(item)
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        list,
    ):
        return [
            json_safe(item)
            for item in value
        ]

    return value


def compact_trajectory(
    time_years,
    efc,
    q,
    r,
):
    selected = [0]

    last_time = float(
        time_years[0]
    )

    for index in range(
        1,
        len(time_years) - 1,
    ):
        if (
            time_years[index]
            - last_time
            >= 30.0 / 365.0
        ):
            selected.append(
                index
            )

            last_time = float(
                time_years[index]
            )

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
        "r":
            r[selected],
    })


def run_candidate(
    candidate,
    filename,
):
    input_frame = pd.read_csv(
        SOURCE_DIR / filename
    )[
        [
            "Time_s",
            "SOC",
            "Temperature_C",
        ]
    ]

    soc = input_frame[
        "SOC"
    ].to_numpy(
        dtype=float
    )

    annual_efc = float(
        0.5
        * np.abs(
            np.diff(soc)
        ).sum()
    )

    battery = (
        Nmc111_Gr_Kokam75Ah_Battery(
            degradation_scalar=
                DEGRADATION_SCALAR
        )
    )

    start = time.time()

    battery.simulate_battery_life(
        input_frame,
        threshold_capacity=
            TARGET_Q,
        threshold_time=
            MAX_YEARS,
        is_constant_input=False,
    )

    elapsed = (
        time.time() - start
    )

    time_days = np.asarray(
        battery.stressors[
            "t_days"
        ],
        dtype=float,
    )

    time_years = (
        time_days / 365.0
    )

    efc = np.asarray(
        battery.stressors[
            "efc"
        ],
        dtype=float,
    )

    q = np.asarray(
        battery.outputs[
            "q"
        ],
        dtype=float,
    )

    r = np.asarray(
        battery.outputs[
            "r"
        ],
        dtype=float,
    )

    pickle_path = (
        STATE_DIR
        / f"{candidate}_"
          "aged_battery.pkl"
    )

    with pickle_path.open(
        "wb"
    ) as file:
        pickle.dump(
            battery,
            file,
        )

    state_record = {
        "candidate":
            candidate,
        "battery_class":
            type(
                battery
            ).__name__,
        "degradation_scalar":
            DEGRADATION_SCALAR,
        "target_q":
            TARGET_Q,
        "maximum_years":
            MAX_YEARS,
        "target_reached":
            bool(
                q[-1]
                <= TARGET_Q
                + 1e-6
            ),
        "final_q":
            float(q[-1]),
        "final_r":
            float(r[-1]),
        "final_time_years":
            float(
                time_years[-1]
            ),
        "final_efc":
            float(efc[-1]),
        "annual_input_efc":
            annual_efc,
        "states":
            json_safe(
                battery.states
            ),
        "outputs_final": {
            key:
                float(
                    np.asarray(
                        values
                    )[-1]
                )
            for key, values
            in battery.outputs.items()
        },
        "rates_final": {
            key:
                float(
                    np.asarray(
                        values
                    )[-1]
                )
            for key, values
            in battery.rates.items()
        },
        "stressors_final": {
            key:
                float(
                    np.asarray(
                        values
                    )[-1]
                )
            for key, values
            in battery.stressors.items()
        },
        "pickle_file":
            str(
                pickle_path.relative_to(
                    BASE_DIR
                )
            ),
        "pickle_size_bytes":
            pickle_path.stat().st_size,
        "execution_seconds":
            float(elapsed),
    }

    state_path = (
        STATE_DIR
        / f"{candidate}_"
          "aged_state.json"
    )

    state_path.write_text(
        json.dumps(
            state_record,
            indent=2,
        ),
        encoding="utf-8",
    )

    trajectory = compact_trajectory(
        time_years,
        efc,
        q,
        r,
    )

    trajectory_path = (
        RESULTS_DIR
        / f"{candidate}_"
          "first_life_trajectory.csv"
    )

    trajectory.to_csv(
        trajectory_path,
        index=False,
    )

    return {
        "candidate":
            candidate,
        "source_file":
            filename,
        "annual_input_efc":
            annual_efc,
        "input_soc_min":
            float(
                soc.min()
            ),
        "input_soc_mean":
            float(
                soc.mean()
            ),
        "input_soc_max":
            float(
                soc.max()
            ),
        "target_q":
            TARGET_Q,
        "target_reached":
            state_record[
                "target_reached"
            ],
        "final_q":
            state_record[
                "final_q"
            ],
        "final_r":
            state_record[
                "final_r"
            ],
        "final_time_years":
            state_record[
                "final_time_years"
            ],
        "final_efc":
            state_record[
                "final_efc"
            ],
        "pickle_file":
            state_record[
                "pickle_file"
            ],
        "state_file":
            str(
                state_path.relative_to(
                    BASE_DIR
                )
            ),
        "trajectory_file":
            str(
                trajectory_path.relative_to(
                    BASE_DIR
                )
            ),
        "execution_seconds":
            state_record[
                "execution_seconds"
            ],
        "_time_years":
            time_years,
        "_q":
            q,
        "_r":
            r,
    }


def main():
    results = []
    errors = []

    for candidate, filename in (
        CANDIDATES.items()
    ):
        print(
            f"Running {candidate}..."
        )

        try:
            result = run_candidate(
                candidate,
                filename,
            )

            results.append(
                result
            )

            print(
                "  q = "
                f"{result['final_q']:.6f}"
            )

            print(
                "  years = "
                f"{result['final_time_years']:.3f}"
            )

            print(
                "  EFC = "
                f"{result['final_efc']:.1f}"
            )

        except Exception as error:
            errors.append({
                "candidate":
                    candidate,
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

    summary_path = (
        RESULTS_DIR
        / "first_life_candidate_results.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    error_path = (
        LOG_DIR
        / "first_life_candidate_errors.json"
    )

    error_path.write_text(
        json.dumps(
            errors,
            indent=2,
        ),
        encoding="utf-8",
    )

    if results:
        fig, axes = plt.subplots(
            1,
            2,
            figsize=(12, 5.2),
        )

        for result in results:
            axes[0].plot(
                result[
                    "_time_years"
                ],
                result["_q"],
                label=result[
                    "candidate"
                ],
                linewidth=2,
            )

            axes[1].plot(
                result[
                    "_time_years"
                ],
                result["_r"],
                label=result[
                    "candidate"
                ],
                linewidth=2,
            )

        axes[0].axhline(
            TARGET_Q,
            color="#B52D30",
            linestyle="--",
            label="Target q=0.80",
        )

        axes[0].set_xlabel(
            "Time (years)"
        )

        axes[0].set_ylabel(
            "Normalized capacity, q"
        )

        axes[0].grid(
            alpha=0.18
        )

        axes[0].legend(
            frameon=False,
            fontsize=8,
        )

        axes[1].set_xlabel(
            "Time (years)"
        )

        axes[1].set_ylabel(
            "Normalized resistance, r"
        )

        axes[1].grid(
            alpha=0.18
        )

        axes[1].legend(
            frameon=False,
            fontsize=8,
        )

        fig.suptitle(
            "Candidate First-Life Aging Histories",
            fontsize=15,
            fontweight="bold",
        )

        fig.tight_layout()

        figure_path = (
            FIGURE_DIR
            / "first_life_candidate_comparison.png"
        )

        fig.savefig(
            figure_path,
            dpi=220,
            bbox_inches="tight",
        )

        plt.close(fig)

    else:
        figure_path = None

    record = {
        "battery_model":
            "Nmc111_Gr_Kokam75Ah_Battery",
        "degradation_scalar":
            DEGRADATION_SCALAR,
        "target_q":
            TARGET_Q,
        "maximum_years":
            MAX_YEARS,
        "successful_candidates":
            len(results),
        "failed_candidates":
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

    record_path = (
        RESULTS_DIR
        / "first_life_candidate_run_record.json"
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
        summary.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
