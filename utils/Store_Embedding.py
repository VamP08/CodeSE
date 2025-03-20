import chromadb
import uuid
import json
from Vector_Embedding_Test import generate_embeddings, preprocess_chunks  # Import previous functions

# Initialize ChromaDB Client
chroma_client = chromadb.PersistentClient(path="./chromadb_store")  # Persistent storage

# Create a Collection
collection = chroma_client.get_or_create_collection(name="code_embeddings")

def store_embeddings_in_chromadb(chunks):
    """Preprocess, generate embeddings, and store in ChromaDB with metadata."""
    
    # Step 1: Preprocess chunks to extract code
    processed_chunks = preprocess_chunks(chunks)
    # Step 2: Generate vector embeddings
    vector_embeddings = generate_embeddings(processed_chunks)
    if not processed_chunks:
        print("Error: No valid code chunks processed. Check input format.")
        return
    
    # Step 3: Store in ChromaDB with metadata
    for idx, (chunk, embedding) in enumerate(zip(chunks, vector_embeddings)):
        metadata = {}
        lines = chunk.splitlines()
        for line in lines:
            if line.startswith("Chunk ID:"):
                metadata["chunk_id"] = line.split("Chunk ID:")[-1].strip()
            elif line.startswith("File:"):
                metadata["file_path"] = line.split("File:")[-1].strip()
            elif line.startswith("Lines:"):
                metadata["line_numbers"] = line.split("Lines:")[-1].strip()
            elif line.startswith("Language:"):
                metadata["language"] = line.split("Language:")[-1].strip()
        
        # Unique ID for ChromaDB
        doc_id = str(uuid.uuid4())  # Generate a unique ID for this chunk
        print(metadata)
        # Store in ChromaDB
        collection.add(
            ids=[doc_id],  # Unique ID for this entry
            embeddings=[embedding.tolist()],  # Convert numpy/tensor to list
            metadatas=[metadata]  # Store metadata as JSON
        )

    print(f"Stored {len(vector_embeddings)} code chunks successfully in ChromaDB.")

# Example Usage
if __name__ == "__main__":
    code_chunk = """Chunk ID: python_function_7
    File: D:/New folder/Work/CodeSE/CodeSE/test/dodebase/PYTHON/TWO SUM.py
    Lines: 20-32
    Language: python
    Code:
        def twoSum(self, nums, target):

            elements = dict()

            for count, value in enumerate(nums):
                ans = target - value

                if ans in elements:
                    return [elements[ans], count]

                elements[value] = count

            return []"""

    store_embeddings_in_chromadb([code_chunk])
    print("done")
