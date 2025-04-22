import ollama
import pandas as pd
import logging
import json
import time

class OllamaClient:
    """
    A client wrapper for interacting with the Ollama API using predefined system prompts
    for cybersecurity-related log analysis.
    """

    def __init__(self, model: str, mode: str):
        """
        Initialize the Ollama client.

        Args:
            mode  (str): The mode of operation, either "filtering" or "inference".
            model (str): The name of the Ollama model to use (e.g., "llama3").

        Raises:
            ValueError: If the provided mode is not valid.
        """
        self.model = model
        self.message = []
        modes = {"filtering": [{"role": "system", "content": ("You are a cybersecurity expert. Please review each log individually and return ONLY the classification as 'IMPORTANT' or 'NOT IMPORTANT'. Sensitive data is obfuscated.")}],
                 "inference": [{"role": "system", "content": ("You are a cybersecurity expert with extensive experience in analyzing system logs to identify malicious behavior. Your task is to analyze the complete set of presented log events and classify them as 'Interesting' or 'Not Interesting'. DO NOT use excessive PowerShell usage as justification.")},
                               {"role": "system", "content": ("Return ONLY in the format {CLASSIFICATION:{'INTERESTING'|'NOT INTERESTING'}, JUSTIFICATION:{justification}}.")}
                            ]
                    }
        if mode not in modes:
            raise ValueError(f"Invalid mode: {mode}. ('filtering' or 'inference').")
        
        self.mode = mode
        self.mode_message = modes[mode]
    
    def send_message(self, logs: pd.DataFrame | dict | str, file_name: str):
        """
        Sends logs to the Ollama model for analysis based on the selected mode.

        Args:
            logs (str): A string containing log data to be analyzed.

        Returns:
            str: The classification and/or justification returned by the model.
        """
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