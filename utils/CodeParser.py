import os
import ast
import re
from typing import List, Dict, Tuple
from pathlib import Path

# For C++ Parsing
try:
    import clang.cindex
    CLANG_AVAILABLE = True
except ImportError:
    CLANG_AVAILABLE = False
    print("Warning: clang.cindex not available. C++ parsing will use fallback method.")


# For JavaScript parsing
try:
    import esprima
    ESPRIMA_AVAILABLE = True
except ImportError:
    ESPRIMA_AVAILABLE = False
    print("Warning: esprima not available. JavaScript parsing will be limited.")

# For Java parsing
try:
    import javalang
    JAVALANG_AVAILABLE = True
except ImportError:
    JAVALANG_AVAILABLE = False
    print("Warning: javalang not available. Java parsing will be limited.")

# For C/C++ parsing
try:
    import pycparser
    from pycparser import c_parser, c_ast
    PYCPARSER_AVAILABLE = True
except ImportError:
    PYCPARSER_AVAILABLE = False
    print("Warning: pycparser not available. C/C++ parsing will be limited.")

class CodeChunker:
    def __init__(self):
        self.code_chunks = []
        self.chunk_counter = 0

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

    def _calculate_line_offsets(self, code: str) -> List[int]:
        line_offsets = [0]
        current = 0
        for line in code.split('\n'):
            current += len(line) + 1
            line_offsets.append(current)
        if not code.endswith('\n'):
            line_offsets[-1] -= 1
        return line_offsets

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
                end_byte = line_offsets[global_end-1] if global_end-1 < len(line_offsets) else line_offsets[-1]
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

    def process_javascript(self, file_path: str, code: str) -> None:
        if not ESPRIMA_AVAILABLE:
            # Fallback to regex-based parsing if esprima is not available
            self._process_javascript_fallback(file_path, code)
            return
            
        try:
            # Parse JavaScript code using esprima
            ast = esprima.parseScript(code, {'loc': True, 'range': True})
            
            # Extract functions and classes
            functions = []
            classes = []
            
            def visit_node(node, parent=None):
                if node.type == 'FunctionDeclaration':
                    functions.append(node)
                elif node.type == 'ClassDeclaration':
                    classes.append(node)
                elif node.type == 'VariableDeclaration':
                    for declarator in node.declarations:
                        if (declarator.init and 
                            (declarator.init.type == 'FunctionExpression' or 
                             declarator.init.type == 'ArrowFunctionExpression')):
                            functions.append(declarator)
                
                # Recursively visit all properties of the node
                for key, value in node.__dict__.items():
                    if key == 'parent':
                        continue
                    if isinstance(value, list):
                        for item in value:
                            if hasattr(item, 'type'):
                                visit_node(item, node)
                    elif hasattr(value, 'type'):
                        visit_node(value, node)
            
            visit_node(ast)
            
            # Sort by start position
            all_nodes = sorted(functions + classes, key=lambda x: x.range[0])
            
            # Process chunks
            previous_end = 0
            for node in all_nodes:
                start, end = node.range
                
                # Add global code before this node if any
                if start > previous_end:
                    global_code = code[previous_end:start]
                    if global_code.strip():
                        start_line = code.count('\n', 0, previous_end) + 1
                        end_line = code.count('\n', 0, start) + 1
                        self.chunk_counter += 1
                        self.store_chunk(
                            file_path, 
                            f"javascript_global_{self.chunk_counter}", 
                            global_code, 
                            start_line, 
                            end_line, 
                            (previous_end, start), 
                            "javascript"
                        )
                
                # Add the node
                chunk_code = code[start:end]
                start_line = node.loc.start.line
                end_line = node.loc.end.line
                node_type = 'class' if hasattr(node, 'type') and node.type == 'ClassDeclaration' else 'function'
                self.chunk_counter += 1
                self.store_chunk(
                    file_path, 
                    f"javascript_{node_type}_{self.chunk_counter}", 
                    chunk_code, 
                    start_line, 
                    end_line, 
                    (start, end), 
                    "javascript"
                )
                
                previous_end = end
            
            # Add any remaining code as a global chunk
            if previous_end < len(code):
                global_code = code[previous_end:]
                if global_code.strip():
                    start_line = code.count('\n', 0, previous_end) + 1
                    end_line = code.count('\n', 0, len(code)) + 1
                    self.chunk_counter += 1
                    self.store_chunk(
                        file_path, 
                        f"javascript_global_{self.chunk_counter}", 
                        global_code, 
                        start_line, 
                        end_line, 
                        (previous_end, len(code)), 
                        "javascript"
                    )
                    
        except Exception as e:
            print(f"Error parsing JavaScript in {file_path}: {e}")
            # Fallback to regex-based parsing
            self._process_javascript_fallback(file_path, code)

    def _process_javascript_fallback(self, file_path: str, code: str) -> None:
        # Fallback regex patterns for JavaScript
        patterns = {
            'function': r'(?:async\s+)?(?:function\s+([a-zA-Z_]\w*)|(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s+)?(?:function\s*)?\(.*?\)\s*=>\s*{?|\(.*?\)\s*=>\s*{?|\bfunction\s*\([^)]*\)\s*{',
            'class': r'class\s+([a-zA-Z_]\w*)\s*(?:extends\s+[a-zA-Z_]\w*)?\s*{',
            'comment': r'//.*$|/\*[\s\S]*?\*/'
        }
        
        # Process with regex
        self._process_with_regex(file_path, code, "javascript", patterns)
    def process_python(self, file_path: str, code: str) -> None:
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"SyntaxError in {file_path}: {e}")
            # Fallback to regex-based parsing
            self._process_python_fallback(file_path, code)
            return

        lines = code.split('\n')
        line_offsets = self._calculate_line_offsets(code)

        nodes = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Calculate start_line considering decorators
                start_line = node.lineno
                if hasattr(node, 'decorator_list') and node.decorator_list:
                    decorator_lines = [dec.lineno for dec in node.decorator_list if hasattr(dec, 'lineno')]
                    if decorator_lines:
                        start_line = min(decorator_lines + [start_line])
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
                end_byte = line_offsets[global_end-1] if global_end-1 < len(line_offsets) else line_offsets[-1]
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

    def _process_python_fallback(self, file_path: str, code: str) -> None:
        patterns = {
            'function': r'^\s*(?:async\s+)?def\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*:',
            'class': r'^\s*class\s+([a-zA-Z_]\w*)\s*(?:\([^)]*\))?\s*:',
            'comment': r'#.*$'
        }
        self._process_with_regex(file_path, code, 'python', patterns)

    def process_java(self, file_path: str, code: str) -> None:
        if not JAVALANG_AVAILABLE:
            # Fallback to regex-based parsing if javalang is not available
            self._process_java_fallback(file_path, code)
            return
            
        try:
            # Parse Java code using javalang
            tree = javalang.parse.parse(code)
            
            # Extract classes and methods
            classes = []
            methods = []
            
            for path, node in tree.filter(javalang.tree.ClassDeclaration):
                classes.append(node)
                
            for path, node in tree.filter(javalang.tree.MethodDeclaration):
                methods.append(node)
                
            # Sort by position
            all_nodes = []
            
            for node in classes:
                if hasattr(node, 'position') and node.position:
                    start_pos = node.position.line
                    # Approximate end position by counting braces
                    class_text = code[code.find("class " + node.name):]
                    open_braces = 0
                    close_braces = 0
                    for i, char in enumerate(class_text):
                        if char == '{':
                            open_braces += 1
                        elif char == '}':
                            close_braces += 1
                            if open_braces == close_braces:
                                end_pos = code.count('\n', 0, code.find("class " + node.name) + i) + 1
                                all_nodes.append(('class', node, start_pos, end_pos))
                                break
            
            for node in methods:
                if hasattr(node, 'position') and node.position:
                    start_pos = node.position.line
                    # Approximate end position by counting braces
                    method_text = code[code.find(node.name + "("):]
                    open_braces = 0
                    close_braces = 0
                    for i, char in enumerate(method_text):
                        if char == '{':
                            open_braces += 1
                        elif char == '}':
                            close_braces += 1
                            if open_braces == close_braces:
                                end_pos = code.count('\n', 0, code.find(node.name + "(") + i) + 1
                                all_nodes.append(('method', node, start_pos, end_pos))
                                break
            
            # Sort by start position
            all_nodes.sort(key=lambda x: x[2])
            
            # Process chunks
            lines = code.split('\n')
            line_offsets = self._calculate_line_offsets(code)
            previous_end_line = 0
            
            for node_type, node, start_line, end_line in all_nodes:
                if previous_end_line < start_line - 1:
                    global_start = previous_end_line + 1
                    global_end = start_line - 1
                    global_code = '\n'.join(lines[global_start-1:global_end])
                    if global_code.strip():
                        start_byte = line_offsets[global_start-1]
                        end_byte = line_offsets[global_end] - 1 if global_end < len(line_offsets) else line_offsets[-1]
                        self.chunk_counter += 1
                        self.store_chunk(
                            file_path, 
                            f"java_global_{self.chunk_counter}", 
                            global_code, 
                            global_start, 
                            global_end, 
                            (start_byte, end_byte), 
                            "java"
                        )
                
                node_code = '\n'.join(lines[start_line-1:end_line])
                start_byte = line_offsets[start_line-1]
                end_byte = line_offsets[end_line] - 1 if end_line < len(line_offsets) else line_offsets[-1]
                self.chunk_counter += 1
                chunk_type = 'class' if node_type == 'class' else 'function'
                self.store_chunk(
                    file_path, 
                    f"java_{chunk_type}_{self.chunk_counter}", 
                    node_code, 
                    start_line, 
                    end_line, 
                    (start_byte, end_byte), 
                    "java"
                )
                
                previous_end_line = end_line
            
            # Add any remaining code as a global chunk
            if previous_end_line < len(lines):
                global_start = previous_end_line + 1
                global_end = len(lines)
                global_code = '\n'.join(lines[global_start-1:global_end])
                if global_code.strip():
                    start_byte = line_offsets[global_start-1]
                    end_byte = line_offsets[global_end-1] if global_end-1 < len(line_offsets) else line_offsets[-1]
                    self.chunk_counter += 1
                    self.store_chunk(
                        file_path, 
                        f"java_global_{self.chunk_counter}", 
                        global_code, 
                        global_start, 
                        global_end, 
                        (start_byte, end_byte), 
                        "java"
                    )
                    
        except Exception as e:
            print(f"Error parsing Java in {file_path}: {e}")
            # Fallback to regex-based parsing
            self._process_java_fallback(file_path, code)

    def _process_java_fallback(self, file_path: str, code: str) -> None:
        # Fallback regex patterns for Java
        patterns = {
            'function': r'(?:public|private|protected)?\s+(?:static\s+)?[\w<>\[\],\s]+\s+([a-zA-Z_]\w*)\s*\([^)]*\)\s*(?:throws\s+[\w\s,]+)?\s*{',
            'class': r'(?:public|private|protected)?\s+class\s+([a-zA-Z_]\w*)\s*(?:extends\s+[a-zA-Z_]\w*)?(?:\s+implements\s+[a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)*)?\s*{',
            'comment': r'//.*$|/\*[\s\S]*?\*/'
        }
        
        # Process with regex
        self._process_with_regex(file_path, code, "java", patterns)

    def process_c_cpp(self, file_path: str, code: str, language: str) -> None:
        if language == 'cpp' and CLANG_AVAILABLE:
            self._process_cpp_with_clang(file_path, code)
            return
        
        if not PYCPARSER_AVAILABLE:
            # Fallback to regex-based parsing if pycparser is not available
            self._process_c_cpp_fallback(file_path, code, language)
            return
            
        try:
            # For C/C++ parsing with pycparser, we need to preprocess the code
            # This is a simplified approach and may not work for all C/C++ code
            
            # Remove preprocessor directives and comments for parsing
            preprocessed_code = re.sub(r'#.*?(?:\n|$)', '\n', code)
            preprocessed_code = re.sub(r'//.*?(?:\n|$)', '\n', preprocessed_code)
            preprocessed_code = re.sub(r'/\*.*?\*/', '', preprocessed_code, flags=re.DOTALL)
            
            # Parse the code
            parser = c_parser.CParser()
            ast = parser.parse(preprocessed_code, filename=file_path)
            
            # Extract functions and structs/classes
            functions = []
            structs = []
            
            class NodeVisitor(c_ast.NodeVisitor):
                def visit_FuncDef(self, node):
                    functions.append(node)
                    self.generic_visit(node)
                    
                def visit_Struct(self, node):
                    structs.append(node)
                    self.generic_visit(node)
                    
                def visit_Union(self, node):
                    structs.append(node)
                    self.generic_visit(node)
            
            visitor = NodeVisitor()
            visitor.visit(ast)
            
            # Map AST nodes to original code positions
            # This is approximate since pycparser doesn't provide source positions
            all_nodes = []
            
            for node in functions:
                if hasattr(node, 'decl') and hasattr(node.decl, 'name'):
                    func_name = node.decl.name
                    # Find function in original code
                    pattern = r'\b' + re.escape(func_name) + r'\s*\([^)]*\)\s*{'
                    match = re.search(pattern, code)
                    if match:
                        start_pos = match.start()
                        # Find the end by matching braces
                        open_braces = 0
                        close_braces = 0
                        for i, char in enumerate(code[start_pos:]):
                            if char == '{':
                                open_braces += 1
                            elif char == '}':
                                close_braces += 1
                                if open_braces == close_braces:
                                    end_pos = start_pos + i + 1
                                    start_line = code.count('\n', 0, start_pos) + 1
                                    end_line = code.count('\n', 0, end_pos) + 1
                                    all_nodes.append(('function', start_line, end_line, start_pos, end_pos))
                                    break
            
            for node in structs:
                if hasattr(node, 'name') and node.name:
                    struct_name = node.name
                    # Find struct/class in original code
                    pattern = r'(?:struct|class|union)\s+' + re.escape(struct_name) + r'\s*{'
                    match = re.search(pattern, code)
                    if match:
                        start_pos = match.start()
                        # Find the end by matching braces
                        open_braces = 0
                        close_braces = 0
                        for i, char in enumerate(code[start_pos:]):
                            if char == '{':
                                open_braces += 1
                            elif char == '}':
                                close_braces += 1
                                if open_braces == close_braces:
                                    end_pos = start_pos + i + 1
                                    start_line = code.count('\n', 0, start_pos) + 1
                                    end_line = code.count('\n', 0, end_pos) + 1
                                    all_nodes.append(('struct', start_line, end_line, start_pos, end_pos))
                                    break
            
            # Sort by start position
            all_nodes.sort(key=lambda x: x[3])
            
            # Process chunks
            previous_end = 0
            
            for node_type, start_line, end_line, start_pos, end_pos in all_nodes:
                # Add global code before this node if any
                if start_pos > previous_end:
                    global_code = code[previous_end:start_pos]
                    if global_code.strip():
                        global_start_line = code.count('\n', 0, previous_end) + 1
                        global_end_line = code.count('\n', 0, start_pos) + 1
                        self.chunk_counter += 1
                        self.store_chunk(
                            file_path, 
                            f"{language}_global_{self.chunk_counter}", 
                            global_code, 
                            global_start_line, 
                            global_end_line, 
                            (previous_end, start_pos), 
                            language
                        )
                
                # Add the node
                chunk_code = code[start_pos:end_pos]
                chunk_type = 'class' if node_type == 'struct' else 'function'
                self.chunk_counter += 1
                self.store_chunk(
                    file_path, 
                    f"{language}_{chunk_type}_{self.chunk_counter}", 
                    chunk_code, 
                    start_line, 
                    end_line, 
                    (start_pos, end_pos), 
                    language
                )
                
                previous_end = end_pos
            
            # Add any remaining code as a global chunk
            if previous_end < len(code):
                global_code = code[previous_end:]
                if global_code.strip():
                    start_line = code.count('\n', 0, previous_end) + 1
                    end_line = code.count('\n', 0, len(code)) + 1
                    self.chunk_counter += 1
                    self.store_chunk(
                        file_path, 
                        f"{language}_global_{self.chunk_counter}", 
                        global_code, 
                        start_line, 
                        end_line, 
                        (previous_end, len(code)), 
                        language
                    )
                    
        except Exception as e:
            print(f"Error parsing {language} in {file_path}: {e}")
            # Fallback to regex-based parsing
            self._process_c_cpp_fallback(file_path, code, language)
    
    def _process_c_cpp_fallback(self, file_path: str, code: str, language: str) -> None:
        # Fallback regex patterns for C/C++
        if language == 'c':
            patterns = {
                'function': r'\b[a-zA-Z_][a-zA-Z0-9_]*\s+\**([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*{',
                'struct': r'struct\s+([a-zA-Z_]\w*)\s*{',
                'union': r'union\s+([a-zA-Z_]\w*)\s*{',
                'comment': r'//.*$|/\*[\s\S]*?\*/'
            }
        else:  # cpp
            patterns = {
                'function': r'(?:virtual\s+|static\s+|inline\s+)?\b(?:[a-zA-Z_][a-zA-Z0-9_:<>]*(?:::[a-zA-Z_][a-zA-Z0-9_:<>]*)*)\s+\**(?:[a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_][a-zA-Z0-9_]*)*)?\s*\([^)]*\)\s*(?:const|noexcept|override|final|throw\([^)]*\))?\s*(?:->.*?)?\s*{',
                'class': r'(?:class|struct)\s+([a-zA-Z_]\w*)\s*(?:final|sealed)?(?:\s*:\s*(?:public|private|protected)?\s+[a-zA-Z_][a-zA-Z0-9_:<>]*(?:\s*,\s*(?:public|private|protected)?\s+[a-zA-Z_][a-zA-Z0-9_:<>]*)*)?(?:\s*\{)',
                'namespace': r'namespace\s+(?:[a-zA-Z_]\w*)\s*\{',
                'template': r'template\s*<[^>]*>\s*(?:class|struct|typename)\s+([a-zA-Z_]\w*)\s*(?::[^{]*)?{',
                'comment': r'//.*$|/\*[\s\S]*?\*/'
            }
        
        # Process with regex
        self._process_with_regex(file_path, code, language, patterns)

    
    def _process_cpp_with_clang(self, file_path: str, code: str) -> None:
        """Process C++ code using clang."""
        try:
            # Create a temporary file with the code
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.cpp', delete=False, mode='w') as temp_file:
                temp_file.write(code)
                temp_path = temp_file.name
            
            # Parse the file with clang
            index = clang.cindex.Index.create()
            tu = index.parse(temp_path)
            
            # Extract functions, classes, structs, and namespaces
            all_nodes = []
            
            def visit_node(node, parent=None):
                if node.location.file and node.location.file.name == temp_path:
                    if node.kind in [
                        clang.cindex.CursorKind.FUNCTION_DECL,
                        clang.cindex.CursorKind.CXX_METHOD,
                        clang.cindex.CursorKind.CONSTRUCTOR,
                        clang.cindex.CursorKind.DESTRUCTOR,
                        clang.cindex.CursorKind.CLASS_DECL,
                        clang.cindex.CursorKind.STRUCT_DECL,
                        clang.cindex.CursorKind.NAMESPACE,
                        clang.cindex.CursorKind.CLASS_TEMPLATE
                    ]:
                        # Get the source range
                        start_line = node.extent.start.line
                        end_line = node.extent.end.line
                        start_offset = node.extent.start.offset
                        end_offset = node.extent.end.offset
                        
                        # Determine node type
                        if node.kind in [clang.cindex.CursorKind.FUNCTION_DECL, 
                                        clang.cindex.CursorKind.CXX_METHOD,
                                        clang.cindex.CursorKind.CONSTRUCTOR,
                                        clang.cindex.CursorKind.DESTRUCTOR]:
                            node_type = 'function'
                        elif node.kind in [clang.cindex.CursorKind.CLASS_DECL, 
                                        clang.cindex.CursorKind.STRUCT_DECL,
                                        clang.cindex.CursorKind.CLASS_TEMPLATE]:
                            node_type = 'class'
                        else:
                            node_type = 'namespace'
                        
                        all_nodes.append((node_type, start_line, end_line, start_offset, end_offset))
                
                # Visit children
                for child in node.get_children():
                    visit_node(child, node)
            
            # Start traversal from the translation unit
            visit_node(tu.cursor)
            
            # Sort nodes by start position
            all_nodes.sort(key=lambda x: x[3])
            
            # Process chunks
            previous_end = 0
            
            for node_type, start_line, end_line, start_offset, end_offset in all_nodes:
                # Map offsets from temp file to original code
                start_pos = min(start_offset, len(code) - 1)
                end_pos = min(end_offset, len(code))
                
                # Add global code before this node if any
                if start_pos > previous_end:
                    global_code = code[previous_end:start_pos]
                    if global_code.strip():
                        global_start_line = code.count('\n', 0, previous_end) + 1
                        global_end_line = code.count('\n', 0, start_pos) + 1
                        self.chunk_counter += 1
                        self.store_chunk(
                            file_path, 
                            f"cpp_global_{self.chunk_counter}", 
                            global_code, 
                            global_start_line, 
                            global_end_line, 
                            (previous_end, start_pos), 
                            "cpp"
                        )
                
                # Add the node
                chunk_code = code[start_pos:end_pos]
                if chunk_code.strip():
                    self.chunk_counter += 1
                    self.store_chunk(
                        file_path, 
                        f"cpp_{node_type}_{self.chunk_counter}", 
                        chunk_code, 
                        start_line, 
                        end_line, 
                        (start_pos, end_pos), 
                        "cpp"
                    )
                
                previous_end = end_pos
            
            # Add any remaining code as a global chunk
            if previous_end < len(code):
                global_code = code[previous_end:]
                if global_code.strip():
                    start_line = code.count('\n', 0, previous_end) + 1
                    end_line = code.count('\n', 0, len(code)) + 1
                    self.chunk_counter += 1
                    self.store_chunk(
                        file_path, 
                        f"cpp_global_{self.chunk_counter}", 
                        global_code, 
                        start_line, 
                        end_line, 
                        (previous_end, len(code)), 
                        "cpp"
                    )
            
            # Clean up the temporary file
            import os
            os.unlink(temp_path)
            
        except Exception as e:
            print(f"Error parsing C++ with clang in {file_path}: {e}")
            # Fallback to regex-based parsing
            self._process_c_cpp_fallback(file_path, code, "cpp")

    
    def _process_with_regex(self, file_path: str, code: str, language: str, patterns: Dict) -> None:
        """Process code using regex patterns for the given language."""
        # Remove comments to avoid false positives
        if 'comment' in patterns:
            code_without_comments = re.sub(patterns['comment'], '', code, flags=re.MULTILINE)
        else:
            code_without_comments = code
            
        # Find all definitions
        definitions = []
        
        for def_type, pattern in patterns.items():
            if def_type == 'comment':
                continue
                
            if pattern:
                for match in re.finditer(pattern, code_without_comments, re.MULTILINE):
                    start_pos = match.start()
                    # Find the opening brace
                    open_brace_pos = code_without_comments.find('{', start_pos)
                    if open_brace_pos != -1:
                        # Find the matching closing brace
                        close_brace_pos = self._find_matching_brace(code_without_comments, open_brace_pos + 1)
                        if close_brace_pos != -1:
                            definitions.append((start_pos, close_brace_pos, def_type))
        
        # Sort definitions by start position
        definitions.sort(key=lambda x: x[0])
        
        # Process chunks
        previous_end = 0
        for start, end, def_type in definitions:
            # Add global code before this definition if any
            if start > previous_end:
                global_code = code[previous_end:start]
                if global_code.strip():
                    start_line = code.count('\n', 0, previous_end) + 1
                    end_line = code.count('\n', 0, start) + 1
                    self.chunk_counter += 1
                    self.store_chunk(
                        file_path, 
                        f"{language}_global_{self.chunk_counter}", 
                        global_code, 
                        start_line, 
                        end_line, 
                        (previous_end, start), 
                        language
                    )
            
            # Add the definition
            chunk_code = code[start:end]
            start_line = code.count('\n', 0, start) + 1
            end_line = code.count('\n', 0, end) + 1
            self.chunk_counter += 1
            chunk_type = 'class' if def_type in ('class', 'struct', 'union') else def_type
            self.store_chunk(
                file_path, 
                f"{language}_{chunk_type}_{self.chunk_counter}", 
                chunk_code, 
                start_line, 
                end_line, 
                (start, end), 
                language
            )
            
            previous_end = end
        
        # Add any remaining code as a global chunk
        if previous_end < len(code):
            global_code = code[previous_end:]
            if global_code.strip():
                start_line = code.count('\n', 0, previous_end) + 1
                end_line = code.count('\n', 0, len(code)) + 1
                self.chunk_counter += 1
                self.store_chunk(
                    file_path, 
                    f"{language}_global_{self.chunk_counter}", 
                    global_code, 
                    start_line, 
                    end_line, 
                    (previous_end, len(code)), 
                    language
                )

    def _find_matching_brace(self, code: str, start_pos: int) -> int:
        """Find the matching closing brace for an opening brace."""
        stack = 1
        pos = start_pos
        
        while pos < len(code) and stack > 0:
            if code[pos] == '{':
                stack += 1
            elif code[pos] == '}':
                stack -= 1
            pos += 1
            
        return pos if stack == 0 else -1

    def process_code(self, file_path: str, code: str) -> List[Dict]:
        """Process code and extract chunks based on language."""
        self.code_chunks = []  # Reset chunks for new file
        self.chunk_counter = 0
        
        language = self.detect_language(file_path)
        if language == 'unknown':
            return []

        if language == 'python':
            self.process_python(file_path, code)
        elif language in ['javascript', 'jsx']:
            self.process_javascript(file_path, code)
        elif language == 'java':
            self.process_java(file_path, code)
        elif language in ['c', 'cpp']:
            self.process_c_cpp(file_path, code, language)
        else:
            print(f"Warning: Language '{language}' is recognized but not fully supported.")
            # Try to use regex-based fallback for other languages
            self._process_with_regex(file_path, code, language, {
                'function': r'\b\w+\s+\w+\s*\([^)]*\)\s*{',
                'class': r'(?:class|struct)\s+\w+\s*{',
                'comment': r'//.*$|/\*[\s\S]*?\*/'
            })

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
                print("   - The AST-based chunking might not fully support this file format.")
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
    file_path = 'D:\\New folder\\Work\\College Assignments\\Uni-Work\\SEM-4\\Javascript\\ASSIGNMENT - 7\script.js'  # Example file path
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

