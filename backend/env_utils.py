# backend/env_utils.py
import gymnasium as gym
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from scheduler_env import EMSDispatchEnv
import numpy as np

def make_normalized_env(pv_series, load_series, price_series, weather_series=None):
    """
    Create EMSDispatchEnv wrapped in DummyVecEnv + VecNormalize for stable RL training.

    Returns:
        env: normalized vectorized environment ready for RL
        obs_dim: int, size of observation vector
    """

    def _init_env():
        return EMSDispatchEnv(
            pv_series=pv_series,
            load_series=load_series,
            grid_price_series=price_series,
            weather_series=weather_series
        )

    # Wrap environment
    env = DummyVecEnv([_init_env])

    # VecNormalize scales observations and rewards
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)

    # Automatic observation dimension
    obs_dim = env.observation_space.shape[0]

    return env, obs_dim

# Example usage:
# pv, load, price, weather = resample_align_relative(pv_df, load_df, weather_df)
# env, obs_dim = make_normalized_env(pv, load, price, weather)
# print("Observation dimension:", obs_dim)
