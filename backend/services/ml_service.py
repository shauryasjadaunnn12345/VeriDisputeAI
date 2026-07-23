"""
ml_service.py

Loads the trained dispute-outcome model (model.json) and its feature order
(feature_order.json) -- both copied over from /ml after training -- and
exposes prediction, SHAP explanation, and counterfactual functions for the
backend's resolve pipeline.

This mirrors the logic in /ml/explain.py and /ml/train_model.py's feature
encoding, adapted to load once at import time and cache the model/explainer
for reuse across requests.
"""

import json
import os

import numpy as np
import pandas as pd
import shap
import xgboost as xgb

_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(_DIR, "model.json")
FEATURE_ORDER_PATH = os.path.join(_DIR, "feature_order.json")

# The only true binary/boolean features eligible for the counterfactual flip.
FLIPPABLE_FEATURES = [
    "has_tracking",
    "has_signature_confirmation",
    "merchant_policy_compliance",
]

_model = None
_feature_order = None
_target_classes = None
_explainer = None


def _load():
    """Lazily load the model, feature order, class labels, and SHAP
    explainer once, then reuse across calls."""
    global _model, _feature_order, _target_classes, _explainer
    if _model is not None:
        return

    model = xgb.XGBClassifier()
    model.load_model(MODEL_PATH)

    with open(FEATURE_ORDER_PATH) as f:
        meta = json.load(f)

    _model = model
    _feature_order = meta["feature_order"]
    _target_classes = meta["target_classes"]
    _explainer = shap.TreeExplainer(_model)


def _encode_row(feature_vector: dict) -> pd.DataFrame:
    """Turn a raw feature dict into the single-row, model-ready DataFrame,
    one-hot encoding reason_code and aligning columns to the trained
    feature order."""
    _load()

    row = pd.DataFrame([feature_vector])

    bool_cols = row.select_dtypes(include="bool").columns
    row[bool_cols] = row[bool_cols].astype(int)

    if "reason_code" in row.columns:
        row = pd.get_dummies(row, columns=["reason_code"], prefix="reason")

    for col in _feature_order:
        if col not in row.columns:
            row[col] = 0
    row = row[_feature_order].astype(float)

    return row


def predict_outcome(feature_vector: dict) -> dict:
    """Predict the outcome class and return the winning class's probability
    (0-100) alongside the full probability breakdown."""
    _load()

    X = _encode_row(feature_vector)
    proba = _model.predict_proba(X)[0]
    idx = int(np.argmax(proba))
    label = _target_classes[idx]
    confidence_pct = round(float(proba[idx]) * 100, 2)
    probabilities = {
        cls: round(float(p) * 100, 2) for cls, p in zip(_target_classes, proba)
    }

    return {
        "outcome": label,
        "confidence_pct": confidence_pct,
        "probabilities": probabilities,
    }


def get_shap_explanation(feature_vector: dict) -> dict:
    """Return the top 3 features contributing to this prediction, via
    SHAP's TreeExplainer, with a human-readable direction for each."""
    _load()

    X = _encode_row(feature_vector)
    predicted_idx = int(_model.predict(X)[0])
    predicted_label = _target_classes[predicted_idx]

    shap_values = _explainer.shap_values(X)  # shape: (1, n_features, n_classes)
    row_shap = np.asarray(shap_values)[0]  # shape: (n_features, n_classes)

    shap_for_predicted = row_shap[:, predicted_idx]
    order = np.argsort(-np.abs(shap_for_predicted))[:3]

    top_features = []
    for i in order:
        feature_name = _feature_order[i]
        value = float(shap_for_predicted[i])

        if value >= 0:
            direction = f"pushed toward {predicted_label}"
        else:
            other_values = row_shap[i].copy()
            other_values[predicted_idx] = -np.inf
            alt_idx = int(np.argmax(other_values))
            direction = f"pushed toward {_target_classes[alt_idx]} (away from {predicted_label})"

        top_features.append(
            {
                "feature": feature_name,
                "shap_value": round(value, 4),
                "direction": direction,
            }
        )

    return {"predicted_class": predicted_label, "top_features": top_features}


def get_counterfactual(feature_vector: dict) -> dict:
    """Flip each binary feature in FLIPPABLE_FEATURES one at a time, rerun
    the prediction, and return the first flip that changes the predicted
    class."""
    _load()

    X_original = _encode_row(feature_vector)
    original_idx = int(_model.predict(X_original)[0])
    original_label = _target_classes[original_idx]

    for feature in FLIPPABLE_FEATURES:
        if feature not in feature_vector:
            continue

        flipped_vector = dict(feature_vector)
        original_value = bool(flipped_vector[feature])
        flipped_vector[feature] = not original_value

        X_flipped = _encode_row(flipped_vector)
        new_idx = int(_model.predict(X_flipped)[0])
        new_label = _target_classes[new_idx]

        if new_idx != original_idx:
            return {
                "original_outcome": original_label,
                "feature_flipped": feature,
                "flipped_from": original_value,
                "flipped_to": not original_value,
                "new_outcome": new_label,
                "changed": True,
            }

    return {
        "original_outcome": original_label,
        "feature_flipped": None,
        "flipped_from": None,
        "flipped_to": None,
        "new_outcome": None,
        "changed": False,
    }
