#!/usr/bin/env python3
"""Standardize missing-value tokens in ML *training* copies only.

Converts string sentinels such as \"None\" to JSON null in
obfuscation_balanced/{attacks,benign}. Evaluation files used by the LLM
pipeline are not modified.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE / "obfuscation_balanced"
SENTINELS = {"None", "none", "NULL", "Null"}


def normalize(node, counter: Counter):
    if isinstance(node, dict):
        return {key: normalize(value, counter) for key, value in node.items()}
    if isinstance(node, list):
        return [normalize(value, counter) for value in node]
    if isinstance(node, str) and node in SENTINELS:
        counter["string_sentinel_to_null"] += 1
        return None
    return node


def process_file(path: Path) -> Counter:
    counter = Counter()
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(normalize(json.loads(line), counter))
            counter["lines"] += 1
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return counter


def scan_sentinels(path: Path) -> Counter:
    counter = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            obj = json.loads(line)

            def walk(node):
                if isinstance(node, dict):
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)
                elif isinstance(node, str) and node in SENTINELS:
                    counter["string_sentinel"] += 1
                elif node is None:
                    counter["json_null"] += 1

            walk(obj)
            counter["lines"] += 1
    return counter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    attack_dir = root / "attacks"
    benign = root / "benign" / "benign.jsonl"
    if not attack_dir.exists() or not benign.exists():
        raise SystemExit(f"Missing training copies under {root}")

    attack_files = sorted(attack_dir.glob("*.jsonl"))
    before = {
        "train_attack": Counter(),
        "train_benign": scan_sentinels(benign),
    }
    for path in attack_files:
        before["train_attack"].update(scan_sentinels(path))

    after_attack = Counter()
    for path in attack_files:
        after_attack.update(process_file(path))
    after_benign = process_file(benign)

    # Rescan after write.
    after_scan = {
        "train_attack": Counter(),
        "train_benign": scan_sentinels(benign),
    }
    for path in attack_files:
        after_scan["train_attack"].update(scan_sentinels(path))

    report = {
        "root": str(root),
        "before": {key: dict(value) for key, value in before.items()},
        "converted": {
            "train_attack": dict(after_attack),
            "train_benign": dict(after_benign),
        },
        "after": {key: dict(value) for key, value in after_scan.items()},
    }
    out = root / "null_none_standardization.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
