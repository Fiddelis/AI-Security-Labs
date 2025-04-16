# AI-Security-Labs

## 🗂️ Repository Structure  
- **`attack_script/`**: PowerShell script and CSV scenarios to generate logs with [invoke-atomicredteam](https://github.com/redcanaryco/invoke-atomicredteam) for detection with sysmon
- **`src/`**: Core source code  
  - `main.py`: CLI entry point and orchestration
  - `ollama_client.py`: Wrapper around Ollama API with timing and JSONL logging
  - `logger.py`: Configures file‐and‐console logging

## 🛠️ Technologies  
- **Python 3.9+**  
- **[Ollama](https://github.com/ollama/ollama)** for LLM hosting
- **pandas** for JSONL parsing and DataFrame handling

## ⚙️ Installation
1. Clone the repo:
   ```bash
   git clone https://github.com/Fiddelis/AI-Security-Labs.git
   cd AI-Security-Labs
   ```  
2. Create a virtual environment and install deps:  
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate      # Linux/macOS
   .venv\Scripts\activate         # Windows PowerShell
   
   pip install -r requirements.txt
   ``` 

## 🚀 Usage  
Start your Ollama server locally (e.g., `ollama serve`) and then run:  
```bash
cd src
python main.py \
  --mode inference \
  --path events/scenario_1 \
  --model mistral-small3.1:24b
```  
- **`--mode`**: `filtering` or `inference`
- **`--path`**: Path with JSONL log files
- **`--model`**: Ollama model(s), e.g., `llama3.2:3b`

Results are saved under `filtering/<model>/…` or `inference/<model>/…`, preserving original filenames.

## 📝 Examples  
- **Filtering mode** (entry‑by‑entry):  
  ```bash
  python src/main.py --mode filtering --path events/scenario1 --model llama3.2:3b
  ```  
- **Inference mode** (batch‑with‑justification):  
  ```bash
  python src/main.py --mode inference --path events/scenario2 --model phi4:14b
  ```  
