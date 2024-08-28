from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from pymongo import MongoClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# Elasticsearch configuration
ES_HOST = 'http://10.251.151.76:9200'
ES_INDEX_PREFIX = 'logstash-test-'
SCROLL_SIZE = 10000

# MongoDB configuration
MONGO_HOST = 'localhost'
MONGO_PORT = 27017
MONGO_DB_NAME = 'Elastic'
MONGO_COLLECTION_NAME = 'blacklist'
MONGO_EMAIL_COLLECTION_NAME = 'gmail'  # Assuming the collection that holds emails is named 'gmail'

# Email configuration (sender's details)
sender_email = "ratchanon.cu@mail.wu.ac.th"
password = "0629757858"  # Replace with your actual password or an app-specific password

# SMTP server configuration for Gmail
smtp_server = "smtp.gmail.com"
port = 587

def get_email_addresses():
    """Fetch all receiver email addresses from MongoDB."""
    mongo_client = MongoClient(MONGO_HOST, MONGO_PORT)
    db = mongo_client[MONGO_DB_NAME]
    collection = db[MONGO_EMAIL_COLLECTION_NAME]
    documents = collection.find({}, {'mail': 1})
    emails = [doc['mail'] for doc in documents]
    mongo_client.close()
    return emails

def send_email(receiver_email, subject, body):
    """Send an email."""
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        server.quit()
        print(f"Email sent successfully to {receiver_email}!")
    except Exception as e:
        print(f"Failed to send email to {receiver_email}: {e}")

def get_blacklist_ips():
    """Connect to MongoDB and fetch blacklist IPs."""
    mongo_client = MongoClient(MONGO_HOST, MONGO_PORT)
    db = mongo_client[MONGO_DB_NAME]
    collection = db[MONGO_COLLECTION_NAME]
    cursor = collection.find({}, {'blacklistip': 1})
    blacklist_ips = [doc['blacklistip'] for doc in cursor]
    mongo_client.close()
    return blacklist_ips

def getdata(receiver_email):
    """Fetch data from Elasticsearch and send an email summarizing the findings."""
    if not receiver_email:
        print("No receiver email provided.")
        return

    es = Elasticsearch([ES_HOST])
    current_time = datetime.now()
    five_minutes_ago = current_time - timedelta(minutes=5)
    current_time_str = current_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    five_minutes_ago_str = five_minutes_ago.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    index_date = datetime.now().strftime("%Y.%m.%d")
    index_name = f"{ES_INDEX_PREFIX}{index_date}"
    
    search_body = {
        "query": {"range": {"@timestamp": {"gte": five_minutes_ago_str, "lte": current_time_str}}},
        "_source": ["time", "date", "srcip", "dstip", "app", "proto", "msg_t"],
        "size": SCROLL_SIZE,
    }

    response = es.search(index=index_name, body=search_body, scroll='100m')
    scroll_id = response['_scroll_id']
    results = []
    blacklist_ips = get_blacklist_ips()

    while True:
        hits = response['hits']['hits']
        if not hits:
            break
        for hit in hits:
            if '_source' in hit and 'srcip' in hit['_source'] and hit['_source']['srcip'] in blacklist_ips:
                results.append(hit['_source'])
        response = es.scroll(scroll_id=scroll_id, scroll='100m')

    if results:
        first_match = results[0]
        message_body = f"""พบ {len(results)} blacklisted IP . รายละเอียด:

Date: {first_match.get("date", "N/A")}
Application: {first_match.get("app", "N/A")}
Source IP: {first_match.get("srcip", "N/A")}
Message Type: {first_match.get("msg_t", "N/A")}
Protocol: {first_match.get("proto", "N/A")}
Destination IP: {first_match.get("dstip", "N/A")}
Time: {first_match.get("time", "N/A")}
"""
        send_email(receiver_email, "Blacklist IP Match Summary", message_body)
    else:
        print("No data found")

# Call the function to get the receiver's email addresses from MongoDB
receiver_emails = get_email_addresses()

# Check if there are receiver_emails before proceeding

    
while True:
    current_time = datetime.now()
    if receiver_emails:
        for receiver_email in receiver_emails:
        # Call the function to get data and potentially send an email summary
            getdata(receiver_email)
    else:
        print("No receiver emails found in MongoDB.")
        
    print("Date",current_time.strftime("%Y-%m-%d"),"Time",current_time.strftime("%H:%M:%S"))
    time.sleep(300)

