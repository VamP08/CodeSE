import React, { useState } from "react";
import axios from "axios";

function App() {
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleProcessPath = async () => {
    setLoading(true);
    setMessage("");
  
    try {
      const response = await axios.post(
        "http://127.0.0.1:5000/process_path",
        { path },  // Ensure it's sending a JSON object
        { headers: { "Content-Type": "application/json" } } // Explicitly set headers
      );
      
      setMessage(response.data.message);
    } catch (error) {
      setMessage("Error processing the path.");
      console.error("Error:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-5">
      <h1 className="text-2xl font-bold mb-4">ChromaDB Code Indexer</h1>

      <div className="flex space-x-2">
        <input
          type="text"
          placeholder="Enter the CodeBase path..."
          value={path}
          onChange={(e) => setPath(e.target.value)}
          className="p-2 border border-gray-400 rounded-md w-80"
        />
        <button
          onClick={handleProcessPath}
          className="bg-blue-500 text-white px-4 py-2 rounded-md"
          disabled={loading}
        >
          {loading ? "Processing..." : "Submit"}
        </button>
      </div>

      {message && <p className="mt-4 text-lg text-gray-700">{message}</p>}
    </div>
  );
}

export default App;
