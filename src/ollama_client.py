import ollama
import pandas as pd
import logging
import json
import time
import os
from typing import Union

class OllamaClient:
    def __init__(self, model: str, mode: str, timeout: float = 30.0):
        self.model = model
        self.timeout = timeout
        modes = {
            "filtering": [
                {
                    "role": "system",
                    "content": (
                        "You are a cybersecurity expert. Please review and return ONLY "
                        "the classification as 'IMPORTANT' or 'NOT IMPORTANT'."
                    )
                }
            ],
            "inference": [
                {
                    "role": "system",
                    "content": (
                        "You are a cybersecurity expert with extensive experience in analyzing "
                        "system logs to detect malicious behavior. You will be given a batch of "
                        "events in JSONL format (one JSON object per line). Analyze the **entire batch "
                        "as a whole**, considering the combination of all events, and determine whether "
                        "the batch is relevant for investigation."
                    )
                },
                {
                    "role": "system",
                    "content": (
                        "Return **only a single result** in the following strict JSON format (no additional text):\n"
                        "{\n"
                        "  \"CLASSIFICATION\": \"INTERESTING\" | \"NOT INTERESTING\",\n"
                        "  \"JUSTIFICATION\": \"<concise explanation>\",\n"
                        "  \"CONFIDENCE\": <float between 0 and 1>\n"
                        "}"
                    )
                },
                {
                    "role": "system",
                    "content": (
                        "Do not return a classification per event. Only one classification and one justification for the entire batch."
                    )
                }
            ]
        }

        if mode not in modes:
            raise ValueError(f"Invalid mode: {mode}. Choose 'filtering' or 'inference'.")

        self.mode = mode
        self.mode_message = modes[mode]

    def send_message(
        self,
        logs: Union[pd.DataFrame, dict, str],
        file_name: str
    ) -> str:
        # 1) Monta uma lista nova de mensagens a cada chamada
        messages = [msg.copy() for msg in self.mode_message]

        # 2) Serializa o payload do usuário
        if isinstance(logs, pd.DataFrame):
            content = logs.to_json(orient="records", lines=True, force_ascii=False)
        elif isinstance(logs, dict):
            content = json.dumps(logs)
        else:
            content = logs

        messages.append({"role": "user", "content": content})

        # 3) Chama a API com timeout e captura exceções
        start_time = time.time()
        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
            )
            analysis = response["message"]["content"].strip()
        except Exception as exc:
            logging.error(f"[{self.model}] erro na API: {exc}")
            analysis = ""
        elapsed = round(time.time() - start_time, 6)

        # 4) Prepara o objeto de log
        data = {
            "model": self.model,
            "mode": self.mode,
            "file": file_name,
            "duration_seconds": elapsed,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "content": content,
            "analysis": analysis,
        }

        # 6) Grava no JSONL com flush + fsync e trata possíveis erros de I/O
        log_path = f"logs/{self.model.replace(':', '_')}.jsonl"
        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as io_exc:
            logging.error(f"[{self.model}] falha ao gravar log: {io_exc}")

        print(analysis)
        return analysis
