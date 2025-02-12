from Tree_parser import (
    PythonCodeChunker,
    JavaCodeChunker,
    JavaScriptCodeChunker,
    CppCodeChunker
)

# Create chunkers for different languages
python_chunker = PythonCodeChunker()
js_chunker = JavaScriptCodeChunker()
java_chunker = JavaCodeChunker()
cpp_chunker = CppCodeChunker()

# Process code in any language
chunks = cpp_chunker.chunk_code("""
#include <iostream>

namespace MyApp {
    class Calculator {
    public:
        int add(int a, int b) {
            return a + b;
        }
    };
}

int main() {
    MyApp::Calculator calc;
    std::cout << calc.add(2, 3);
    return 0;
}
""")

for chunk in chunks:
    print(f"{chunk['type']} (lines {chunk['start_line']}-{chunk['end_line']})")
    print(chunk['text'])
    print("---")