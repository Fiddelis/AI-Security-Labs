from ollama_client import OllamaClient
from logger import LoggerSetup
import pandas as pd
import logging
import glob
import argparse
import os
import re

class Main:
    def __init__(self, models: list[str], mode: str, path: list[str]):
        self.models = models
        self.mode = mode
        self.path = path

    def __inference(self, client: OllamaClient, file: str):
        alerts = pd.read_json(file, orient='records', lines=True)
        results = []
        
        if self.mode == "filtering":
            logging.info(f"Filtering with {client.model}")
            for _, row in alerts.iterrows():
                alert = row.to_dict()
                response = client.send_message(alert, file)
                if "NOT IMPORTANT" not in response:
                    results.append(alert)
        
        elif self.mode == "inference":
            logging.info(f"Inference with {client.model}")
            response = client.send_message(alerts, file)
            results.append({"file": file, "analysis": response})
        
        else:
            logging.error(f"Mode not found: {self.mode}")
        
        return results

    def run(self):
        for model in self.models:
            client = OllamaClient(model, self.mode)
            try:
                client.send_message({}, "") # start model
                logging.info(f"model started: {model}")
            except:
                logging.error(f"Model not started: {model}")
                continue
            
            for path in self.path:
                if not os.path.exists(path):
                    logging.error(f"Path not found: {path}")
                    continue
                
                files = glob.glob(f"{path}/*.jsonl")
                for file in files:
                    result = self.__inference(client, file)
                    output_path = f"{client.mode}/{client.model.replace(':', '_')}/{path}"
                    os.makedirs(output_path, exist_ok=True)

                    file_name = os.path.basename(file)
                    output_file = f"{output_path}/{file_name}"

                    pd.DataFrame(result).to_json(output_file, orient="records", lines=True, force_ascii=False)
                    logging.info(f"{self.mode} Saved: {output_file}")

class ArgumentParserBuilder:
    @staticmethod
    def build():
        parser = argparse.ArgumentParser(description="Run AI log analysis with Ollama.")
        parser.add_argument("--model", type=str, nargs='+', required=False, help="Models to use.")
        parser.add_argument("--mode", type=str, choices=["filtering", "inference"], required=True, help="Analysis mode.")
        parser.add_argument("--path", type=str, nargs='+', required=True, help="Path to log file.")
        return parser

def main():
    LoggerSetup().setup()
    models_dict = {
        "models_filtering": ["llama3.2:3b", "tinyllama:1.1b", "gemma2:2b"],
        "models_inference": ["mistral-small3.1:24b", "deepseek-r1:14b", "phi4:14b"]
    }

    parser = ArgumentParserBuilder.build()
    args = parser.parse_args()

    if not args.model:
        if "filtering" in args.mode:
            models = models_dict["models_filtering"]
        elif "inference" in args.mode:
            models = models_dict["models_inference"]
    else:
        models = args.model

    app = Main(models=models, mode=args.mode, path=args.path)
    app.run()

if __name__ == "__main__":
    main()
