"""
Expense Classification Engine
Classifies expenses using cascading methods: Rules -> ML Model -> OpenAI fallback

Trained on Liezel's 682 reviewed transactions from BEI stores.
Categories mapped to GL codes from the BEI Chart of Accounts.

Author: Claude Code
Date: 2026-02-02
"""
import frappe
from frappe import _
import json
import os
from frappe.utils import flt

# Optional imports - handled gracefully if not installed
try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False
    joblib = None

try:
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    pd = None

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    http_requests = None


# Model path for trained classifier
MODEL_PATH = '/home/frappe/frappe-bench/sites/assets/expense_classifier.joblib'

# COA mapping from training data labels to GL codes
# Based on Liezel's 682 reviewed transactions
COA_MAPPING = {
    # Delivery (18% of transactions)
    "Delivery Riders-Lalamove": "6009003",

    # Representation & Entertainment (16%)
    "Representation & Entertainment": "6010100",

    # Store Supplies (14%)
    "Store Supplies": "6006001",

    # Office Supplies (12%)
    "Office Supplies": "6006003",

    # Transportation (12%)
    "T&T - Motor & Car Taxi/Jeepney Fares": "6010003",
    "T&T - Motor & Car Fares": "6010003",  # Alternate naming

    # Employee Benefits (5%)
    "EB-Other Benefits": "6002308",

    # Direct Materials - Food (4%)
    "Direct Materials-Food": "5000001",

    # Janitorial Supplies (4%)
    "Janitorial Supplies": "6006002",

    # Utilities - Internet (3%)
    "Utility Cost - Internet Charges": "6004005",
    "Utility Cost - Internet": "6004005",  # Alternate naming

    # Utilities - Cellphone (1%)
    "Utility Cost - Cellphone": "6004004",

    # Smallwares (1%)
    "Smallwares Expense": "6007000",
    "Smallwares Supplies": "6007000",  # Alternate naming

    # Repairs & Maintenance (0.4%)
    "R & M - Contract Services": "6008002",
    "R & M -Contract Services": "6008002",  # Typo variant in training data

    # Miscellaneous
    "Misc - Photocopy": "6010209",
    "Misc - First Aid Supplies": "6010208",

    # Water for Staff
    "WATER FOR STAFF": "6002303",

    # Taxes & Licenses
    "Prepaid Taxes and Licences": "6020500",
}

# Reverse mapping: GL code to label (for display)
COA_LABELS = {v: k for k, v in COA_MAPPING.items()}
# Remove duplicates by preferring the canonical name
COA_LABELS["6010003"] = "T&T - Motor & Car Taxi/Jeepney Fares"
COA_LABELS["6004005"] = "Utility Cost - Internet Charges"
COA_LABELS["6007000"] = "Smallwares Expense"
COA_LABELS["6008002"] = "R & M - Contract Services"


@frappe.whitelist()
def classify_expense(description: str, vendor: str = None, amount: float = None):
    """
    Classify an expense using cascading methods:
    1. Rule-based (instant, free) - handles ~80% of cases
    2. ML Model (trained on Liezel's data) - for ambiguous cases
    3. OpenAI fallback (GPT-3.5) - for very low confidence cases

    Args:
        description: What was purchased (user's own words)
        vendor: Where it was purchased
        amount: How much (optional, for context)

    Returns:
        {
            "coa": "6006002",  # GL account code
            "coa_label": "Janitorial Supplies",
            "confidence": 95.0,
            "alternatives": [{"coa": "...", "coa_label": "...", "confidence": 80.0}],
            "method": "rule" | "ml" | "openai"
        }
    """
    if not description:
        return {
            "coa": None,
            "coa_label": None,
            "confidence": 0,
            "alternatives": [],
            "method": "none",
            "error": "No description provided"
        }

    # Step 1: Try rule-based classification (instant, free)
    result = classify_by_rules(description, vendor)
    if result.get("confidence", 0) >= 80:
        return result

    # Step 2: Try ML model if trained model exists
    if JOBLIB_AVAILABLE and os.path.exists(MODEL_PATH):
        ml_result = classify_by_ml(description, vendor, amount)
        if ml_result.get("confidence", 0) >= 70:
            return ml_result
        # Keep ML result as fallback
        if ml_result.get("confidence", 0) > result.get("confidence", 0):
            result = ml_result

    # Step 3: OpenAI fallback for low confidence cases
    if result.get("confidence", 0) < 70:
        try:
            openai_result = classify_by_openai(description, vendor)
            if openai_result.get("confidence", 0) > 0:
                return openai_result
        except Exception as e:
            frappe.log_error(
                title="OpenAI Classification Error",
                message=f"Failed to classify expense: {str(e)}\nDescription: {description}\nVendor: {vendor}"
            )

    # Return best result we have
    return result


def classify_by_rules(description: str, vendor: str = None):
    """
    Rule-based classification using keyword patterns.
    Fast and free - handles 80% of typical cases.

    Rules are ordered by specificity (most specific first).
    Each rule: (keywords_list, coa_label, confidence_score)
    """
    text = f"{description or ''} {vendor or ''}".lower()

    # Rules ordered by specificity (most specific first)
    RULES = [
        # ========== DELIVERY SERVICES (distinguish from transport) ==========
        (["lalamove"], "Delivery Riders-Lalamove", 98),
        (["grab delivery", "grab express", "grab send", "grabexpress"], "Delivery Riders-Lalamove", 95),
        (["mr speedy", "mrspeedy"], "Delivery Riders-Lalamove", 95),
        (["toktok", "transportify"], "Delivery Riders-Lalamove", 90),
        (["rider fee", "delivery fee", "delivery charge"], "Delivery Riders-Lalamove", 85),

        # ========== TRANSPORTATION (NOT delivery) ==========
        (["taxi fare", "cab fare", "taxi ride"], "T&T - Motor & Car Taxi/Jeepney Fares", 95),
        (["jeepney fare", "jeep fare", "fx fare"], "T&T - Motor & Car Taxi/Jeepney Fares", 95),
        (["tricycle fare", "trike fare", "pedicab"], "T&T - Motor & Car Taxi/Jeepney Fares", 95),
        (["angkas", "joyride", "move it"], "T&T - Motor & Car Taxi/Jeepney Fares", 95),
        (["grab car", "grab taxi", "grabcar", "grabtaxi"], "T&T - Motor & Car Taxi/Jeepney Fares", 90),
        (["bus fare", "mrt fare", "lrt fare"], "T&T - Motor & Car Taxi/Jeepney Fares", 90),
        (["pamasahe", "fare to", "fare from", "transpo"], "T&T - Motor & Car Taxi/Jeepney Fares", 85),

        # ========== UTILITIES - INTERNET ==========
        (["pldt", "globe fiber", "converge", "sky fiber"], "Utility Cost - Internet Charges", 98),
        (["internet bill", "wifi bill", "broadband"], "Utility Cost - Internet Charges", 95),
        (["internet payment", "wifi payment"], "Utility Cost - Internet Charges", 95),
        (["pocket wifi", "mobile internet", "data plan"], "Utility Cost - Internet Charges", 90),
        (["internet", "wifi connection"], "Utility Cost - Internet Charges", 85),

        # ========== UTILITIES - CELLPHONE ==========
        (["load allowance", "phone allowance", "mobile allowance"], "Utility Cost - Cellphone", 95),
        (["cellphone load", "cp load", "prepaid load"], "Utility Cost - Cellphone", 95),
        (["sim card", "new sim", "postpaid"], "Utility Cost - Cellphone", 90),
        (["globe load", "smart load", "tnt load", "tm load"], "Utility Cost - Cellphone", 90),

        # ========== OFFICE SUPPLIES (distinguish from store supplies) ==========
        (["ballpen", "ball pen", "pen ink", "pencil"], "Office Supplies", 95),
        (["bond paper", "folder", "envelope", "notebook"], "Office Supplies", 95),
        (["stapler", "paper clip", "binder clip", "fastener"], "Office Supplies", 95),
        (["correction tape", "highlighter", "marker pen"], "Office Supplies", 95),
        (["whiteboard marker", "permanent marker"], "Office Supplies", 90),
        (["office supplies", "school supplies"], "Office Supplies", 90),
        (["calculator", "ruler", "scissor"], "Office Supplies", 85),

        # ========== STORE SUPPLIES (food service items) ==========
        (["tissue paper", "table napkin", "paper napkin"], "Store Supplies", 95),
        (["paper cup", "plastic cup", "styro cup", "disposable cup"], "Store Supplies", 95),
        (["straw", "stirrer", "toothpick"], "Store Supplies", 95),
        (["take out box", "takeout box", "meal box", "food container"], "Store Supplies", 95),
        (["plastic bag", "paper bag", "eco bag"], "Store Supplies", 90),
        (["aluminum foil", "cling wrap", "food wrap"], "Store Supplies", 90),
        (["store supplies", "dining supplies", "packaging"], "Store Supplies", 85),
        (["tape", "masking tape", "packaging tape"], "Store Supplies", 80),

        # ========== JANITORIAL SUPPLIES ==========
        (["mop", "mop head", "mop handle", "broom"], "Janitorial Supplies", 95),
        (["zonrox", "bleach", "clorox"], "Janitorial Supplies", 95),
        (["detergent", "dishwashing liquid", "joy", "smart"], "Janitorial Supplies", 95),
        (["floor wax", "floor cleaner", "domex"], "Janitorial Supplies", 95),
        (["sanitizer", "alcohol", "disinfectant"], "Janitorial Supplies", 90),
        (["garbage bag", "trash bag", "bin liner"], "Janitorial Supplies", 90),
        (["cleaning materials", "cleaning supplies", "janitorial"], "Janitorial Supplies", 90),
        (["air freshener", "lysol", "spray cleaner"], "Janitorial Supplies", 85),
        (["toilet cleaner", "bathroom cleaner", "muriatic"], "Janitorial Supplies", 85),
        (["rag", "wiper", "dust pan", "dustpan"], "Janitorial Supplies", 85),

        # ========== DIRECT MATERIALS - FOOD ==========
        (["mineral water", "drinking water", "distilled water"], "Direct Materials-Food", 95),
        (["ice cube", "tube ice", "ice block"], "Direct Materials-Food", 90),
        (["water for store", "water supply"], "Direct Materials-Food", 85),
        (["emergency food", "ingredients"], "Direct Materials-Food", 80),

        # ========== REPAIRS & MAINTENANCE ==========
        (["water analysis", "water testing", "water test"], "R & M - Contract Services", 95),
        (["pest control", "fumigation", "exterminator"], "R & M - Contract Services", 95),
        (["aircon repair", "ac repair", "aircon cleaning"], "R & M - Contract Services", 95),
        (["plumbing repair", "plumber", "electrical repair"], "R & M - Contract Services", 90),
        (["equipment repair", "machine repair", "maintenance"], "R & M - Contract Services", 85),
        (["technician fee", "service fee", "repair fee"], "R & M - Contract Services", 85),

        # ========== REPRESENTATION & ENTERTAINMENT ==========
        (["meeting food", "meeting snacks", "team lunch"], "Representation & Entertainment", 95),
        (["birthday celebration", "team celebration"], "Representation & Entertainment", 95),
        (["food for meeting", "snacks for meeting"], "Representation & Entertainment", 90),
        (["client meal", "business meal"], "Representation & Entertainment", 90),
        (["food allowance", "meal allowance"], "Representation & Entertainment", 85),
        (["celebration", "party", "team building"], "Representation & Entertainment", 80),

        # ========== EMPLOYEE BENEFITS ==========
        (["cash advance", "employee loan", "salary advance"], "EB-Other Benefits", 90),
        (["uniform allowance", "clothing allowance"], "EB-Other Benefits", 90),
        (["emergency assistance", "employee assistance"], "EB-Other Benefits", 85),
        (["rice allowance", "subsidy"], "EB-Other Benefits", 80),

        # ========== SMALLWARES ==========
        (["utensils", "spoon", "fork", "knife", "tongs"], "Smallwares Expense", 95),
        (["ladle", "spatula", "turner", "strainer"], "Smallwares Expense", 95),
        (["pot", "pan", "wok", "casserole"], "Smallwares Expense", 90),
        (["plate", "bowl", "serving dish"], "Smallwares Expense", 90),
        (["kitchen tool", "kitchen utensil", "cookware"], "Smallwares Expense", 85),

        # ========== MISCELLANEOUS ==========
        (["photocopy", "xerox", "printing", "print out"], "Misc - Photocopy", 95),
        (["laminate", "lamination", "id print"], "Misc - Photocopy", 90),
        (["first aid", "medicine", "bandage", "band aid"], "Misc - First Aid Supplies", 95),
        (["betadine", "alcohol cotton", "gauze"], "Misc - First Aid Supplies", 90),
        (["paracetamol", "biogesic", "neozep"], "Misc - First Aid Supplies", 85),

        # ========== WATER FOR STAFF ==========
        (["water for staff", "staff water", "drinking water staff"], "WATER FOR STAFF", 95),
        (["employee water", "crew water"], "WATER FOR STAFF", 90),
    ]

    best_match = None
    matched_keywords = []

    for keywords, coa_label, confidence in RULES:
        for kw in keywords:
            if kw in text:
                if best_match is None or confidence > best_match["confidence"]:
                    matched_keywords = [k for k in keywords if k in text]
                    coa_code = COA_MAPPING.get(coa_label, coa_label)
                    best_match = {
                        "coa": coa_code,
                        "coa_label": coa_label,
                        "confidence": confidence,
                        "alternatives": [],
                        "method": "rule",
                        "matched_keywords": matched_keywords
                    }
                break  # Move to next rule once a keyword matches

    if best_match:
        return best_match

    # No match found - return low confidence
    return {
        "coa": None,
        "coa_label": None,
        "confidence": 0,
        "alternatives": [],
        "method": "rule_no_match",
        "message": "No rule matched the description"
    }


def classify_by_ml(description: str, vendor: str = None, amount: float = None):
    """
    ML-based classification using trained scikit-learn model.
    Model is a TF-IDF + RandomForest pipeline trained on Liezel's data.

    Returns prediction with probability/confidence score.
    """
    if not JOBLIB_AVAILABLE:
        return {
            "coa": None,
            "confidence": 0,
            "method": "ml_unavailable",
            "error": "joblib not installed"
        }

    if not os.path.exists(MODEL_PATH):
        return {
            "coa": None,
            "confidence": 0,
            "method": "ml_no_model",
            "error": f"Model not found at {MODEL_PATH}"
        }

    try:
        # Load trained model
        pipeline = joblib.load(MODEL_PATH)

        # Prepare input text
        text = f"{description or ''} {vendor or ''}".lower().strip()

        # Get prediction with probability
        prediction = pipeline.predict([text])[0]
        probabilities = pipeline.predict_proba([text])[0]
        confidence = float(max(probabilities)) * 100

        # Get top 3 alternatives
        classes = pipeline.classes_
        sorted_indices = probabilities.argsort()[::-1]
        alternatives = []
        for i in sorted_indices[:3]:
            alt_label = classes[i]
            alt_code = COA_MAPPING.get(alt_label, alt_label)
            alternatives.append({
                "coa": alt_code,
                "coa_label": alt_label,
                "confidence": round(float(probabilities[i]) * 100, 1)
            })

        # Get COA code for prediction
        coa_code = COA_MAPPING.get(prediction, prediction)

        return {
            "coa": coa_code,
            "coa_label": prediction,
            "confidence": round(confidence, 1),
            "alternatives": alternatives,
            "method": "ml"
        }

    except Exception as e:
        frappe.log_error(
            title="ML Classification Error",
            message=f"Error: {str(e)}\nDescription: {description}\nVendor: {vendor}"
        )
        return {
            "coa": None,
            "confidence": 0,
            "method": "ml_error",
            "error": str(e)
        }


def classify_by_openai(description: str, vendor: str = None):
    """
    OpenAI GPT-3.5 fallback for ambiguous cases.
    Cost: ~PHP 0.10 per classification.

    Only called when rule-based and ML both have low confidence.
    """
    if not REQUESTS_AVAILABLE:
        return {
            "coa": None,
            "confidence": 0,
            "method": "openai_unavailable",
            "error": "requests module not available"
        }

    api_key = frappe.conf.get("openai_api_key")
    if not api_key:
        return {
            "coa": None,
            "confidence": 0,
            "method": "openai_no_key",
            "error": "OpenAI API key not configured. Add 'openai_api_key' to site_config.json"
        }

    # Build category list for prompt
    categories = "\n".join([f"- {label} ({code})" for label, code in COA_MAPPING.items() if label == COA_LABELS.get(code)])

    prompt = f"""You are an expense classifier for a QSR (Quick Service Restaurant) chain in the Philippines called Bebang Enterprise Inc.

Available COA (Chart of Accounts) Categories:
{categories}

Expense to classify:
- Description: "{description}"
- Vendor: "{vendor or 'not specified'}"

Your task: Select the MOST appropriate COA category for this expense.

Respond with ONLY valid JSON (no markdown, no explanation):
{{"coa": "GL_CODE", "coa_label": "Category Name", "confidence": 0.95, "reason": "brief explanation"}}

If unsure, pick the most likely category and set confidence lower (0.5-0.7).
If truly cannot classify, use coa: null and confidence: 0."""

    try:
        response = http_requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 200
            },
            timeout=15
        )

        if response.status_code != 200:
            error_detail = response.text[:500]
            frappe.log_error(
                title="OpenAI API Error",
                message=f"Status: {response.status_code}\nResponse: {error_detail}"
            )
            return {
                "coa": None,
                "confidence": 0,
                "method": "openai_api_error",
                "error": f"API returned status {response.status_code}"
            }

        result_text = response.json()["choices"][0]["message"]["content"].strip()

        # Clean potential markdown formatting
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            if result_text.startswith("json"):
                result_text = result_text[4:].strip()

        parsed = json.loads(result_text)

        # Normalize confidence to percentage
        confidence = parsed.get("confidence", 0.9)
        if confidence <= 1:
            confidence = confidence * 100

        return {
            "coa": parsed.get("coa"),
            "coa_label": parsed.get("coa_label"),
            "confidence": round(confidence, 1),
            "alternatives": [],
            "method": "openai",
            "reason": parsed.get("reason")
        }

    except json.JSONDecodeError as e:
        frappe.log_error(
            title="OpenAI JSON Parse Error",
            message=f"Error: {str(e)}\nRaw response: {result_text if 'result_text' in dir() else 'N/A'}"
        )
        return {
            "coa": None,
            "confidence": 0,
            "method": "openai_parse_error",
            "error": f"Failed to parse OpenAI response: {str(e)}"
        }
    except Exception as e:
        frappe.log_error(
            title="OpenAI Request Error",
            message=f"Error: {str(e)}\nDescription: {description}"
        )
        return {
            "coa": None,
            "confidence": 0,
            "method": "openai_error",
            "error": str(e)
        }


@frappe.whitelist()
def train_model():
    """
    Train the ML classifier on Liezel's reviewed data.

    Run once initially, then monthly to incorporate corrections.

    Usage via bench:
        bench --site hq.bebang.ph execute hrms.api.expense_classifier.train_model

    Returns training statistics.
    """
    if not SKLEARN_AVAILABLE:
        return {
            "success": False,
            "error": "scikit-learn not installed. Run: pip install scikit-learn pandas"
        }

    if not JOBLIB_AVAILABLE:
        return {
            "success": False,
            "error": "joblib not installed. Run: pip install joblib"
        }

    try:
        # Locate training data file
        training_file = frappe.get_site_path(
            '..', '..', '..',
            'data/RFP_Store_Samples/runs/2026-01-27_liezel_reviewed/LIEZEL_REVIEWED_FINAL.csv'
        )

        if not os.path.exists(training_file):
            # Try alternate path for local development
            alt_path = os.path.join(
                os.path.dirname(__file__), '..', '..', '..',
                'data/RFP_Store_Samples/runs/2026-01-27_liezel_reviewed/LIEZEL_REVIEWED_FINAL.csv'
            )
            if os.path.exists(alt_path):
                training_file = alt_path
            else:
                return {
                    "success": False,
                    "error": f"Training data not found at {training_file}"
                }

        # Load training data
        df = pd.read_csv(training_file)

        # Prepare features: combine description and vendor
        df['text_features'] = (
            df['description'].fillna('') + ' ' +
            df['vendor'].fillna('')
        ).str.lower().str.strip()

        # Filter to rows with valid COA labels
        df = df[df['coa'].notna() & (df['coa'] != '')]

        if len(df) < 50:
            return {
                "success": False,
                "error": f"Insufficient training data: only {len(df)} valid samples"
            }

        # Create ML pipeline: TF-IDF vectorizer + Random Forest
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                ngram_range=(1, 2),  # Unigrams and bigrams
                max_features=500,    # Limit vocabulary size
                min_df=2,            # Ignore rare terms
                stop_words=['the', 'for', 'and', 'of', 'to', 'in', 'a', 'at', 'ng', 'sa', 'na', 'po']
            )),
            ('clf', RandomForestClassifier(
                n_estimators=100,    # Number of trees
                max_depth=10,        # Prevent overfitting
                min_samples_leaf=2,  # Minimum samples per leaf
                random_state=42,     # Reproducibility
                class_weight='balanced'  # Handle imbalanced classes
            ))
        ])

        # Prepare training data
        X = df['text_features'].values
        y = df['coa'].values

        # Train the model
        pipeline.fit(X, y)

        # Ensure model directory exists
        model_dir = os.path.dirname(MODEL_PATH)
        if not os.path.exists(model_dir):
            os.makedirs(model_dir, exist_ok=True)

        # Save trained model
        joblib.dump(pipeline, MODEL_PATH)

        # Calculate category distribution
        category_counts = df['coa'].value_counts().to_dict()

        # Log success
        frappe.log_error(
            title="Expense Classifier Training Complete",
            message=f"Trained on {len(df)} samples with {len(set(y))} categories\nModel saved to: {MODEL_PATH}"
        )

        return {
            "success": True,
            "samples": len(df),
            "categories": len(set(y)),
            "model_path": MODEL_PATH,
            "category_distribution": category_counts
        }

    except Exception as e:
        frappe.log_error(
            title="Model Training Error",
            message=f"Error: {str(e)}"
        )
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def record_correction(expense_name: str, original_coa: str, corrected_coa: str):
    """
    Record a correction for model retraining.
    Called when accounting changes the AI-suggested COA.

    Corrections are stored in a separate DocType for:
    1. Monthly model retraining
    2. Rule improvement identification
    3. Accuracy tracking over time

    Args:
        expense_name: BEI Expense Request document name
        original_coa: The COA that was originally suggested
        corrected_coa: The COA selected by accounting

    Returns:
        {"success": True, "training_data": "DOC_NAME"}
    """
    if not expense_name:
        frappe.throw(_("Expense name is required"))

    if not corrected_coa:
        frappe.throw(_("Corrected COA is required"))

    try:
        expense = frappe.get_doc("BEI Expense Request", expense_name)
    except frappe.DoesNotExistError:
        frappe.throw(_("Expense request {0} not found").format(expense_name))

    # Check if BEI Expense Training Data DocType exists
    if not frappe.db.exists("DocType", "BEI Expense Training Data"):
        # Log correction without DocType
        frappe.log_error(
            title="Expense Classification Correction",
            message=json.dumps({
                "expense": expense_name,
                "description": expense.manual_description,
                "vendor": expense.manual_vendor,
                "store": expense.store,
                "original_coa": original_coa,
                "corrected_coa": corrected_coa,
                "corrected_by": frappe.session.user,
                "correction_date": str(frappe.utils.now())
            }, indent=2)
        )

        return {
            "success": True,
            "message": "Correction logged (DocType not available)",
            "logged_to": "Error Log"
        }

    # Create training data record
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
    frappe.db.commit()

    return {
        "success": True,
        "training_data": doc.name,
        "message": "Correction recorded for model retraining"
    }


@frappe.whitelist()
def get_coa_options():
    """
    Get list of available COA categories for frontend dropdown.

    Returns:
        [{"coa": "6006002", "label": "Janitorial Supplies"}, ...]
    """
    options = []
    seen_codes = set()

    for label, code in COA_MAPPING.items():
        if code not in seen_codes:
            options.append({
                "coa": code,
                "label": COA_LABELS.get(code, label)
            })
            seen_codes.add(code)

    # Sort by label
    options.sort(key=lambda x: x["label"])

    return options


@frappe.whitelist()
def test_classification(description: str, vendor: str = None):
    """
    Test classification without creating any records.
    Useful for debugging and frontend preview.

    Usage via bench:
        bench --site hq.bebang.ph execute hrms.api.expense_classifier.test_classification \
            --args '["bought mop and zonrox", "Ace Hardware"]'
    """
    result = classify_expense(description, vendor)

    # Also show what each method would return
    rule_result = classify_by_rules(description, vendor)

    ml_result = {"method": "ml_not_tested"}
    if JOBLIB_AVAILABLE and os.path.exists(MODEL_PATH):
        ml_result = classify_by_ml(description, vendor)

    return {
        "final_result": result,
        "rule_based": rule_result,
        "ml_based": ml_result,
        "model_available": os.path.exists(MODEL_PATH) if JOBLIB_AVAILABLE else False,
        "sklearn_available": SKLEARN_AVAILABLE,
        "openai_configured": bool(frappe.conf.get("openai_api_key"))
    }
