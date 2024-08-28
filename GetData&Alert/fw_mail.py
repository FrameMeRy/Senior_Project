from datetime import datetime,timedelta
from elasticsearch import Elasticsearch
from pymongo import MongoClient
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
# Database configuration
MONGO_DB_NAME = 'Elastic'
MONGO_COLLECTION_NAME = 'netmon'

def send_email(receiver_email, subject, message):
    sender_email = 'ratchanon.cu@mail.wu.ac.th'  # Enter your email address
    password = '0629757858'  # Enter your email password

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender_email, password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)

def getdata():
    es = Elasticsearch(['http://10.251.151.76:9200'])
    
    # Dynamically construct the index name based on the current date
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=5)
    index_date = end_time.strftime("%Y.%m.%d")
    index_name = f"logstash-test-{index_date}"

    scroll_size = 10000
    search_body = {
        "query": {
            "bool": {
                "must": [
                    {"range": {"@timestamp": {"gte": start_time, "lte": end_time}}},  # Filter by timestamp
                ]
            } # Match all documents
        },
        "size": scroll_size,
    }

    response = es.search(index=index_name, body=search_body, scroll='100m')
    scroll_id = response['_scroll_id']

    # Connect to MongoDB to fetch the recipient email address
    mongo_client = MongoClient('mongodb://localhost:27017/')
    db = mongo_client['Elastic']
    collection = db['gmail']  # MongoDB collection where emails are stored

    # Fetch the recipient email address from MongoDB
    document = collection.find_one({})
    if document and 'mail' in document:
        receiver_email = document['mail']
        print("Recipient email fetched from MongoDB:", receiver_email)
    else:
        print("Recipient email not found in MongoDB")
        return

    # Flag to check if 'Attack' field is found
    attack_detected = False

    while True:
        hits = response['hits']['hits']
        if not hits:
            break
        for hit in hits:
            source = hit['_source']
            # Check if the document has an 'Attack' field
            if 'attack' in source:
                # Set the flag to True if 'Attack' field is found
                attack_detected = True
                # Extract relevant fields
                srcip = source.get('srcip', 'Unknown')
                srcport = source.get('srcport', 'Unknown')
                dstip = source.get('dstip', 'Unknown')
                dstport = source.get('dstport', 'Unknown')
                attack = source.get('attack', 'Unknown')
                time = source.get('time', 'Unknown')
                date = source.get('date', 'date')

                
                # Construct email message
                message += f"รูปแบบการโจมตี: {attack}\n"
                message += f"Source IP: {srcip}\n"
                message += f"Source Port: {srcport}\n"
                message += f"Destination IP: {dstip}\n"
                message += f"Destination Port: {dstport}\n"
                message += f"Date: {date}\n"
                message += f"Time: {time}\n"
                break  # No need to check further if attack is detected
        if attack_detected:
            break
        response = es.scroll(scroll_id=scroll_id, scroll='100m')

    # If 'Attack' field is found, send email notification
    if attack_detected:
        subject = "มีการโจมตีเกิดขึ้นโดยการตรวจจับของ firewall"
        # Send email notification
        send_email(receiver_email, subject, message)
        print("Email notification sent")
    else:
        print("No attack detected in the dataset")

# Call the function to get data and send email notifications if 'Attack' field is found
while True:
    getdata()
    time.sleep(300)
