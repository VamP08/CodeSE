import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import axios from "axios";

function SearchResults() {
  const location = useLocation();
  const { query } = location.state || {};
  const [results, setResults] = useState([]);

  useEffect(() => {
    if (query) {
      axios.post("http://127.0.0.1:5000/search", { query })
        .then(res => setResults(res.data.results))
        .catch(err => console.error("Search error:", err));
    }
  }, [query]);

  return (
    <div className="p-8 bg-gray-100 min-h-screen">
      <h1 className="text-2xl font-bold mb-6">Search Results for: "{query}"</h1>
      {results.length === 0 ? (
        <p>No results found.</p>
      ) : (
        results.map((res, idx) => {
          const meta = res.metadata;
          return (
            <div key={idx} className="bg-white shadow-md rounded-md p-4 mb-4">
              <p className="font-semibold">File: {meta.file_path}</p>
              <p>Language: {meta.language}</p>
              <p>Lines: {meta.start_line}-{meta.end_line}</p>
              <p>Sources: {res.sources.join(", ")}</p>
              <pre className="mt-2 bg-gray-200 p-2 rounded overflow-auto text-sm">{meta.code}</pre>
            </div>
          );
        })
      )}
    </div>
  );
}

export default SearchResults;
