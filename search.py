from flask import Flask, jsonify, request
from database import Database
import logging

# Настройка логирования
logging.basicConfig(
    filename='server.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

app = Flask(__name__)
db = Database('data.db')

@app.route('/api/sections', methods=['GET'])
def get_sections():
    try:
        sections = db.get_sections()
        return jsonify(sections)
    except Exception as e:
        logging.error(f"Ошибка при получении разделов: {e}")
        return jsonify({'error': 'Ошибка при получении разделов'}), 500

@app.route('/api/content', methods=['GET'])
def get_content():
    key = request.args.get('key')
    if not key:
        return jsonify({'error': 'Не указан ключ'}), 400
    try:
        content = db.load_content(key)
        return jsonify({'key': key, 'content': content})
    except Exception as e:
        logging.error(f"Ошибка при загрузке содержимого для ключа '{key}': {e}")
        return jsonify({'error': 'Ошибка при загрузке содержимого'}), 500

@app.route('/api/save_content', methods=['POST'])
def save_content():
    data = request.json
    key = data.get('key')
    content = data.get('content')
    if not key or content is None:
        return jsonify({'error': 'Не указаны ключ или содержимое'}), 400
    try:
        db.save_content(key, content)
        return jsonify({'status': 'success'})
    except Exception as e:
        logging.error(f"Ошибка при сохранении содержимого для ключа '{key}': {e}")
        return jsonify({'error': 'Ошибка при сохранении содержимого'}), 500

@app.route('/api/files', methods=['GET'])
def get_files():
    key = request.args.get('key')
    if not key:
        return jsonify({'error': 'Не указан ключ'}), 400
    try:
        files = db.get_files(key)
        return jsonify({'files': list(files.keys())})
    except Exception as e:
        logging.error(f"Ошибка при получении файлов для ключа '{key}': {e}")
        return jsonify({'error': 'Ошибка при получении файлов'}), 500

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    key = request.form.get('key')
    file = request.files.get('file')
    if not key or not file:
        return jsonify({'error': 'Не указаны ключ или файл'}), 400
    try:
        file_name = file.filename
        file_content = file.read()
        db.add_file(key, file_name, file_content)
        return jsonify({'status': 'success'})
    except Exception as e:
        logging.error(f"Ошибка при загрузке файла '{file.filename}' для ключа '{key}': {e}")
        return jsonify({'error': 'Ошибка при загрузке файла'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
