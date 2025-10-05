# backend/custom_vec_normalize.py
"""
Custom VecNormalize that doesn't normalize battery/EV SOC values.
Only normalizes: PV, Load, Price, Weather
Keeps SOC in [0,1] range for the agent to see properly.
"""
import numpy as np
from stable_baselines3.common.vec_env import VecNormalize


class SelectiveVecNormalize(VecNormalize):
    """
    VecNormalize that skips normalization for specific observation indices.
    
    For EMS environment:
    - obs[0] = PV (normalize)
    - obs[1] = Load (normalize)
    - obs[2] = Battery SOC (DO NOT normalize - keep in [0,1])
    - obs[3] = EV SOC (DO NOT normalize - keep in [0,1])
    - obs[4] = Price (normalize)
    - obs[5+] = Weather (normalize)
    """
    
    def __init__(self, venv, skip_indices=(2, 3), **kwargs):
        """
        Args:
            venv: Vectorized environment
            skip_indices: Tuple of observation indices to skip normalization
        """
        super().__init__(venv, **kwargs)
        self.skip_indices = set(skip_indices)
        
    def normalize_obs(self, obs, update=True):
        """
        Normalize observations except for skip_indices
        """
        if not self.norm_obs:
            return obs
            
        # Create mask for indices to normalize
        normalized_obs = obs.copy()
        
        for i in range(obs.shape[1]):  # For each observation dimension
            if i not in self.skip_indices:
                # Apply standard normalization
                if update:
                    self.obs_rms.update(obs[:, i:i+1])
                normalized_obs[:, i] = np.clip(
                    (obs[:, i] - self.obs_rms.mean[i]) / np.sqrt(self.obs_rms.var[i] + self.epsilon),
                    -self.clip_obs,
                    self.clip_obs
                )
            # else: keep original value (SOC stays in [0,1])
        
        return normalized_obs


class NoObsNormalize(VecNormalize):
    """
    VecNormalize that ONLY normalizes rewards, not observations.
    Use this if selective normalization doesn't work.
    """
    
    def __init__(self, venv, **kwargs):
        # Force norm_obs=False
        kwargs['norm_obs'] = False
        super().__init__(venv, **kwargs)
        
    def normalize_obs(self, obs, update=True):
        """Don't normalize observations at all"""
        return obs