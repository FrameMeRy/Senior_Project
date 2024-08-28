from flask import Flask, render_template, send_file, request , make_response , redirect , jsonify , url_for
import pdfkit
import matplotlib.pyplot as plt
from pymongo import MongoClient
import io
import base64
import numpy as np
from io import BytesIO
import tempfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime ,timedelta
from dateutil.relativedelta import relativedelta
import json
import pymongo


app = Flask(__name__, static_url_path='/static')

# MongoDB connection
client = MongoClient('localhost', 27017)
db = client['Elastic']
# collection = db['17/12/2023']
collection = db['netmon']



config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')  



#Normal part (all data)

@app.route('/')
def top_15_bw_usage_gb_app():
    today = datetime.now().strftime("%Y-%m-%d")
    # Retrieve data from MongoDB
    data = collection.find()

    # Calculate bandwidth usage
    bandwidth_usage_gb = {}
    for doc in data:
        if 'app' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            app = doc['app'].strip('"')
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))
            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)
            bandwidth_usage_gb[app] = bandwidth_usage_gb.get(app, 0) + total_gb

    # Sort and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = dict(list(sorted_bandwidth_usage_gb.items())[:15])

    # Prepare data for table (Removing quotation marks from dates)
    table_data_app = [(i+1, app.replace('"', ''), round(usage, 2)) for i, (app, usage) in enumerate(top_15_bandwidth_usage_gb.items())]
    
   # Call the function to get data for destination ports
    table_data_dstport, pie_src_dst = top_15_bw_usage_gb_dstport()

    # any graph and any table
    # plot_src = top_15_bw_usage_gb_app_time() plot_src=plot_src
    table_data_source = top_15_bw_usage_gb_source_ip()
    
    # Return rendered template with all data
    return render_template('test.html', table_data=table_data_app, pie_src=generate_pie_chart(top_15_bandwidth_usage_gb), table_data_source=table_data_source,
                           table_data_dstport=table_data_dstport, pie_src_dst=pie_src_dst,today=today)

def top_15_bw_usage_gb_dstport():
    # Retrieve data from MongoDB
    data = collection.find()

    # Calculate bandwidth usage by destination port
    bandwidth_usage_gb = {}
    for doc in data:
        if 'dstport' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            dstport = doc['dstport']
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))
            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)
            bandwidth_usage_gb[dstport] = bandwidth_usage_gb.get(dstport, 0) + total_gb

    # Sort and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = dict(list(sorted_bandwidth_usage_gb.items())[:15])

    # Prepare data for table
    table_data_dstport = [(i+1, dstport, round(usage, 2)) for i, (dstport, usage) in enumerate(top_15_bandwidth_usage_gb.items())]
    # Return both table data and pie chart source
    return table_data_dstport, generate_pie_chart(top_15_bandwidth_usage_gb)

def generate_pie_chart(data):
    # Generate pie chart
    labels = list(data.keys())
    sizes = list(data.values())
    cmap = plt.get_cmap("tab20c")  # Choose a color map with enough distinct colors
    colors = [cmap(i) for i in range(len(labels))]  # Generate colors from the color map

    explode = [0] * len(labels)  # Initialize explode list with zeros

    if len(explode) > 0:  # Ensure the list is not empty
        explode[0] = 0.1  # Set the first element of explode to 0.1 if the list is not empty

    total = sum(sizes)
    percentages = [(size / total) * 100 for size in sizes]  # Calculate percentages

    labels_with_percentages = [f'{label} ({percentage:.2f}%)' for label, percentage in zip(labels, percentages)]

    plt.figure(figsize=(8, 8))
    patches, _ = plt.pie(sizes, colors=colors, explode=explode, startangle=140)
    plt.axis('equal')
    plt.legend(patches, labels_with_percentages, loc="upper center", bbox_to_anchor=(0.7, 0.7))  # Include percentages in legend

    pie_buffer = io.BytesIO()
    plt.savefig(pie_buffer, format='png')
    pie_buffer.seek(0)
    pie_data = base64.b64encode(pie_buffer.getvalue()).decode('utf-8')
    pie_src_dst = f"data:image/png;base64,{pie_data}"

    return pie_src_dst
   
def top_15_bw_usage_gb_source_ip():
    data = collection.find()

    # Process bandwidth data
    bandwidth_usage_gb = {}
    source_ip_count = {}

    for doc in data:
        if 'app' in doc and 'srcip' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            app = doc['app'].strip('"')  # Remove double quotes
            srcip = doc['srcip']
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))

            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)

            key = f"{app}, {srcip}"
            bandwidth_usage_gb[key] = bandwidth_usage_gb.get(key, 0) + total_gb

            # Count source IPs for each application
            if app in source_ip_count:
                source_ip_count[app].add(srcip)
            else:
                source_ip_count[app] = {srcip}

    # Sort bandwidth usage and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = list(sorted_bandwidth_usage_gb.items())[:15]

    # Add source IP count to each item
    indexed_bandwidth_usage_gb = []
    for i, (key, value) in enumerate(top_15_bandwidth_usage_gb):
        app, srcip = key.split(', ')
        bandwidth = round(value, 2)  
        indexed_bandwidth_usage_gb.append((i+1, app, srcip, bandwidth, len(source_ip_count[app])))

    return indexed_bandwidth_usage_gb
        



#Modify the generate_pdf function to use receiver email from MongoDB
def get_receiver_emails():
    # Connect to MongoDB
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["Elastic"]
    collection = db["gmail"]

    # Query MongoDB collection to get receiver emails
    documents = collection.find({}, {"_id": 0, "mail": 1})  # Assuming each document contains one email

    receiver_emails = [document["mail"] for document in documents]

    return receiver_emails

# Modify the generate_pdf function to use receiver emails from MongoDB and return to test.html
@app.route('/generate_pdf', methods=['GET'])
def generate_pdf():
    today = datetime.now().strftime("%Y-%m-%d")
    # Retrieve data and generate PDF as before
    sorted_bandwidth_usage_gb = top_15_bw_usage_gb_app_data()
    top_15_bandwidth_usage_gb = dict(list(sorted_bandwidth_usage_gb.items())[:15])
    table_data_app = [(i+1, app, round(usage, 2)) for i, (app, usage) in enumerate(top_15_bandwidth_usage_gb.items())]
    pie_src = generate_pie_chart(top_15_bandwidth_usage_gb)
    table_data_source = top_15_bw_usage_gb_source_ip()
    table_data_dstport, pie_src_dst = top_15_bw_usage_gb_dstport()

    # Render HTML template with data
    rendered_html = render_template('pdf_template_all.html', table_data_app=table_data_app, pie_src=pie_src, table_data_source=table_data_source,
                                    table_data_dstport=table_data_dstport, pie_src_dst=pie_src_dst,today=today)

    # Create PDF
    pdf = pdfkit.from_string(rendered_html, False, configuration=config)

    # Save PDF to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        temp_pdf.write(pdf)
        temp_pdf_path = temp_pdf.name

    # Get receiver emails from MongoDB
    receiver_emails = get_receiver_emails()

    if receiver_emails:
        # Send email with PDF to each receiver
        for receiver_email in receiver_emails:
            send_email(temp_pdf_path, receiver_email)

        # Return to test.html
        return redirect('/')
    else:
        return "No receiver emails found in MongoDB"

    
def send_email(pdf_path, receiver_email):
    sender_email = "ratchanon.cu@mail.wu.ac.th"  # Update with your email
    sender_password = "0629757858"  # Update with your password

    # Create message container
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "รายงานของการสรุปผลข้อมูล"

    # Attach PDF
    filename = f"report_{datetime.now().strftime('%Y/%m/%d_%H:%M:%S')}.pdf"
    with open(pdf_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    encoders.encode_base64(part)

    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {filename}",
    )


    msg.attach(part)

    # Connect to SMTP server and send email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())

def top_15_bw_usage_gb_app_data():
    # Retrieve data from MongoDB
    data = collection.find()

    # Calculate bandwidth usage
    bandwidth_usage_gb = {}
    for doc in data:
        if 'app' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            app = doc['app'].strip('"')
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))
            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)
            bandwidth_usage_gb[app] = bandwidth_usage_gb.get(app, 0) + total_gb

    # Sort and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))

    return sorted_bandwidth_usage_gb
    





#data date
@app.route('/date')
def day():
    today = datetime.now().strftime("%Y-%m-%d")
    
    qry = {"date": today}
    # response = make_response(json.dumps(qry), 200)
    # response.mimetype = "application/json"
    # return response
    # Retrieve data from MongoDB
    data = collection.find(qry)

    # Calculate bandwidth usage
    bandwidth_usage_gb = {}
    for doc in data:
        if 'app' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            app = doc['app'].strip('"')
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))
            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)
            bandwidth_usage_gb[app] = bandwidth_usage_gb.get(app, 0) + total_gb

    # Sort and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = dict(list(sorted_bandwidth_usage_gb.items())[:15])

    # Prepare data for table (Removing quotation marks from dates)
    table_data_app = [(i+1, app.replace('"', ''), round(usage, 2)) for i, (app, usage) in enumerate(top_15_bandwidth_usage_gb.items())]
    
   # Call the function to get data for destination ports
    table_data_dstport, pie_src_dst = top_15_bw_usage_gb_dstport()

    # any graph and any table
    # plot_src = top_15_bw_usage_gb_app_time() plot_src=plot_src
    table_data_source = top_15_bw_usage_gb_source_ip()
    
    # Return rendered template with all data
    return render_template('day.html', table_data=table_data_app, pie_src=generate_pie_chart(top_15_bandwidth_usage_gb), table_data_source=table_data_source,
                           table_data_dstport=table_data_dstport, pie_src_dst=pie_src_dst,today=today)

def top_15_bw_usage_gb_dstport():
    # Retrieve data from MongoDB
    today = datetime.now().strftime("%Y-%m-%d")
    
    qry = {"date": today}
    
    data = collection.find(qry)

    # Calculate bandwidth usage by destination port
    bandwidth_usage_gb = {}
    for doc in data:
        if 'dstport' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            dstport = doc['dstport']
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))
            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)
            bandwidth_usage_gb[dstport] = bandwidth_usage_gb.get(dstport, 0) + total_gb

    # Sort and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = dict(list(sorted_bandwidth_usage_gb.items())[:15])

    # Prepare data for table
    table_data_dstport = [(i+1, dstport, round(usage, 2)) for i, (dstport, usage) in enumerate(top_15_bandwidth_usage_gb.items())]
    # Return both table data and pie chart source
    return table_data_dstport, generate_pie_chart(top_15_bandwidth_usage_gb)

def generate_pie_chart(data):
        # Generate pie chart
    labels = list(data.keys())
    sizes = list(data.values())
    cmap = plt.get_cmap("tab20c")  # Choose a color map with enough distinct colors
    colors = [cmap(i) for i in range(len(labels))]  # Generate colors from the color map

    explode = [0] * len(labels)  # Initialize explode list with zeros

    if len(explode) > 0:  # Ensure the list is not empty
        explode[0] = 0.1  # Set the first element of explode to 0.1 if the list is not empty

    total = sum(sizes)
    percentages = [(size / total) * 100 for size in sizes]  # Calculate percentages

    labels_with_percentages = [f'{label} ({percentage:.2f}%)' for label, percentage in zip(labels, percentages)]

    plt.figure(figsize=(8, 8))
    patches, _ = plt.pie(sizes, colors=colors, explode=explode, startangle=140)
    plt.axis('equal')
    plt.legend(patches, labels_with_percentages, loc="upper center", bbox_to_anchor=(0.7, 0.7))  # Include percentages in legend

    pie_buffer = io.BytesIO()
    plt.savefig(pie_buffer, format='png')
    pie_buffer.seek(0)
    pie_data = base64.b64encode(pie_buffer.getvalue()).decode('utf-8')
    pie_src_dst = f"data:image/png;base64,{pie_data}"

    return pie_src_dst
   
def top_15_bw_usage_gb_source_ip():
    today = datetime.now().strftime("%Y-%m-%d")
    
    qry = {"date": today}
    
    data = collection.find(qry)

    # Process bandwidth data
    bandwidth_usage_gb = {}
    source_ip_count = {}

    for doc in data:
        if 'app' in doc and 'srcip' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            app = doc['app'].strip('"')  # Remove double quotes
            srcip = doc['srcip']
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))

            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)

            key = f"{app}, {srcip}"
            bandwidth_usage_gb[key] = bandwidth_usage_gb.get(key, 0) + total_gb

            # Count source IPs for each application
            if app in source_ip_count:
                source_ip_count[app].add(srcip)
            else:
                source_ip_count[app] = {srcip}

    # Sort bandwidth usage and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = list(sorted_bandwidth_usage_gb.items())[:15]

    # Add source IP count to each item
    indexed_bandwidth_usage_gb = []
    for i, (key, value) in enumerate(top_15_bandwidth_usage_gb):
        app, srcip = key.split(', ')
        bandwidth = round(value, 2)  
        indexed_bandwidth_usage_gb.append((i+1, app, srcip, bandwidth, len(source_ip_count[app])))

    return indexed_bandwidth_usage_gb
        






        
# #Select date Part

@app.route('/process_date', methods=['POST'])
def process_date():
    today = datetime.now().strftime("%Y-%m-%d")
    data_type = request.form.get('type', 'date')  # Default to 'date' if not provided
    current_time = datetime.now().strftime("%H:%M:%S")
    select_time = request.form.get('select_time', '00:00:00')  # Default to '00:00:00' if not provided
    start_date = request.form.get('start_date', today)
    end_date = request.form.get('end_date', today)
    
    # Get start_date and end_date from form data or default to today if not provided
    start_date = request.form.get('start_date', today)
    end_date = request.form.get('end_date', today)
    
    if data_type == 'date':
        qry = json.loads('{"date": {"$gte":"' + start_date + '", "$lte":"' + end_date + '"}}')
        
    elif data_type == 'time':
        # Set start_date and end_date to today when selecting time
        start_date = end_date = today
        
        # Create qry based on 'date' field and today's date
        qry = json.loads('{"date": "' + today + '"}')
        
        #response_data = f"Selected time: {select_time}, Current time: {current_time}"
        
        # Convert select_time and current_time to datetime objects
        select_time_obj = datetime.strptime(select_time, "%H:%M:%S")
        current_time_obj = datetime.strptime(current_time, "%H:%M:%S")
        
        # Calculate time difference
        time_difference = abs(current_time_obj - select_time_obj)
        qry["$and"] = [
            {"time": {"$gte": str(time_difference)}},
            {"time": {"$lte": str(current_time)}}
        ]

    # Continue processing with qry...


        
    #     response_data += f", Time difference: {time_difference}"
    
    # response = make_response(qry, 200)
    # response.mimetype = "text/plain"
    # return response
    data_count = collection.count_documents(qry)
    
    if data_count == 0:
        # If no documents are found, redirect to the /nodate route
        return redirect(url_for('no_date'))
#     qry = json.loads('{"@timestamp": {"$gte":"' + start_date + '", "$lte":"' + end_date + '"}}')
    data = collection.find(qry)
    
#     # Retrieve data from MongoDB based on the selected date
    
    
    bandwidth_usage_gb = {}
    for doc in data:
        if 'app' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            app = doc['app'].strip('"')
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))
            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)
            bandwidth_usage_gb[app] = bandwidth_usage_gb.get(app, 0) + total_gb

    # Sort and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb_date = dict(list(sorted_bandwidth_usage_gb.items())[:15])

    # Prepare data for table (Removing quotation marks from dates)
    table_data_app_date = [(i+1, app.replace('"', ''), round(usage, 2)) for i, (app, usage) in enumerate(top_15_bandwidth_usage_gb_date.items())]
    
    # Call the function to get data for destination ports
    table_data_dstport_date, pie_src_dst_date = top_15_bw_usage_gb_dstport_date()

    # any graph and any table
    # plot_src = top_15_bw_usage_gb_app_time() plot_src=plot_src
    table_data_source_date = top_15_bw_usage_gb_source_ip_date()
    
    # Return rendered template with all data
    return render_template('day.html', table_data=table_data_app_date, pie_src=generate_pie_chart_date(top_15_bandwidth_usage_gb_date), table_data_source=table_data_source_date,
                           table_data_dstport=table_data_dstport_date, pie_src_dst=pie_src_dst_date ,start_date=start_date,end_date=end_date,today=today)

def top_15_bw_usage_gb_dstport_date():
    today = datetime.now().strftime("%Y-%m-%d")
    data_type = request.form.get('type', 'date')  # Default to 'date' if not provided
    current_time = datetime.now().strftime("%H:%M:%S")
    select_time = request.form.get('select_time', '00:00:00')  # Default to '00:00:00' if not provided
    start_date = request.form.get('start_date', today)
    end_date = request.form.get('end_date', today)
    
    if data_type == 'date':
        qry = json.loads('{"date": {"$gte":"' + start_date + '", "$lte":"' + end_date + '"}}')
        
    elif data_type == 'time':
        # Set start_date and end_date to today when selecting time
        start_date = end_date = today
        
        # Create qry based on 'date' field and today's date
        qry = json.loads('{"date": "' + today + '"}')
        
        #response_data = f"Selected time: {select_time}, Current time: {current_time}"
        
        # Convert select_time and current_time to datetime objects
        select_time_obj = datetime.strptime(select_time, "%H:%M:%S")
        current_time_obj = datetime.strptime(current_time, "%H:%M:%S")
        
        # Calculate time difference
        time_difference = abs(current_time_obj - select_time_obj)
        qry["$and"] = [
            {"time": {"$gte": str(time_difference)}},
            {"time": {"$lte": str(current_time)}}
        ]
    
    # Calculate bandwidth usage by destination port
    bandwidth_usage_gb = {}
    data = collection.find(qry)
    
    for doc in data:
        if 'dstport' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            dstport = doc['dstport']
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))
            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)
            bandwidth_usage_gb[dstport] = bandwidth_usage_gb.get(dstport, 0) + total_gb

    # Sort and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = dict(list(sorted_bandwidth_usage_gb.items())[:15])

    # Prepare data for table
    table_data_dstport_date = [(i+1, dstport, round(usage, 2)) for i, (dstport, usage) in enumerate(top_15_bandwidth_usage_gb.items())]
    # Return both table data and pie chart source
    return table_data_dstport_date, generate_pie_chart_date(top_15_bandwidth_usage_gb)

def generate_pie_chart_date(data):
    # Generate pie chart
    labels = list(data.keys())
    sizes = list(data.values())
    cmap = plt.get_cmap("tab20c")  # Choose a color map with enough distinct colors
    colors = [cmap(i) for i in range(len(labels))]  # Generate colors from the color map

    explode = [0] * len(labels)  # Initialize explode list with zeros

    if len(explode) > 0:  # Ensure the list is not empty
        explode[0] = 0.1  # Set the first element of explode to 0.1 if the list is not empty

    total = sum(sizes)
    percentages = [(size / total) * 100 for size in sizes]  # Calculate percentages

    labels_with_percentages = [f'{label} ({percentage:.2f}%)' for label, percentage in zip(labels, percentages)]

    plt.figure(figsize=(8, 8))
    patches, _ = plt.pie(sizes, colors=colors, explode=explode, startangle=140)
    plt.axis('equal')
    plt.legend(patches, labels_with_percentages, loc="upper center", bbox_to_anchor=(0.7, 0.7))  # Include percentages in legend

    pie_buffer = io.BytesIO()
    plt.savefig(pie_buffer, format='png')
    pie_buffer.seek(0)
    pie_data = base64.b64encode(pie_buffer.getvalue()).decode('utf-8')
    pie_src_dst = f"data:image/png;base64,{pie_data}"

    return pie_src_dst
   
def top_15_bw_usage_gb_source_ip_date():
    today = datetime.now().strftime("%Y-%m-%d")
    data_type = request.form.get('type', 'date')  # Default to 'date' if not provided
    current_time = datetime.now().strftime("%H:%M:%S")
    select_time = request.form.get('select_time', '00:00:00')  # Default to '00:00:00' if not provided
    start_date = request.form.get('start_date', today)
    end_date = request.form.get('end_date', today)
    
    if data_type == 'date':
        qry = json.loads('{"date": {"$gte":"' + start_date + '", "$lte":"' + end_date + '"}}')
        
    elif data_type == 'time':
        # Set start_date and end_date to today when selecting time
        start_date = end_date = today
        
        # Create qry based on 'date' field and today's date
        qry = json.loads('{"date": "' + today + '"}')
        
        #response_data = f"Selected time: {select_time}, Current time: {current_time}"
        
        # Convert select_time and current_time to datetime objects
        select_time_obj = datetime.strptime(select_time, "%H:%M:%S")
        current_time_obj = datetime.strptime(current_time, "%H:%M:%S")
        
        # Calculate time difference
        time_difference = abs(current_time_obj - select_time_obj)
        qry["$and"] = [
            {"time": {"$gte": str(time_difference)}},
            {"time": {"$lte": str(current_time)}}
        ]
    data = collection.find(qry)

    # Process bandwidth data
    bandwidth_usage_gb = {}
    source_ip_count = {}

    for doc in data:
        if 'app' in doc and 'srcip' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
            app = doc['app'].strip('"')  # Remove double quotes
            srcip = doc['srcip']
            sent_byte = int(doc.get('sentbyte', 0))
            rcvd_byte = int(doc.get('rcvdbyte', 0))

            total_byte = sent_byte + rcvd_byte
            total_gb = total_byte / (1024 ** 3)

            key = f"{app}, {srcip}"
            bandwidth_usage_gb[key] = bandwidth_usage_gb.get(key, 0) + total_gb

            # Count source IPs for each application
            if app in source_ip_count:
                source_ip_count[app].add(srcip)
            else:
                source_ip_count[app] = {srcip}

    # Sort bandwidth usage and select top 15
    sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))
    top_15_bandwidth_usage_gb = list(sorted_bandwidth_usage_gb.items())[:15]

    # Add source IP count to each item
    indexed_bandwidth_usage_gb_date = []
    for i, (key, value) in enumerate(top_15_bandwidth_usage_gb):
        app, srcip = key.split(', ')
        bandwidth = round(value, 2)  
        indexed_bandwidth_usage_gb_date.append((i+1, app, srcip, bandwidth, len(source_ip_count[app])))

    return indexed_bandwidth_usage_gb_date


#Modify the generate_pdf function to use receiver email from MongoDB
def get_receiver_emails():
    # Connect to MongoDB
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client["Elastic"]
    collection = db["gmail"]

    # Query MongoDB collection to get receiver emails
    documents = collection.find({}, {"_id": 0, "mail": 1})  # Assuming each document contains one email

    receiver_emails = [document["mail"] for document in documents]

    return receiver_emails

# Modify the generate_pdf function to use receiver emails from MongoDB and return to test.html
@app.route('/generate_pdf_date', methods=['POST'])
def generate_pdf_date():
    today = datetime.now().strftime("%Y-%m-%d")
    if 'start_date' in request.form:
        start_date = request.form['start_date']
    else:
        start_date = today
    
    if 'end_date' in request.form:
        end_date = request.form['end_date']
    else:
        end_date = today
    # Retrieve data and generate PDF as before
    sorted_bandwidth_usage_gb = top_15_bw_usage_gb_app_data_date()
    top_15_bandwidth_usage_gb = dict(list(sorted_bandwidth_usage_gb.items())[:15])
    table_data_app = [(i+1, app, round(usage, 2)) for i, (app, usage) in enumerate(top_15_bandwidth_usage_gb.items())]
    pie_src = generate_pie_chart_date(top_15_bandwidth_usage_gb)
    table_data_source_date = top_15_bw_usage_gb_source_ip_date()
    table_data_dstport_date, pie_src_dst_date = top_15_bw_usage_gb_dstport_date()

    # Render HTML template with data
    rendered_html = render_template('pdf_template.html', table_data_app=table_data_app, pie_src=pie_src, table_data_source=table_data_source_date,
                                    table_data_dstport=table_data_dstport_date, pie_src_dst=pie_src_dst_date,start_date=start_date,end_date=end_date,today=today)

    # Create PDF
    pdf = pdfkit.from_string(rendered_html, False, configuration=config)

    # Save PDF to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        temp_pdf.write(pdf)
        temp_pdf_path = temp_pdf.name

    # Get receiver emails from MongoDB
    receiver_emails = get_receiver_emails()

    if receiver_emails:
        # Send email with PDF to each receiver
        for receiver_email in receiver_emails:
            send_email(temp_pdf_path, receiver_email)

        # Return to test.html
        return redirect('/date')
    else:
        return "No receiver emails found in MongoDB"

    
def send_email(pdf_path, receiver_email):
    sender_email = "ratchanon.cu@mail.wu.ac.th"  # Update with your email
    sender_password = "0629757858"  # Update with your password

    # Create message container
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "รายงานของการสรุปผลข้อมูล"

    # Attach PDF
    filename = f"report_{datetime.now().strftime('%Y/%m/%d_%H:%M:%S')}.pdf"
    with open(pdf_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    encoders.encode_base64(part)

    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {filename}",
    )


    msg.attach(part)

    # Connect to SMTP server and send email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())

def top_15_bw_usage_gb_app_data_date():
    today = datetime.now().strftime("%Y-%m-%d")
    data_type = request.form.get('type')
    current_time = datetime.now().strftime("%H:%M:%S")  # Current time
    select_time = request.form.get('select_time')

    # Get start_date and end_date from form data or default to today if not provided
    start_date = request.form.get('start_date', today)
    end_date = request.form.get('end_date', today)

    # Provide a default value for data_type if it's not present or not 'date' or 'time'
    data_type = data_type or 'date'

    if data_type == 'date':
        qry = json.loads('{"date": {"$gte":"' + start_date + '", "$lte":"' + end_date + '"}}')

    elif data_type == 'time':
        # Set start_date and end_date to today when selecting time
        start_date = end_date = today

        # Create qry based on 'date' field and today's date
        qry = json.loads('{"date": "' + today + '"}')

        # Convert select_time and current_time to datetime objects
        select_time_obj = datetime.strptime(select_time, "%H:%M:%S")
        current_time_obj = datetime.strptime(current_time, "%H:%M:%S")

        # Calculate time difference
        time_difference = abs(current_time_obj - select_time_obj)
        qry["$and"] = [
            {"time": {"$gte": str(time_difference)}},
            {"time": {"$lte": str(current_time)}}
        ]

    if qry is not None:  # Check if qry has been assigned a value
        data = collection.find(qry)

        # Calculate bandwidth usage
        bandwidth_usage_gb = {}
        for doc in data:
            if 'app' in doc and ('sentbyte' in doc or 'rcvdbyte' in doc):
                app = doc['app'].strip('"')
                sent_byte = int(doc.get('sentbyte', 0))
                rcvd_byte = int(doc.get('rcvdbyte', 0))
                total_byte = sent_byte + rcvd_byte
                total_gb = total_byte / (1024 ** 3)
                bandwidth_usage_gb[app] = bandwidth_usage_gb.get(app, 0) + total_gb

        # Sort and select top 15
        sorted_bandwidth_usage_gb = dict(sorted(bandwidth_usage_gb.items(), key=lambda x: x[1], reverse=True))

        return sorted_bandwidth_usage_gb
    else:
        return {}




@app.route('/nodate')
def no_date():
    return render_template('week.html')


if __name__ == '__main__':
    app.run(debug=True)
    #  ,host="172.16.137.172"