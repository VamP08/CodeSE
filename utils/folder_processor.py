import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from utils.TreeParser import CodeChunker
from oswalker import find_files

class FolderProcessor:
    def __init__(self):
        self.all_chunks = []
        self.global_chunk_counter = 0
        self.chunker = CodeChunker()
        
    def generate_unique_chunk_id(self, file_path: str, chunk_type: str) -> str:
        """Generate a unique chunk ID that includes file info and global counter."""
        self.global_chunk_counter += 1
        # Extract filename without extension for more readable IDs
        filename = Path(file_path).stem
        # Create ID with format: filename_chunktype_globalcounter
        return f"{filename}_{chunk_type}_{self.global_chunk_counter}"
    
    def process_single_file(self, file_path: str) -> List[Dict]:
        """Process a single file with unique chunk IDs."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            if not code.strip():
                print(f"⚠️ Error: The file '{file_path}' is empty or contains only whitespace.")
                return []

            # Reset the chunker's internal counter since we're using our global counter
            self.chunker.code_chunks = []
            self.chunker.chunk_counter = 0
            
            language = self.chunker.detect_language(file_path)
            if language == "unknown":
                print(f"⚠️ Error: Unable to detect the language for '{file_path}'. Unsupported file extension.")
                return []
                
            # Process the code based on language
            if language == 'python':
                self.chunker.process_python(file_path, code)
            elif language in ['javascript', 'jsx']:
                self.chunker.process_javascript(file_path, code)
            elif language == 'java':
                self.chunker.process_java(file_path, code)
            elif language in ['c', 'cpp']:
                self.chunker.process_c_cpp(file_path, code, language)
            else:
                print(f"Warning: Language '{language}' is recognized but not fully supported.")
                self.chunker._process_with_regex(file_path, code, language, {
                    'function': r'\b\w+\s+\w+\s*\([^)]*\)\s*{',
                    'class': r'(?:class|struct)\s+\w+\s*{',
                    'comment': r'//.*$|/\*[\s\S]*?\*/'
                })
            
            # Replace chunk IDs with our unique IDs
            chunks_with_unique_ids = []
            for chunk in self.chunker.code_chunks:
                # Extract chunk type from the original ID (e.g., "python_function_1" -> "function")
                chunk_type = chunk['chunk_id'].split('_')[1] if '_' in chunk['chunk_id'] else 'unknown'
                # Generate new unique ID
                unique_id = self.generate_unique_chunk_id(file_path, chunk_type)
                # Create new chunk with unique ID
                new_chunk = chunk.copy()
                new_chunk['chunk_id'] = unique_id
                chunks_with_unique_ids.append(new_chunk)
            
            if not chunks_with_unique_ids:
                print(f"⚠️ Warning: No chunks detected in '{file_path}'.")
            
            return chunks_with_unique_ids

        except FileNotFoundError:
            print(f"❌ Error: The file '{file_path}' was not found.")
            return []
        except PermissionError:
            print(f"❌ Error: Insufficient permissions to read the file '{file_path}'.")
            return []
        except Exception as e:
            print(f"❌ Unexpected error processing '{file_path}': {str(e)}")
            return []
    
    def process_folder(self, folder_path: str, file_extensions: Optional[List[str]] = None) -> List[Dict]:
        """Process all files in a folder and its subfolders."""
        if not os.path.exists(folder_path):
            print(f"❌ Error: The folder '{folder_path}' does not exist.")
            return []
            
        # Find all files in the folder
        file_paths = find_files(folder_path)
        
        # Filter by extensions if specified
        if file_extensions:
            file_paths = [f for f in file_paths if any(f.lower().endswith(ext.lower()) for ext in file_extensions)]
        
        print(f"Found {len(file_paths)} files to process in '{folder_path}'")
        
        # Process each file
        self.all_chunks = []
        self.global_chunk_counter = 0
        
        for file_path in file_paths:
            print(f"Processing: {file_path}")
            file_chunks = self.process_single_file(file_path)
            self.all_chunks.extend(file_chunks)
            print(f"  - Extracted {len(file_chunks)} chunks")
        
        print(f"Total chunks extracted: {len(self.all_chunks)}")
        return self.all_chunks
    
    def save_chunks_to_file(self, output_path: str) -> None:
        """Save all chunks to a file in a structured format."""
        import json
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_chunks, f, indent=2)
        
        print(f"Saved {len(self.all_chunks)} chunks to {output_path}")

if __name__ == "__main__":
    # Example usage
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = input("Enter folder path to process: ")
    
    processor = FolderProcessor()
    chunks = processor.process_folder(folder_path)
    
    # Save chunks to file
    output_path = os.path.join(os.path.dirname(folder_path), "code_chunks.json")
    processor.save_chunks_to_file(output_path)
    
    # Print sample of chunks
    if chunks:
        print("\nSample of extracted chunks:")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\nChunk ID: {chunk['chunk_id']}")
            print(f"File: {chunk['file_path']}")
            print(f"Lines: {chunk['start_line']}-{chunk['end_line']}")
            print(f"Language: {chunk['language']}")
            print("Code (first 100 chars):")
            print(chunk['code'][:100] + "..." if len(chunk['code']) > 100 else chunk['code'])
            print("-" * 50)
        
        if len(chunks) > 3:
            print(f"... and {len(chunks) - 3} more chunks")
