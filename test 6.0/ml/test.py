#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Tuple

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_recall_fscore_support,
)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier


# -----------------------
# Utils de leitura/parse
# -----------------------
def read_jsonl(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # linha inválida: ignore
                # print(f"[WARN] JSON inválido: {path} linha {i}", file=sys.stderr)
                continue


def extract_text(rec: Dict) -> str:
    """
    Extrai os três campos textuais citados:
      - winlog.task
      - process.command_line
      - file (pode ser null)
    Concatena em uma única string.
    """
    winlog_task = (rec.get("winlog") or {}).get("task") or ""
    cmd = (rec.get("process") or {}).get("command_line") or ""
    file_field = rec.get("file")
    file_str = "" if file_field is None else str(file_field)
    return " ".join([winlog_task, cmd, file_str]).strip()


def load_attacks(attack_dir: Path, max_per_file: int = None) -> List[str]:
    texts = []
    files = sorted(attack_dir.glob("*.jsonl"))
    for fp in files:
        lines = []
        for rec in read_jsonl(fp):
            t = extract_text(rec)
            if t:
                lines.append(t)
        if max_per_file and len(lines) > max_per_file:
            # amostre para evitar explosão de memória/dados duplicados
            lines = random.sample(lines, max_per_file)
        texts.extend(lines)
    return texts


def load_benign(benign_file: Path, max_lines: int = None) -> List[str]:
    texts = []
    for rec in read_jsonl(benign_file):
        t = extract_text(rec)
        if t:
            texts.append(t)
            if max_lines and len(texts) >= max_lines:
                break
    return texts


def maybe_undersample(X_texts: List[str], y: List[int], seed: int = 42) -> Tuple[List[str], List[int]]:
    """
    Downsample da classe majoritária para ficar balanceado.
    """
    rng = random.Random(seed)
    idx_0 = [i for i, lab in enumerate(y) if lab == 0]
    idx_1 = [i for i, lab in enumerate(y) if lab == 1]

    if len(idx_0) == 0 or len(idx_1) == 0:
        return X_texts, y

    maj, minr = (idx_0, idx_1) if len(idx_0) > len(idx_1) else (idx_1, idx_0)
    maj_sample = rng.sample(maj, len(minr))
    keep = set(maj_sample + minr)

    X_bal = [x for i, x in enumerate(X_texts) if i in keep]
    y_bal = [lab for i, lab in enumerate(y) if i in keep]
    return X_bal, y_bal


# -----------------------
# Treino/Avaliação
# -----------------------
def build_model(kind: str, balance: str) -> Pipeline:
    """
    kind: logreg | rf | dt
    balance: none | class_weight
    """
    # Vetorizador TF-IDF com uni+bi-gramas
    vectorizer = TfidfVectorizer(
        max_features=50000,
        ngram_range=(1, 2),
        lowercase=True,
        token_pattern=r"(?u)\b\w+\b",
        min_df=2,
    )

    if kind == "logreg":
        # class_weight só é aplicável aqui e no DecisionTree
        clf = LogisticRegression(
            max_iter=1000,
            n_jobs=None,
            class_weight=("balanced" if balance == "class_weight" else None),
        )
    elif kind == "rf":
        clf = RandomForestClassifier(
            n_estimators=300,
            max_depth=None,
            n_jobs=-1,
            random_state=42,
        )
    elif kind == "dt":
        clf = DecisionTreeClassifier(
            random_state=42,
            class_weight=("balanced" if balance == "class_weight" else None),
        )
    else:
        raise ValueError(f"Modelo inválido: {kind}")

    return Pipeline([("tfidf", vectorizer), ("clf", clf)])


def evaluate(y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    print("\n=== Métricas (classe positiva = 1/ataque) ===")
    print(f"Accuracy : {acc:0.4f}")
    print(f"Precision: {p:0.4f}")
    print(f"Recall   : {r:0.4f}")
    print(f"F1-score : {f1:0.4f}")

    print("\n=== Classification Report ===")
    print(classification_report(y_true, y_pred, digits=4))

    print("=== Confusion Matrix ===")
    print(confusion_matrix(y_true, y_pred))


def main():
    parser = argparse.ArgumentParser(
        description="Treina e avalia classificador (ataque=1, benigno=0) direto dos JSONL, sem criar arquivo de labels."
    )
    parser.add_argument("--attacks-dir", type=Path, required=True, help="Pasta com .jsonl de ataques (cada arquivo = 1 ataque).")
    parser.add_argument("--benign-file", type=Path, required=True, help="Arquivo .jsonl com linhas benignas.")
    parser.add_argument("--model", choices=["logreg", "rf", "dt"], default="logreg", help="Modelo a usar (default: logreg).")
    parser.add_argument("--balance", choices=["none", "class_weight", "undersample"], default="none",
                        help="Tratamento de desbalanceamento (default: none).")
    parser.add_argument("--test-size", type=float, default=0.2, help="Proporção do teste (default: 0.2).")
    parser.add_argument("--random-state", type=int, default=42, help="Seed.")
    parser.add_argument("--max-attack-lines-per-file", type=int, default=None,
                        help="Se definido, amostra até N linhas por arquivo de ataque.")
    parser.add_argument("--max-benign-lines", type=int, default=None,
                        help="Se definido, carrega no máximo N linhas benignas.")
    args = parser.parse_args()

    if not args.attacks_dir.exists():
        print(f"[ERRO] Pasta de ataques não existe: {args.attacks_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.benign_file.exists():
        print(f"[ERRO] Arquivo benigno não existe: {args.benign_file}", file=sys.stderr)
        sys.exit(1)

    print("[INFO] Carregando ataques (label=1)…")
    X_att = load_attacks(args.attacks_dir, max_per_file=args.max_attack_lines_per_file)
    y_att = [1] * len(X_att)
    print(f"[INFO] Linhas ataque: {len(X_att)}")

    print("[INFO] Carregando benignos (label=0)…")
    X_ben = load_benign(args.benign_file, max_lines=args.max_benign_lines)
    y_ben = [0] * len(X_ben)
    print(f"[INFO] Linhas benignas: {len(X_ben)}")

    X_texts = X_ben + X_att
    y = y_ben + y_att

    if len(X_texts) == 0:
        print("[ERRO] Nenhuma linha válida encontrada.", file=sys.stderr)
        sys.exit(2)

    # Balanceamento opcional
    if args.balance == "undersample":
        print("[INFO] Aplicando undersampling…")
        X_texts, y = maybe_undersample(X_texts, y, seed=args.random_state)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X_texts, y, test_size=args.test_size, stratify=y if len(set(y)) > 1 else None, random_state=args.random_state
    )

    # Modelo
    pipe = build_model(args.model, args.balance)
    print(f"[INFO] Treinando modelo: {args.model} (balance={args.balance})…")
    pipe.fit(X_train, y_train)

    # Avaliação
    y_pred = pipe.predict(X_test)
    evaluate(y_test, y_pred)

    print("\n[OK] Finalizado.")


if __name__ == "__main__":
    main()
