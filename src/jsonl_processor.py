import glob
import re

class JsonlChunker:
    """
    Classe responsável por dividir arquivos JSONL em lotes de linhas, garantindo que cada lote
    não ultrapasse um número máximo de tokens.
    """
    def __init__(self, max_tokens):
        self.max_tokens = max_tokens

    def count_tokens(self, text: str) -> int:
        tokens = re.findall(r'\w+|[^\w\s]', text, re.UNICODE)
        return len(tokens)

    def chunk_file(self, file_path: str) -> list[list[str]]:
        """
        Lê o arquivo JSONL linha a linha e retorna uma lista de lotes,
        onde cada lote é uma lista de strings JSON que não ultrapassa max_tokens.
        """
        batches: list[list[str]] = []
        current_batch: list[str] = []
        current_tokens = 0

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                tokens = self.count_tokens(line)

                # Se a linha isolada excede max_tokens, envia sozinha
                if tokens > self.max_tokens:
                    if current_batch:
                        batches.append(current_batch)
                        current_batch = []
                    batches.append([line])
                    current_tokens = 0
                    continue

                # Se não cabe no lote atual, inicia um novo lote
                if current_tokens + tokens > self.max_tokens:
                    batches.append(current_batch)
                    current_batch = [line]
                    current_tokens = tokens
                else:
                    current_batch.append(line)
                    current_tokens += tokens

        # Adiciona o último lote restante
        if current_batch:
            batches.append(current_batch)

        return batches