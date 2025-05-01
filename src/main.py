from ollama_client import OllamaClient
from jsonl_processor import JsonlChunker

from logger import LoggerSetup
from io import StringIO
import pandas as pd
import logging
import glob
import argparse
import os
import re

class Main:
    def __init__(self, models: list[str], mode: str, path: list[str], max_tokens: int):
        self.models = models
        self.mode = mode
        self.path = path
        self.max_tokens = max_tokens

    def __inference(self, client: OllamaClient, file_name: str, chunker: JsonlChunker):
        event_chunks = chunker.chunk_file(file_name)
        results = []
        
        for event in event_chunks:
            content = "\n".join(event)
            alerts = pd.read_json(StringIO(content), orient='records', lines=True)
            if self.mode == "filtering":
                for _, row in alerts.iterrows():
                    alert = row.to_dict()
                    response = client.send_message(alert, file_name).lower()
                    if "not important" not in response:
                        results.append(alert)

            elif self.mode == "inference":
                response = client.send_message(alerts, file_name)
                results.append({"file": file_name, "analysis": response})
            else:
                logging.error(f"Mode not found: {self.mode}")

        return results

    def run(self):
        for model in self.models:
            client = OllamaClient(model, self.mode)
            chunker = JsonlChunker(self.max_tokens)
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
                file_names = [os.path.basename(f) for f in files]
                for file_name, file in zip(file_names, files):
                    output_path = f"{client.mode}/{client.model.replace(':', '_')}/{path}"
                    os.makedirs(output_path, exist_ok=True)

                    result = self.__inference(client, file, chunker)
                    
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
        parser.add_argument("--tokens", type=int, default=2048, required=False, help="Amount of tokens per inference.")
        return parser

def main():
    LoggerSetup().setup()
    models_dict = {
        "models_filtering": ["llama3.2:3b", "tinyllama:1.1b", "gemma2:2b", "phi"],
        "models_inference": ["gemma2", "deepseek-r1:14b", "phi4:14b", "mistral-nemo", "llama3.1"]
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

    path_output = []
    for path in args.path:
        for i in range(1, 7):
            path_output.append(f'{path}/scenario{i}')

    logging.info(f"Model: {models}")
    logging.info(f"Mode: {args.mode}")
    logging.info(f"Paths: {path_output}")

    app = Main(models=models, mode=args.mode, path=path_output, max_tokens=args.tokens)
    app.run()

if __name__ == "__main__":
    main()
