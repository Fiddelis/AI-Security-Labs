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
                    "You are a cybersecurity expert specializing in Sysmon log analysis. "
                    "For each individual event (provided as JSON), return only the classification "
                    "'IMPORTANT' or 'NOT IMPORTANT'. "
                    "Do not include any additional text or formatting. "
                )
                }
            ],
            "inference": [
                {
                    "role": "system",
                    "content": (
                        "You are a cybersecurity expert with extensive experience in analyzing system logs "
                        "to detect malicious behavior. Review the entire batch of events (JSONL file) "
                        "and determine which are relevant."
                    )
                },
                {
                    "role": "system",
                    "content": (
                        "Return strictly in the following JSON format, with no extra text:\n"
                        "{\n"
                        "  \"CLASSIFICATION\": \"INTERESTING\" | \"NOT INTERESTING\",\n"
                        "  \"JUSTIFICATION\": \"<concise explanation of your reasoning>\"\n"
                        "}"
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

        data = {
            "model": self.model,
            "mode": self.mode,
            "file": file_name,
            "duration_seconds": round(elapsed_time, 6),
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(f"logs/{self.model.replace(':', '_')}.jsonl", "a") as f:
            f.write(json.dumps(data) + "\n")
        return analysis

    def __reset_message(self):
        self.message = []