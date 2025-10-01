\# 🚀 Next-Gen EMS: Smart Energy Management System (Hackathon 2025, IIT Gandhinagar)



\### Problem Statement

Design and prototype a \*\*cloud-enabled Smart Energy Management System (EMS)\*\* with real-time monitoring, diagnostics, and adaptive scheduling.  

The system must ingest IoT data streams (renewables, storage, EVs, grid), analyze them for health/performance, and provide actionable alerts with recommended dispatch/charging strategies.  



This project is developed for \*\*VidyutAI Hackathon 2025 (IIEC, IIT Gandhinagar)\*\*.



---



\## 🛠 Tech Stack



\*\*Backend \& Data Ingestion\*\*

\- MQTT (Mosquitto broker) for IoT data streaming

\- FastAPI (Python) for ingestion + APIs

\- InfluxDB (time-series database)

\- Docker Compose for orchestration



\*\*Analytics\*\*

\- Diagnostics engine for subsystem health indices

\- Rule-based alert system

\- Optional Reinforcement Learning (Stable-Baselines3) for adaptive scheduling



\*\*Frontend / Dashboard\*\*

\- React + Tailwind CSS

\- Grafana (optional, for quick time-series visualization)



\*\*Cloud\*\*

\- Local (Docker-based) for development

\- AWS EC2 / IoT Core (optional deployment for demo)



---



\## 📊 Features (Planned)



1\. \*\*Cloud Monitoring Backend\*\*  

&nbsp;  - Real-time IoT data ingestion (solar, battery, EV, grid).  

&nbsp;  - Scalable time-series storage and APIs.



2\. \*\*Diagnostics Module\*\*  

&nbsp;  - Health indices for renewables, storage, EV chargers.  

&nbsp;  - Clear diagnostic messages (not just anomalies).



3\. \*\*Alerts \& Advisory\*\*  

&nbsp;  - Real-time alerts (e.g., “Battery SoC low”).  

&nbsp;  - Recommended actions (e.g., “Switch to grid, schedule maintenance”).  



4\. \*\*Scheduling Engine\*\*  

&nbsp;  - Rule-based EMS dispatch decisions.  

&nbsp;  - RL-based scheduler (bonus).  



5\. \*\*Unified Dashboard\*\*  

&nbsp;  - Live metrics visualization.  

&nbsp;  - Subsystem health cards.  

&nbsp;  - Alerts \& recommendations.  

&nbsp;  - Advisory panel (scheduler vs RL dispatch).



---



\## 📂 Repo Structure (Proposed)





