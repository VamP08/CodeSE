from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import chromadb
from utils.oswalker import find_files
from utils.TreeParser import process_file

app = Flask(__name__)
CORS(app,resources={r"/*": {"origins": "*"}}, supports_credentials=True)  # Allow frontend communication

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="code_chunks")

@app.route('/process_path', methods=['POST'])

@app.route('/process_path', methods=['POST'])
def process_path():
    try:
        data = request.get_json()  # Ensure JSON is parsed correctly
        if not data or "path" not in data:
            return jsonify({"message": "Invalid request, 'path' is required"}), 400

        folder_path = data["path"]
        if not os.path.exists(folder_path):
            return jsonify({"message": "Invalid path. Folder does not exist."}), 400

        file_paths = find_files(folder_path)
        for file_path in file_paths:
            chunk = process_file(file_path)
            print(chunk)
        return jsonify({"message": f"Processing path: {folder_path}"}), 200
    
    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"}), 500
if __name__ == '__main__':
    app.run(debug=True)
