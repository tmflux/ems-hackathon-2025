# mqtt_data_simulator_rl.py

import os
import time
import json
import math
import random
import logging
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulator")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

client = mqtt.Client(client_id="simulator")

# RL action storage
rl_action = 0

def on_rl_action(client, userdata, msg):
    global rl_action
    try:
        payload = json.loads(msg.payload.decode())
        rl_action = payload.get("action", 0)
        logger.info(f"✅ Received RL action: {rl_action}")
    except Exception as e:
        logger.exception("Failed to parse RL action: %s", e)

client.on_message = on_rl_action
client.connect(MQTT_HOST, MQTT_PORT)
client.subscribe("ems/site1/actions")
client.loop_start()

def iso_now():
    return datetime.now(timezone.utc).isoformat()

def publish(topic, payload):
    payload_str = json.dumps(payload)
    client.publish(topic, payload_str, qos=0)

def generate_pv_power(t):
    hour = (t / 3600) % 24
    value = max(0, math.sin((hour - 6) / 24 * 2 * math.pi))
    return round(value * 5 * (0.7 + 0.6 * random.random()), 3)

# CRITICAL SCENARIOS
SCENARIOS = [
    {
        "name": "Battery Critical Low",
        "trigger_time": 60,
        "condition": lambda soc, ev_soc, price: soc < 15,
        "message": "🚨 CRITICAL: Battery SoC dropped below 15%!"
    },
    {
        "name": "High Grid Price + Low Battery",
        "trigger_time": 120,
        "condition": lambda soc, ev_soc, price: price > 6 and soc < 40,
        "message": "⚠️ WARNING: High grid prices with low battery!"
    },
    {
        "name": "EV Needs Urgent Charge",
        "trigger_time": 180,
        "condition": lambda soc, ev_soc, price: ev_soc < 20,
        "message": "🚗 ALERT: EV battery critically low!"
    },
    {
        "name": "Peak Demand Hour",
        "trigger_time": 240,
        "condition": lambda soc, ev_soc, price: price >= 7,
        "message": "⚡ PEAK HOUR: Maximum grid prices!"
    }
]

def main_loop():
    start = time.time()
    soc = 80.0
    ev_soc = 40.0
    scenario_triggered = {s["name"]: False for s in SCENARIOS}

    iteration = 0
    while True:
        t = time.time() - start
        iteration += 1

        # Trigger critical scenarios
        for scenario in SCENARIOS:
            if t >= scenario["trigger_time"] and not scenario_triggered[scenario["name"]]:
                logger.warning(f"\n{'='*60}")
                logger.warning(f"🎯 SCENARIO TRIGGERED: {scenario['name']}")
                logger.warning(scenario["message"])
                logger.warning(f"{'='*60}\n")
                scenario_triggered[scenario["name"]] = True

        # Generate time-based conditions
        hour = (t / 3600) % 24

        # Simulate grid price variations
        if 17 <= hour <= 21:  # Peak hours
            grid_price = 7.0
        elif 22 <= hour or hour <= 6:  # Off-peak
            grid_price = 3.0
        else:
            grid_price = 5.0

        # Add random spikes
        if random.random() < 0.1:
            grid_price = random.choice([7.0, 7.0, 5.0])

        # PV telemetry
        pv_power = generate_pv_power(time.time())
        pv = {
            "ts": iso_now(),
            "device_id": "pv-01",
            "type": "solar_inverter",
            "power_kW": pv_power,
            "voltage": round(400 + random.uniform(-5, 5), 2),
            "current": round((pv_power / max(0.1, 400/1000)) + random.uniform(-0.2, 0.2), 2),
            "temperature_C": round(30 + random.uniform(-5, 10), 1),
            "harmonics_thd": round(random.uniform(1.0, 4.0), 2),
            "rl_action": rl_action   # 👈 include RL action
        }
        publish("ems/site1/solar/telemetry", pv)

        # Battery behavior based on RL action
        old_soc = soc
        if rl_action == 1:  # Charge Battery
            soc = min(100.0, soc + 2.0)
            logger.info(f"🔋 RL Charging Battery: {old_soc:.1f}% → {soc:.1f}%")
        elif rl_action == 2:  # Discharge Battery
            soc = max(0.0, soc - 2.0)
            logger.info(f"🔋 RL Discharging Battery: {old_soc:.1f}% → {soc:.1f}%")
        else:  # Natural drift
            if pv_power > 1.0:
                soc = min(100.0, soc + 0.1 * (pv_power / 5.0))
            else:
                soc = max(0.0, soc - 0.1 * (1 + random.random()))

        # Force critical low battery after 1 minute
        if 50 < t < 80 and soc > 15:
            soc = max(12.0, soc - 3.0)

        batt = {
            "ts": iso_now(),
            "device_id": "batt-01",
            "type": "battery",
            "soc": round(soc, 2),
            "soh": 92.0,
            "voltage": 48.0 + random.uniform(-0.5, 0.5),
            "current": round(random.uniform(-20, 20), 2),
            "temperature_C": round(35 + random.uniform(-5, 10), 1),
            "rl_action": rl_action   # 👈 include RL action
        }
        publish("ems/site1/battery/telemetry", batt)

        # EV behavior based on RL action
        old_ev_soc = ev_soc
        if rl_action == 3:  # Charge EV
            ev_soc = min(100.0, ev_soc + 3.0)
            logger.info(f"🚗 RL Charging EV: {old_ev_soc:.1f}% → {ev_soc:.1f}%")
        else:
            if random.random() < 0.05:
                ev_soc = min(100.0, ev_soc + random.uniform(0.5, 2))
            else:
                ev_soc = max(0.0, ev_soc - random.uniform(0.1, 0.3))

        # Force EV critical after 3 minutes
        if 170 < t < 200 and ev_soc > 20:
            ev_soc = max(15.0, ev_soc - 2.0)

        ev = {
            "ts": iso_now(),
            "device_id": "ev-01",
            "type": "ev_charger",
            "ev_soc": round(ev_soc, 2),
            "charging_power_kW": 3.3 if rl_action == 3 else 0.0,
            "plug_status": "plugged" if ev_soc < 95 else "idle",
            "temperature_C": round(30 + random.uniform(-3, 8), 1),
            "rl_action": rl_action   # 👈 include RL action
        }
        publish("ems/site1/ev/telemetry", ev)

        # Load telemetry
        base_load = 1.5
        if 8 <= hour <= 10 or 18 <= hour <= 21:
            base_load = 2.5
        load = {
            "ts": iso_now(),
            "device_id": "load-01",
            "type": "load",
            "demand_kW": round(base_load + random.uniform(-0.3, 0.5), 2),
            "rl_action": rl_action   # 👈 optional, include if you want RL overlay on load chart
        }
        publish("ems/site1/load/telemetry", load)

        # Grid telemetry
        grid = {
            "ts": iso_now(),
            "device_id": "grid-01",
            "type": "grid",
            "price": grid_price,
            "rl_action": rl_action   # 👈 optional
        }
        publish("ems/site1/grid/telemetry", grid)

        # Check if scenarios are being handled by RL
        for scenario in SCENARIOS:
            if scenario_triggered[scenario["name"]] and scenario["condition"](soc, ev_soc, grid_price):
                logger.info(f"⏳ Waiting for RL Agent to respond to: {scenario['name']} (Action: {rl_action})")

        # Status log every 10 iterations
        if iteration % 10 == 0:
            logger.info(f"\n📊 Status | Batt: {soc:.1f}% | EV: {ev_soc:.1f}% | PV: {pv_power:.2f}kW | Price: ${grid_price} | RL: {rl_action}")

        time.sleep(5)

if __name__ == "__main__":
    try:
        logger.info("🚀 Starting ENHANCED simulator with critical scenarios")
        logger.info("=" * 60)
        main_loop()
    except KeyboardInterrupt:
        logger.info("\n✋ Simulator stopped by user")