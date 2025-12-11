# --- utils.py ---

import csv
from io import StringIO, BytesIO
from flask import send_file

def export_to_csv(data_list, filename):
    """Exports a list of model objects to a CSV file."""
    if not data_list:
        keys = ["id", "name", "price", "stock"] 
    else:
        keys = list(data_list[0].__dict__.keys())
        keys = [k for k in keys if not k.startswith('_')] 

    # 1. Create an in-memory text buffer (StringIO)
    proxy = StringIO()
    writer = csv.writer(proxy)
    
    writer.writerow(keys) 
    
    for item in data_list:
        writer.writerow([getattr(item, key, '') for key in keys])
        
    proxy.seek(0)
    
    # 2. Convert the content of the StringIO buffer (text) to bytes
    buffer = BytesIO(proxy.getvalue().encode('utf-8'))
    
    # 3. Send the file
    return send_file(
        buffer,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{filename}.csv'
    )

def import_csv_to_list(file_stream):
    """Reads a file stream (from an upload) and returns a list of dictionaries."""
    
    # Decode the file stream content to text, then wrap it in StringIO
    stream = StringIO(file_stream.stream.read().decode("UTF8"))
    
    # Use csv.DictReader to read data with headers as keys
    reader = csv.DictReader(stream)
    
    data_list = []
    for row in reader:
        data_list.append(dict(row))
        
    return data_list