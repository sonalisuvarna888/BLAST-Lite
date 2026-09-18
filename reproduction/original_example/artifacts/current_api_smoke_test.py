
import inspect
import numpy as np
import matplotlib
matplotlib.use("Agg")

from blast.models import (
    Nmc111_Gr_Kokam75Ah_Battery
)

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

print("Current method signature:")
print(signature)

kwargs = {
    "is_constant_input": True
}

if "threshold_time" in parameter_names:
    kwargs["threshold_time"] = 0.1
    selected_duration_argument = (
        "threshold_time=0.1"
    )

elif "simulation_years" in parameter_names:
    kwargs["simulation_years"] = 0.1
    selected_duration_argument = (
        "simulation_years=0.1"
    )

else:
    raise RuntimeError(
        "No supported duration argument found in "
        "simulate_battery_life."
    )

print("Duration argument selected:")
print(selected_duration_argument)

battery.simulate_battery_life(
    inputs,
    **kwargs
)

q = np.atleast_1d(
    np.asarray(
        battery.outputs["q"]
    ).squeeze()
)

time_days = np.atleast_1d(
    np.asarray(
        battery.stressors["t_days"]
    ).squeeze()
)

print("Smoke test completed.")
print("Output keys:", list(battery.outputs.keys()))
print("Stressor keys:", list(battery.stressors.keys()))
print("Number of q points:", len(q))
print("Initial q:", float(q[0]))
print("Final q:", float(q[-1]))
print("Final time in days:", float(time_days[-1]))
print("Final time in years:", float(time_days[-1] / 365))
