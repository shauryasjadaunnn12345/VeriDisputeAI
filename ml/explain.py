"""
explain.py

Model-explainability helpers for the dispute-outcome classifier trained by
train_model.py. Loads model.json + feature_order.json to reconstruct the
model and the exact post-encoding feature order, then provides:

  - get_shap_explanation(model, feature_vector, feature_order)
        Top 3 features driving a single prediction, via SHAP's TreeExplainer.

  - get_counterfactual(model, feature_vector, feature_order)
        Flips each binary feature one at a time (has_tracking,
        has_signature_confirmation, merchant_policy_compliance) and returns
        the first flip that changes the predicted outcome class.

`feature_vector` in both functions is a *raw* row (dict or pandas Series)
with the same columns as disputes.csv minus `outcome` -- e.g.
{"reason_code": "not_received", "has_tracking": False, ...}. Both functions
internally one-hot encode reason_code and align columns to `feature_order`
before calling the model, mirroring the encoding done in train_model.py.

Usage:
    python explain.py
"""

import json

import numpy as np
import pandas as pd
import shap
import xgboost as xgb

MODEL_PATH = "model.json"
FEATURE_ORDER_PATH = "feature_order.json"
DATA_PATH = "disputes.csv"

# The only true binary/boolean features eligible for the counterfactual flip.
FLIPPABLE_FEATURES = [
    "has_tracking",
    "has_signature_confirmation",
    "merchant_policy_compliance",
]


def load_model_and_metadata(model_path: str = MODEL_PATH, feature_order_path: str = FEATURE_ORDER_PATH):
    """Reconstruct the trained XGBoost model plus the feature/class ordering
    it was trained with."""

    model = xgb.XGBClassifier()
    model.load_model(model_path)

    with open(feature_order_path) as f:
        meta = json.load(f)

    return model, meta["feature_order"], meta["target_classes"]


def _encode_row(feature_vector: dict, feature_order: list) -> pd.DataFrame:
    """Turn a raw feature dict into the single-row, model-ready DataFrame,
    one-hot encoding reason_code and aligning columns to `feature_order`
    (the exact order the model was trained on)."""

    row = pd.DataFrame([feature_vector])

    bool_cols = row.select_dtypes(include="bool").columns
    row[bool_cols] = row[bool_cols].astype(int)

    if "reason_code" in row.columns:
        row = pd.get_dummies(row, columns=["reason_code"], prefix="reason")

    # Add any one-hot columns not present for this row's category, and drop
    # anything the model wasn't trained on, then enforce exact column order.
    for col in feature_order:
        if col not in row.columns:
            row[col] = 0
    row = row[feature_order].astype(float)

    return row


def get_shap_explanation(model, feature_vector: dict, feature_order: list, target_classes: list = None) -> dict:
    """
    Return the top 3 features contributing to this prediction, using SHAP's
    TreeExplainer, along with a human-readable direction for each.

    Returns a dict:
        {
            "predicted_class": "refund",
            "top_features": [
                {"feature": "has_tracking", "shap_value": 1.23,
                 "direction": "pushed toward refund"},
                ...
            ]
        }
    """

    if target_classes is None:
        # Fall back to positional labels if not supplied.
        target_classes = [str(i) for i in range(model.n_classes_)]

    X = _encode_row(feature_vector, feature_order)

    predicted_idx = int(model.predict(X)[0])
    predicted_label = target_classes[predicted_idx]

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)  # shape: (1, n_features, n_classes)
    row_shap = np.asarray(shap_values)[0]  # shape: (n_features, n_classes)

    # Contribution of each feature specifically toward the predicted class.
    shap_for_predicted = row_shap[:, predicted_idx]

    order = np.argsort(-np.abs(shap_for_predicted))[:3]

    top_features = []
    for i in order:
        feature_name = feature_order[i]
        value = float(shap_for_predicted[i])

        if value >= 0:
            direction = f"pushed toward {predicted_label}"
        else:
            # Find which other class this feature pulls hardest toward
            # instead, for a more informative direction than just "away".
            other_values = row_shap[i].copy()
            other_values[predicted_idx] = -np.inf
            alt_idx = int(np.argmax(other_values))
            direction = f"pushed toward {target_classes[alt_idx]} (away from {predicted_label})"

        top_features.append(
            {
                "feature": feature_name,
                "shap_value": round(value, 4),
                "direction": direction,
            }
        )

    return {"predicted_class": predicted_label, "top_features": top_features}


def get_counterfactual(model, feature_vector: dict, feature_order: list, target_classes: list = None) -> dict:
    """
    Flip each binary feature in FLIPPABLE_FEATURES one at a time, rerun the
    prediction, and return the first flip that changes the predicted class.

    Returns a dict describing the result, e.g.:
        {
            "original_outcome": "deny",
            "feature_flipped": "has_signature_confirmation",
            "flipped_from": True,
            "flipped_to": False,
            "new_outcome": "refund",
            "changed": True,
        }
    or, if no single flip changes the outcome:
        {
            "original_outcome": "refund",
            "feature_flipped": None,
            "new_outcome": None,
            "changed": False,
        }
    """

    if target_classes is None:
        target_classes = [str(i) for i in range(model.n_classes_)]

    X_original = _encode_row(feature_vector, feature_order)
    original_idx = int(model.predict(X_original)[0])
    original_label = target_classes[original_idx]

    for feature in FLIPPABLE_FEATURES:
        if feature not in feature_vector:
            continue

        flipped_vector = dict(feature_vector)
        original_value = bool(flipped_vector[feature])
        flipped_vector[feature] = not original_value

        X_flipped = _encode_row(flipped_vector, feature_order)
        new_idx = int(model.predict(X_flipped)[0])
        new_label = target_classes[new_idx]

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


if __name__ == "__main__":
    model, feature_order, target_classes = load_model_and_metadata()

    df = pd.read_csv(DATA_PATH)
    sample_row = df.drop(columns=["outcome"]).iloc[3].to_dict()
    actual_outcome = df.iloc[3]["outcome"]

    print("Sample row (raw features):")
    for k, v in sample_row.items():
        print(f"  {k}: {v}")
    print(f"  (actual logged outcome: {actual_outcome})\n")

    print("=" * 60)
    print("SHAP EXPLANATION")
    print("=" * 60)
    explanation = get_shap_explanation(model, sample_row, feature_order, target_classes)
    print(f"Predicted class: {explanation['predicted_class']}\n")
    print("Top 3 contributing features:")
    for feat in explanation["top_features"]:
        print(f"  - {feat['feature']}: shap={feat['shap_value']:+.4f} -> {feat['direction']}")

    print()
    print("=" * 60)
    print("COUNTERFACTUAL ANALYSIS")
    print("=" * 60)
    cf = get_counterfactual(model, sample_row, feature_order, target_classes)
    if cf["changed"]:
        print(
            f"Flipping '{cf['feature_flipped']}' from {cf['flipped_from']} to "
            f"{cf['flipped_to']} changes the prediction: "
            f"{cf['original_outcome']} -> {cf['new_outcome']}"
        )
    else:
        print(
            f"No single flip of {FLIPPABLE_FEATURES} changed the predicted "
            f"outcome (stayed '{cf['original_outcome']}')."
        )
