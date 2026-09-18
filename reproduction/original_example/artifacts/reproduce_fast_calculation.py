
import inspect
import json
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from blast.models import (
    Nmc111_Gr_Kokam75Ah_Battery
)

# Same physical inputs as the official notebook.
inputs = {
    "Time_s": np.array([0, 86399]),
    "SOC": np.array([0.8, 0.8]),
    "Temperature_C": np.array([45, 45])
}

battery = Nmc111_Gr_Kokam75Ah_Battery()

signature = inspect.signature(
    battery.simulate_battery_life
)

parameter_names = list(
    signature.parameters.keys()
)

kwargs = {
    "is_constant_input": True
}

if "threshold_time" in parameter_names:
    kwargs["threshold_time"] = 5
    api_duration_argument = "threshold_time=5"

elif "simulation_years" in parameter_names:
    kwargs["simulation_years"] = 5
    api_duration_argument = "simulation_years=5"

else:
    raise RuntimeError(
        "No supported duration argument found."
    )

print("Method signature:")
print(signature)

print("Duration argument used:")
print(api_duration_argument)

battery.simulate_battery_life(
    inputs,
    **kwargs
)

time_days = np.atleast_1d(
    np.asarray(
        battery.stressors["t_days"]
    ).squeeze()
)

time_years = time_days / 365.0

q = np.atleast_1d(
    np.asarray(
        battery.outputs["q"]
    ).squeeze()
)

if len(time_years) != len(q):
    raise ValueError(
        f"Length mismatch: "
        f"time={len(time_years)}, q={len(q)}"
    )

results = pd.DataFrame({
    "Time_days": time_days,
    "Time_years": time_years,
    "q": q
})

csv_path = (
    "/content/blast_lite_reproduction/"
    "fast_calculation_results.csv"
)

figure_path = (
    "/content/blast_lite_reproduction/"
    "fast_calculation_q_trajectory.png"
)

summary_path = (
    "/content/blast_lite_reproduction/"
    "fast_calculation_summary.json"
)

results.to_csv(
    csv_path,
    index=False
)

plt.figure(figsize=(9, 5))

plt.plot(
    time_years,
    q,
    color="#176B87",
    linewidth=2.8
)

plt.xlabel("Time (years)")
plt.ylabel("q output")
plt.title(
    "BLAST-Lite Fast-Calculation Example\n"
    "Compatibility-Adjusted Reproduction"
)

plt.grid(alpha=0.25)
plt.tight_layout()

plt.savefig(
    figure_path,
    dpi=220,
    bbox_inches="tight"
)

summary = {
    "battery_model":
        "Nmc111_Gr_Kokam75Ah_Battery",

    "SOC":
        "Constant 0.8",

    "temperature_C":
        45,

    "input_period_seconds":
        [0, 86399],

    "duration_years":
        5,

    "constant_input":
        True,

    "API_duration_argument":
        api_duration_argument,

    "method_signature":
        str(signature),

    "number_of_output_points":
        int(len(q)),

    "initial_q":
        float(q[0]),

    "final_q":
        float(q[-1]),

    "minimum_q":
        float(np.min(q)),

    "maximum_q":
        float(np.max(q)),

    "final_time_days":
        float(time_days[-1]),

    "final_time_years":
        float(time_years[-1])
}

with open(
    summary_path,
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        summary,
        file,
        indent=2
    )

print("Five-year simulation completed.")
print(json.dumps(summary, indent=2))
print("CSV:", csv_path)
print("Figure:", figure_path)
print("Summary:", summary_path)
