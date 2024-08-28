from datetime import datetime, timedelta
from pymongo import MongoClient
from elasticsearch import Elasticsearch
import time

# Specify the fields you want to retrieve
FIELDS = ["app", "sentbyte", "rcvdbyte", "eventime", "dstport", "dstip", "srcip", "srcport", "level", "type", "@timestamp", "date" ,"time"]

# Database configuration
MONGO_DB_NAME = 'Elastic'
MONGO_COLLECTION_NAME = 'netmon'

def getdata():
    es = Elasticsearch(['http://10.251.151.76:9200'])
    
    # Specify the time range for data selection (last 5 minutes)
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=5)
    print(end_time)
    # Delete yesterday's index for the current time
    yesterday_index_date = (end_time - timedelta(days=1)).strftime("%Y.%m.%d")
    yesterday_index_name = f"logstash-test-{yesterday_index_date}"
    if es.indices.exists(index=yesterday_index_name):
        es.indices.delete(index=yesterday_index_name)
        print(f"Deleted yesterday's index: {yesterday_index_name}")
    else:
        print(f"Yesterday's index not found: {yesterday_index_name}")
        
        

    # Delete indexes starting with "."
    prefix_index_names = es.indices.get(index=".*").keys()
    for prefix_index_name in prefix_index_names:
        es.indices.delete(index=prefix_index_name)
        print(f"Deleted index: {prefix_index_name}")
    
    # Dynamically construct the index name based on the current date
    index_date = end_time.strftime("%Y.%m.%d")
    index_name = f"logstash-test-{index_date}"
    
    scroll_size = 10000
    search_body = {
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": start_time, "lte": end_time}}},  # Filter by timestamp
                ]
            }
        },
        "size": scroll_size,
        "_source": FIELDS  # Specify the fields to retrieve
    }
    

    response = es.search(index=index_name, body=search_body, scroll='100m')
    scroll_id = response['_scroll_id']
    results = {}

    while True:
        hits = response['hits']['hits']
        if not hits:
            break
        for hit in hits:
            source = hit['_source']
            app = source.get('app')
            eventime = source.get('eventime')
            dstport = source.get('dstport')
            dstip = source.get('dstip')
            srcip = source.get('srcip')
            srcport = source.get('srcport')
            level = source.get('level')
            type_ = source.get('type')
            timestamp = source.get('@timestamp')
            date = source.get('date')
            time = source.get('time')
            sentbyte = int(source.get('sentbyte', 0))
            rcvdbyte = int(source.get('rcvdbyte', 0))
            
            # For each unique app
            if app:
                key = ('app', app)
                if key not in results:
                    results[key] = {"sentbyte": 0, "rcvdbyte": 0}
                results[key]["sentbyte"] += sentbyte
                results[key]["rcvdbyte"] += rcvdbyte
            
            # For each unique dstport
            if dstport:
                key = ('dstport', dstport)
                if key not in results:
                    results[key] = {"sentbyte": 0, "rcvdbyte": 0}
                results[key]["sentbyte"] += sentbyte
                results[key]["rcvdbyte"] += rcvdbyte
        
        response = es.scroll(scroll_id=scroll_id, scroll='100m')

    # Save to MongoDB
    if results:
        mongo_client = MongoClient('mongodb://localhost:27017/')
        db = mongo_client[MONGO_DB_NAME]
        collection = db[MONGO_COLLECTION_NAME]

        # Insert data into MongoDB
        for key, value in results.items():
            entry = {
                "type": key[0],   # Indicates whether it's 'app' or 'dstport'
            }
            if key[0] == 'app':
                entry["app"] = key[1]  # App name
                if eventime:
                    entry["eventime"] = eventime  # Eventime
            elif key[0] == 'dstport':
                entry["dstport"] = key[1]  # Dstport
            # Include other fields only if they have data
            if dstip:
                entry["dstip"] = dstip
            if srcip:
                entry["srcip"] = srcip
            if srcport:
                entry["srcport"] = srcport
            if level:
                entry["level"] = level
            if type_:
                entry["type"] = type_
            if timestamp:
                entry["@timestamp"] = timestamp
            if date:
                entry["date"] = date
            if time:
                entry["time"] = time
            # Include sentbyte and rcvdbyte regardless
            entry["sentbyte"] = value["sentbyte"]
            entry["rcvdbyte"] = value["rcvdbyte"]
            collection.insert_one(entry)
        
        print("Data inserted into MongoDB")
    else:
        print("No data found to insert into MongoDB")

# Call the function to get data and store in MongoDB
while True:
    getdata()
    time.sleep(300)
