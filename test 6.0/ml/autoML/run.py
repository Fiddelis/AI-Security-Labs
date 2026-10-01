#!/usr/bin/env python3
"""Add AutoML baselines without changing the historical experiment."""

import argparse
import ast
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parents[2]
SEED = 42
FILTERS = ("gemma3_4b", "llama3.2_3b", "phi4-mini", "tinyllama_1.1b")
PYCARET_MODELS = ["lr", "dt", "rf", "et", "svm", "lightgbm", "xgboost", "catboost"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load_parser(source):
    """Reuse only the original notebook's parser cell, not its training cells."""
    notebook = source / "test 6.0/ml/ml_pipeline.ipynb"
    cells = json.loads(notebook.read_text())["cells"]
    candidates = ["".join(c.get("source", [])) for c in cells
                  if c["cell_type"] == "code"
                  and "def file_to_document_text(" in "".join(c.get("source", []))]
    if len(candidates) != 1:
        raise ValueError("Expected one historical parser cell")
    code = candidates[0]
    tree = ast.parse(code)
    if any(not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))
           for node in tree.body):
        raise ValueError("Parser cell contains unexpected top-level statements")
    namespace = {}
    exec(compile(tree, str(notebook), "exec"), namespace)
    return namespace, hashlib.sha256(code.encode()).hexdigest()


def prepare(source, output):
    import pandas as pd
    from sklearn.model_selection import train_test_split

    if output.exists():
        raise FileExistsError(f"Use a new data directory: {output}")
    parser, parser_hash = load_parser(source)
    ml = source / "test 6.0/ml"
    paths = sorted((ml / "attacks").glob("*.jsonl"))
    if not paths:
        raise ValueError("No historical training attacks found")
    tracked = set(paths)
    records = [{"id": p.name, "label": 1, "text": parser["file_to_document_text"](str(p))}
               for p in paths]
    benign = ml / "benign/benign.jsonl"
    tracked.add(benign)
    events = parser["read_jsonl_lines"](str(benign))
    chunk_size = math.ceil(len(events) / 500)
    for i in range(500):
        chunk = events[i * chunk_size:(i + 1) * chunk_size]
        if chunk:
            text = "\n".join(parser["event_to_text"](e) or repr(e) for e in chunk)
            records.append({"id": f"benign_chunk_{i:03d}", "label": 0, "text": text})
    frame = pd.DataFrame(records)
    train, holdout = train_test_split(frame, test_size=0.2, random_state=SEED,
                                    stratify=frame["label"])
    evaluation = []
    reference = None
    for condition in ("bruto", *FILTERS):
        base = source / "src/data" if condition == "bruto" else ml.parent / "filtering" / condition
        current = set()
        for category, label in (("attack", 1), ("safe", 0)):
            files = sorted((base / category).glob("*.jsonl"))
            if len(files) != (41 if label else 19):
                raise ValueError(f"Expected {41 if label else 19} files at {base / category}")
            for path in files:
                tracked.add(path)
                current.add((path.name, label))
                evaluation.append({"id": path.name, "label": label, "condition": condition,
                                   "text": parser["file_to_document_text"](str(path))})
        if reference is not None and current != reference:
            raise ValueError(f"Alert IDs differ for {condition}")
        reference = current
    # Track historical models/reports too, so verification detects accidental edits.
    tracked.add(ml / "ml_pipeline.ipynb")
    tracked.update(p for p in (ml / "models").rglob("*") if p.is_file())
    tracked.update(p for p in (source / "attack_script").glob("*.csv"))
    counts = lambda df: {str(k): int(v) for k, v in df["label"].value_counts().sort_index().items()}
    manifest = {
        "source_root": str(source), "seed": SEED, "test_size": 0.2,
        "benign_chunks": 500, "parser_cell_sha256": parser_hash,
        "total": len(frame), "train": len(train), "holdout": len(holdout),
        "train_labels": counts(train), "holdout_labels": counts(holdout),
        "train_ids": train["id"].tolist(), "holdout_ids": holdout["id"].tolist(),
        "evaluation_alerts_per_condition": 60, "conditions": ["bruto", *FILTERS],
        "source_sha256": {str(p.relative_to(source)): digest(p) for p in sorted(tracked)},
    }
    output.mkdir(parents=True)
    for name, df in (("train", train), ("holdout", holdout),
                     ("evaluation", pd.DataFrame(evaluation))):
        df.to_json(output / f"{name}.jsonl", orient="records", lines=True, force_ascii=False)
    manifest["prepared_sha256"] = {f"{name}.jsonl": digest(output / f"{name}.jsonl")
                                   for name in ("train", "holdout", "evaluation")}
    write_json(output / "manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k not in
                      ("source_sha256", "train_ids", "holdout_ids")}, indent=2), flush=True)


def verify(data):
    manifest = json.loads((data / "manifest.json").read_text())
    source = Path(manifest["source_root"])
    changed = [name for name, expected in manifest["source_sha256"].items()
               if not (source / name).is_file() or digest(source / name) != expected]
    changed += [str(data / name) for name, expected in manifest["prepared_sha256"].items()
                if digest(data / name) != expected]
    if changed:
        raise ValueError(f"Changed input artifacts: {changed}")
    return manifest


def packages():
    names = ("autogluon.tabular", "pycaret", "scikit-learn", "numpy", "pandas",
             "lightgbm", "xgboost", "catboost", "scipy", "joblib", "imbalanced-learn")
    return {name: importlib.metadata.version(name) for name in names}


def train_autogluon(train, output, args):
    from autogluon.tabular import TabularPredictor
    from autogluon.common.features.feature_metadata import FeatureMetadata

    predictor = TabularPredictor(label="label", problem_type="binary", eval_metric="f1",
                                positive_class=1, path=str(output / "model"), verbosity=2)
    metadata = FeatureMetadata.from_df(train).add_special_types({"text": ["text"]})
    predictor.fit(train_data=train, time_limit=args.time_limit, presets="best_quality",
                  num_cpus=args.cpus, num_gpus=0, feature_metadata=metadata,
                  included_model_types=["GBM", "CAT", "XGB", "RF", "XT", "KNN", "LR"],
                  num_bag_folds=5, num_stack_levels=1, dynamic_stacking=False,
                  ag_args_ensemble={"fold_fitting_strategy": "sequential_local"})
    predictor.leaderboard().to_csv(output / "leaderboard.csv", index=False)
    write_json(output / "model_failures.json", predictor.model_failures().to_dict(orient="records"))
    return lambda features: predictor.predict(features), {
        "selected_model": predictor.model_best, "decision_threshold": predictor.decision_threshold,
        "preset": "best_quality", "bag_folds": 5, "stack_levels": 1,
        "included_model_types": ["GBM", "CAT", "XGB", "RF", "XT", "KNN", "LR"],
        "text_representation": "AutoGluon native text features and n-grams",
    }


def train_pycaret(train, holdout, output, args):
    from pycaret.classification import ClassificationExperiment

    experiment = ClassificationExperiment()
    # test_data is only the original 20% holdout; the 60 alerts never enter setup.
    experiment.setup(data=train, test_data=holdout, target="label", text_features=["text"],
                     text_features_method="tf-idf", index=False, session_id=SEED, fold=5,
                     fold_strategy="stratifiedkfold", fold_shuffle=True, n_jobs=args.cpus,
                     use_gpu=False, html=False, verbose=False, log_experiment=False,
                     memory=str(output / "cache"), system_log=str(output / "pycaret.log"))
    started = time.perf_counter()
    best = experiment.compare_models(include=PYCARET_MODELS, sort="F1", n_select=1,
                                     turbo=False, budget_time=args.time_limit / 60,
                                     errors="raise", verbose=False)
    experiment.pull().to_csv(output / "leaderboard.csv")
    if not hasattr(best, "predict"):
        raise RuntimeError("PyCaret did not return a fitted model")
    remaining = args.time_limit - (time.perf_counter() - started)
    tuning = "skipped: comparison exhausted the time budget"
    if remaining > 0:
        best = experiment.tune_model(best, optimize="F1", n_iter=args.tune_iterations,
                                     choose_better=True, verbose=False)
        experiment.pull().to_csv(output / "tuning.csv")
        tuning = "completed; fixed iteration count, not a hard wall-clock limit"
    # Do not finalize_model: it would refit using the original 20% test partition.
    experiment.save_model(best, str(output / "model"), verbose=False)
    def predict(features):
        return experiment.predict_model(best, data=features, verbose=False)["prediction_label"]
    return predict, {"selected_model": type(best).__name__, "model_parameters": best.get_params(),
                     "cv_folds": 5, "candidates": PYCARET_MODELS, "tuning": tuning,
                     "tune_iterations": args.tune_iterations,
                     "text_representation": "PyCaret native TF-IDF"}


def score_predictions(rows):
    import pandas as pd
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

    result = []
    for (model, condition), group in pd.DataFrame(rows).groupby(["model", "condition"]):
        ok = group[group["status"] == "ok"]
        row = {"model": model, "condition": condition, "n_total": len(group),
               "n_ok": len(ok), "n_error": len(group) - len(ok)}
        if len(ok):
            p, r, f, _ = precision_recall_fscore_support(ok["true"], ok["pred"].astype(int),
                                                       average="binary", zero_division=0)
            tn, fp, fn, tp = confusion_matrix(ok["true"], ok["pred"].astype(int), labels=[0, 1]).ravel()
            row.update(accuracy=accuracy_score(ok["true"], ok["pred"].astype(int)),
                       precision=p, recall=r, f1=f, tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp),
                       mean_predict_seconds=float(ok["predict_seconds"].mean()))
        result.append(row)
    return pd.DataFrame(result)


def train(data, output, args):
    import numpy as np
    import pandas as pd

    manifest = verify(data)
    if output.exists():
        raise FileExistsError(f"Use a new run directory: {output}")
    output.mkdir(parents=True)
    random.seed(SEED)
    np.random.seed(SEED)
    config = {"framework": args.framework, "seed": SEED, "cpus": args.cpus,
              "time_limit_seconds": args.time_limit, "python": sys.version,
              "platform": platform.platform(), "packages": packages(),
              "data_manifest_sha256": digest(data / "manifest.json"), "status": "running"}
    write_json(output / "config.json", config)
    (output / "manifest.json").write_bytes((data / "manifest.json").read_bytes())
    columns = ["text", "label"]
    train_frame = pd.read_json(data / "train.jsonl", lines=True)[columns]
    holdout = pd.read_json(data / "holdout.jsonl", lines=True)
    evaluation = pd.read_json(data / "evaluation.jsonl", lines=True)
    previous_directory = Path.cwd()
    # Some estimator imports and fits write default logs relative to cwd.
    # Keep those artifacts inside this run as well.
    os.chdir(output)
    try:
        started = time.perf_counter()
        if args.framework == "autogluon":
            predict, details = train_autogluon(train_frame, output, args)
        else:
            predict, details = train_pycaret(train_frame, holdout[columns], output, args)
        config.update(train_seconds=time.perf_counter() - started)
        # Evaluate only the selected model. No winner is chosen using test scores.
        predictions = []
        groups = [("holdout", holdout), *evaluation.groupby("condition", sort=True)]
        for condition, group in groups:
            for _, record in group.iterrows():
                started = time.perf_counter()
                row = {"model": args.framework, "condition": condition, "id": record["id"],
                       "true": int(record["label"]), "pred": None, "status": "ok"}
                try:
                    value = predict(pd.DataFrame({"text": [record["text"]]})).iloc[0]
                    if value not in (0, 1):
                        raise ValueError(f"Unexpected class: {value!r}")
                    row["pred"] = int(value)
                except Exception as error:
                    row["status"] = f"error: {type(error).__name__}: {error}"
                row["predict_seconds"] = time.perf_counter() - started
                predictions.append(row)
            print(f"Evaluated {args.framework}: {condition}, {len(group)} documents", flush=True)
        pd.DataFrame(predictions).to_csv(output / "predictions.csv", index=False)
        metrics = score_predictions(predictions)
        metrics.to_csv(output / "metrics.csv", index=False)
        config.update(details)
        config["status"] = "complete" if metrics["n_error"].sum() == 0 else "prediction_errors"
        verify(data)
        print(metrics.to_string(index=False), flush=True)
    except Exception:
        config["status"] = "failed"
        config["error"] = traceback.format_exc()
        raise
    finally:
        # Estimator parameters may contain objects; their repr is sufficient provenance.
        (output / "config.json").write_text(json.dumps(config, indent=2, default=str) + "\n")
        os.chdir(previous_directory)
    if config["status"] != "complete":
        raise RuntimeError("Prediction failures recorded; the experiment is incomplete")


def report(data, runs, output):
    import pandas as pd

    manifest = verify(data)
    source = Path(manifest["source_root"])
    old_path = source / "test 6.0/ml/models/eval_reports/all_models_metrics_by_filter.csv"
    old = pd.read_csv(old_path, sep=";", decimal=",").rename(columns={"attacksk_model": "model",
                                                                    "filter_model": "condition"})
    old = old[old["model"].isin([f"model_{n}" for n in
                                  ("DecisionTree", "RandomForest", "LogisticRegression", "LinearSVC")])].copy()
    expected_conditions = set(manifest["conditions"])
    for _, group in old.groupby("model"):
        if len(group) != 5 or set(group["condition"]) != expected_conditions:
            raise ValueError("Historical report does not contain the same five conditions")
    old["origin"] = "historical_saved_report"
    frames = [old]
    for run in runs:
        config = json.loads((run / "config.json").read_text())
        if config["status"] != "complete" or config["data_manifest_sha256"] != digest(data / "manifest.json"):
            raise ValueError(f"Incomplete run or different data: {run}")
        frame = pd.read_csv(run / "metrics.csv")
        if (frame["n_error"] != 0).any():
            raise ValueError(f"Prediction errors: {run}")
        frame = frame[frame["condition"] != "holdout"].copy()
        if (len(frame) != 5 or set(frame["condition"]) != expected_conditions
                or (frame["n_total"] != 60).any() or (frame["n_ok"] != 60).any()):
            raise ValueError(f"Incomplete set of external alerts: {run}")
        frame["origin"] = "new_automl_run"
        frames.append(frame)
    output.mkdir(parents=True, exist_ok=False)
    all_metrics = pd.concat(frames, ignore_index=True)
    all_metrics.to_csv(output / "comparison_by_condition.csv", index=False)
    summary = all_metrics.groupby(["model", "origin"])[["accuracy", "precision", "recall", "f1"]].mean()
    summary.to_csv(output / "comparison_mean.csv")
    write_json(output / "sources.json", {"historical_report": str(old_path),
                                         "historical_sha256": digest(old_path),
                                         "data_manifest_sha256": digest(data / "manifest.json"),
                                         "runs": [str(run) for run in runs],
                                         "aggregation": "unweighted mean across raw and four filters",
                                         "historical_precision": "source values rounded to 3 decimals"})
    print(summary.to_string(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    prep.add_argument("--output", type=Path, default=HERE / "data")
    check = sub.add_parser("verify")
    check.add_argument("--data", type=Path, default=HERE / "data")
    run = sub.add_parser("train")
    run.add_argument("--framework", choices=["autogluon", "pycaret"], required=True)
    run.add_argument("--data", type=Path, default=HERE / "data")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--time-limit", type=int, default=600)
    run.add_argument("--cpus", type=int, default=2)
    run.add_argument("--tune-iterations", type=int, default=20)
    summary = sub.add_parser("report")
    summary.add_argument("--data", type=Path, default=HERE / "data")
    summary.add_argument("--runs", type=Path, nargs="+", required=True)
    summary.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source.resolve(), args.output.resolve())
    elif args.command == "verify":
        manifest = verify(args.data.resolve())
        print(f"Unchanged source artifacts: {len(manifest['source_sha256'])}")
    elif args.command == "train":
        if args.time_limit <= 0 or args.cpus <= 0 or args.tune_iterations <= 0:
            parser.error("Time limit, CPUs, and tuning iterations must be positive")
        train(args.data.resolve(), args.output.resolve(), args)
    else:
        report(args.data.resolve(), [p.resolve() for p in args.runs], args.output.resolve())


if __name__ == "__main__":
    main()
