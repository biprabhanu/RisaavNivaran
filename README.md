# PlumeProof: From Satellite Methane Alerts to Verified Mitigation

**Developed for the Agentic AI Hackathon 2026 by Team RisaavNivaran, IIT Bombay**

PlumeProof is an autonomous, evidence-driven AI application that converts satellite-detected methane emissions into structured investigation cases, adaptive investigation recommendations, coordinated actions, and independently verified mitigation outcomes.

---

## Project Background & Features

The application addresses the critical operational gap between satellite methane detection and verified mitigation, using the **Kanjur Landfill in Mumbai, India** as its primary demonstration test case.

### Core Modules Built:
1. **Main Monitoring Dashboard**: Interactive Leaflet map of Mumbai/Kanjur landfill, live summary cards, and case management table.
2. **Investigation Case Details**: Detailed case inspection (`KJ-2025-02`) displaying historical satellite observations, source attribution hypotheses with Bayesian prior probabilities, and outstanding information requirements.
3. **Satellite Data & Geospatial Pipeline**: CSV/JSON ingestion module with coordinate validation, timestamp checking, unit standardisation, and provenance tagging (`HISTORICAL SATELLITE DATA`).
4. **Interactive Evidence Planner**: Decision engine ranking investigation actions by Expected Information Gain (EIG) per ₹10,000, supporting dynamic resource un-availability and adaptive replanning.
5. **Investigation Timeline & Audit Log**: Chronological audit trail distinguishing real observations, agent decisions, and simulated events.
6. **Mitigation Verification Engine**: Rigorous evidence-gated verification rule (`Post Rate + Uncertainty < Pre Rate - Uncertainty`) ensuring operator-reported repairs alone never close cases without independent verification.

---

## Installation & Startup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+ & npm

### 1. Start the Backend API (FastAPI)
Open a terminal in the project root folder:
```bash
cd backend
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate
# On macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
*The backend API will run at `http://localhost:8000` with interactive Swagger docs at `http://localhost:8000/docs`.*

### 2. Start the Frontend Dashboard (React + Vite)
Open a second terminal in the project root folder:
```bash
cd frontend
npm install
npm run dev
```
*The frontend dashboard will run at `http://localhost:5173`.*

---

## 7-Step Demonstration Sequence
1. **Monitoring Dashboard**: Open `http://localhost:5173`, view summary cards, the Kanjur marker on the interactive Leaflet map, and the active case table.
2. **Investigation Case**: Click on the Kanjur case (`KJ-2025-02`) to inspect competing source attribution hypotheses and historical satellite observations.
3. **Evidence Planner**: Navigate to the Evidence Planner to view ranked investigation actions and cost-efficiency scores (`Gain per ₹10,000`).
4. **Adaptive Replanning**: Click **Mark Unavailable** on an investigation resource to see the agent automatically exclude it and re-rank the remaining plan.
5. **Unsupported Repair Rejection**: Click **Simulate Operator Repair Notification** to observe the AI automatically reject case closure because no independent post-intervention measurement is present.
6. **Mitigation Verification**: Go to **Mitigation Verification**, adjust pre/post emission rates and uncertainty intervals, and run the verification engine to confirm verified reduction.
7. **Audit Timeline**: Review the complete chronological audit log tracking every satellite observation, agent decision, and verification outcome.

---
*Team RisaavNivaran | IIT Bombay | PlumeProof 2026*
