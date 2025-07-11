from ollama_client import OllamaClient
from jsonl_processor import JsonlChunker

from concurrent.futures import ThreadPoolExecutor, as_completed
from logger import LoggerSetup
from io import StringIO
import pandas as pd
import logging
import glob
import argparse
import os
import random

class Main:
    def __init__(self, models: list[str], mode: str, path: list[str], max_tokens: int, num_tests: int):
        self.models = models
        self.mode = mode
        self.path = path
        self.max_tokens = max_tokens
        self.num_tests = num_tests

    def __inference(self, client: OllamaClient, file_name: str, chunker: JsonlChunker):
        event_chunks = chunker.chunk_file(file_name)

        # Processamento de um único chunk
        def process_chunk(event):
            content = "\n".join(event)
            alerts = pd.read_json(StringIO(content), orient='records', lines=True)

            if self.mode == "filtering":
                filtered = []
                for _, row in alerts.iterrows():
                    alert = row.to_dict()
                    response = client.send_message(alert, file_name).lower()
                    if "not important" not in response:
                        filtered.append(alert)
                return filtered

            elif self.mode == "inference":
                response = client.send_message(alerts, file_name)
                return {"file": file_name, "analysis": response}

            else:
                logging.error(f"Mode not found: {self.mode}")
                return None
        
        results = []
        for event in event_chunks:
            res = process_chunk(event)
            if res is not None:
                results.append(res)

        # Executa em paralelo com um pool de threads
        flattened_results = []
        max_workers = min(4, len(event_chunks))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # dispara todas as tarefas
            futures = {executor.submit(process_chunk, chunk): chunk for chunk in event_chunks}

            # coleta conforme cada thread termina
            for future in as_completed(futures):
                try:
                    res = future.result()
                except Exception as e:
                    logging.error(f"Erro no processamento de um chunk: {e}")
                    continue

                if res is None:
                    continue
                if isinstance(res, list):
                    flattened_results.extend(res)
                else:
                    flattened_results.append(res)

        return flattened_results

    def run(self):
        files = []
        for path in self.path:
            if not os.path.exists(path):
                logging.error(f"Path not found: {path}")
                continue
            files.extend(glob.glob(f"{path}/*.jsonl"))
        random.shuffle(files)
        print(files)

        for test_num in range(0, self.num_tests):
            for model in self.models:
                client = OllamaClient(model, self.mode)
                chunker = JsonlChunker(self.max_tokens)
                try:
                    client.start()
                    logging.info(f"model started: {model}")
                except:
                    logging.error(f"Model not started: {model}")
                    continue
                
                for file_name in files:
                    output_dir = f"{test_num}/{client.mode}/{client.model.replace(':', '_')}/{os.path.dirname(file_name)}"
                    os.makedirs(output_dir, exist_ok=True)

                    output_file = os.path.join(output_dir, os.path.basename(file_name))
                    result = self.__inference(client, file_name, chunker)
                    
                    pd.DataFrame(result).to_json(output_file, orient="records", lines=True, force_ascii=False)
                    logging.info(f"{self.mode} Saved: {output_file}")
                client.stop()

class ArgumentParserBuilder:
    @staticmethod
    def build():
        parser = argparse.ArgumentParser(description="Run AI log analysis with Ollama.")
        parser.add_argument("--model", type=str, nargs='+', required=False, help="Models to use.")
        parser.add_argument("--mode", type=str, choices=["filtering", "inference"], required=True, help="Analysis mode.")
        parser.add_argument("--path", type=str, nargs='+', required=True, help="Path to log file.")
        parser.add_argument("--tokens", type=int, default=2048, required=False, help="Amount of tokens per inference.")
        parser.add_argument("--tests", type=int, default=1, required=False, help="Number of tests.")
        return parser

def main():
    LoggerSetup().setup()
    models_dict = {
        "models_filtering": ["gemma3:4b", "tinyllama:1.1b", "llama3.2:3b", "phi4-mini"],
        "models_inference": ["deepseek-r1:14b", "phi4", "gemma3:12b", "qwen3:14b", "llama3.1", "mistral-nemo"]
    }

    parser = ArgumentParserBuilder.build()
    args = parser.parse_args()

    models = []
    if not args.model:
        if "filtering" in args.mode:
            models = models_dict["models_filtering"]
        elif "inference" in args.mode:
            models = models_dict["models_inference"]
    else:
        models = args.model

    logging.info(f"Model: {models}")
    logging.info(f"Mode: {args.mode}")
    logging.info(f"Paths: {args.path}")

    app = Main(models=models, mode=args.mode, path=args.path, max_tokens=args.tokens, num_tests=args.tests)
    app.run()

if __name__ == "__main__":
    main()
