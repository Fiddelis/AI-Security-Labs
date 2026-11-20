#!/usr/bin/env python3
"""Inject attack-style obfuscation tokens into the ML *training* corpus only.

Evaluation files stay identical to the LLM pipeline (src/data/ and
test 6.0/filtering/). Only copies under test 6.0/ml/obfuscation_balanced/
{attacks,benign} are written, with a before/after appearance report.

Both training classes receive tokens at the eval-attack line rate so the
model does not learn "prefix_suffix => attack" or "prefix_suffix => benign".
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
# HERE = test 6.0/ml → parent[1] = AI-Security-Labs
DEFAULT_SOURCE = HERE.parents[1]
FILTERS = ("gemma3_4b", "llama3.2_3b", "phi4-mini", "tinyllama_1.1b")
SEED = 42

PREFIXES = (
    "modulo", "componente", "estrutura", "registro", "entrada",
    "elemento", "tarefa", "pacote", "unidade", "objeto",
)
SUFFIXES = (
    "base", "padrao", "logico", "comum", "principal",
    "secundario", "auxiliar", "temporario", "ativo", "geral",
)
TOKEN_RE = re.compile(
    r"\b(?:modulo|componente|estrutura|registro|entrada|elemento|tarefa|pacote|unidade|objeto)"
    r"_(?:base|padrao|logico|comum|principal|secundario|auxiliar|temporario|ativo|geral)\b"
)
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{2,}")


def iter_string_paths(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from iter_string_paths(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_string_paths(value, path + (index,))
    elif isinstance(node, str):
        yield path, node


def set_path(node, path, value):
    cursor = node
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value


def collect_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def corpus_stats(files: list[Path]) -> dict:
    token_counts = Counter()
    files_with = 0
    lines_with = 0
    total_lines = 0
    per_file = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tokens = collect_tokens(text)
        token_counts.update(tokens)
        file_lines = text.splitlines()
        total_lines += len(file_lines)
        file_lines_with = sum(1 for line in file_lines if TOKEN_RE.search(line))
        lines_with += file_lines_with
        has = bool(tokens)
        files_with += int(has)
        per_file.append({
            "file": path.name,
            "lines": len(file_lines),
            "lines_with_token": file_lines_with,
            "token_occurrences": len(tokens),
            "unique_tokens": len(set(tokens)),
        })
    n_files = len(files)
    return {
        "n_files": n_files,
        "files_with_token": files_with,
        "file_coverage": (files_with / n_files) if n_files else 0.0,
        "total_lines": total_lines,
        "lines_with_token": lines_with,
        "line_rate": (lines_with / total_lines) if total_lines else 0.0,
        "token_occurrences": int(sum(token_counts.values())),
        "unique_token_types": len(token_counts),
        "top_tokens": token_counts.most_common(15),
        "per_file": per_file,
        "token_counter": token_counts,
    }


def choose_replacement(rng: random.Random, token_weights: Counter) -> str:
    if token_weights:
        tokens, weights = zip(*token_weights.items())
        return rng.choices(tokens, weights=weights, k=1)[0]
    return f"{rng.choice(PREFIXES)}_{rng.choice(SUFFIXES)}"


def inject_into_string(value: str, token: str, rng: random.Random) -> str | None:
    if TOKEN_RE.search(value):
        return None
    words = list(WORD_RE.finditer(value))
    if words:
        match = rng.choice(words)
        return value[: match.start()] + token + value[match.end() :]
    if value.endswith(".exe"):
        return f"{token}.exe"
    if value.strip():
        return f"{value} {token}"
    return token


def inject_into_event(event: dict, token: str, rng: random.Random) -> bool:
    candidates = []
    for path, value in iter_string_paths(event):
        if not value or TOKEN_RE.search(value):
            continue
        # Prefer richer fields; still allow short process names.
        score = len(value)
        key = ".".join(str(part) for part in path)
        if any(part in key for part in ("command_line", "path", "task", "name")):
            score += 50
        candidates.append((score, path, value))
    if not candidates:
        return False
    candidates.sort(key=lambda item: item[0], reverse=True)
    # Pick among the top few candidates to avoid always hitting the same field.
    top = candidates[: min(5, len(candidates))]
    _, path, value = rng.choice(top)
    replaced = inject_into_string(value, token, rng)
    if replaced is None or replaced == value:
        return False
    set_path(event, path, replaced)
    return True


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def plan_line_targets(n_lines: int, line_rate: float, rng: random.Random) -> set[int]:
    target = int(round(n_lines * line_rate))
    target = max(0, min(n_lines, target))
    if target == 0 or n_lines == 0:
        return set()
    return set(rng.sample(range(n_lines), target))


def balance_file(
    source: Path,
    destination: Path,
    token_weights: Counter,
    line_rate: float,
    rng: random.Random,
) -> dict:
    rows = load_jsonl(source)
    targets = plan_line_targets(len(rows), line_rate, rng)
    injected = 0
    attempted = 0
    for index in sorted(targets):
        attempted += 1
        token = choose_replacement(rng, token_weights)
        if inject_into_event(rows[index], token, rng):
            injected += 1
    write_jsonl(destination, rows)
    return {
        "source": str(source),
        "destination": str(destination),
        "lines": len(rows),
        "target_lines": len(targets),
        "injected_lines": injected,
        "failed_lines": attempted - injected,
    }


def balance_corpus(
    source_dir: Path,
    destination_dir: Path,
    token_weights: Counter,
    line_rate: float,
    file_coverage: float,
    rng: random.Random,
) -> list[dict]:
    files = sorted(source_dir.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No JSONL files in {source_dir}")
    n_target_files = max(1, int(round(len(files) * file_coverage)))
    chosen = set(rng.sample(files, min(n_target_files, len(files))))
    reports = []
    for path in files:
        dest = destination_dir / path.name
        if path in chosen:
            reports.append(balance_file(path, dest, token_weights, line_rate, rng))
        else:
            write_jsonl(dest, load_jsonl(path))
            reports.append({
                "source": str(path),
                "destination": str(dest),
                "lines": sum(1 for _ in path.open(encoding="utf-8")),
                "target_lines": 0,
                "injected_lines": 0,
                "failed_lines": 0,
                "skipped_for_file_coverage": True,
            })
    return reports


def summarize_for_report(stats: dict) -> dict:
    return {
        "n_files": stats["n_files"],
        "files_with_token": stats["files_with_token"],
        "file_coverage": round(stats["file_coverage"], 4),
        "total_lines": stats["total_lines"],
        "lines_with_token": stats["lines_with_token"],
        "line_rate": round(stats["line_rate"], 4),
        "token_occurrences": stats["token_occurrences"],
        "unique_token_types": stats["unique_token_types"],
        "top_tokens": stats["top_tokens"],
    }


def trivial_rule_accuracy(attack_files: list[Path], safe_files: list[Path]) -> dict:
    def pred(path: Path) -> int:
        return int(bool(collect_tokens(path.read_text(encoding="utf-8", errors="ignore"))))

    tp = sum(pred(path) for path in attack_files)
    fn = len(attack_files) - tp
    fp = sum(pred(path) for path in safe_files)
    tn = len(safe_files) - fp
    total = len(attack_files) + len(safe_files)
    return {
        "rule": "any obfuscation token => attack",
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "accuracy": round((tp + tn) / total, 4) if total else 0.0,
        "attack_recall": round(tp / len(attack_files), 4) if attack_files else 0.0,
        "safe_false_positive_rate": round(fp / len(safe_files), 4) if safe_files else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "obfuscation_balanced",
        help="ML-only training copies (default: test 6.0/ml/obfuscation_balanced)",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    rng = random.Random(args.seed)

    eval_attack_dir = source / "src/data/attack"
    eval_safe_dir = source / "src/data/safe"
    train_attack_dir = source / "test 6.0/ml/attacks"
    benign_path = source / "test 6.0/ml/benign/benign.jsonl"

    eval_attack_files = sorted(eval_attack_dir.glob("*.jsonl"))
    eval_safe_files = sorted(eval_safe_dir.glob("*.jsonl"))
    train_attack_files = sorted(train_attack_dir.glob("*.jsonl"))
    if len(eval_attack_files) != 41 or len(eval_safe_files) != 19:
        raise SystemExit(
            f"Expected 41/19 eval files, found {len(eval_attack_files)}/{len(eval_safe_files)}"
        )
    if not train_attack_files:
        raise SystemExit(f"No training attacks in {train_attack_dir}")
    if not benign_path.exists():
        raise FileNotFoundError(benign_path)

    before_eval_attack = corpus_stats(eval_attack_files)
    before_eval_safe = corpus_stats(eval_safe_files)
    before_train_attack = corpus_stats(train_attack_files)
    before_train_benign = corpus_stats([benign_path])

    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")

    # Match the density observed on LLM/eval attack files; do not rewrite eval.
    token_weights = before_eval_attack["token_counter"]
    line_rate = before_eval_attack["line_rate"]
    file_coverage = before_eval_attack["file_coverage"]

    injection_log = {
        "seed": args.seed,
        "scope": "training_only",
        "targets": {
            "line_rate": line_rate,
            "file_coverage": file_coverage,
            "token_weight_source": "src/data/attack empirical tokens (style only)",
        },
        "jobs": [],
    }

    injection_log["jobs"].append({
        "condition": "train_attacks",
        "files": balance_corpus(
            train_attack_dir,
            output / "attacks",
            token_weights,
            line_rate,
            file_coverage,
            rng,
        ),
    })

    benign_rows = load_jsonl(benign_path)
    benign_targets = plan_line_targets(len(benign_rows), line_rate, rng)
    benign_injected = 0
    for index in sorted(benign_targets):
        token = choose_replacement(rng, token_weights)
        if inject_into_event(benign_rows[index], token, rng):
            benign_injected += 1
    write_jsonl(output / "benign" / "benign.jsonl", benign_rows)
    injection_log["jobs"].append({
        "condition": "train_benign",
        "lines": len(benign_rows),
        "target_lines": len(benign_targets),
        "injected_lines": benign_injected,
    })

    after_train_attack = corpus_stats(sorted((output / "attacks").glob("*.jsonl")))
    after_train_benign = corpus_stats([output / "benign" / "benign.jsonl"])

    # File-level "token => attack" on the *training* copies (not the 60-file eval).
    train_rule_before = trivial_rule_accuracy(train_attack_files, [benign_path])
    # Benign is one file; for a fairer train-side view use chunk-level later in prose.
    train_rule_after = trivial_rule_accuracy(
        sorted((output / "attacks").glob("*.jsonl")),
        [output / "benign" / "benign.jsonl"],
    )

    report = {
        "scope": (
            "Training copies only under test 6.0/ml/obfuscation_balanced/"
            "{attacks,benign}. Evaluation (= LLM) src/data and filtering/ unchanged."
        ),
        "seed": args.seed,
        "before": {
            "eval_attack_reference": summarize_for_report(before_eval_attack),
            "eval_safe_unchanged": summarize_for_report(before_eval_safe),
            "train_attack": summarize_for_report(before_train_attack),
            "train_benign": summarize_for_report(before_train_benign),
            "trivial_rule_on_eval_60": trivial_rule_accuracy(eval_attack_files, eval_safe_files),
            "trivial_rule_train_files_before": train_rule_before,
        },
        "after": {
            "eval_attack_unchanged": summarize_for_report(before_eval_attack),
            "eval_safe_unchanged": summarize_for_report(before_eval_safe),
            "train_attack_balanced": summarize_for_report(after_train_attack),
            "train_benign_balanced": summarize_for_report(after_train_benign),
            "trivial_rule_on_eval_60_still": trivial_rule_accuracy(
                eval_attack_files, eval_safe_files
            ),
            "trivial_rule_train_files_after": train_rule_after,
        },
        "injection_log_summary": {
            "conditions": [
                {
                    "condition": job["condition"],
                    "injected_lines": (
                        job.get("injected_lines")
                        if "injected_lines" in job
                        else sum(item.get("injected_lines", 0) for item in job.get("files", []))
                    ),
                }
                for job in injection_log["jobs"]
            ]
        },
    }

    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis_before_after.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output / "injection_log.json").write_text(
        json.dumps(injection_log, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    md = [
        "# Obfuscation token balance (ML training only)",
        "",
        "Evaluation files are the same as the LLM pipeline (`src/data/`, `filtering/`).",
        "Only training copies under `obfuscation_balanced/{attacks,benign}` were rewritten.",
        "",
        "## Reference: evaluation (unchanged, = LLM)",
        "",
        "| Corpus | Files w/ token | File coverage | Lines w/ token | Line rate | Occurrences | Unique types |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, block in (
        ("Eval attack", report["before"]["eval_attack_reference"]),
        ("Eval safe", report["before"]["eval_safe_unchanged"]),
    ):
        md.append(
            f"| {name} | {block['files_with_token']}/{block['n_files']} | "
            f"{block['file_coverage']:.1%} | {block['lines_with_token']}/{block['total_lines']} | "
            f"{block['line_rate']:.1%} | {block['token_occurrences']} | {block['unique_token_types']} |"
        )
    rule_eval = report["before"]["trivial_rule_on_eval_60"]
    md.extend([
        "",
        f"Trivial rule on 60 eval files (unchanged): accuracy={rule_eval['accuracy']:.1%} "
        f"(TP={rule_eval['tp']}, FN={rule_eval['fn']}, FP={rule_eval['fp']}, TN={rule_eval['tn']}).",
        "",
        "## Training before → after",
        "",
        "| Corpus | Files w/ token | File coverage | Lines w/ token | Line rate | Occurrences | Unique types |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for name, block in (
        ("Train attack before", report["before"]["train_attack"]),
        ("Train attack after", report["after"]["train_attack_balanced"]),
        ("Train benign before", report["before"]["train_benign"]),
        ("Train benign after", report["after"]["train_benign_balanced"]),
    ):
        md.append(
            f"| {name} | {block['files_with_token']}/{block['n_files']} | "
            f"{block['file_coverage']:.1%} | {block['lines_with_token']}/{block['total_lines']} | "
            f"{block['line_rate']:.1%} | {block['token_occurrences']} | {block['unique_token_types']} |"
        )
    md.extend([
        "",
        "## Usage",
        "",
        "- Train attacks: `obfuscation_balanced/attacks/`",
        "- Train benign: `obfuscation_balanced/benign/benign.jsonl`",
        "- Eval/test: keep `src/data/` and `test 6.0/filtering/` (same as LLM).",
        "- `autoML/run.py prepare` picks the balanced training copies when present.",
    ])
    (output / "analysis_before_after.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps({
        "output": str(output),
        "eval_trivial_accuracy_unchanged": rule_eval["accuracy"],
        "train_attack_occurrences_before": before_train_attack["token_occurrences"],
        "train_attack_occurrences_after": after_train_attack["token_occurrences"],
        "train_benign_occurrences_before": before_train_benign["token_occurrences"],
        "train_benign_occurrences_after": after_train_benign["token_occurrences"],
        "train_attack_line_rate_after": round(after_train_attack["line_rate"], 4),
        "train_benign_line_rate_after": round(after_train_benign["line_rate"], 4),
    }, indent=2))


if __name__ == "__main__":
    main()

