import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os.path
from pymongo import MongoClient
import time

def send_email_with_attachment(email_sender, email_password, mongo_host, mongo_port, mongo_db_name, mongo_collection_name, subject, body, filename):
    # Connect to MongoDB
    client = MongoClient(mongo_host, mongo_port)
    db = client[mongo_db_name]
    collection = db[mongo_collection_name]

    # Query MongoDB to get the email receiver
    email_receiver_document = collection.find_one()
    if email_receiver_document is None:
        print("Receiver email address not found in MongoDB.")
        return
    email_receiver = email_receiver_document.get("mail")
    if email_receiver is None:
        print("Email field not found in the document.")
        return

    # Check if the CSV file exists and has data
    if os.path.isfile(filename) and os.path.getsize(filename) > 0:
        # Open the file
        with open(filename, 'rb') as attachment:
            # Create a MIMEBase object
            part = MIMEBase('application', 'octet-stream')
            part.set_payload((attachment).read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', "attachment; filename= %s" % filename)

            # Create a MIMEMultipart object
            msg = MIMEMultipart()
            msg['From'] = email_sender
            msg['To'] = email_receiver
            msg['Subject'] = subject

            # Add the text content to the email
            msg.attach(MIMEText(body, 'plain'))

            # Attach the file to the MIMEMultipart object
            msg.attach(part)

            # Connect to the SMTP server
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()

            # Log in
            server.login(email_sender, email_password)

            # Send the email
            server.send_message(msg)

            # Disconnect
            server.quit()

            print("Email sent successfully to", email_receiver)

        # Delete the file after sending email
        os.remove(filename)
        print("File", filename, "deleted.")
    else:
        print("The CSV file is empty or doesn't exist.")

# Specify email details
email_sender = 'ratchanon.cu@mail.wu.ac.th'
email_password = '0629757858'
subject = 'High Attack Probability Records'
body = 'Please find attached the high attack probability records.'
# Specify the full path to the CSV file
filename = 'C:/Users/googl/Desktop/project/ML/report.csv'
# MongoDB configuration
mongo_host = 'localhost'
mongo_port = 27017
mongo_db_name = 'Elastic'
mongo_collection_name = 'gmail'

# Send email with attachment and delete file afterwards
while True:
    send_email_with_attachment(email_sender, email_password, mongo_host, mongo_port, mongo_db_name, mongo_collection_name, subject, body, filename)
    time.sleep(300)
