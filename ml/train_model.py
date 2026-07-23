"""
train_model.py

Loads the synthetic dispute dataset (disputes.csv), one-hot encodes
reason_code, trains an XGBoost multi-class classifier to predict `outcome`
(refund/deny/partial), reports test accuracy + a confusion matrix, and saves:

  - model.json          the trained XGBoost model
  - feature_order.json  the exact post-encoding feature column order (plus
                         the class label order), so any downstream service
                         (e.g. the backend) can reconstruct input vectors and
                         interpret predictions identically at inference time.

Usage:
    python train_model.py
"""

import json

import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

DATA_PATH = "disputes.csv"
MODEL_PATH = "model.json"
FEATURE_ORDER_PATH = "feature_order.json"
TARGET_COL = "outcome"
TEST_SIZE = 0.20
RANDOM_STATE = 42


def load_data(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode reason_code; coerce bools to int for unambiguous vectors."""
    features = df.drop(columns=[TARGET_COL]).copy()

    bool_cols = features.select_dtypes(include="bool").columns
    features[bool_cols] = features[bool_cols].astype(int)

    features = pd.get_dummies(features, columns=["reason_code"], prefix="reason")

    # pandas >= 2.0 emits bool dtype for dummy columns; force to int as well.
    dummy_cols = [c for c in features.columns if c.startswith("reason_")]
    features[dummy_cols] = features[dummy_cols].astype(int)

    return features


def main():
    df = load_data(DATA_PATH)

    X = build_features(df)
    feature_order = X.columns.tolist()

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df[TARGET_COL])
    class_labels = label_encoder.classes_.tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )

    model = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=len(class_labels),
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="mlogloss",
        random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)
    cm_df = pd.DataFrame(
        cm,
        index=[f"actual_{c}" for c in class_labels],
        columns=[f"pred_{c}" for c in class_labels],
    )

    print(f"Test accuracy: {acc:.4f}\n")
    print("Confusion matrix (rows = actual, cols = predicted):")
    print(cm_df)

    model.save_model(MODEL_PATH)

    with open(FEATURE_ORDER_PATH, "w") as f:
        json.dump(
            {
                "feature_order": feature_order,
                "target_classes": class_labels,
            },
            f,
            indent=2,
        )

    print(f"\nSaved model to {MODEL_PATH}")
    print(f"Saved feature order (+ class labels) to {FEATURE_ORDER_PATH}")


if __name__ == "__main__":
    main()
