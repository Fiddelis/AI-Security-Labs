import ollama
import pandas as pd
import logging
import json
import time

class OllamaClient:
    def __init__(self, model: str, mode: str):
        self.model = model
        self.message = []
        modes = {
            "filtering": [
                {
                "role": "system",
                "content": (
                    "You are a cybersecurity expert. Please review and return ONLY the classification as 'IMPORTANT' or 'NOT IMPORTANT'."
                )
                }
            ],
            "inference": [
            {
                "role": "system",
                "content": (
                "You are a cybersecurity expert with extensive experience in analyzing system logs to detect malicious behavior. "
                "You will be given a batch of events in JSONL format (one JSON object per line). "
                "Analyze the **entire batch as a whole**, considering the combination of all events, and determine whether the batch is relevant for investigation."
                )
            },
            {
                "role": "system",
                "content": (
                "Return **only a single result** in the following strict JSON format (no additional text):\n"
                "{\n"
                "  \"CLASSIFICATION\": \"INTERESTING\" | \"NOT INTERESTING\",\n"
                "  \"JUSTIFICATION\": \"<concise explanation for why the batch is or isn't interesting>\"\n"
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
            raise ValueError(f"Invalid mode: {mode}. ('filtering' or 'inference').")
        
        self.mode = mode
        self.mode_message = modes[mode]
    
    def send_message(self, logs: pd.DataFrame | dict | str, file_name: str):
        self.message.extend(self.mode_message)

        if isinstance(logs, pd.DataFrame):
            content = logs.to_json(orient="records", lines=True, force_ascii=False)
        elif isinstance(logs, dict):
            content = json.dumps(logs)
        elif isinstance(logs, str):
            content = logs
        self.message.append({"role": "user", "content": content})

        start_time = time.time()
        response = ollama.chat(
            model=self.model,
            messages=self.message
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        analysis = response['message']['content'].strip()
        self.__reset_message()
        
        print(f"{analysis}\n-----------------------------------------")
        data = {
            "model": self.model,
            "mode": self.mode,
            "file": file_name,
            "duration_seconds": round(elapsed_time, 6),
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "content": content,
            "analysis":analysis,
        }
        with open(f"logs/{self.model.replace(':', '_')}.jsonl", "a") as f:
            f.write(json.dumps(data) + "\n")
        return analysis

    def __reset_message(self):
        self.message = []