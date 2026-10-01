# Resultados do C31

As duas execuções terminaram sem erros de previsão. Cada ferramenta avaliou os 333 documentos do teste original e os mesmos 60 alertas em cinco condições. O teste de 333 documentos não entra nas médias da comparação externa.

| Ferramenta | Accuracy média | Precisão média | Recall médio | F1 médio |
| --- | ---: | ---: | ---: | ---: |
| AutoGluon | 0,700 | 0,704 | 0,971 | 0,815 |
| PyCaret | 0,673 | 0,684 | 0,971 | 0,802 |

AutoGluon selecionou `WeightedEnsemble_L2`, com peso 1,0 para `LightGBMXT_BAG_L1`, um LightGBM treinado com bagging de cinco folds. PyCaret selecionou `svm`, implementado como `SGDClassifier(loss='hinge')`. O ajuste de 20 tentativas não superou a configuração inicial em validação; `choose_better=True` preservou o modelo inicial.

`comparison_by_condition.csv` inclui os quatro baselines históricos e as duas ferramentas AutoML. `comparison_mean.csv` calcula a média simples entre dados brutos e as quatro versões filtradas dos mesmos alertas. Os valores históricos foram lidos do relatório salvo com três casas decimais. Os novos valores vêm das previsões por alerta.

Cada execução tem cópias de configuração, leaderboard, métricas e previsões nesta pasta. `data-manifest.json` registra os documentos, a divisão e hashes. `protocol.json` registra os parâmetros comuns e detalhes do ambiente. Os modelos completos e os logs estão em `../runs/` e não fazem parte do controle de versão.

A representação textual difere entre as ferramentas. AutoGluon usa seu processamento nativo e reduziu o vocabulário de n-gramas de 1.110 para 767 durante a preparação devido à memória disponível. PyCaret usa TF-IDF nativo. Nenhum documento foi excluído ou trocado por causa dessa adaptação. Os tempos locais de previsão não foram usados para comparar com os tempos históricos dos LLMs.

As verificações compararam todos os textos e rótulos das duas partições com os construídos pelo notebook original. Os hashes dos 1.492 artefatos de origem acompanhados permaneceram iguais. Os testes, os modelos salvos e os resultados dos quatro baselines antigos foram preservados.

O manuscrito recebeu o protocolo em `Baseline Machine Learning Models`, duas linhas adicionais na tabela e a análise em `Comparative Discussion`. Retirada a afirmação de que os testes Atomic da avaliação foram excluídos do treinamento, porque os registros disponíveis não a sustentam. Os dados e os resultados antigos permaneceram intactos. As alterações textuais estão em azul.
