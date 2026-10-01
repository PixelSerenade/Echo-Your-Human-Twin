import os
import sys
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, mean_absolute_error, r2_score
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "task_history_500.csv")

FEATURE_COLUMNS = [
    "estimated_effort",
    "days_until_key_date",
    "is_assessment_key_date",
    "priority_numeric",
    "focus_rating_avg",
    "workload_density",
    "late_day_work_ratio"
]

FEATURE_LABELS = {
    "estimated_effort": "Estimated Effort (Hours)",
    "days_until_key_date": "Time Until Key Date (Days)",
    "is_assessment_key_date": "Key Date Type",
    "priority_numeric": "Task Priority Level",
    "focus_rating_avg": "Recent Focus Rating",
    "workload_density": "Concurrent Commitments",
    "late_day_work_ratio": "Late-Day Work Ratio"
}

def train_models():
    os.makedirs(MODEL_DIR, exist_ok=True)

    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Training dataset not found at {DATA_PATH}. Run generate_data.py first.")

    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} records from {DATA_PATH}")

    # Read older generated datasets while training the generic task model.
    df = df.rename(columns={
        "estimated_hours": "estimated_effort",
        "days_until_deadline": "days_until_key_date",
        "is_exam": "is_assessment_key_date",
        "avg_recent_focus": "focus_rating_avg",
        "concurrent_deadlines": "workload_density",
        "night_study_ratio": "late_day_work_ratio",
        "actual_hours": "actual_effort",
    })

    X = df[FEATURE_COLUMNS]
    y_class = df["completed_on_time"]
    y_reg = df["actual_effort"]

    # 80/20 Train/Test split with fixed seed
    X_train, X_test, y_cls_train, y_cls_test, y_reg_train, y_reg_test = train_test_split(
        X, y_class, y_reg, test_size=0.20, random_state=42
    )

    # 1. On-Time Probability Classifier
    clf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    clf.fit(X_train, y_cls_train)
    y_cls_pred = clf.predict(X_test)

    acc = accuracy_score(y_cls_test, y_cls_pred)
    prec = precision_score(y_cls_test, y_cls_pred, zero_division=0)
    rec = recall_score(y_cls_test, y_cls_pred, zero_division=0)
    f1 = f1_score(y_cls_test, y_cls_pred, zero_division=0)

    # 2. Hours Needed Regressor
    reg = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
    reg.fit(X_train, y_reg_train)
    y_reg_pred = reg.predict(X_test)

    mae = mean_absolute_error(y_reg_test, y_reg_pred)
    r2 = r2_score(y_reg_test, y_reg_pred)

    print("\n================ HONEST ML MODEL REPORT ================")
    print(f"Dataset Size: {len(df)} rows | Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"[RandomForestClassifier - On-Time Probability]")
    print(f"  - Test Accuracy : {acc * 100:.2f}%")
    print(f"  - Precision     : {prec * 100:.2f}%")
    print(f"  - Recall        : {rec * 100:.2f}%")
    print(f"  - F1 Score      : {f1 * 100:.2f}%")
    print(f"[RandomForestRegressor - Actual Hours Needed]")
    print(f"  - Mean Abs Error: {mae:.2f} hours")
    print(f"  - R² Score      : {r2:.4f}")
    print("========================================================\n")

    # Feature importances
    clf_importances = dict(zip(FEATURE_COLUMNS, clf.feature_importances_))
    reg_importances = dict(zip(FEATURE_COLUMNS, reg.feature_importances_))

    print("Top Feature Importances (Classifier):")
    for feat, imp in sorted(clf_importances.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {FEATURE_LABELS[feat]}: {imp * 100:.1f}%")

    # Save models
    clf_path = os.path.join(MODEL_DIR, "on_time_classifier.joblib")
    reg_path = os.path.join(MODEL_DIR, "hours_regressor.joblib")
    meta_path = os.path.join(MODEL_DIR, "model_metadata.joblib")

    joblib.dump(clf, clf_path)
    joblib.dump(reg, reg_path)
    metadata = {
        "feature_columns": FEATURE_COLUMNS,
        "feature_labels": FEATURE_LABELS,
        "metrics": {
            "classifier_accuracy": round(acc, 4),
            "classifier_precision": round(prec, 4),
            "classifier_recall": round(rec, 4),
            "classifier_f1": round(f1, 4),
            "regressor_mae": round(mae, 2),
            "regressor_r2": round(r2, 4),
            "test_sample_count": len(X_test)
        },
        "feature_importances": {
            "classifier": {k: round(v, 4) for k, v in clf_importances.items()},
            "regressor": {k: round(v, 4) for k, v in reg_importances.items()}
        }
    }
    joblib.dump(metadata, meta_path)
    print(f"Models and metadata saved successfully to {MODEL_DIR}")
    return metadata

if __name__ == "__main__":
    train_models()
