# engine.py
from typing import List, Dict, Set

RULES = [
    {
        "disease": "Common Cold",
        "symptoms": {"runny_nose", "sneezing", "sore_throat"},
        "urgency": "Low",
        "advice": "Rest, stay hydrated, and use over-the-counter decongestants."
    },
    {
        "disease": "Influenza (Flu)",
        "symptoms": {"fever", "body_ache", "fatigue", "dry_cough"},
        "urgency": "Moderate",
        "advice": "Rest, take antipyretics, and monitor body temperature."
    },
    {
        "disease": "Emergency: Possible Cardiac Event",
        "symptoms": {"chest_pain", "shortness_of_breath", "arm_numbness"},
        "urgency": "CRITICAL",
        "advice": "SEEK IMMEDIATE EMERGENCY MEDICAL ASSISTANCE (Call 112/911)."
    }
]

def diagnose(patient_symptoms: Set[str]) -> List[Dict]:
    results = []
    for rule in RULES:
        matched = rule["symptoms"].intersection(patient_symptoms)
        if len(matched) >= 2 or rule["symptoms"].issubset(patient_symptoms):
            confidence = round((len(matched) / len(rule["symptoms"])) * 100, 1)
            results.append({
                "disease": rule["disease"],
                "confidence": confidence,
                "urgency": rule["urgency"],
                "advice": rule["advice"]
            })
    return sorted(results, key=lambda x: x["confidence"], reverse=True)