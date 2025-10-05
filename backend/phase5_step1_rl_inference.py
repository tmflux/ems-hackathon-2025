# phase5_env.py
import os
import pickle
from datetime import datetime
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecNormalize
from influxdb import InfluxDBClient

class RLInferenceEnv:
    def __init__(self, model_path, vecnorm_path):
        # --- Connect to InfluxDB ---
        INFLUX_HOST = os.getenv("INFLUXDB_HOST", "localhost")
        INFLUX_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
        INFLUX_DB = os.getenv("INFLUXDB_DB", "ems")
        INFLUX_USER = os.getenv("INFLUXDB_USER", "admin")
        INFLUX_PASSWORD = os.getenv("INFLUXDB_PASSWORD", "admin123")

        self.client = InfluxDBClient(
            host=INFLUX_HOST, port=INFLUX_PORT,
            username=INFLUX_USER, password=INFLUX_PASSWORD,
            database=INFLUX_DB
        )

        # Device IDs
        self.battery_id = "batt-01"
        self.pv_id = "pv-01"
        self.ev_id = "ev-01"

        # Load RL model
        self.model = PPO.load(model_path)
        with open(vecnorm_path, "rb") as f:
            self.vec_norm: VecNormalize = pickle.load(f)
        self.vec_norm.training = False
        self.vec_norm.norm_reward = False

    def get_latest(self, device_id, field):
        query = f'SELECT LAST("{field}") FROM telemetry WHERE "device_id" = \'{device_id}\''
        result = list(self.client.query(query).get_points())
        if result:
            return result[0].get("last")
        return 0.0

    def get_observation(self):
        pv_power = self.get_latest(self.pv_id, "power_kW")
        load_power = self.get_latest("load-01", "demand_kW")
        battery_soc = self.get_latest(self.battery_id, "soc")
        ev_soc = self.get_latest(self.ev_id, "ev_soc")
        grid_price = self.get_latest("grid-01", "price") or 3.0

        now = datetime.now()
        hour_of_day = now.hour + now.minute / 60.0
        day_of_week = now.weekday()

        obs = np.array([[pv_power, load_power, battery_soc, ev_soc, grid_price, hour_of_day, day_of_week]], dtype=np.float32)
        obs = self.vec_norm.normalize_obs(obs)
        return obs

    def predict_action(self, obs=None):
        if obs is None:
            obs = self.get_observation()
        action, _ = self.model.predict(obs, deterministic=True)
        return int(action[0])
