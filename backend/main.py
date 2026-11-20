from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import os
import shutil
from datetime import datetime

app = FastAPI(
    title="PlumeProof API",
    description="Agentic AI backend for satellite methane emissions investigation and verification (Team RisaavNivaran, IIT Bombay)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "seed.json")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"cases": [], "investigations": [], "timeline": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

class ObservationUpload(BaseModel):
    observation_id: str
    facility_name: str
    latitude: float
    longitude: float
    observation_date: str
    emission_rate_kg_hour: float
    source: str
    confidence: Optional[float] = 0.95

class VerificationRequest(BaseModel):
    pre_rate: float
    pre_uncertainty: float
    post_rate: float
    post_uncertainty: float
    comparable_conditions: bool
    independent_measurement: bool

@app.get("/api/cases")
def get_cases():
    data = load_data()
    return {"cases": data.get("cases", [])}

@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    data = load_data()
    cases = data.get("cases", [])
    case = next((c for c in cases if c["case_id"] == case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.get("/api/observations")
def get_observations():
    data = load_data()
    cases = data.get("cases", [])
    obs = []
    for c in cases:
        for sat in c.get("satellite_observations", []):
            obs.append({
                "observation_id": f"OBS-{c['case_id']}",
                "facility_name": c["facility"],
                "latitude": c["latitude"],
                "longitude": c["longitude"],
                "observation_date": sat["date"],
                "emission_rate_kg_hour": sat["emission_rate"],
                "source": sat["label"],
                "confidence": 0.95
            })
    return {"observations": obs}

@app.post("/api/observations/upload")
def upload_observation(obs: ObservationUpload):
    data = load_data()
    new_case = {
        "case_id": f"IMP-{int(datetime.now().timestamp())}",
        "facility": obs.facility_name,
        "location": "Imported Location",
        "latitude": obs.latitude,
        "longitude": obs.longitude,
        "observation_date": obs.observation_date,
        "emission_rate_kg_hour": obs.emission_rate_kg_hour,
        "priority": "High" if obs.emission_rate_kg_hour > 1000 else "Medium",
        "investigation_status": "Source Attribution Pending",
        "source_attribution": [
            {"source": "Exposed waste surface", "probability": 0.50},
            {"source": "Gas collection system", "probability": 0.35},
            {"source": "Flare system", "probability": 0.15}
        ],
        "satellite_observations": [
            {
                "plume_id": obs.observation_id,
                "emission_rate": obs.emission_rate_kg_hour,
                "unit": "kg CH4/hour",
                "date": obs.observation_date,
                "label": "HISTORICAL SATELLITE DATA"
            }
        ],
        "outstanding_requirements": [
            "Verify facility operational status",
            "Check local meteorological wind vector"
        ]
    }
    data["cases"].append(new_case)
    
    # Add audit timeline event
    data["timeline"].append({
        "event_id": f"EVT-{int(datetime.now().timestamp())}",
        "event_type": "Satellite observation recorded",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": f"Imported observation {obs.observation_id} for {obs.facility_name} with {obs.emission_rate_kg_hour} kg/hr.",
        "evidence": "HISTORICAL SATELLITE DATA",
        "responsible_actor": "Data Ingestion Pipeline",
        "approval_status": "Auto-Approved"
    })
    
    save_data(data)
    return {"status": "success", "case": new_case}

@app.get("/api/investigations")
def get_investigations():
    data = load_data()
    invs = data.get("investigations", [])
    # Calculate gain per 10k
    ranked = []
    for inv in invs:
        cost = inv["cost"]
        gain = inv["information_gain"]
        gain_per_10k = round((gain / (cost / 10000)) if cost > 0 else 0.0, 2)
        inv_copy = dict(inv)
        inv_copy["gain_per_10k"] = gain_per_10k
        ranked.append(inv_copy)
    
    # Sort by available=true first, then gain_per_10k descending
    ranked.sort(key=lambda x: (x["available"], x["gain_per_10k"]), reverse=True)
    return {"investigations": ranked}

@app.post("/api/investigations/generate-plan")
def generate_plan():
    return get_investigations()

@app.post("/api/investigations/resource-unavailable")
def resource_unavailable(payload: dict):
    inv_id = payload.get("investigation_id")
    data = load_data()
    updated = False
    for inv in data.get("investigations", []):
        if inv["id"] == inv_id:
            inv["available"] = False
            updated = True
    
    if updated:
        # Add timeline event
        data["timeline"].append({
            "event_id": f"EVT-{int(datetime.now().timestamp())}",
            "event_type": "Investigation resource unavailable",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": f"Investigation resource '{inv_id}' marked unavailable. Agent triggered adaptive replanning.",
            "evidence": "SIMULATED DEMONSTRATION DATA",
            "responsible_actor": "Operations Coordinator",
            "approval_status": "Logged"
        })
        save_data(data)
        
    return get_investigations()

@app.post("/api/verification/evaluate")
def evaluate_verification(req: VerificationRequest):
    # Rule: Post + uncertainty < Pre - uncertainty AND independent AND comparable
    pre_lower = req.pre_rate - req.pre_uncertainty
    post_upper = req.post_rate + req.post_uncertainty
    
    valid_inequality = post_upper < pre_lower
    
    if valid_inequality and req.comparable_conditions and req.independent_measurement:
        outcome = "VERIFIED EMISSION REDUCTION"
        description = f"Upper bound of post-intervention interval ({post_upper}) < lower bound of pre-intervention interval ({pre_lower}). Independent evidence and comparable conditions confirmed."
    elif not req.independent_measurement or not req.comparable_conditions:
        outcome = "INCONCLUSIVE"
        description = "Missing independent post-intervention measurement or incomparable measurement conditions."
    else:
        outcome = "STILL LEAKING OR RECURRING"
        description = f"Uncertainty intervals overlap or post-intervention emission level remains high (Post upper: {post_upper} vs Pre lower: {pre_lower})."

    # Log to audit timeline
    data = load_data()
    data["timeline"].append({
        "event_id": f"EVT-{int(datetime.now().timestamp())}",
        "event_type": "Verification assessment generated",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": f"Verification evaluation result: {outcome}. {description}",
        "evidence": "AGENT-GENERATED OUTPUT",
        "responsible_actor": "Verification Engine",
        "approval_status": "Approved & Case Processed"
    })
    save_data(data)

    return {
        "outcome": outcome,
        "description": description,
        "pre_lower_bound": pre_lower,
        "post_upper_bound": post_upper,
        "rule_satisfied": valid_inequality
    }

@app.get("/api/cases/{case_id}/timeline")
def get_timeline(case_id: str):
    data = load_data()
    return {"timeline": data.get("timeline", [])}

@app.post("/api/cases/{case_id}/events")
def add_event(case_id: str, event: dict):
    data = load_data()
    new_evt = {
        "event_id": f"EVT-{int(datetime.now().timestamp())}",
        "event_type": event.get("event_type", "Operational event"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": event.get("description", ""),
        "evidence": event.get("evidence", "SIMULATED DEMONSTRATION DATA"),
        "responsible_actor": event.get("responsible_actor", "Operator"),
        "approval_status": event.get("approval_status", "Submitted")
    }
    data["timeline"].append(new_evt)
    save_data(data)
    return {"status": "success", "event": new_evt}
