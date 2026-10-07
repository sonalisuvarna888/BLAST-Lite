
import copy
import json
import pickle
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

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

FIGURE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


AGED_PICKLE = (
    STATE_DIR
    / "combined_unscaled_aged_battery.pkl"
)

SERVICE_PROFILE = (
    SOURCE_DIR
    / "second_life_stationary_service_DR_plus_battery.csv"
)


def final_metrics(
    battery,
):
    return {
        "q":
            float(
                np.asarray(
                    battery.outputs["q"]
                )[-1]
            ),
        "r":
            float(
                np.asarray(
                    battery.outputs["r"]
                )[-1]
            ),
        "time_days":
            float(
                np.asarray(
                    battery.stressors[
                        "t_days"
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


def history_lengths(
    battery,
):
    return {
        "q":
            len(
                battery.outputs[
                    "q"
                ]
            ),
        "r":
            len(
                battery.outputs[
                    "r"
                ]
            ),
        "time":
            len(
                battery.stressors[
                    "t_days"
                ]
            ),
        "efc":
            len(
                battery.stressors[
                    "efc"
                ]
            ),
    }


def run_continuation(
    battery,
    input_frame,
):
    before = final_metrics(
        battery
    )

    before_lengths = (
        history_lengths(
            battery
        )
    )

    # threshold_time is an absolute cumulative
    # modeled time, not an incremental duration.
    target_time_years = (
        before["time_years"]
        + 1.0
    )

    battery.simulate_battery_life(
        input_frame,
        threshold_time=
            target_time_years,
        is_constant_input=False,
    )

    after = final_metrics(
        battery
    )

    after_lengths = (
        history_lengths(
            battery
        )
    )

    return {
        "battery":
            battery,
        "before":
            before,
        "after":
            after,
        "before_lengths":
            before_lengths,
        "after_lengths":
            after_lengths,
    }


def main():
    if not AGED_PICKLE.exists():
        raise FileNotFoundError(
            AGED_PICKLE
        )

    if not SERVICE_PROFILE.exists():
        raise FileNotFoundError(
            SERVICE_PROFILE
        )

    service = pd.read_csv(
        SERVICE_PROFILE
    )[
        [
            "Time_s",
            "SOC",
            "Temperature_C",
        ]
    ].copy()

    with AGED_PICKLE.open(
        "rb"
    ) as file:
        aged_loaded = pickle.load(
            file
        )

    aged_direct = aged_loaded

    aged_deepcopy = copy.deepcopy(
        aged_loaded
    )

    with AGED_PICKLE.open(
        "rb"
    ) as file:
        aged_reloaded = pickle.load(
            file
        )

    cases = {
        "aged_direct":
            aged_direct,
        "aged_deepcopy":
            aged_deepcopy,
        "aged_reloaded":
            aged_reloaded,
        "fresh_reference":
            Nmc111_Gr_Kokam75Ah_Battery(
                degradation_scalar=2.75
            ),
    }

    results = {}

    for case, battery in cases.items():
        print(
            f"Running {case}..."
        )

        results[case] = (
            run_continuation(
                battery,
                service,
            )
        )

        print(
            "  before q = "
            f"{results[case]['before']['q']:.9f}"
        )

        print(
            "  after q = "
            f"{results[case]['after']['q']:.9f}"
        )

    aged_case_names = [
        "aged_direct",
        "aged_deepcopy",
        "aged_reloaded",
    ]

    reference_after = (
        results[
            "aged_direct"
        ][
            "after"
        ]
    )

    tolerance = 1e-10

    equivalence = {}

    for case in aged_case_names:
        after = results[
            case
        ][
            "after"
        ]

        equivalence[case] = {
            key:
                bool(
                    np.isclose(
                        after[key],
                        reference_after[key],
                        atol=tolerance,
                        rtol=0,
                    )
                )
            for key in [
                "q",
                "r",
                "time_days",
                "efc",
            ]
        }

    records = []

    for case, result in (
        results.items()
    ):
        before = result[
            "before"
        ]

        after = result[
            "after"
        ]

        records.append({
            "case":
                case,
            "before_q":
                before["q"],
            "after_q":
                after["q"],
            "delta_q":
                after["q"]
                - before["q"],
            "before_r":
                before["r"],
            "after_r":
                after["r"],
            "delta_r":
                after["r"]
                - before["r"],
            "before_time_years":
                before[
                    "time_years"
                ],
            "after_time_years":
                after[
                    "time_years"
                ],
            "delta_time_years":
                after[
                    "time_years"
                ]
                - before[
                    "time_years"
                ],
            "before_efc":
                before["efc"],
            "after_efc":
                after["efc"],
            "delta_efc":
                after["efc"]
                - before["efc"],
            "before_q_length":
                result[
                    "before_lengths"
                ][
                    "q"
                ],
            "after_q_length":
                result[
                    "after_lengths"
                ][
                    "q"
                ],
        })

    summary = pd.DataFrame(
        records
    )

    summary_path = (
        RESULTS_DIR
        / "second_life_continuation_summary.csv"
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    # Save continued selected state.
    continued_pickle = (
        STATE_DIR
        / "combined_unscaled_"
          "after_one_year_stationary.pkl"
    )

    with continued_pickle.open(
        "wb"
    ) as file:
        pickle.dump(
            results[
                "aged_direct"
            ][
                "battery"
            ],
            file,
        )

    # Plot only the appended service segment.
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12, 5)
    )

    for case in [
        "aged_direct",
        "fresh_reference",
    ]:
        battery = results[
            case
        ][
            "battery"
        ]

        before_length = results[
            case
        ][
            "before_lengths"
        ][
            "q"
        ]

        q = np.asarray(
            battery.outputs["q"]
        )

        r = np.asarray(
            battery.outputs["r"]
        )

        t = (
            np.asarray(
                battery.stressors[
                    "t_days"
                ]
            )
            / 365.0
        )

        start_index = max(
            0,
            before_length - 1,
        )

        axes[0].plot(
            t[
                start_index:
            ],
            q[
                start_index:
            ],
            label=case,
            linewidth=2.2,
        )

        axes[1].plot(
            t[
                start_index:
            ],
            r[
                start_index:
            ],
            label=case,
            linewidth=2.2,
        )

    axes[0].set_xlabel(
        "Cumulative modeled time (years)"
    )

    axes[0].set_ylabel(
        "Normalized capacity, q"
    )

    axes[0].grid(
        alpha=0.18
    )

    axes[0].legend(
        frameon=False
    )

    axes[1].set_xlabel(
        "Cumulative modeled time (years)"
    )

    axes[1].set_ylabel(
        "Normalized resistance, r"
    )

    axes[1].grid(
        alpha=0.18
    )

    axes[1].legend(
        frameon=False
    )

    fig.suptitle(
        "Second-Life Continuation: "
        "Aged vs Fresh Stationary Service",
        fontsize=15,
        fontweight="bold",
    )

    fig.tight_layout()

    figure_path = (
        FIGURE_DIR
        / "second_life_continuation_comparison.png"
    )

    fig.savefig(
        figure_path,
        dpi=220,
        bbox_inches="tight",
    )

    plt.close(fig)

    checks = {
        "aged_equivalence":
            all(
                all(
                    values.values()
                )
                for values
                in equivalence.values()
            ),
        "aged_q_does_not_reset":
            bool(
                results[
                    "aged_direct"
                ][
                    "before"
                ][
                    "q"
                ]
                < 0.801
            ),
        "aged_r_does_not_reset":
            bool(
                results[
                    "aged_direct"
                ][
                    "before"
                ][
                    "r"
                ]
                > 1.0
            ),
        "aged_time_continues":
            bool(
                results[
                    "aged_direct"
                ][
                    "after"
                ][
                    "time_years"
                ]
                > results[
                    "aged_direct"
                ][
                    "before"
                ][
                    "time_years"
                ]
            ),
        "aged_continuation_is_one_year":
            bool(
                np.isclose(
                    results[
                        "aged_direct"
                    ][
                        "after"
                    ][
                        "time_years"
                    ]
                    - results[
                        "aged_direct"
                    ][
                        "before"
                    ][
                        "time_years"
                    ],
                    1.0,
                    atol=0.02,
                )
            ),
        "aged_efc_continues":
            bool(
                results[
                    "aged_direct"
                ][
                    "after"
                ][
                    "efc"
                ]
                > results[
                    "aged_direct"
                ][
                    "before"
                ][
                    "efc"
                ]
            ),
        "history_appended":
            bool(
                results[
                    "aged_direct"
                ][
                    "after_lengths"
                ][
                    "q"
                ]
                > results[
                    "aged_direct"
                ][
                    "before_lengths"
                ][
                    "q"
                ]
            ),
    }

    record = {
        "selected_candidate":
            "combined_unscaled",
        "service_profile":
            SERVICE_PROFILE.name,
        "equivalence":
            equivalence,
        "checks":
            checks,
        "all_checks_passed":
            all(
                checks.values()
            ),
        "summary_file":
            str(summary_path),
        "continued_pickle":
            str(
                continued_pickle.relative_to(
                    BASE_DIR
                )
            ),
        "figure":
            str(figure_path),
        "classification":
            (
                "Internally consistent aged "
                "second-life state continued "
                "under one annual stationary "
                "service profile."
            ),
    }

    record_path = (
        RESULTS_DIR
        / "second_life_continuation_record.json"
    )

    record_path.write_text(
        json.dumps(
            record,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nSUMMARY")
    print(
        summary.to_string(
            index=False
        )
    )

    print("\nRECORD")
    print(
        json.dumps(
            record,
            indent=2,
        )
    )

    if not record[
        "all_checks_passed"
    ]:
        raise RuntimeError(
            "Continuation equivalence "
            "checks failed."
        )


if __name__ == "__main__":
    main()
