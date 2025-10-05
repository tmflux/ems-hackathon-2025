# 🚀 Next-Gen EMS: Smart Energy Management System  
### VidyutAI Hackathon 2025 | IIT Gandhinagar

---

## 🧩 Problem Statement

Design and prototype a **cloud-enabled Smart Energy Management System (EMS)** with real-time monitoring, diagnostics, and adaptive scheduling.  
The system must ingest IoT data streams from renewables, storage, EVs, and grid subsystems; analyze them for health and performance; and provide actionable alerts with recommended dispatch and charging strategies.

Developed for **VidyutAI Hackathon 2025 (IIEC, IIT Gandhinagar)**.

---

## 🛠 Tech Stack

**Backend & Data Ingestion**
- MQTT (Mosquitto) – IoT data streaming  
- FastAPI (Python) – ingestion & REST APIs  
- InfluxDB – time-series database  
- Docker Compose – orchestration & deployment

**Analytics**
- Diagnostics engine for subsystem health  
- Rule-based alerting system  
- Optional Reinforcement Learning (Stable-Baselines3) for adaptive scheduling

**Frontend / Dashboard**
- React + Vite  
- Tailwind CSS (for UI)  
- Grafana (optional quick visualization)

**Cloud**
- Local (Docker) for development  
- AWS EC2 / IoT Core (optional for demo deployment)

---

## 📊 Key Features

1. **Cloud Monitoring Backend**  
   - Real-time IoT data ingestion (solar, battery, EV, grid)  
   - Scalable time-series storage and unified APIs  

2. **Diagnostics Module**  
   - Computes health indices for renewables, storage, EV chargers  
   - Generates clear diagnostic outputs, not just anomaly flags  

3. **Alerts & Advisory System**  
   - Real-time alerts (e.g., “Battery SoC low”)  
   - Recommended actions (e.g., “Switch to grid, schedule maintenance”)  

4. **Scheduling Engine**  
   - Rule-based dispatch strategy  
   - Reinforcement Learning (RL) scheduler – optional bonus  

5. **Unified Dashboard**  
   - Live metrics visualization  
   - Health indices and diagnostic recommendations  
   - Alerts with recommended actions  
   - Advisory panel showing current vs. RL-based dispatch

---

## 📂 Repository Structure
ems-hackathon-2025/
├── backend/ # FastAPI backend, diagnostics, scheduler 
│ ├── data/ # Datasets (Kaggle, Mendeley, etc.)
│ ├── ems_checkpoints/ # Trained RL models
│ ├── ems_eval_logs/ # Evaluation logs
│ ├── ems_best_model/ # Final model artifacts
│ ├── *.py / *.ipynb # Core backend scripts
│ └── requirements.txt # Backend dependencies
├── frontend/ # React dashboard
│ ├── src/ # Components and pages
│ ├── index.html # Entry point
│ └── Dockerfile # Frontend container
├── simulator/ # IoT data simulator
│ ├── mqtt_data_simulator.py
│ └── requirements.txt
├── mosquitto/ # MQTT broker configuration
│ └── config/mosquitto.conf
├── docker-compose.yml # Service orchestration
├── README.md # Project overview
└── .gitignore / .dockerignore

---

## ⚙️ Setup & Run

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/ems-hackathon-2025.git
cd ems-hackathon-2025
docker-compose up --build
Frontend: http://localhost:3000
```

Backend API Docs: http://localhost:8000/docs

MQTT Broker: localhost:1883
cd simulator
python mqtt_data_simulator.py


📢 Credits

Developed by Parth Thorat & Team
For VidyutAI Hackathon 2025 – IIT Gandhinagar (IIEC)
Special thanks to mentors and organizing team for guidance and support.

