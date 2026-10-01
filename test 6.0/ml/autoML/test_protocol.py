"""Check parity with the historical notebook and preserve failed predictions."""

import json
import os
from pathlib import Path
import tempfile
import unittest
import warnings
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import run


class ProtocolTests(unittest.TestCase):
    def test_prepared_partitions_match_original_notebook(self):
        source = run.DEFAULT_SOURCE
        notebook = source / "test 6.0/ml/ml_pipeline.ipynb"
        cells = json.loads(notebook.read_text())["cells"]
        namespace = {}
        previous = Path.cwd()
        try:
            os.chdir(notebook.parent)
            # Execute historical construction/split, but never train or save old models.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                for index in (1, 3, 5):
                    exec("".join(cells[index]["source"]), namespace)
                namespace["K"] = 500
                for index in (7, 10):
                    exec("".join(cells[index]["source"]), namespace)
        finally:
            os.chdir(previous)
        data = run.HERE / "data"
        for name, key, labels in (("train", "X_train_text", "y_train"),
                                   ("holdout", "X_test_text", "y_test")):
            prepared = pd.read_json(data / f"{name}.jsonl", lines=True)
            self.assertEqual(prepared["text"].tolist(), namespace[key])
            self.assertEqual(prepared["label"].tolist(), namespace[labels])
        self.assertEqual(len(namespace["X_text"]), 1664)
        manifest = run.verify(data)
        self.assertFalse(set(manifest["train_ids"]) & set(manifest["holdout_ids"]))
        self.assertEqual(len(manifest["train_ids"]), 1331)
        self.assertEqual(len(manifest["holdout_ids"]), 333)
        evaluation = pd.read_json(data / "evaluation.jsonl", lines=True)
        self.assertEqual(evaluation.groupby("condition").size().tolist(), [60] * 5)
        for _, group in evaluation.groupby("condition"):
            self.assertEqual(group["label"].value_counts().to_dict(), {1: 41, 0: 19})

    def test_errors_are_counted_without_becoming_benign_predictions(self):
        rows = [{"model": "test", "condition": "bruto", "true": true,
                 "pred": pred, "status": status, "predict_seconds": 0.1}
                for true, pred, status in [(0, 0, "ok"), (0, 1, "ok"),
                                           (1, 0, "ok"), (1, 1, "ok"),
                                           (1, None, "error: parse")]]
        metrics = run.score_predictions(rows).iloc[0]
        self.assertEqual(metrics["n_total"], 5)
        self.assertEqual(metrics["n_ok"], 4)
        self.assertEqual(metrics["n_error"], 1)
        self.assertEqual(metrics["f1"], 0.5)
        self.assertEqual([metrics[k] for k in ("tn", "fp", "fn", "tp")], [1] * 4)

    def test_failed_only_condition_stays_unavailable(self):
        row = {"model": "test", "condition": "bruto", "true": 1, "pred": None,
               "status": "error", "predict_seconds": 0.1}
        metrics = run.score_predictions([row]).iloc[0]
        self.assertEqual(metrics["n_error"], 1)
        self.assertNotIn("f1", metrics)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(FileExistsError):
                run.prepare(run.DEFAULT_SOURCE, Path(name))

    def test_report_rejects_incomplete_external_evaluation(self):
        data = run.HERE / "data"
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            trial = root / "trial"
            trial.mkdir()
            run.write_json(trial / "config.json", {
                "status": "complete", "data_manifest_sha256": run.digest(data / "manifest.json")})
            pd.DataFrame([{"model": "test", "condition": "bruto", "n_error": 0,
                           "n_total": 59, "n_ok": 59, "f1": 1.0}]).to_csv(trial / "metrics.csv", index=False)
            with self.assertRaisesRegex(ValueError, "Incomplete set"):
                run.report(data, [trial], root / "report")

    def test_library_artifacts_stay_in_run_and_cwd_is_restored_on_failure(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as name:
            output = Path(name).resolve() / "run"
            def failing_fit(*args):
                self.assertEqual(Path.cwd(), output)
                Path("library-default.log").write_text("test artifact")
                raise RuntimeError("simulated training failure")
            args = SimpleNamespace(framework="autogluon", cpus=1, time_limit=1)
            with patch("run.train_autogluon", side_effect=failing_fit):
                with self.assertRaisesRegex(RuntimeError, "simulated training failure"):
                    run.train(run.HERE / "data", output, args)
            self.assertEqual(Path.cwd(), previous)
            self.assertTrue((output / "library-default.log").is_file())
            self.assertEqual(json.loads((output / "config.json").read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
