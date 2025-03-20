import os
from tree_sitter import Language, Parser
import pickle
import ast
from pathlib import Path
import re
from typing import List, Dict, Tuple

class CodeChunker:
    def __init__(self, force_rebuild=False):
        self.code_chunks = []
        self.chunk_counter = 0
        self.language_so_path = 'build/languages.so'
        # Initialize parsers
        self._initialize_parsers(force_rebuild)
        
        # Define Tree-sitter queries for each language
        self.queries = {
            'python': None,  # Using AST for Python
            'javascript': self._create_query('javascript', """
                (function_declaration) @function.def
                (class_declaration) @class.def
            """),
            'java': self._create_query('java', """
                (class_declaration) @class.def
                (method_declaration) @function.def
            """),
            'c': self._create_query('c', """
                (function_definition) @function.def
                (struct_specifier) @class.def
                (union_specifier) @class.def
            """),
            'cpp': self._create_query('cpp', """
                (function_definition) @function.def
                (class_specifier) @class.def
                (struct_specifier) @class.def
                (namespace_definition) @namespace.def
            """),
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

    def _initialize_parsers(self, force_rebuild=False):
        """Initialize all parsers with caching mechanism"""
        self.parsers = {}
        
        # Check if we have a cached .so file
        if not force_rebuild and os.path.exists(self.language_so_path):
            try:
                self._load_parsers_from_so()
                return
            except Exception as e:
                print(f"Error loading cached parsers: {e}")
                # If loading fails, continue to rebuild
        
        try:
            # Ensure build directory exists
            os.makedirs('build', exist_ok=True)
            
            # Build the language library
            Language.build_library(
                self.language_so_path,
                [
                    'vendor/tree-sitter-python',
                    'vendor/tree-sitter-javascript',
                    'vendor/tree-sitter-java',
                    'vendor/tree-sitter-c',
                    'vendor/tree-sitter-cpp',
                ]
            )
            
            self._load_parsers_from_so()
            
        except Exception as e:
            print(f"Error during parser initialization: {e}")
            self.parsers = {lang: None for lang in ['python', 'javascript', 'java', 'c', 'cpp']}

    def _load_parsers_from_so(self):
        """Load parsers from the .so file"""
        for lang in ['python', 'javascript', 'java', 'c', 'cpp']:
            try:
                lang_lib = Language(self.language_so_path, lang)
                parser = Parser()
                parser.set_language(lang_lib)
                self.parsers[lang] = parser
            except Exception as e:
                print(f"Error loading {lang} parser: {e}")
                self.parsers[lang] = None

    def _create_query(self, lang, query_str):
        """Create a query for the specified language"""
        if self.parsers[lang] is None:
            return None
        try:
            return self.parsers[lang].language.query(query_str)
        except Exception as e:
            print(f"Error creating query for {lang}: {e}")
            return None

    def parse_code(self, code, language):
        """Parse code using the appropriate parser"""
        if language not in self.parsers or self.parsers[language] is None:
            return None
        
        try:
            return self.parsers[language].parse(bytes(code, 'utf8'))
        except Exception as e:
            print(f"Error parsing {language} code: {e}")
            return None

    def get_chunks(self, code, language):
        """Get code chunks using the appropriate parser and query"""
        tree = self.parse_code(code, language)
        if tree is None:
            return []
        
        if language not in self.queries or self.queries[language] is None:
            return []
            
        chunks = []
        captures = self.queries[language].captures(tree.root_node)
        
        for node, type_ in captures:
            chunk = {
                'type': type_,
                'code': code[node.start_byte:node.end_byte],
                'start_line': node.start_point[0],
                'end_line': node.end_point[0],
                'start_byte': node.start_byte,
                'end_byte': node.end_byte
            }
            chunks.append(chunk)
    
        return chunks
    
    def store_chunk(self, file_path, chunk_id, code, start_line, end_line, byte_range, language):
        self.code_chunks.append({
        'chunk_id': chunk_id,
        'file_path': file_path,
        'code': code,
        'start_line': start_line,
        'end_line': end_line,
        'byte_range': byte_range,
        'language': language
        })
        self.chunk_counter += 1

    def normalize_code(self, code: str) -> str:
        code = code.strip()
        code = re.sub(r'\n\s*\n', '\n\n', code)
        code = code.replace('\r\n', '\n')
        return code

    def process_python(self, file_path: str, code: str) -> None:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"SyntaxError in {file_path}: {e}")
            return

        lines = code.split('\n')
        line_offsets = self._calculate_line_offsets(code)

        nodes = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = getattr(node, 'end_lineno', start_line)
                nodes.append((start_line, end_line, node))

        nodes.sort(key=lambda x: x[0])
        all_chunks = []
        previous_end_line = 0

        for i, (start_line, end_line, node) in enumerate(nodes):
            if previous_end_line < start_line - 1:
                global_start = previous_end_line + 1
                global_end = start_line - 1
                global_code = '\n'.join(lines[global_start-1:global_end])
                if global_code.strip():
                    start_byte = line_offsets[global_start-1]
                    end_byte = line_offsets[global_end] - 1 if global_end < len(line_offsets) else line_offsets[-1]
                    all_chunks.append(('global', global_start, global_end, start_byte, end_byte, global_code))

            node_code = '\n'.join(lines[start_line-1:end_line])
            start_byte = line_offsets[start_line-1]
            end_byte = line_offsets[end_line] - 1 if end_line < len(line_offsets) else line_offsets[-1]
            all_chunks.append(('node', start_line, end_line, start_byte, end_byte, node_code, node))
            previous_end_line = end_line

        if previous_end_line < len(lines):
            global_start = previous_end_line + 1
            global_end = len(lines)
            global_code = '\n'.join(lines[global_start-1:global_end])
            if global_code.strip():
                start_byte = line_offsets[global_start-1]
                end_byte = line_offsets[global_end] - 1 if global_end < len(line_offsets) else line_offsets[-1]
                all_chunks.append(('global', global_start, global_end, start_byte, end_byte, global_code))

        if not nodes and code.strip():
            start_byte = 0
            end_byte = len(code)
            self.store_chunk(file_path, "python_global_1", code, 1, len(lines), (start_byte, end_byte), "python")

        for chunk in all_chunks:
            if chunk[0] == 'global':
                _, sl, el, sb, eb, code_chunk = chunk
                self.chunk_counter += 1
                self.store_chunk(file_path, f"python_global_{self.chunk_counter}", code_chunk, sl, el, (sb, eb), "python")
            else:
                _, sl, el, sb, eb, code_chunk, node = chunk
                self.chunk_counter += 1
                type_name = 'function' if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else 'class'
                self.store_chunk(file_path, f"python_{type_name}_{self.chunk_counter}", code_chunk, sl, el, (sb, eb), "python")

    def _calculate_line_offsets(self, code: str) -> List[int]:
        line_offsets = [0]
        current = 0
        for line in code.split('\n'):
            current += len(line) + 1
            line_offsets.append(current)
        if not code.endswith('\n'):
            line_offsets[-1] -= 1
        return line_offsets

    def process_tree_sitter(self, file_path: str, code: str, language: str) -> None:
        parser = self.parsers.get(language)
        if not parser:
            return

        tree = parser.parse(bytes(code, 'utf-8'))
        query = self.queries.get(language)
        if not query:
            return

        nodes = []
        for node, tag in query.captures(tree.root_node):
            start = node.start_byte
            end = node.end_byte
            nodes.append((start, end, tag))

        nodes.sort(key=lambda x: x[0])
        previous_end = 0

        for start, end, tag in nodes:
            if start > previous_end:
                global_code = code[previous_end:start]
                if global_code.strip():
                    self._store_global_chunk(file_path, code, previous_end, start, language)
            self._store_node_chunk(file_path, code, start, end, tag, language)
            previous_end = end

        if previous_end < len(code):
            global_code = code[previous_end:]
            if global_code.strip():
                self._store_global_chunk(file_path, code, previous_end, len(code), language)

    def _store_global_chunk(self, file_path, code, start_byte, end_byte, lang):
        chunk_code = code[start_byte:end_byte]
        start_line = code.count('\n', 0, start_byte) + 1
        end_line = code.count('\n', 0, end_byte) + 1
        self.store_chunk(file_path, f"{lang}_global_{self.chunk_counter}", chunk_code, start_line, end_line, (start_byte, end_byte), lang)

    def _store_node_chunk(self, file_path, code, start_byte, end_byte, tag, lang):
        chunk_code = code[start_byte:end_byte]
        start_line = code.count('\n', 0, start_byte) + 1
        end_line = code.count('\n', 0, end_byte) + 1
        type_name = 'function' if 'function' in tag else 'class'
        self.store_chunk(file_path, f"{lang}_{type_name}_{self.chunk_counter}", chunk_code, start_line, end_line, (start_byte, end_byte), lang)

    def process_code(self, file_path: str, code: str) -> List[Dict]:
        language = self.detect_language(file_path)
        if language == 'unknown':
            return []

        if language == 'python':
            self.process_python(file_path, code)
        else:
            self.process_tree_sitter(file_path, code, language)

        return self.code_chunks

def process_file(file_path: str) -> List[Dict]:

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    if not code.strip():
        print(f"Error: The file '{file_path}' is empty.")
        return []

    chunker = CodeChunker()
    chunks = chunker.process_code(file_path, code)

    if not chunks:
        print(f"Warning: No chunks found in '{file_path}'.")
        print("   Possible reasons: no functions/classes detected or parsing error.")

    return chunks

    
if __name__ == "__main__":
    file_path = 'D:/New folder/Work/CodeSE/CodeSE/test/dodebase/C++/NUMBER PRISON PATTERN.cpp'  # Example file path
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
        print("No chunks extracted.")

