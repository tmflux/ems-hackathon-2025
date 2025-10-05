# backend/scheduler_train.py
import sys
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from scheduler_env import EMSDispatchEnv
from data_loaders import (
    load_kaggle_generation,
    load_kaggle_weather,       # added weather loader
    load_mendeley_all,
    resample_align_relative     # updated version that truncates by length & normalizes
)

def prepare_series():
    """
    Load PV, demand, and optional weather, align and normalize for RL.

    Returns:
        pv_arr, load_arr, price_arr, weather_arr
    """
    print("📥 Entered prepare_series()", flush=True)

    # Load PV
    pv_df = load_kaggle_generation(
        r"D:\ems-hackathon-2025\backend\data\Kaggle\Plant_1_Generation_Data.csv"
    )
    print("PV DF shape:", pv_df.shape, flush=True)

    # Load Demand
    demand_df = load_mendeley_all(
        r"D:\ems-hackathon-2025\backend\data\Mendeley\Electricity Demand, Solar and Wind Generation Data",
        year=None
    )
    print("Demand DF shape:", demand_df.shape, flush=True)

    # Load Weather
    weather_df = load_kaggle_weather(
        r"D:\ems-hackathon-2025\backend\data\Kaggle\Plant_1_Weather_Sensor_Data.csv"
    )
    print("Weather DF shape:", weather_df.shape if weather_df is not None else "None", flush=True)

    # Check datasets
    if pv_df.empty:
        raise RuntimeError("PV dataset is empty.")
    if demand_df.empty:
        raise RuntimeError("Demand dataset is empty.")

    # Alignment + normalization
    pv_arr, load_arr, price_arr, weather_arr = resample_align_relative(
        pv_df, demand_df, weather_df
    )

    print(f"✅ Final lengths: PV={len(pv_arr)}, Load={len(load_arr)}, Price={len(price_arr)}, "
          f"Weather={len(weather_arr) if weather_arr is not None else 'None'}", flush=True)

    return pv_arr, load_arr, price_arr, weather_arr


if __name__ == "__main__":
    prepare_series()
