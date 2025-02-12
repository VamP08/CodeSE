import re
import os
import ast
from typing import List, Dict, Tuple

class CodeChunker:
    def __init__(self):
        self.code_chunks = []
        self.chunk_counter = 0

        # Language-specific regex patterns
        self.patterns = {
            'javascript': {
                'function': r'(?:async\s+)?(?:function\s+([a-zA-Z_]\w*)|(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s+)?function|\(.*?\)\s*=>\s*{)',
                'class': r'class\s+([a-zA-Z_]\w*)\s*(?:extends\s+[a-zA-Z_]\w*)?\s*{',
                'comment': r'//.*$|/\*[\s\S]*?\*/'
            },
            'java': {
                'function': r'(?:public|private|protected)?\s+(?:static\s+)?[\w<>\[\],\s]+\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*(?:throws\s+[\w\s,]+)?\s*{',
                'class': r'(?:public|private|protected)?\s+class\s+([a-zA-Z_]\w*)\s*(?:extends\s+[a-zA-Z_]\w*)?(?:\s+implements\s+[a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)*)?\s*{',
                'comment': r'//.*$|/\*[\s\S]*?\*/'
            },
            'c': {
                'function': r'\b[a-zA-Z_][a-zA-Z0-9_]*\s+\**([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*{',
                'class': None,  # No classes in C
                'comment': r'//.*$|/\*[\s\S]*?\*/'
            },
            'cpp': {
                'function': r'(?:virtual\s+|static\s+)?\b[a-zA-Z_][a-zA-Z0-9_:<>]*\s+\**([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:const)?\s*{',
                'class': r'class\s+([a-zA-Z_]\w*)\s*(?:[:\s]+(?:public|private|protected)?\s+[a-zA-Z_]\w*)?\s*{',
                'comment': r'//.*$|/\*[\s\S]*?\*/'
            }
        }

    def detect_language(self, file_path: str) -> str:
        """Detect programming language based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'cpp'
        }
        return ext_to_lang.get(ext, 'unknown')

    def remove_comments(self, code: str, language: str) -> str:
        """Remove comments while preserving line numbers."""
        if language in self.patterns:
            return re.sub(self.patterns[language]['comment'], '', code)
        return code

    def find_matching_brace(self, code: str, start: int) -> int:
        """Find the matching closing brace while handling nested structures."""
        if code[start] != '{':
            return -1

        stack = []
        in_string = False
        escape = False
        pos = start

        while pos < len(code):
            char = code[pos]

            if char in "\"'":
                if not escape:
                    in_string = not in_string
            elif not in_string:
                if char == '{':
                    stack.append('{')
                elif char == '}':
                    if stack:
                        stack.pop()
                        if not stack:
                            return pos
            escape = (char == '\\')
            pos += 1

        return -1  # Unmatched brace

    def store_chunk(self, file_path: str, chunk_id: str, code: str, start_line: int, end_line: int, byte_offset: Tuple[int, int], language: str) -> None:
        """Store code chunk with metadata."""
        chunk = {
            "file_path": file_path,
            "chunk_id": chunk_id,
            "code": code.strip(),
            "start_line": start_line,
            "end_line": end_line,
            "byte_offset": byte_offset,
            "language": language
        }
        self.code_chunks.append(chunk)

    def process_python(self, file_path: str, code: str) -> None:
        """Process Python files using AST."""
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = getattr(node, 'end_lineno', None) or len(code.split('\n'))

                start_byte = node.col_offset
                end_byte = len(code)

                self.chunk_counter += 1
                chunk_id = f"python_{self.chunk_counter}"

                chunk_code = "\n".join(code.split("\n")[start_line-1:end_line])

                self.store_chunk(file_path, chunk_id, chunk_code, start_line, end_line, (start_byte, end_byte), "python")

    def process_other_languages(self, file_path: str, code: str, language: str) -> None:
        """Process C, C++, Java, and JavaScript using regex-based chunking."""
        class_pattern = self.patterns[language]['class']
        function_pattern = self.patterns[language]['function']

        combined_pattern = function_pattern if not class_pattern else f"({class_pattern})|({function_pattern})"

        for match in re.finditer(combined_pattern, code):
            abs_start = match.start()

            block_start = code.find('{', abs_start)
            if block_start == -1:
                continue

            block_end = self.find_matching_brace(code, block_start)
            if block_end == -1:
                continue

            chunk_code = code[abs_start:block_end + 1]
            start_line = code[:abs_start].count('\n') + 1
            end_line = code[:block_end].count('\n') + 1

            self.chunk_counter += 1
            chunk_id = f"{language}_{self.chunk_counter}"

            self.store_chunk(file_path, chunk_id, chunk_code, start_line, end_line, (abs_start, block_end + 1), language)

    def process_code(self, file_path: str, code: str) -> List[Dict]:
        """Process a code file and extract chunks."""
        language = self.detect_language(file_path)
        if language == 'unknown':
            return []

        clean_code = self.remove_comments(code, language)

        if language == 'python':
            self.process_python(file_path, clean_code)
        else:
            self.process_other_languages(file_path, clean_code, language)

        return self.code_chunks


def process_file(file_path: str) -> List[Dict]:
    """Process a single file and return code chunks with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()

        if not code.strip():
            print(f"⚠️ Error: The file '{file_path}' is empty or contains only whitespace.")
            return []

        chunker = CodeChunker()
        chunks = chunker.process_code(file_path, code)

        if not chunks:
            language = chunker.detect_language(file_path)
            if language == "unknown":
                print(f"⚠️ Error: Unable to detect the language for '{file_path}'. Unsupported file extension.")
            else:
                print(f"⚠️ Warning: No chunks detected in '{file_path}'.")
                print("   Possible reasons:")
                print("   - The file might not contain class/function definitions.")
                print("   - The regex-based chunking might not fully support this file format.")
                print("   - The file uses an uncommon syntax that the parser doesn't recognize.")
            return []

        return chunks

    except FileNotFoundError:
        print(f"❌ Error: The file '{file_path}' was not found.")
        return []
    except PermissionError:
        print(f"❌ Error: Insufficient permissions to read the file '{file_path}'.")
        return []
    except Exception as e:
        print(f"❌ Unexpected error processing '{file_path}': {str(e)}")
        return []

if __name__ == "__main__":
    file_path = 'D:\\New folder\\Work\\CodeSE\\CodeSE\\test\\dodebase\\C++\\A DIFFERENCE OF VALUES AND INDEX.cpp'  # Change this to test different files
    chunks = process_file(file_path)

    if chunks:
        for chunk in chunks:
            print(f"\nChunk ID: {chunk['chunk_id']}")
            print(f"File: {chunk['file_path']}")
            print(f"Lines: {chunk['start_line']}-{chunk['end_line']}")
            print(f"Language: {chunk['language']}")
            print("Code:")
            print(chunk['code'])
            print("-" * 50)
    else:
        print("🚨 No chunks extracted. Check the error messages above.")
