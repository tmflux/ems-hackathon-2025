# %% Imports
import os
import json
import logging
import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from influxdb import InfluxDBClient
import paho.mqtt.client as mqtt
from phase5_step1_rl_inference import RLInferenceEnv
from datetime import timezone

# Near the top with other globals
current_rl_action = 0
# %% Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

# %% Config from environment
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

INFLUX_HOST = os.getenv("INFLUXDB_HOST", "influxdb")
INFLUX_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
INFLUX_DB = os.getenv("INFLUXDB_DB", "ems")
INFLUX_USER = os.getenv("INFLUXDB_USER", "admin")
INFLUX_PASSWORD = os.getenv("INFLUXDB_PASSWORD", "admin123")

# Global clients
influx_client: Optional[InfluxDBClient] = None
mqtt_client: Optional[mqtt.Client] = None
rl_env: Optional[RLInferenceEnv] = None

# Connected WebSocket clients
connected_clients: list[WebSocket] = []

# Event loop for async operations
main_loop = None

# %% Helper functions
def to_float_safe(v):
    try:
        return float(v)
    except Exception:
        return None

async def broadcast(message: dict):
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception as e:
            logger.warning("Failed to send to client: %s", e)
            disconnected.append(ws)
    for ws in disconnected:
        try:
            connected_clients.remove(ws)
        except ValueError:
            pass

# Updated on_connect to subscribe RL actions
def on_connect(client, userdata, flags, rc):
    logger.info("Connected to MQTT broker with rc=%s", rc)
    client.subscribe("ems/+/+/telemetry")
    client.subscribe("ems/site1/actions")  # RL action subscription

# Updated on_message to handle RL actions
def on_message(client, userdata, msg):
    global influx_client, main_loop, current_rl_action

    # Handle RL action updates
    if msg.topic == "ems/site1/actions":
        try:
            payload = json.loads(msg.payload.decode())
            current_rl_action = payload.get("action", 0)
            logger.info(f"RL Action Updated: {current_rl_action}")
        except Exception as e:
            logger.exception("Failed to parse RL action: %s", e)
        return

    # Parse telemetry payload
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
    except Exception as e:
        logger.exception("Malformed MQTT payload: %s", e)
        return

    device_id = data.get("device_id", "unknown")
    dev_type = data.get("type", "unknown")
    timestamp = data.get("ts")

    # Extract numeric fields for InfluxDB
    fields = {
        k: to_float_safe(v)
        for k, v in data.items()
        if k not in ("device_id", "type", "ts") and to_float_safe(v) is not None
    }

    if fields:
        point = {
            "measurement": "telemetry",
            "tags": {"device_id": device_id, "type": dev_type},
            "fields": fields,
        }
        if timestamp:
            point["time"] = timestamp

        try:
            influx_client.write_points([point])
            logger.debug("Wrote point for %s: %s", device_id, fields)
        except Exception as e:
            logger.exception("Failed to write to InfluxDB: %s", e)

    # Broadcast the full original payload, preserving rl_action
    if connected_clients and main_loop:
        try:
            message = data.copy()
            # ensure rl_action is always present (from payload or global fallback)
            if "rl_action" not in message:
                message["rl_action"] = current_rl_action
            asyncio.run_coroutine_threadsafe(
                broadcast(message),
                main_loop
            )
        except Exception as e:
            logger.error("Failed to schedule broadcast: %s", e)
# %% Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    global influx_client, mqtt_client, rl_env, main_loop

    main_loop = asyncio.get_event_loop()

    influx_client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER,
        password=INFLUX_PASSWORD,
        database=INFLUX_DB,
    )
    try:
        influx_client.create_database(INFLUX_DB)
    except Exception:
        pass

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT)
    mqtt_client.loop_start()

    rl_model_path = "./ems_ppo_model_fixed.zip"
    vecnorm_path = "./ems_vecnormalize_fixed.pkl"
    try:
        rl_env = RLInferenceEnv(rl_model_path, vecnorm_path)
        logger.info("RL Inference environment initialized")
    except Exception as e:
        logger.exception("Failed to initialize RL Inference: %s", e)

    logger.info("Backend started: MQTT -> InfluxDB ingestion active")
    yield

    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

# %% FastAPI app
app = FastAPI(title="EMS Backend (ingestion)", lifespan=lifespan)

origins = [
    "http://localhost:5173", 
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket endpoint and other routes remain unchanged...

# %% WebSocket endpoint (SINGLE DEFINITION)
@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    logger.info(f"WebSocket client connected. Total clients: {len(connected_clients)}")
    
    try:
        # Send initial data
        try:
            result = influx_client.query('SELECT LAST(*) FROM telemetry GROUP BY "device_id"')
            output = []
            for (measurement, tags), points in result.items():
                for p in points:
                    p.update(tags)
                    output.append(p)
            if output:
                await ws.send_json({"type": "initial", "data": output})
        except Exception as e:
            logger.error(f"Failed to send initial data: {e}")
        
        # Keep connection alive
        while True:
            try:
                # Receive any messages (heartbeat/ping)
                data = await ws.receive_text()
                logger.debug(f"Received from client: {data}")
            except Exception:
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)
        logger.info(f"WebSocket client removed. Remaining clients: {len(connected_clients)}")

# %% Routes

@app.get("/")
def root():
    return {
        "status": "ok", 
        "note": "EMS ingestion backend running",
        "websocket_clients": len(connected_clients)
    }

@app.get("/metrics/latest")
def metrics_latest(device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id required")
    query = f'SELECT * FROM telemetry WHERE "device_id" = \'{device_id}\' ORDER BY time DESC LIMIT 1'
    try:
        result = influx_client.query(query)
        points = list(result.get_points(measurement="telemetry"))
        if not points:
            return {"device_id": device_id, "found": False}
        return {"device_id": device_id, "found": True, "point": points[0]}
    except Exception as e:
        logger.exception("Query failed: %s", e)
        raise HTTPException(status_code=500, detail="Query failed")

@app.get("/metrics/live")
def get_live_metrics():
    try:
        result = influx_client.query('SELECT LAST(*) FROM telemetry GROUP BY "device_id"')
        output = []
        for (measurement, tags), points in result.items():
            for p in points:
                p.update(tags)
                output.append(p)
        return output
    except Exception as e:
        logger.exception("Query failed: %s", e)
        raise HTTPException(status_code=500, detail="Query failed")

@app.get("/alerts")
def get_alerts():
    alerts = []
    try:
        # Battery checks
        batt_query = "SELECT LAST(soc) AS soc, LAST(temperature_C) AS temp FROM telemetry WHERE device_id='batt-01'"
        batt_result = list(influx_client.query(batt_query).get_points())
        if batt_result:
            soc = batt_result[0].get("soc")
            temp = batt_result[0].get("temp")
            if soc is not None and soc < 20:
                alerts.append({"device_id": "batt-01", "alert": "Critical: SoC too low"})
            if temp is not None and temp > 80:
                alerts.append({"device_id": "batt-01", "alert": "Battery overheating"})

        # Inverter checks
        inv_query = "SELECT LAST(temperature_C) AS temp FROM telemetry WHERE device_id='pv-01'"
        inv_result = list(influx_client.query(inv_query).get_points())
        if inv_result and inv_result[0].get("temp", 0) > 80:
            alerts.append({"device_id": "pv-01", "alert": "Inverter overheating"})

        # EV checks
        ev_query = "SELECT LAST(charging_power_kW) AS power, LAST(plug_status) AS plug FROM telemetry WHERE device_id='ev-01'"
        ev_result = list(influx_client.query(ev_query).get_points())
        if ev_result:
            power = ev_result[0].get("power")
            plug = ev_result[0].get("plug")
            if plug == "plugged" and (power is None or power == 0):
                alerts.append({"device_id": "ev-01", "alert": "EV plugged but not charging"})

    except Exception as e:
        logger.exception("Alert evaluation failed: %s", e)
        raise HTTPException(status_code=500, detail="Alert evaluation failed")

    return {"alerts": alerts}

@app.get("/health")
def get_health_index():
    health = {"pv-01": 100, "batt-01": 100, "ev-01": 100}
    try:
        # Battery penalties
        batt_query = "SELECT LAST(soc) AS soc, LAST(temperature_C) AS temp FROM telemetry WHERE device_id='batt-01'"
        batt_result = list(influx_client.query(batt_query).get_points())
        if batt_result:
            soc = batt_result[0].get("soc")
            temp = batt_result[0].get("temp")
            if soc is not None and soc < 20: health["batt-01"] -= 30
            if temp is not None and temp > 80: health["batt-01"] -= 20

        # Inverter penalties
        inv_query = "SELECT LAST(temperature_C) AS temp FROM telemetry WHERE device_id='pv-01'"
        inv_result = list(influx_client.query(inv_query).get_points())
        if inv_result and inv_result[0].get("temp",0) > 80: health["pv-01"] -= 20

        # EV penalties
        ev_query = "SELECT LAST(charging_power_kW) AS power, LAST(plug_status) AS plug FROM telemetry WHERE device_id='ev-01'"
        ev_result = list(influx_client.query(ev_query).get_points())
        if ev_result:
            power = ev_result[0].get("power")
            plug = ev_result[0].get("plug")
            if plug == "plugged" and (power is None or power == 0): health["ev-01"] -= 25
    except Exception as e:
        logger.exception("Health index calculation failed: %s", e)
        raise HTTPException(status_code=500, detail="Health index calculation failed")

    return {"health_index": health}

@app.get("/advisory")
def get_advisory():
    if rl_env is None:
        return {
            "current_dispatch": {"battery": "unknown", "ev": "unknown"},
            "recommended_dispatch": {"battery": "unknown", "ev": "unknown"}
        }

    try:
        action = rl_env.predict_action()
        action_map = {
            0: {"battery": "idle", "ev": "idle"},
            1: {"battery": "charge", "ev": "idle"},
            2: {"battery": "discharge", "ev": "idle"},
            3: {"battery": "idle", "ev": "charge"}
        }

        return {
            "current_dispatch": {"battery": "idle", "ev": "idle"},
            "recommended_dispatch": action_map.get(action, {"battery": "idle", "ev": "idle"}),
            "action_id": action
        }
    except Exception as e:
        logger.exception("Failed to get RL advisory: %s", e)
        raise HTTPException(status_code=500, detail="RL advisory failed")