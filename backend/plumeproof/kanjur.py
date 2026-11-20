"""
Kanjur landfill (Mumbai) demonstration data.

REAL DATA  : the Carbon Mapper plume emission rates and dates (PDF ref [2]):
             9 Feb 2025: Plume A ~1,600 kg/h, Plume B ~136 kg/h
             3 Apr 2026: two plumes, ~3,300 kg/h combined
ILLUSTRATIVE: plume positions inside the site, facility/zone polygons, wind arrow.
SIMULATED  : the stakeholder mapping and every operational event in the replay.
"""
from __future__ import annotations

from .config import FLARE, GAS, WASTE
from .schemas import (
    ActorType,
    DataLabel,
    Facility,
    FacilityZone,
    Measurement,
    Observation,
    Stakeholder,
    Wind,
)

FACILITY_ID = "kanjur"
CASE_ID = "KJ-2025-02"

# Approximately 1.5 km across, centred near 19.13 N, 72.93 E. Illustrative, not a surveyed boundary.
FACILITY = Facility(
    id=FACILITY_ID,
    name="Kanjur Landfill",
    location="Kanjurmarg (East), Mumbai, India",
    lat=19.1300,
    lng=72.9305,
    boundary=[(19.1372, 72.9228), (19.1376, 72.9378), (19.1234, 72.9382), (19.1226, 72.9232)],
    zones=[
        FacilityZone(
            id="zone-waste-face", name="Active waste face (exposed surface)", hypothesis_id=WASTE,
            polygon=[(19.1356, 72.9244), (19.1360, 72.9312), (19.1262, 72.9316), (19.1254, 72.9248)],
        ),
        FacilityZone(
            id="zone-gas-field", name="Gas-collection well field", hypothesis_id=GAS,
            polygon=[(19.1362, 72.9320), (19.1366, 72.9364), (19.1290, 72.9366), (19.1286, 72.9322)],
        ),
        FacilityZone(
            id="zone-flare", name="Flare station", hypothesis_id=FLARE,
            polygon=[(19.1278, 72.9328), (19.1278, 72.9366), (19.1244, 72.9366), (19.1244, 72.9328)],
        ),
    ],
)

_POS_NOTE = "Emission rate and date are real (Carbon Mapper). Marker position is approximate/illustrative."

OBS_2025_A = Observation(
    id="OBS-2025-02-09-A", facility_id=FACILITY_ID, date="2025-02-09", lat=19.1310, lng=72.9280,
    rate_kg_h=1600.0, plume_label="Plume A", source="Carbon Mapper", label=DataLabel.REAL_DATA, notes=_POS_NOTE,
)
OBS_2025_B = Observation(
    id="OBS-2025-02-09-B", facility_id=FACILITY_ID, date="2025-02-09", lat=19.1326, lng=72.9344,
    rate_kg_h=136.0, plume_label="Plume B", source="Carbon Mapper", label=DataLabel.REAL_DATA, notes=_POS_NOTE,
)
OBS_2026 = Observation(
    id="OBS-2026-04-03", facility_id=FACILITY_ID, date="2026-04-03", lat=19.1316, lng=72.9314,
    rate_kg_h=3300.0, plume_label="Plumes C+D (combined)", source="Carbon Mapper", label=DataLabel.REAL_DATA,
    notes="Two plumes, ~3,300 kg/h combined (individual split not public). " + _POS_NOTE,
)
REAL_OBSERVATIONS: list[Observation] = [OBS_2025_A, OBS_2025_B, OBS_2026]

# Stakeholder mapping: SIMULATED (who is accountable is resolved by the agent from the facility record).
STAKEHOLDERS: list[Stakeholder] = [
    Stakeholder(
        role="Responsible operator", name="Kanjur landfill operator (contractor)",
        contact="operator@example.invalid (simulated)",
        responsibility="Runs the site, gas-collection wells and flare; performs corrective repairs.",
    ),
    Stakeholder(
        role="Municipal authority", name="BMC Solid Waste Management Dept",
        contact="swm@example.invalid (simulated)",
        responsibility="Owns the landfill contract; can direct the operator.",
    ),
    Stakeholder(
        role="Regulator", name="Maharashtra Pollution Control Board (MPCB)",
        contact="mpcb@example.invalid (simulated)",
        responsibility="Assesses compliance and verifies reported corrective actions.",
    ),
    Stakeholder(
        role="UN focal point", name="UNEP IMEO / MARS national focal point",
        contact="mars@example.invalid (simulated)",
        responsibility="Receives the MARS alert and tracks the response outcome.",
    ),
]

WIND = Wind(from_deg=290.0, speed_m_s=4.5, label="WNW sea breeze, 4.5 m/s (illustrative, not measured)", illustrative=True)

# Pre-intervention measurement used by the verification rule.
PRE_MEASUREMENT = Measurement(
    id="PRE-2025-02-09",
    rate_kg_h=1736.0,
    uncertainty_kg_h=434.0,  # ±25% assumption (docs/ASSUMPTIONS.md §5)
    date="2025-02-09",
    method="Carbon Mapper satellite (combined plumes A+B)",
    independent=True,
    comparable_conditions=True,
    actor=ActorType.SATELLITE,
    label=DataLabel.REAL_DATA,
    notes="1,600 + 136 kg/h; ±25% uncertainty is an assumption.",
)

OUTSTANDING_QUESTIONS: list[str] = [
    "Which organisation operates the gas-processing infrastructure?",
    "When was the flare system last non-operational?",
    "Are gas-collection well maintenance records available for Jan–Feb 2025?",
]
