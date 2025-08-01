import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

function App() {
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    axios.get("http://127.0.0.1:5000/get_projects")
      .then(res => setProjects(res.data.projects))
      .catch(err => console.error("Error loading projects", err));
  }, []);

  const handleProjectSelect = async (e) => {
    const selectedPath = e.target.value;
    setSelectedProject(selectedPath);

    try {
      await axios.post("http://127.0.0.1:5000/set_active_project", { path: selectedPath }, {
        headers: { "Content-Type": "application/json" }
      });
    } catch (err) {
      console.error("Error setting active project:", err);
    }
  };

  const handleProcessPath = async () => {
    setLoading(true);
    setMessage("");
    try {
      const response = await axios.post(
        "http://127.0.0.1:5000/process_path",
        { path },
        { headers: { "Content-Type": "application/json" } }
      );

      setMessage(response.data.message);
      const updated = await axios.get("http://127.0.0.1:5000/get_projects");
      setProjects(updated.data.projects);
    } catch (error) {
      setMessage("Error processing the path.");
      console.error("Error:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    navigate("/results", { state: { query } });
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-5">
      <h1 className="text-2xl font-bold mb-4">ChromaDB Code Indexer</h1>

      <div className="flex space-x-2 mb-6">
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

      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Select a Project</h2>
        <select
          value={selectedProject}
          onChange={handleProjectSelect}
          className="p-2 border border-gray-400 rounded-md w-80"
        >
          <option value="">-- Select Project --</option>
          {projects.map((proj, idx) => (
            <option key={idx} value={proj.path}>
              {proj.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex space-x-2">
        <input
          type="text"
          placeholder="Enter your search query..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="p-2 border border-gray-400 rounded-md w-80"
        />
        <button
          onClick={handleSearch}
          className="bg-green-600 text-white px-4 py-2 rounded-md"
        >
          Search
        </button>
      </div>

      {message && <p className="mt-4 text-lg text-gray-700">{message}</p>}
    </div>
  );
}

export default App;
