import chromadb

chroma_client = chromadb.PersistentClient(path="./chromadb_store")  # Use the same path
collection = chroma_client.get_or_create_collection(name="code_embeddings")

# Retrieve stored items
stored_items = collection.count()
print(f"Total items stored: {stored_items}")
