# Executar os baselines AutoML do C31

Esta extensão acrescenta AutoGluon e PyCaret ao experimento em `../ml_pipeline.ipynb`. O notebook, os modelos e os resultados antigos permanecem intactos. Todos os novos arquivos ficam nesta pasta.

## Instalar o ambiente

Na raiz de `AI-Security-Labs`, entre na pasta dos novos testes:

```sh
cd "test 6.0/ml/c31"
```

Use Python 3.11. As versões diretas estão em `requirements.txt` e o ambiente usado nesta execução está em `requirements.lock.txt`.

```sh
rtk proxy uv venv --python 3.11 .venv
rtk proxy uv pip install --python .venv/bin/python -r requirements.lock.txt
```

No macOS, LightGBM e XGBoost precisam de OpenMP. Se `libomp` não estiver instalado, extraia a biblioteca localmente. O helper baixa o bottle oficial do Homebrew, confere SHA-256 e extrai somente `libomp.dylib`.

```sh
rtk proxy python3 install_libomp.py
```

Nos comandos de treinamento em macOS, informe `DYLD_LIBRARY_PATH` com o caminho absoluto de `.cache/libomp`. Em Linux, use o runtime OpenMP da máquina.

```sh
export DYLD_LIBRARY_PATH="$PWD/.cache/libomp"
```

## Preparar e conferir os mesmos dados

Execute dentro de `test 6.0/ml/c31`:

```sh
rtk proxy .venv/bin/python run.py prepare
rtk proxy .venv/bin/python -m unittest discover -s . -p test_protocol.py -v
```

A preparação reutiliza a célula original de leitura e extração textual. Ela mantém a ordem dos arquivos de ataques, as 500 fatias benignas, `test_size=0.2`, estratificação e `random_state=42`. Nenhum teste Atomic é excluído.

São 1.664 documentos, com 1.331 no treinamento e 333 no teste original. O teste contém 233 documentos de ataques e 100 benignos. A avaliação externa mantém os 41 alertas de ataques e 19 benignos em cada condição: dados brutos, Gemma 3 4B, LLaMA 3.2 3B, Phi-4 Mini e TinyLlama 1.1B.

Os testes executam a construção e a divisão do notebook antigo, sem treinar seus modelos, e comparam todos os textos e rótulos com os dados preparados. `data/manifest.json` registra IDs, divisão e hashes dos arquivos de origem. Os dados preparados também recebem hashes.

## Treinar e avaliar

Use diretórios de saída novos. O script recusa sobrescrever uma execução existente.

```sh
rtk proxy .venv/bin/python run.py train --framework autogluon --output runs/autogluon-600 --time-limit 600 --cpus 1
rtk proxy .venv/bin/python run.py train --framework pycaret --output runs/pycaret-600-v2 --time-limit 600 --cpus 1 --tune-iterations 20
```

AutoGluon usa `best_quality`, F1 para a classe positiva 1, cinco folds de bagging e um nível de stacking. O portfólio inclui LightGBM, CatBoost, XGBoost, Random Forest, Extra Trees, KNN e regressão logística quando presentes no preset. Os modelos usam CPU. Modelos neurais que exigem PyTorch não participam desta configuração. A representação textual é a nativa do AutoGluon.

PyCaret recebe os 1.331 documentos como treinamento e os 333 como `test_data`. Compara regressão logística, árvore de decisão, Random Forest, Extra Trees, SVM linear, LightGBM, XGBoost e CatBoost. Seleciona por F1 em validação cruzada estratificada de cinco folds e ajusta o vencedor com até 20 tentativas. A representação textual é TF-IDF nativa do PyCaret. Os hiperparâmetros do TF-IDF podem diferir daqueles do notebook antigo.

O orçamento de 600 segundos limita a busca do AutoGluon e a comparação inicial do PyCaret. O ajuste do PyCaret usa um número fixo de tentativas e pode ultrapassar o orçamento. A preparação, a inicialização e a avaliação ficam fora desse limite. `config.json` registra o tempo efetivo e as versões instaladas.

Os 333 documentos de teste e os 60 alertas não escolhem o vencedor. O script não chama `finalize_model`, que incorporaria o teste de 20% ao treinamento. Avalia somente o modelo selecionado, emite uma previsão por documento e salva:

- `config.json`, parâmetros, versões e estado da execução.
- `leaderboard.csv`, comparação baseada no treinamento.
- `predictions.csv`, rótulo verdadeiro, previsão, tempo e eventual erro por documento.
- `metrics.csv`, métricas e matriz de confusão por condição.
- O modelo salvo e o manifesto dos dados.

Falhas de previsão são registradas como erros, sem conversão para a classe benigna. A execução com erros não é aceita pelo relatório de comparação. Os tempos por documento medem a chamada de previsão sobre o texto já preparado, incluindo o processamento da ferramenta. Não incluem coleta, filtragem por LLM, leitura do JSONL ou inicialização do modelo.

## Comparar com os resultados antigos

```sh
rtk proxy .venv/bin/python run.py report --runs runs/autogluon-600 runs/pycaret-600-v2 --output results
rtk proxy .venv/bin/python run.py verify
```

O relatório lê os números antigos de `all_models_metrics_by_filter.csv`, sem recalcular ou alterar os quatro baselines. Exclui somente a cópia chamada `best_model_RandomForest` da tabela combinada, porque ela duplica o Random Forest. O arquivo de origem continua intacto. Seus valores têm precisão de três casas decimais.

`comparison_by_condition.csv` mantém cada condição separada. `comparison_mean.csv` calcula a média simples sobre dados brutos e quatro filtros. O teste de 333 documentos fica em `metrics.csv` e não entra nessa média. As cinco versões dos mesmos alertas não são tratadas como 300 alertas independentes.

Os testes e a distribuição de classes do experimento antigo foram mantidos por solicitação do autor. A avaliação continua restrita ao conjunto Windows controlado. AutoML acrescenta busca de modelos e parâmetros a essa comparação.

## Documentação das ferramentas

- [AutoGluon 1.4: treinamento de TabularPredictor](https://auto.gluon.ai/1.4.0/api/autogluon.tabular.TabularPredictor.fit.html).
- [PyCaret: classificação, comparação e ajuste](https://pycaret.readthedocs.io/en/latest/api/classification.html).
