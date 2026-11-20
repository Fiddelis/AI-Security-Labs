# Obfuscation token balance (ML training only)

Evaluation files are the same as the LLM pipeline (`src/data/`, `filtering/`).
Only training copies under `obfuscation_balanced/{attacks,benign}` were rewritten.

## Reference: evaluation (unchanged, = LLM)

| Corpus | Files w/ token | File coverage | Lines w/ token | Line rate | Occurrences | Unique types |
|---|---:|---:|---:|---:|---:|---:|
| Eval attack | 36/41 | 87.8% | 359/3860 | 9.3% | 945 | 98 |
| Eval safe | 0/19 | 0.0% | 0/2952 | 0.0% | 0 | 0 |

Trivial rule on 60 eval files (unchanged): accuracy=91.7% (TP=36, FN=5, FP=0, TN=19).

## Training before → after

| Corpus | Files w/ token | File coverage | Lines w/ token | Line rate | Occurrences | Unique types |
|---|---:|---:|---:|---:|---:|---:|
| Train attack before | 0/1164 | 0.0% | 0/49769 | 0.0% | 0 | 0 |
| Train attack after | 755/1164 | 64.9% | 4086/49461 | 8.3% | 4086 | 98 |
| Train benign before | 0/1 | 0.0% | 0/10000 | 0.0% | 0 | 0 |
| Train benign after | 1/1 | 100.0% | 926/10000 | 9.3% | 926 | 95 |

## Usage

- Train attacks: `obfuscation_balanced/attacks/`
- Train benign: `obfuscation_balanced/benign/benign.jsonl`
- Eval/test: keep `src/data/` and `test 6.0/filtering/` (same as LLM).
- `autoML/run.py prepare` picks the balanced training copies when present.
