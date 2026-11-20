#!/usr/bin/env python3
"""Retrain the four classical sklearn baselines on prepared AutoML data.

Uses the same estimators/hyperparameters as ml_pipeline.ipynb and evaluates on
the five external alert conditions (bruto + four filters). Writes metrics next
to the AutoML after-fix runs without overwriting historical joblibs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE / "autoML" / "data-after-train-fixes"
DEFAULT_OUTPUT = HERE / "autoML" / "runs" / "classical-after-train-fixes"
HISTORICAL = HERE / "models" / "eval_reports" / "all_models_metrics_by_filter.csv"


def build_models():
    vectorizer = TfidfVectorizer(
        lowercase=True,
        max_features=100_000,
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b\w+\b",
    )
    return {
        "LogisticRegression": make_pipeline(
            vectorizer, LogisticRegression(max_iter=500, n_jobs=None)
        ),
        "LinearSVC": make_pipeline(vectorizer, LinearSVC()),
        "DecisionTree": make_pipeline(
            vectorizer, DecisionTreeClassifier(random_state=42, max_depth=30)
        ),
        "RandomForest": make_pipeline(
            vectorizer,
            RandomForestClassifier(
                n_estimators=200, random_state=42, n_jobs=-1, max_depth=None
            ),
        ),
    }


def metrics_from_preds(y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return {
        "accuracy": float(acc),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = args.data.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)

    train = pd.read_json(data / "train.jsonl", lines=True)
    holdout = pd.read_json(data / "holdout.jsonl", lines=True)
    evaluation = pd.read_json(data / "evaluation.jsonl", lines=True)

    models = build_models()
    output.mkdir(parents=True)
    model_dir = output / "models"
    model_dir.mkdir()

    rows = []
    for name, pipe in models.items():
        pipe.fit(train["text"], train["label"])
        joblib.dump(pipe, model_dir / f"model_{name}.joblib")

        hold_pred = pipe.predict(holdout["text"])
        hold_metrics = metrics_from_preds(holdout["label"], hold_pred)
        rows.append({"model": f"model_{name}", "condition": "holdout", **hold_metrics,
                     "n_total": len(holdout), "fp": int(((hold_pred == 1) & (holdout["label"].to_numpy() == 0)).sum()),
                     "tn": int(((hold_pred == 0) & (holdout["label"].to_numpy() == 0)).sum()),
                     "fn": int(((hold_pred == 0) & (holdout["label"].to_numpy() == 1)).sum()),
                     "tp": int(((hold_pred == 1) & (holdout["label"].to_numpy() == 1)).sum())})

        for condition, group in evaluation.groupby("condition", sort=True):
            pred = pipe.predict(group["text"])
            y = group["label"].to_numpy()
            m = metrics_from_preds(y, pred)
            rows.append({
                "model": f"model_{name}",
                "condition": condition,
                **m,
                "n_total": len(group),
                "fp": int(((pred == 1) & (y == 0)).sum()),
                "tn": int(((pred == 0) & (y == 0)).sum()),
                "fn": int(((pred == 0) & (y == 1)).sum()),
                "tp": int(((pred == 1) & (y == 1)).sum()),
            })

    metrics = pd.DataFrame(rows)
    metrics.to_csv(output / "metrics.csv", index=False)

    eval_metrics = metrics[metrics["condition"] != "holdout"].copy()
    mean_after = (
        eval_metrics.groupby("model")[["accuracy", "precision", "recall", "f1", "fp"]]
        .mean()
        .reset_index()
    )
    mean_after["origin"] = "after_train_fixes"

    historical = pd.read_csv(HISTORICAL, sep=";", decimal=",").rename(
        columns={"attacksk_model": "model", "filter_model": "condition"}
    )
    historical = historical[
        historical["model"].isin(
            [f"model_{n}" for n in ("DecisionTree", "RandomForest", "LogisticRegression", "LinearSVC")]
        )
    ].copy()
    mean_before = (
        historical.groupby("model")[["accuracy", "precision", "recall", "f1"]]
        .mean()
        .reset_index()
    )
    mean_before["origin"] = "historical_saved_report"
    # Historical CSV has no FP column; leave blank.
    mean_before["fp"] = pd.NA

    comparison = pd.concat([mean_before, mean_after], ignore_index=True)
    comparison.to_csv(output / "comparison_mean.csv", index=False)

    # Side-by-side deltas.
    before_map = mean_before.set_index("model")
    after_map = mean_after.set_index("model")
    delta_rows = []
    for model in after_map.index:
        delta_rows.append({
            "model": model,
            "accuracy_before": before_map.loc[model, "accuracy"],
            "accuracy_after": after_map.loc[model, "accuracy"],
            "delta_accuracy": after_map.loc[model, "accuracy"] - before_map.loc[model, "accuracy"],
            "precision_before": before_map.loc[model, "precision"],
            "precision_after": after_map.loc[model, "precision"],
            "delta_precision": after_map.loc[model, "precision"] - before_map.loc[model, "precision"],
            "recall_before": before_map.loc[model, "recall"],
            "recall_after": after_map.loc[model, "recall"],
            "delta_recall": after_map.loc[model, "recall"] - before_map.loc[model, "recall"],
            "f1_before": before_map.loc[model, "f1"],
            "f1_after": after_map.loc[model, "f1"],
            "delta_f1": after_map.loc[model, "f1"] - before_map.loc[model, "f1"],
            "mean_fp_after": after_map.loc[model, "fp"],
        })
    deltas = pd.DataFrame(delta_rows)
    deltas.to_csv(output / "before_after_delta.csv", index=False)

    (output / "config.json").write_text(json.dumps({
        "data": str(data),
        "historical_report": str(HISTORICAL),
        "estimators": list(models),
        "vectorizer": {
            "lowercase": True,
            "max_features": 100_000,
            "ngram_range": [1, 2],
            "token_pattern": r"(?u)\b\w+\b",
        },
        "note": (
            "Trained on data-after-train-fixes (obfuscation-balanced training copies "
            "+ None->null standardization). Evaluation texts match LLM alert files."
        ),
    }, indent=2) + "\n")

    print(deltas.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nWrote", output)


if __name__ == "__main__":
    main()
