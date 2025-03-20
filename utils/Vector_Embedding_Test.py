# Import necessary libraries
from sentence_transformers import SentenceTransformer
import torch

def preprocess_chunks(chunks):
    """Extract and clean code from detailed chunk info."""
    cleaned_chunks = []
    
    for chunk in chunks:

        lines = chunk.splitlines()

        # Find index of "Code:"
        code_index = next((i for i, line in enumerate(lines) if line.strip().startswith("Code:")), None)
        
        if code_index is None:
            print("Error: 'Code:' not found in chunk!")
            continue  # Skip this chunk
        
        # Extract the code block
        code_block = lines[code_index + 1:]  # Lines after "Code:"

        if not code_block:
            print("Error: No code found after 'Code:'")
            continue  # Skip this chunk

        # Preserve indentation, removing empty lines
        cleaned = "\n".join([line for line in code_block if line.strip()])
        cleaned_chunks.append(cleaned)
    
    print(f"Processed {len(cleaned_chunks)} chunks successfully.")
    return cleaned_chunks


# Input code_chunk
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

# Preprocess the chunk
processed_chunks = preprocess_chunks([code_chunk])

# Step 2: Model Loading
# Load all-MiniLM-L6-v2 model
model_name = 'sentence-transformers/all-MiniLM-L6-v2'
model = SentenceTransformer(model_name)

# Check if GPU is available for acceleration
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model.to(device)
print(f'Model loaded on: {device}')

# Step 3: Batch Processing for Vector Embeddings
batch_size = 8  # Adjust based on memory constraints

def generate_embeddings(chunks, batch_size=8):
    """Generate vector embeddings for code chunks in batches."""
    embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        # Move batch to GPU if available
        batch_embeddings = model.encode(batch, batch_size=batch_size, show_progress_bar=True, device=device)
        embeddings.extend(batch_embeddings)
    return embeddings

