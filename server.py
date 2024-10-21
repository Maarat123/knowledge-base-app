from flask import Flask, jsonify, request
from database import Database

app = Flask(__name__)
db = Database('data.db')

@app.route('/sections', methods=['GET'])
def get_sections():
    sections = db.get_sections()
    return jsonify(sections)

@app.route('/content', methods=['GET'])
def get_content():
    key = request.args.get('key')
    content = db.load_content(key)
    return jsonify({'key': key, 'content': content})

@app.route('/content', methods=['POST'])
def save_content():
    data = request.json
    key = data.get('key')
    content = data.get('content')
    db.save_content(key, content)
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
