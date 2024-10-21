import mimetypes
import os

def get_mime_type(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type

def read_file(file_path):
    with open(file_path, 'rb') as f:
        return f.read()

def write_file(file_path, content):
    with open(file_path, 'wb') as f:
        f.write(content)
