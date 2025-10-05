# backend/scheduler_train_phase4.py
"""
UPDATED: Use scheduler_env_v2.py (bulletproof version)
"""
import numpy as np
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
from scheduler_env import EMSDispatchEnv  # Use v2!
from scheduler_train import prepare_series
from collections import Counter
from custom_vec_normalize import NoObsNormalize

# Prepare data
pv_arr, load_arr, price_arr, weather_arr = prepare_series()

# Train/Val/Test Split
def split_series(pv, load, price, train_ratio=0.7, val_ratio=0.15):
    n = len(pv)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    pv_train, pv_val, pv_test = pv[:train_end], pv[train_end:val_end], pv[val_end:]
    load_train, load_val, load_test = load[:train_end], load[train_end:val_end], load[val_end:]
    price_train, price_val, price_test = price[:train_end], price[train_end:val_end], price[val_end:]

    print(f"Split lengths -> Train: {len(pv_train)}, Val: {len(pv_val)}, Test: {len(pv_test)}")
    return (pv_train, load_train, price_train), (pv_val, load_val, price_val), (pv_test, load_test, price_test)

train_data, val_data, test_data = split_series(pv_arr, load_arr, price_arr)

# Create environment factory
def make_env(pv, load, price, weather=None, timestep_minutes=5):
    """
    Set timestep_minutes=1 if your data is 1-minute intervals,
    or timestep_minutes=5 if it's 5-minute intervals
    """
    def _init():
        return EMSDispatchEnv(pv, load, price, weather, timestep_minutes=timestep_minutes)
    return _init

# Training environment with normalization
print("Creating training environment...")
train_env = DummyVecEnv([make_env(*train_data, weather_arr, timestep_minutes=5)])
# CRITICAL FIX: Only normalize rewards, NOT observations
# This prevents SOC values from being scaled beyond [0,1]
train_env = NoObsNormalize(
    train_env,
    norm_reward=True,  # Normalize rewards only
    clip_reward=10.0,
    gamma=0.99
)
print("✓ Using NoObsNormalize - SOC values will stay in [0,1]")

# Create validation environment for callbacks
val_env = DummyVecEnv([make_env(*val_data, weather_arr, timestep_minutes=5)])
val_env = NoObsNormalize(val_env, norm_reward=True, training=False)

# Callbacks for monitoring
eval_callback = EvalCallback(
    val_env,
    best_model_save_path='./ems_best_model/',
    log_path='./ems_eval_logs/',
    eval_freq=10000,  # Evaluate every 10k steps
    deterministic=True,
    render=False
)

checkpoint_callback = CheckpointCallback(
    save_freq=50000,
    save_path='./ems_checkpoints/',
    name_prefix='ems_model'
)

# Train with improved hyperparameters
print("Starting training...")
model = PPO(
    'MlpPolicy',
    train_env,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.01,  # Encourage exploration
    vf_coef=0.5,
    max_grad_norm=0.5,
    verbose=1,
    tensorboard_log="./ppo_ems_logs/"
)

model.learn(
    total_timesteps=200_000,
    callback=[eval_callback, checkpoint_callback],
    progress_bar=True
)

model.save("ems_ppo_model_fixed")
train_env.save("ems_vecnormalize_fixed.pkl")
print("Model saved!")

def evaluate(env, model, collect_data=True):
    """
    Evaluate with direct access to environment info dict
    """
    obs = env.reset()
    total_reward = 0

    batt_socs, ev_socs, grid_imports, actions = [], [], [], []
    pv_vals, load_vals = [], []

    done = [False]

    while not done[0]:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, info = env.step(action)
        
        total_reward += float(reward[0])

        if collect_data and len(info) > 0:
            # Get TRUE SOC from environment info dict, not from observation
            actual_info = info[0] if isinstance(info, list) else info
            batt_socs.append(float(actual_info.get('batt_soc', obs[0][2])))
            ev_socs.append(float(actual_info.get('ev_soc', obs[0][3])))
            grid_imports.append(float(actual_info.get('grid_import', 0)))
            actions.append(int(action[0]))
            pv_vals.append(float(obs[0][0]))
            load_vals.append(float(obs[0][1]))

    return total_reward, batt_socs, ev_socs, grid_imports, actions, pv_vals, load_vals

# Validation
print("\nEvaluating on validation set...")
val_env_eval = DummyVecEnv([make_env(*val_data, weather_arr, timestep_minutes=5)])
val_env_eval = NoObsNormalize(val_env_eval, norm_reward=True, training=False)
val_env_eval.ret_rms = train_env.ret_rms  # Share reward statistics

val_reward, val_batt, val_ev, val_grid, val_actions, val_pv, val_load = evaluate(val_env_eval, model)
print(f"Validation reward: {val_reward:.2f}")
print(f"Validation action distribution: {Counter(val_actions)}")

# Test
print("\nEvaluating on test set...")
test_env = DummyVecEnv([make_env(*test_data, weather_arr, timestep_minutes=5)])
test_env = NoObsNormalize(test_env, norm_reward=True, training=False)
test_env.ret_rms = train_env.ret_rms

test_reward, test_batt, test_ev, test_grid, test_actions, test_pv, test_load = evaluate(test_env, model)
print(f"Test reward: {test_reward:.2f}")
print(f"Test action distribution: {Counter(test_actions)}")

# Enhanced Plots
fig, axes = plt.subplots(3, 1, figsize=(16, 10))
t = range(len(test_pv))

# Plot 1: Power flows
ax1 = axes[0]
ax1.plot(t, test_pv, label="PV Generation", alpha=0.7, linewidth=1)
ax1.plot(t, test_load, label="Load Demand", alpha=0.7, linewidth=1)
ax1.fill_between(t, 0, test_grid, label="Grid Usage", alpha=0.3)
ax1.set_ylabel("Power (normalized)")
ax1.set_title("Power Flows - Test Set")
ax1.legend(loc='upper right')
ax1.grid(alpha=0.3)

# Plot 2: Battery and EV SOC
ax2 = axes[1]
ax2.plot(t, test_batt, label="Battery SOC", linewidth=2, color='blue')
ax2.plot(t, test_ev, label="EV SOC", linewidth=2, color='green')
ax2.axhline(y=0.2, color='red', linestyle='--', alpha=0.5, label='Battery Min (20%)')
ax2.axhline(y=0.8, color='orange', linestyle='--', alpha=0.5, label='Battery Max (80%)')
ax2.set_ylabel("State of Charge")
ax2.set_title("Battery and EV State of Charge")
ax2.legend(loc='upper right')
ax2.grid(alpha=0.3)
ax2.set_ylim(0, 1.05)

# Plot 3: Actions
ax3 = axes[2]
ax3.step(t, test_actions, where='post', color='purple', linewidth=1.5)
ax3.set_xlabel("Time step")
ax3.set_ylabel("Action")
ax3.set_title("RL Agent Actions (0=idle, 1=charge batt, 2=discharge batt, 3=charge EV)")
ax3.set_yticks([0, 1, 2, 3])
ax3.grid(alpha=0.3)

plt.tight_layout()
plt.savefig("test_simulation_fixed.png", dpi=150)
plt.show()

# Action statistics
print("\n=== Action Analysis ===")
for action_id in range(5):
    count = val_actions.count(action_id)
    percentage = (count / len(val_actions)) * 100
    action_names = ['Balance', 'Charge Batt', 'Discharge Batt', 'Charge EV', 'Grid Supply']
    print(f"Action {action_id} ({action_names[action_id]}): {count} times ({percentage:.1f}%)")

print("\n=== Battery Statistics ===")
print(f"Average SOC: {np.mean(test_batt):.2%}")
print(f"Min SOC: {np.min(test_batt):.2%}")
print(f"Max SOC: {np.max(test_batt):.2%}")
print(f"Time in healthy range (20-80%): {np.sum((np.array(test_batt) >= 0.2) & (np.array(test_batt) <= 0.8)) / len(test_batt):.1%}")

# Check for SOC violations
if np.min(test_batt) < -0.01 or np.max(test_batt) > 1.01:
    print("\n⚠️  WARNING: Battery SOC violated physical constraints!")
    print(f"   SOC should be in [0, 1], but got [{np.min(test_batt):.3f}, {np.max(test_batt):.3f}]")
    print("   Check environment implementation - SOC should be clamped.")
else:
    print("\n✓ Battery SOC stayed within physical limits [0, 1]")

print("\nTraining complete!")

