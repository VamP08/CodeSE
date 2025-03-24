import chromadb
import uuid
import json
import os
from Vector_Embedding_Test import CodeEmbeddingModel  # Import the model wrapper

# Initialize ChromaDB Client
chroma_client = chromadb.PersistentClient(path="./chromadb_store")  # Persistent storage

# Create a Collection
collection = chroma_client.get_or_create_collection(name="code_embeddings")

def store_embeddings_from_json(json_file_path):
    """Read chunks from JSON file created by folder_processor.py and store in ChromaDB."""
    
    # Initialize embedding model
    embedding_model = CodeEmbeddingModel()
    
    # Load chunks from JSON file
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        print(f"Loaded {len(chunks)} chunks from {json_file_path}")
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in {json_file_path}")
        return
    
    # Prepare data for embedding
    cleaned_chunks = []
    metadata_list = []
    
    for chunk in chunks:
        # Extract metadata from chunk dictionary
        metadata = {
            "chunk_id": chunk.get("chunk_id", "N/A"),
            "file_path": chunk.get("file_path", "N/A"),
            "line_numbers": f"{chunk.get('start_line', 'N/A')}-{chunk.get('end_line', 'N/A')}",
            "language": chunk.get("language", "N/A")
        }
        
        # Get the code content
        code = chunk.get("code", "").strip()
        
        if code:
            cleaned_chunks.append(code)
            metadata_list.append(metadata)
    
    if not cleaned_chunks:
        print("Error: No valid code chunks found in the JSON file.")
        return
    
    # Generate vector embeddings
    vector_embeddings = embedding_model.generate_embeddings(cleaned_chunks)
    
    # Step 3: Fetch existing metadata and avoid duplicates
    existing_metadata = collection.get(include=['metadatas'])['metadatas']
    
    if existing_metadata is None:
        existing_metadata = []  # Ensure it's an empty list if nothing is stored
    
    existing_chunk_ids = set()
    for meta in existing_metadata:
        if isinstance(meta, dict) and "chunk_id" in meta:
            existing_chunk_ids.add(meta["chunk_id"])
    
    print(f"Existing chunk IDs in DB before insertion: {len(existing_chunk_ids)}")  # Debugging
    
    initial_chunk_count = len(existing_chunk_ids)  # Count of existing chunks before insertion
    new_chunks_added = 0  # Track how many new chunks get stored
    
    for metadata, embedding in zip(metadata_list, vector_embeddings):
        chunk_id = metadata["chunk_id"]
        
        # Check if chunk_id already exists
        if chunk_id in existing_chunk_ids:
            print(f"Skipping duplicate chunk: {chunk_id}")
            continue  # Properly skip duplicates
        
        doc_id = str(uuid.uuid4())  # Generate a unique ID for this chunk
        
        # Store in ChromaDB
        collection.add(
            ids=[doc_id],  # Unique ID for this entry
            embeddings=[embedding.tolist()],  # Convert numpy/tensor to list
            metadatas=[metadata]  # Store metadata as JSON
        )
        
        print(f"Stored new chunk: {chunk_id}")
        new_chunks_added += 1
    
    print(f"Stored {new_chunks_added} new unique code chunks in ChromaDB.")
    
    # Fetch updated metadata
    updated_metadata = collection.get(include=['metadatas'])['metadatas']
    updated_chunk_count = len(updated_metadata)
    
    print(f"Total chunks in DB after insertion: {updated_chunk_count}")
    
    # Only print newly added chunks (up to 10 for brevity)
    if new_chunks_added > 0:
        print("\nSample of Newly Added Chunks:")
        display_count = min(10, new_chunks_added)
        for idx in range(initial_chunk_count, initial_chunk_count + display_count):
            metadata = updated_metadata[idx]
            print(f"\n[Chunk {idx + 1}]")
            print(f"Chunk ID: {metadata.get('chunk_id', 'N/A')}")
            print(f"File Path: {metadata.get('file_path', 'N/A')}")
            print(f"Line Numbers: {metadata.get('line_numbers', 'N/A')}")
            print(f"Language: {metadata.get('language', 'N/A')}")
        
        if new_chunks_added > 10:
            print(f"\n... and {new_chunks_added - 10} more chunks")

# Example Usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        json_file_path = sys.argv[1]
    else:
        # Ask for the JSON file path
        json_file_path = input("Enter path to the JSON file created by folder_processor.py: ")
    
    # Validate file exists and has .json extension
    if not os.path.exists(json_file_path):
        print(f"Error: File '{json_file_path}' does not exist.")
        sys.exit(1)
    
    if not json_file_path.lower().endswith('.json'):
        print(f"Warning: File '{json_file_path}' does not have a .json extension.")
        confirm = input("Continue anyway? (y/n): ")
        if confirm.lower() != 'y':
            sys.exit(0)
    
    # Process the JSON file
    store_embeddings_from_json(json_file_path)
    print("Done.")
