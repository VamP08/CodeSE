import chromadb
import uuid
import json
import os
from Vector_Embedding import CodeEmbeddingModel  # Import the model wrapper

def store_embeddings_from_json(json_file_path):
    """Read chunks from JSON file created by folder_processor.py and store in ChromaDB."""
    
    # Determine base repo path
    base_repo_path = os.path.dirname(os.path.dirname(json_file_path))  # Go up from .code_search
    storage_dir = os.path.join(base_repo_path, ".code_search")
    os.makedirs(storage_dir, exist_ok=True)

    # NEW: Initialize ChromaDB inside .code_search/chromadb_store 
    chroma_store_path = os.path.join(storage_dir, "chromadb_store")
    chroma_client = chromadb.PersistentClient(path=chroma_store_path)

    # Create collection here (after initializing client) 
    collection = chroma_client.get_or_create_collection(name="code_embeddings")

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
    
    

