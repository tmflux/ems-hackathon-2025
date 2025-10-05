# backend/scheduler_env_v2.py
"""
Bulletproof EMS environment with strict physical constraints
"""
import gymnasium as gym
import numpy as np


class EMSDispatchEnv(gym.Env):
    """
    Energy Management System with STRICT physical constraints enforcement
    """
    metadata = {"render_modes": []}

    def __init__(self, pv_series, load_series, grid_price_series, weather_series=None,
                 init_batt_soc=0.5, init_ev_soc=0.5, timestep_minutes=5):
        super().__init__()

        # Data
        self.pv = np.array(pv_series, dtype=np.float32)
        self.load = np.array(load_series, dtype=np.float32)
        self.grid_price = np.array(grid_price_series, dtype=np.float32)
        self.weather = np.array(weather_series, dtype=np.float32) if weather_series is not None else None
        
        self.timestep_minutes = timestep_minutes
        self.timestep_hours = timestep_minutes / 60.0
        self.episode_len = len(self.pv)
        
        # State variables
        self.t = 0
        self.batt_soc = float(init_batt_soc)
        self.ev_soc = float(init_ev_soc)
        
        # System parameters (realistic commercial building)
        self.batt_capacity = 50.0   # kWh
        self.ev_capacity = 60.0     # kWh
        self.max_batt_power = 10.0  # kW
        self.max_ev_charge = 7.0    # kW
        self.batt_eff = 0.95
        self.ev_eff = 0.9
        
        # SOC limits (hard constraints)
        self.batt_soc_min = 0.10
        self.batt_soc_max = 0.95
        self.ev_soc_min = 0.05
        self.ev_soc_max = 0.95
        
        # Observation: [pv, load, batt_soc, ev_soc, price, hour_of_day, day_of_week]
        obs_len = 7
        self.observation_space = gym.spaces.Box(
            low=np.array([0, 0, 0, 0, 0, 0, 0], dtype=np.float32),
            high=np.array([3000, 3000, 1, 1, 20, 24, 7], dtype=np.float32),
            dtype=np.float32
        )
        
        # Simplified actions: 0=idle, 1=charge_batt, 2=discharge_batt, 3=charge_ev
        self.action_space = gym.spaces.Discrete(4)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.t = 0
        self.batt_soc = 0.5
        self.ev_soc = 0.5
        return self._get_obs(), {}

    def step(self, action):
        # Get current conditions
        pv = float(self.pv[self.t])
        load = float(self.load[self.t])
        price = float(self.grid_price[self.t])
        
        # Calculate surplus/deficit
        net_power = pv - load  # Positive = surplus, Negative = deficit
        
        # Initialize power flows
        batt_charge_power = 0.0  # Positive only
        batt_discharge_power = 0.0  # Positive only
        ev_charge_power = 0.0
        grid_import = 0.0
        grid_export = 0.0
        
        # Action logic with physical constraints
        if action == 0:  # Idle - just balance with grid
            if net_power >= 0:
                grid_export = net_power
            else:
                grid_import = abs(net_power)
                
        elif action == 1:  # Charge battery
            if self.batt_soc < self.batt_soc_max:
                # Calculate max chargeable energy
                max_energy = (self.batt_soc_max - self.batt_soc) * self.batt_capacity
                max_power = min(self.max_batt_power, max_energy / self.timestep_hours)
                
                if net_power > 0:
                    # Charge from surplus solar
                    batt_charge_power = min(max_power, net_power)
                    remaining = net_power - batt_charge_power
                    if remaining > 0:
                        grid_export = remaining
                    else:
                        grid_import = abs(remaining)
                else:
                    # Would need grid to charge - only do if cheap
                    if price < 3.0:
                        batt_charge_power = max_power
                    grid_import = abs(net_power) + batt_charge_power
                    
        elif action == 2:  # Discharge battery
            if self.batt_soc > self.batt_soc_min:
                # Calculate max dischargeable energy
                max_energy = (self.batt_soc - self.batt_soc_min) * self.batt_capacity
                max_power = min(self.max_batt_power, max_energy / self.timestep_hours)
                
                if net_power < 0:
                    # Use battery to meet deficit
                    batt_discharge_power = min(max_power, abs(net_power))
                    remaining_deficit = abs(net_power) - batt_discharge_power
                    if remaining_deficit > 0:
                        grid_import = remaining_deficit
                else:
                    # Surplus situation - no need to discharge
                    grid_export = net_power
                    
        elif action == 3:  # Charge EV
            if self.ev_soc < self.ev_soc_max:
                max_energy = (self.ev_soc_max - self.ev_soc) * self.ev_capacity
                max_power = min(self.max_ev_charge, max_energy / self.timestep_hours)
                
                if net_power > 0:
                    ev_charge_power = min(max_power, net_power)
                    remaining = net_power - ev_charge_power
                    if remaining > 0:
                        grid_export = remaining
                    else:
                        grid_import = abs(remaining)
                else:
                    # Only charge EV from grid if cheap
                    if price < 4.0:
                        ev_charge_power = max_power
                    grid_import = abs(net_power) + ev_charge_power
        
        # Update battery SOC
        old_batt_soc = self.batt_soc
        if batt_charge_power > 0:
            energy_in = batt_charge_power * self.timestep_hours * self.batt_eff
            self.batt_soc += energy_in / self.batt_capacity
        if batt_discharge_power > 0:
            energy_out = batt_discharge_power * self.timestep_hours / self.batt_eff
            self.batt_soc -= energy_out / self.batt_capacity
        
        # CRITICAL: Enforce hard limits
        self.batt_soc = float(np.clip(self.batt_soc, 0.0, 1.0))
        
        # Update EV SOC
        old_ev_soc = self.ev_soc
        if ev_charge_power > 0:
            energy_in = ev_charge_power * self.timestep_hours * self.ev_eff
            self.ev_soc += energy_in / self.ev_capacity
        
        self.ev_soc = float(np.clip(self.ev_soc, 0.0, 1.0))
        
        # Reward calculation
        reward = self._calculate_reward(
            pv, load, price, net_power,
            batt_charge_power, batt_discharge_power,
            ev_charge_power, grid_import, grid_export,
            old_batt_soc, old_ev_soc
        )
        
        # Advance time
        self.t += 1
        terminated = (self.t >= self.episode_len)
        truncated = False
        
        # Get next observation
        next_obs = self._get_obs()
        
        # Info for debugging
        info = {
            'batt_soc': self.batt_soc,
            'ev_soc': self.ev_soc,
            'grid_import': grid_import,
            'grid_export': grid_export,
        }
        
        return next_obs, reward, terminated, truncated, info

    def _calculate_reward(self, pv, load, price, net_power,
                         batt_charge, batt_discharge, ev_charge,
                         grid_import, grid_export,
                         old_batt_soc, old_ev_soc):
        """Calculate reward based on economic and operational objectives"""
        reward = 0.0
        
        # 1. Grid cost (primary objective)
        grid_cost = grid_import * price * self.timestep_hours
        grid_revenue = grid_export * price * 0.5 * self.timestep_hours  # Sell at 50% of buy price
        reward -= grid_cost * 0.1
        reward += grid_revenue * 0.1
        
        # 2. Solar utilization bonus
        solar_self_consumption = min(pv, load + batt_charge + ev_charge)
        solar_utilization_ratio = solar_self_consumption / (pv + 0.001)
        reward += solar_utilization_ratio * 1.0
        
        # 3. Battery usage rewards
        if batt_charge > 0 and net_power > 0:
            # Storing excess solar - increase reward
            reward += 2.0
        if batt_discharge > 0 and net_power < 0:
            # Using battery instead of grid during deficit
            reward += 2.0
            
        # 4. Battery health (keep in middle range)
        if 0.3 <= self.batt_soc <= 0.7:
            reward += 0.3
        if self.batt_soc < 0.15 or self.batt_soc > 0.90:
            reward -= 0.5
            
        # 5. Peak shaving bonus (avoid high grid import during peak hours)
        hour = (self.t * self.timestep_minutes) % 1440 / 60
        if 17 <= hour <= 21:  # Peak hours
            if grid_import > 20:
                reward -= 2.0  # Heavy penalty for peak usage
            elif grid_import < 5:
                reward += 1.0  # Bonus for avoiding peak
                
        # 6. EV charging optimization
        if ev_charge > 0:
            if price < 3.0:
                reward += 0.5  # Good time to charge
            elif price > 6.0:
                reward -= 0.5  # Expensive charging
        
        return reward

    def _get_obs(self):
        """Get current observation"""
        if self.t >= self.episode_len:
            return np.zeros(self.observation_space.shape, dtype=np.float32)
        
        pv = self.pv[self.t]
        load = self.load[self.t]
        price = self.grid_price[self.t]
        
        # Time features
        hour_of_day = (self.t * self.timestep_minutes) % 1440 / 60  # 0-24
        day_of_week = ((self.t * self.timestep_minutes) // 1440) % 7  # 0-6
        
        obs = np.array([
            pv, load,
            self.batt_soc, self.ev_soc,
            price,
            hour_of_day, day_of_week
        ], dtype=np.float32)
        
        return obs