import chromadb
import uuid
from Vector_Embedding_Test import CodeEmbeddingModel  # Import the model wrapper

# Initialize ChromaDB Client
chroma_client = chromadb.PersistentClient(path="./chromadb_store")  # Persistent storage

# Create a Collection
collection = chroma_client.get_or_create_collection(name="code_embeddings")

def store_embeddings_in_chromadb(chunks):
    """Preprocess, generate embeddings, and store in ChromaDB with metadata, avoiding duplicates."""
    
    # Initialize embedding model
    embedding_model = CodeEmbeddingModel()

    # Step 1: Extract Metadata First
    metadata_list = []  # Store metadata for each chunk
    cleaned_chunks = []  # Store preprocessed code chunks

    for chunk in chunks:
        metadata = {
            "chunk_id": "N/A",
            "file_path": "N/A",
            "line_numbers": "N/A",
            "language": "N/A"
        }

        lines = chunk.splitlines()
        code_lines = []
        
        for line in lines:
            line = line.strip()  # Remove spaces/tabs at the beginning
            
            # Properly extract metadata using split(":", 1) to avoid errors
            if line.startswith("Chunk ID:"):
                metadata["chunk_id"] = line.split(":", 1)[1].strip()
            elif line.startswith("File:"):
                metadata["file_path"] = line.split(":", 1)[1].strip()
            elif line.startswith("Lines:"):
                metadata["line_numbers"] = line.split(":", 1)[1].strip()
            elif line.startswith("Language:"):
                metadata["language"] = line.split(":", 1)[1].strip()
            else:
                code_lines.append(line)

        # Extract cleaned code
        cleaned_chunk = "\n".join(code_lines).strip()
        if cleaned_chunk:
            cleaned_chunks.append(cleaned_chunk)
            metadata_list.append(metadata)

    if not cleaned_chunks:
        print("Error: No valid code chunks processed. Check input format.")
        return

    # Step 2: Generate vector embeddings
    vector_embeddings = embedding_model.generate_embeddings(cleaned_chunks)
    print(vector_embeddings)

    # Step 3: Fetch existing metadata and avoid duplicates
    existing_metadata = collection.get(include=['metadatas'])['metadatas']
    print(existing_metadata)

    if existing_metadata is None:
        existing_metadata = []  # Ensure it's an empty list if nothing is stored

    existing_chunk_ids = set()
    for meta in existing_metadata:
        if isinstance(meta, dict) and "chunk_id" in meta:
            existing_chunk_ids.add(meta["chunk_id"])

    print(f"Existing chunk IDs in DB before insertion: {existing_chunk_ids}")  # Debugging

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

    # Only print newly added chunks
    if new_chunks_added > 0:
        print("\nNewly Added Chunks:")
        for idx in range(initial_chunk_count, updated_chunk_count):
            metadata = updated_metadata[idx]
            print(f"\n[Chunk {idx + 1}]")
            print(f"Chunk ID: {metadata.get('chunk_id', 'N/A')}")
            print(f"File Path: {metadata.get('file_path', 'N/A')}")
            print(f"Line Numbers: {metadata.get('line_numbers', 'N/A')}")
            print(f"Language: {metadata.get('language', 'N/A')}")

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
    print("Done.")

