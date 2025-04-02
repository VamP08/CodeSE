# Import necessary libraries
from sentence_transformers import SentenceTransformer
import torch

class CodeEmbeddingModel:
    """Encapsulates the Sentence Transformer model for efficient embedding generation."""
    
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2'):
        # Load model
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = SentenceTransformer(model_name)
        self.model.to(self.device)
        print(f'Model loaded on: {self.device}')

    def preprocess_chunks(self, chunks):
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

    def generate_embeddings(self, chunks, batch_size=8):
        """Generate vector embeddings for code chunks in batches."""
        if not chunks:
            print("Error: No valid code chunks to embed.")
            return []

        embeddings = []
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            batch_embeddings = self.model.encode(batch, batch_size=batch_size, show_progress_bar=True, device=self.device)
            embeddings.extend(batch_embeddings)

        return embeddings
