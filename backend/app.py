from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allows frontend to communicate with backend

@app.route('/search', methods=['POST'])
def search():
    data = request.json
    query = data.get("query", "")
    
    # Example response (Replace with your actual search logic)
    results = [
        {"file": "example.py", "path": "/src/example.py", "lines": "10-20", "code": "def example(): pass"},
        {"file": "main.py", "path": "/src/main.py", "lines": "30-40", "code": "print('Hello World')"}
    ]
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
