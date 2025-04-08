from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import chromadb
from utils.folder_processor import FolderProcessor 
from utils.Store_Embedding import store_embeddings_from_json

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
        print(folder_path)
        if not os.path.exists(folder_path):
            return jsonify({"message": "Invalid path. Folder does not exist."}), 400
        
        processor = FolderProcessor()
        chunks = processor.process_folder(folder_path)
    
        # Save chunks to file
        # Create `.code_search` folder in the root of the codebase
        storage_dir = os.path.join(folder_path, ".code_search")
        os.makedirs(storage_dir, exist_ok=True)

        # Define chunk output path inside it
        json_file_path = os.path.join(storage_dir, "code_chunks.json")

        # Save chunks to that path
        processor.save_chunks_to_file(json_file_path)
        try:
            print("Calling store_embeddings_from_json...")
            if not os.path.exists(json_file_path):
                print(f"Error: File '{json_file_path}' does not exist.")
        
            if not json_file_path.lower().endswith('.json'):
                print(f"Warning: File '{json_file_path}' does not have a .json extension.")
                
            # Process the JSON file
            store_embeddings_from_json(json_file_path)
            print("store_embedding completed successfully.")
        except Exception as e:
            print("Error executing store_embedding:", e)

        return jsonify({"message": f"Processing path: {folder_path}"}), 200
    
    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"}), 500
    
if __name__ == '__main__':
    app.run(debug=True)
