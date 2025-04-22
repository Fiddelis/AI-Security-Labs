from elasticsearch import Elasticsearch
import pandas as pd
from datetime import timedelta

es = Elasticsearch(
    "http://192.168.56.102:9200",
    basic_auth=("elastic", "123456")
)

atomicData = pd.read_csv('data/labels/logs_malicious.csv').drop('IP Address', axis=1)

# Conversão de Series para timestamp e adição do tempo final
atomicData['Execution Time (UTC)'] = pd.to_datetime(atomicData['Execution Time (UTC)'], format="%Y-%m-%dT%H:%M:%SZ")
for i in range(1, len(atomicData)):
    if i == len(atomicData) - 1:
        atomicData.loc[i, 'Execution Time End (UTC)'] = atomicData.loc[i, 'Execution Time (UTC)'] + timedelta(seconds=20)
    atomicData.loc[i - 1, 'Execution Time End (UTC)'] = atomicData.loc[i, 'Execution Time (UTC)'] - timedelta(seconds=1)

atomicData = atomicData.drop(['Execution Time (Local)', 'Username', 'GUID', 'ExitCode'], axis=1)
display(atomicData)

for index, row in atomicData.iterrows():
    query = {
        "size": 500,
        "_source": [
            "process.name",
            "process.command_line",
            "file.path",
            "winlog.task"
        ],
        "query": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": row['Execution Time (UTC)'],
                                "lte": row['Execution Time End (UTC)']
                            }
                        }
                    }
                ]
            }
        }
    }

    response = es.search(index="winlogbeat-*", body=query)
    events = [hit["_source"] for hit in response["hits"]["hits"]]
    
    # Salvando dados de eventos em data/events/{timestamp}.csv
    pd_events = pd.DataFrame(events)
    pd_events.to_json(f'data/events/{row['Execution Time (UTC)'].strftime("%Y%m%d_%H%M%S")}.jsonl', orient="records", lines=True, force_ascii=False)