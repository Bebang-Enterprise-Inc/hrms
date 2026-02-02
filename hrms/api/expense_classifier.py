"""
Expense Classification Engine
Classifies expenses using: Rules -> ML Model -> OpenAI fallback

Author: Claude Code
Date: 2026-02-02
"""
import frappe
from frappe import _
import json
import os
from frappe.utils import flt

# Model path for trained classifier
MODEL_PATH = '/home/frappe/frappe-bench/sites/assets/expense_classifier.joblib'

# COA mapping from training data labels to GL codes
COA_MAPPING = {
    "Delivery Riders-Lalamove": "6009003",
    "Representation & Entertainment": "6010100",
    "Store Supplies": "6006001",
    "Office Supplies": "6006003",
    "T&T - Motor & Car Taxi/Jeepney Fares": "6010003",
    "T&T - Motor & Car Fares": "6010003",
    "EB-Other Benefits": "6002308",
    "Direct Materials-Food": "5000001",
    "Janitorial Supplies": "6006002",
    "Utility Cost - Internet Charges": "6004005",
    "Utility Cost - Internet": "6004005",
    "Utility Cost - Cellphone": "6004004",
    "Smallwares Expense": "6007000",
    "Smallwares Supplies": "6007000",
    "R & M - Contract Services": "6008002",
    "R & M -Contract Services": "6008002",
    "Misc - Photocopy": "6010209",
    "Misc - First Aid Supplies": "6010208",
    "WATER FOR STAFF": "6002303",
    "Prepaid Taxes and Licences": "6020500",
}


@frappe.whitelist()
def classify_expense(description: str, vendor: str = None, amount: float = None):
    """
    Classify an expense using cascading methods:
    1. Rule-based (instant, free)
    2. ML Model (trained on Liezel's data)
    3. OpenAI fallback (for ambiguous cases)

    Returns:
        {
            "coa": "6006002",  # GL account code
            "coa_label": "Janitorial Supplies",
            "confidence": 95.0,
            "alternatives": [...],
            "method": "rule" | "ml" | "openai"
        }
    """
    if not description:
        return {"coa": None, "confidence": 0, "method": "none"}

    # Step 1: Try rule-based classification
    result = classify_by_rules(description, vendor)
    if result["confidence"] >= 80:
        return result

    # Step 2: Try ML model
    if os.path.exists(MODEL_PATH):
        ml_result = classify_by_ml(description, vendor, amount)
        if ml_result["confidence"] >= 70:
            return ml_result

    # Step 3: OpenAI fallback for low confidence
    if result["confidence"] < 70:
        try:
            openai_result = classify_by_openai(description, vendor)
            return openai_result
        except Exception as e:
            frappe.log_error(f"OpenAI classification failed: {e}")

    # Return best result we have
    return result


def classify_by_rules(description: str, vendor: str = None):
    """
    Rule-based classification using keyword patterns.
    Fast and free - handles 80% of cases.
    """
    text = f"{description or ''} {vendor or ''}".lower()

    # Rules ordered by specificity (most specific first)
    RULES = [
        # Delivery services (distinguish from transport)
        (["lalamove"], "Delivery Riders-Lalamove", 95),
        (["grab delivery", "grab express", "grab send"], "Delivery Riders-Lalamove", 90),

        # Transportation (NOT delivery)
        (["fare", "taxi", "jeep", "tricycle"], "T&T - Motor & Car Taxi/Jeepney Fares", 90),
        (["angkas", "joyride"], "T&T - Motor & Car Taxi/Jeepney Fares", 90),
        (["grab car", "grab taxi"], "T&T - Motor & Car Taxi/Jeepney Fares", 85),

        # Utilities
        (["internet", "wifi", "broadband", "pldt", "globe fiber"], "Utility Cost - Internet Charges", 95),
        (["mobile internet", "data plan"], "Utility Cost - Internet Charges", 95),
        (["cellphone load", "sim card", "load allowance"], "Utility Cost - Cellphone", 90),

        # Office vs Store supplies (important distinction)
        (["ballpen", "bond paper", "folder", "envelope", "notebook"], "Office Supplies", 95),
        (["whiteboard", "marker", "stapler", "paper clip"], "Office Supplies", 90),
        (["tissue", "cup", "straw", "napkin", "container", "foil"], "Store Supplies", 95),
        (["tape", "plastic bag", "paper bag"], "Store Supplies", 85),

        # Janitorial
        (["mop", "broom", "cleaning", "zonrox", "bleach", "detergent"], "Janitorial Supplies", 95),
        (["sanitizer", "disinfectant", "alcohol"], "Janitorial Supplies", 90),

        # Direct materials (food)
        (["mineral water", "drinking water"], "Direct Materials-Food", 95),
        (["ice", "ice cube"], "Direct Materials-Food", 80),

        # Services & Maintenance
        (["water analysis", "water testing"], "R & M - Contract Services", 95),
        (["repair", "maintenance", "technician", "pest control"], "R & M - Contract Services", 90),

        # Benefits/Entertainment
        (["food allowance", "meal allowance", "meeting food"], "Representation & Entertainment", 90),
        (["birthday", "celebration", "team activity"], "Representation & Entertainment", 85),
        (["cash advance", "employee loan"], "EB-Other Benefits", 85),

        # Misc
        (["photocopy", "xerox", "printing"], "Misc - Photocopy", 95),
        (["first aid", "medicine", "bandage"], "Misc - First Aid Supplies", 90),
    ]

    for keywords, coa_label, confidence in RULES:
        if any(kw in text for kw in keywords):
            matched = [kw for kw in keywords if kw in text]
            coa_code = COA_MAPPING.get(coa_label, coa_label)
            return {
                "coa": coa_code,
                "coa_label": coa_label,
                "confidence": confidence,
                "alternatives": [],
                "method": "rule",
                "matched_keywords": matched
            }

    # No match - low confidence
    return {
        "coa": None,
        "coa_label": None,
        "confidence": 0,
        "alternatives": [],
        "method": "rule_no_match"
    }


def classify_by_ml(description: str, vendor: str = None, amount: float = None):
    """
    ML-based classification using trained scikit-learn model.
    """
    try:
        import joblib
        pipeline = joblib.load(MODEL_PATH)

        # Prepare input
        text = f"{description or ''} {vendor or ''}".lower()

        # Get prediction with probability
        prediction = pipeline.predict([text])[0]
        probabilities = pipeline.predict_proba([text])[0]
        confidence = max(probabilities) * 100

        # Get top 3 alternatives
        classes = pipeline.classes_
        sorted_indices = probabilities.argsort()[::-1]
        alternatives = [
            {
                "coa_label": classes[i],
                "coa": COA_MAPPING.get(classes[i], classes[i]),
                "confidence": round(probabilities[i] * 100, 1)
            }
            for i in sorted_indices[:3]
        ]

        coa_code = COA_MAPPING.get(prediction, prediction)

        return {
            "coa": coa_code,
            "coa_label": prediction,
            "confidence": round(confidence, 1),
            "alternatives": alternatives,
            "method": "ml"
        }
    except Exception as e:
        frappe.log_error(f"ML classification error: {e}")
        return {"coa": None, "confidence": 0, "method": "ml_error"}


def classify_by_openai(description: str, vendor: str = None):
    """
    OpenAI fallback for ambiguous cases.
    Cost: ~PHP 0.10 per classification
    """
    import requests

    api_key = frappe.conf.get("openai_api_key")
    if not api_key:
        return {"coa": None, "confidence": 0, "method": "openai_no_key"}

    categories = "\n".join([f"- {label} ({code})" for label, code in COA_MAPPING.items()])

    prompt = f"""You are an expense classifier for a QSR restaurant chain in the Philippines.

Available COA Categories:
{categories}

Expense description: "{description}"
Vendor: "{vendor or 'not specified'}"

Respond with JSON only:
{{"coa": "GL_CODE", "coa_label": "Category Name", "confidence": 0.95, "reason": "brief explanation"}}"""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            },
            timeout=10
        )

        result = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(result)

        return {
            "coa": parsed.get("coa"),
            "coa_label": parsed.get("coa_label"),
            "confidence": parsed.get("confidence", 0.9) * 100,
            "alternatives": [],
            "method": "openai",
            "reason": parsed.get("reason")
        }
    except Exception as e:
        frappe.log_error(f"OpenAI API error: {e}")
        return {"coa": None, "confidence": 0, "method": "openai_error"}


@frappe.whitelist()
def train_model():
    """
    Train the ML classifier on Liezel's reviewed data.
    Run once initially, then monthly to incorporate corrections.

    Usage: bench --site hq.bebang.ph execute hrms.api.expense_classifier.train_model
    """
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    import joblib

    # Load training data
    training_file = frappe.get_site_path(
        '..', '..', '..',
        'data/RFP_Store_Samples/runs/2026-01-27_liezel_reviewed/LIEZEL_REVIEWED_FINAL.csv'
    )

    df = pd.read_csv(training_file)

    # Prepare features
    df['text_features'] = (
        df['description'].fillna('') + ' ' +
        df['vendor'].fillna('')
    ).str.lower()

    # Filter valid rows
    df = df[df['coa'].notna()]

    # Create pipeline
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=500,
            stop_words=['the', 'for', 'and', 'of', 'to', 'in', 'a']
        )),
        ('clf', RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        ))
    ])

    # Train
    X = df['text_features']
    y = df['coa']
    pipeline.fit(X, y)

    # Save model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    frappe.log_error(
        title="Expense Classifier Trained",
        message=f"Trained on {len(df)} samples, {len(y.unique())} categories"
    )

    return {
        "success": True,
        "samples": len(df),
        "categories": len(y.unique()),
        "model_path": MODEL_PATH
    }


@frappe.whitelist()
def record_correction(expense_name: str, original_coa: str, corrected_coa: str):
    """
    Record a correction for model retraining.
    Called when accounting changes the AI-suggested COA.
    """
    expense = frappe.get_doc("BEI Expense Request", expense_name)

    doc = frappe.get_doc({
        "doctype": "BEI Expense Training Data",
        "expense_reference": expense_name,
        "description": expense.manual_description,
        "vendor": expense.manual_vendor,
        "store": expense.store,
        "original_suggestion": original_coa,
        "corrected_coa": corrected_coa,
        "corrected_by": frappe.session.user,
        "correction_date": frappe.utils.now()
    })
    doc.insert(ignore_permissions=True)

    return {"success": True, "training_data": doc.name}
