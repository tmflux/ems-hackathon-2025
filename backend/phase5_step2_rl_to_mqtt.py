import os
import time
import json
import math
import random
import logging
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

# %%
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulator")

# %%
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

client = mqtt.Client(client_id="simulator")

# -------------------------
# RL action storage
# -------------------------
rl_action = 0  # default action

def on_rl_action(client, userdata, msg):
    global rl_action
    try:
        payload = json.loads(msg.payload.decode())
        rl_action = payload.get("action", 0)
        logger.info(f"Received RL action: {rl_action}")
    except Exception as e:
        logger.exception("Failed to parse RL action: %s", e)

client.on_message = on_rl_action
client.connect(MQTT_HOST, MQTT_PORT)
client.subscribe("ems/site1/actions")
client.loop_start()

# %%
def iso_now():
    return datetime.now(timezone.utc).isoformat()

def publish(topic, payload):
    payload_str = json.dumps(payload)
    client.publish(topic, payload_str, qos=0)
    logger.debug("Published %s -> %s", topic, payload_str)

def generate_pv_power(t):
    hour = (t / 3600) % 24
    value = max(0, math.sin((hour - 6) / 24 * 2 * math.pi))  # 0..1
    return round(value * 5 * (0.7 + 0.6 * random.random()), 3)  # 0..~5 kW

# %%
def main_loop():
    start = time.time()
    soc = 80.0
    ev_soc = 40.0

    while True:
        t = time.time() - start

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
            "harmonics_thd": round(random.uniform(1.0, 4.0), 2)
        }
        publish("ems/site1/solar/telemetry", pv)

        # -------------------------
        # Battery telemetry (apply RL action)
        # -------------------------
        if rl_action == 1:  # Charge Battery
            soc = min(100.0, soc + 1.0)
        elif rl_action == 2:  # Discharge Battery
            soc = max(0.0, soc - 1.0)
        else:  # Balance / no RL effect
            if pv_power > 1.0:
                soc = min(100.0, soc + 0.05 * (pv_power / 5.0))
            else:
                soc = max(0.0, soc - 0.02 * (0.5 + random.random()))

        batt = {
            "ts": iso_now(),
            "device_id": "batt-01",
            "type": "battery",
            "soc": round(soc, 2),
            "soh": 92.0,
            "voltage": 48.0 + random.uniform(-0.5, 0.5),
            "current": round(random.uniform(-20, 20), 2),
            "temperature_C": round(35 + random.uniform(-5, 10), 1)
        }
        publish("ems/site1/battery/telemetry", batt)

        # -------------------------
        # EV telemetry (apply RL action)
        # -------------------------
        if rl_action == 3:  # Charge EV
            ev_soc = min(100.0, ev_soc + 2.0)
        else:
            if random.random() < 0.1:
                ev_soc = min(100.0, ev_soc + random.uniform(1, 5))
            else:
                ev_soc = max(0.0, ev_soc - random.uniform(0, 0.2))

        ev = {
            "ts": iso_now(),
            "device_id": "ev-01",
            "type": "ev_charger",
            "ev_soc": round(ev_soc, 2),
            "charging_power_kW": round(random.choice([0.0, 3.3, 6.6, 11.0]), 2),
            "plug_status": "plugged" if ev_soc < 95 else "idle",
            "temperature_C": round(30 + random.uniform(-3, 8), 1)
        }
        publish("ems/site1/ev/telemetry", ev)

        # Load telemetry
        load = {
            "ts": iso_now(),
            "device_id": "load-01",
            "type": "load",
            "demand_kW": round(random.uniform(1.0, 3.0), 2)
        }
        publish("ems/site1/load/telemetry", load)

        # Grid telemetry
        grid = {
            "ts": iso_now(),
            "device_id": "grid-01",
            "type": "grid",
            "price": random.choice([3.0, 5.0, 7.0])
        }
        publish("ems/site1/grid/telemetry", grid)

        # Log RL action applied
        logger.info(f"Applied RL action this loop: {rl_action}")

        time.sleep(5)

# %%
if __name__ == "__main__":
    try:
        logger.info("Starting simulator, connecting to %s:%s", MQTT_HOST, MQTT_PORT)
        main_loop()
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user")
