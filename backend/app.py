import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import chromadb
from utils.folder_processor import FolderProcessor 
from utils.Store_Embedding import store_embeddings_from_json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)  # Allow frontend communication

# Base directory for storing registry files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(BASE_DIR, "project_registry.json")
ACTIVE_FILE = os.path.join(BASE_DIR, "active_project.json")

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="code_chunks")

@app.route('/process_path', methods=['POST'])
def process_path():
    try:
        data = request.get_json()
        if not data or "path" not in data:
            return jsonify({"message": "Invalid request, 'path' is required"}), 400

        folder_path = data["path"]
        print(folder_path)
        if not os.path.exists(folder_path):
            return jsonify({"message": "Invalid path. Folder does not exist."}), 400
        
        processor = FolderProcessor()
        chunks = processor.process_folder(folder_path)

        # Save chunks to .code_search folder
        storage_dir = os.path.join(folder_path, ".code_search")
        os.makedirs(storage_dir, exist_ok=True)
        json_file_path = os.path.join(storage_dir, "code_chunks.json")
        processor.save_chunks_to_file(json_file_path)

        try:
            print("Calling store_embeddings_from_json...")
            if not os.path.exists(json_file_path):
                print(f"Error: File '{json_file_path}' does not exist.")

            if not json_file_path.lower().endswith('.json'):
                print(f"Warning: File '{json_file_path}' does not have a .json extension.")
                
            store_embeddings_from_json(json_file_path)
            print("store_embedding completed successfully.")

            # Save to registry
            project_name = os.path.basename(folder_path)
            entry = {"name": project_name, "path": folder_path}

            # Load existing registry
            if os.path.exists(REGISTRY_FILE):
                with open(REGISTRY_FILE, 'r') as f:
                    projects = json.load(f)
            else:
                projects = []

            # Avoid duplicates
            if not any(p['path'] == folder_path for p in projects):
                projects.append(entry)
                with open(REGISTRY_FILE, 'w') as f:
                    json.dump(projects, f, indent=2)

        except Exception as e:
            print("Error executing store_embedding:", e)

        return jsonify({"message": f"Processing path: {folder_path}"}), 200

    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"}), 500


@app.route('/get_projects', methods=['GET'])
def get_projects():
    try:
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, "r") as f:
                projects = json.load(f)
        else:
            projects = []
        return jsonify({"projects": projects})
    except Exception as e:
        return jsonify({"message": f"Error loading project list: {str(e)}"}), 500


@app.route('/set_active_project', methods=['POST'])
def set_active_project():
    try:
        data = request.get_json()
        selected_path = data.get("path")
        if not selected_path or not os.path.exists(selected_path):
            return jsonify({"message": "Invalid project path"}), 400

        # Save selected project path to file
        with open(ACTIVE_FILE, "w") as f:
            json.dump({"path": selected_path}, f)

        return jsonify({"message": "Project selected successfully."}), 200
    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True)
