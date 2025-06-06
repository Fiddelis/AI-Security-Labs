from elasticsearch import Elasticsearch
import pandas as pd
from datetime import timedelta

es = Elasticsearch(
    "http://192.168.56.102:9200",
    http_auth=("elastic", "123456")
)

data = pd.read_csv('tests.csv')

# Conversão de Series para timestamp e adição do tempo final
data['Execution Time (UTC)'] = pd.to_datetime(data['Execution Time (UTC)'], format="%Y-%m-%dT%H:%M:%SZ")
data['Execution Time End (UTC)'] = data['Execution Time (UTC)'] + pd.Timedelta(seconds=40)

print(data)

for index, row in data.iterrows():
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
                                "gte": row['Execution Time (UTC)'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                                "lte": row['Execution Time End (UTC)'].strftime('%Y-%m-%dT%H:%M:%SZ')
                            }
                        }
                    }
                ]
            }
        }
    }

    response = es.search(index="winlogbeat-8.15.1", body=query)
    events = [hit["_source"] for hit in response["hits"]["hits"]]
    
    # Salvando dados de eventos em data/events/{timestamp}.csv
    pd_events = pd.DataFrame(events)
    pd_events.to_json(f'attacks/{row['Execution Time (UTC)'].strftime("%Y%m%d_%H%M%S")}.jsonl', orient="records", lines=True, force_ascii=False)