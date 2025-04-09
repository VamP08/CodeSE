import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from utils.folder_processor import FolderProcessor 
from utils.Store_Embedding import store_embeddings_from_json
from utils.SearchEngine import CodeSearchEngine
from utils.Vector_Embedding import CodeEmbeddingModel  # import here

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY_FILE = os.path.join(BASE_DIR, "project_registry.json")
ACTIVE_FILE   = os.path.join(BASE_DIR, "active_project.json")

@app.route('/process_path', methods=['POST'])
def process_path():
    try:
        data = request.get_json()
        if not data or "path" not in data:
            return jsonify({"message": "Invalid request, 'path' is required"}), 400

        folder_path = data["path"]
        if not os.path.exists(folder_path):
            return jsonify({"message": "Invalid path. Folder does not exist."}), 400
        
        processor = FolderProcessor()
        processor.process_folder(folder_path)

        storage_dir   = os.path.join(folder_path, ".code_search")
        os.makedirs(storage_dir, exist_ok=True)
        json_file_path = os.path.join(storage_dir, "code_chunks.json")
        chroma_path    = os.path.join(storage_dir, "chroma_db")

        processor.save_chunks_to_file(json_file_path)
        store_embeddings_from_json(json_file_path, chroma_path=chroma_path)

        # update registry
        project_name = os.path.basename(folder_path)
        entry = {"name": project_name, "path": folder_path}
        projects = []
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, 'r') as f:
                projects = json.load(f)
        if not any(p['path'] == folder_path for p in projects):
            projects.append(entry)
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(projects, f, indent=2)

        return jsonify({"message": f"Processing path: {folder_path}"}), 200

    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@app.route('/get_projects', methods=['GET'])
def get_projects():
    try:
        projects = []
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, "r") as f:
                projects = json.load(f)
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

        with open(ACTIVE_FILE, "w") as f:
            json.dump({"path": selected_path}, f)

        return jsonify({"message": "Project selected successfully."}), 200
    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"}), 500

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"message": "Query is required"}), 400

        if not os.path.exists(ACTIVE_FILE):
            return jsonify({"message": "No active project selected"}), 400
        with open(ACTIVE_FILE, "r") as f:
            active = json.load(f)
        path = active.get("path")
        if not path or not os.path.exists(path):
            return jsonify({"message": "Invalid active project path"}), 400

        code_search_dir = os.path.join(path, ".code_search")
        chunks_path     = os.path.join(code_search_dir, "code_chunks.json")
        chroma_path     = os.path.join(code_search_dir, "chroma_db")

        if not os.path.exists(chunks_path):
            return jsonify({"message": "Code chunks not found. Please process the path first."}), 404
        if not os.path.exists(chroma_path):
            return jsonify({"message": "ChromaDB not found. Please process the path first."}), 404

        # 🔥 Here we pass in the same embedding model with LLM support
        embedding_model = CodeEmbeddingModel()
        search_engine = CodeSearchEngine(
            chroma_path=chroma_path,
            collection_name="code_embeddings",
            embedding_model=embedding_model,
            chunks_filepath=chunks_path
        )

        results = search_engine.combined_search(query, k=10)
        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"message": f"Search error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
