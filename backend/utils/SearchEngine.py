import json
import re
from typing import List, Dict, Any, Optional, Set
import chromadb
from utils.Vector_Embedding import CodeEmbeddingModel
import nltk
from nltk.corpus import wordnet

nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)


class CodeSearchEngine:
    def __init__(self, collection=None, embedding_model=None, chunks_filepath: str = None):
        if collection is None:
            chroma_client = chromadb.PersistentClient(path="./chromadb_store")
            self.collection = chroma_client.get_or_create_collection(name="code_embeddings")
        else:
            self.collection = collection

        if embedding_model is None:
            self.embedding_model = CodeEmbeddingModel()
        else:
            self.embedding_model = embedding_model

        self.code_chunks = []
        if chunks_filepath:
            self.code_chunks = self._load_chunks(chunks_filepath)

    def _load_chunks(self, path: str) -> List[Dict]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading chunks: {e}")
            return []

    def vector_search(self, query: str, k: int = 10) -> Dict[str, Dict]:
        if not query or not isinstance(query, str):
            return {}

        try:
            query_embedding = self.embedding_model.generate_embeddings([query])
            # Change 'k' to 'n_results' as per ChromaDB API
            results = self.collection.query(query_embedding, include=["metadatas", "documents"], n_results=k)
        except Exception as e:
            print(f"Vector search error: {e}")
            return {}

        combined = {}
        # Handle case where results might be empty or not structured as expected
        if results and "metadatas" in results and len(results["metadatas"]) > 0:
            metadatas = results["metadatas"][0]
            distances = results.get("distances", [[]])[0] if results.get("distances") else [1.0] * len(metadatas)
            
            for meta, distance in zip(metadatas, distances):
                chunk_id = meta.get("chunk_id")
                score = 1.0 / (distance + 1e-6)  # Inverse distance as score
                combined[chunk_id] = {
                    "score": score,
                    "metadata": meta,
                    "sources": {"vector"}
                }
        return combined

    def keyword_search(self, query: str) -> Dict[str, Dict]:
        if not query or not isinstance(query, str):
            return {}

        pattern = re.compile(re.escape(query), re.IGNORECASE)
        combined = {}
        for chunk in self.code_chunks:
            code = chunk.get("code", "")
            file_path = chunk.get("file_path", "")
            code_matches = len(pattern.findall(code))
            file_matches = len(pattern.findall(file_path))
            total_matches = code_matches + file_matches
            if total_matches > 0:
                chunk_id = chunk.get("chunk_id")
                bonus_score = min(0.1 * total_matches, 1.0)  # Dynamic score up to 1.0
                combined[chunk_id] = {
                    "score": bonus_score,
                    "metadata": chunk,
                    "sources": {"keyword"}
                }
        return combined

    def synonym_search(self, query: str) -> Dict[str, Dict]:
        if not query or not isinstance(query, str):
            return {}

        expanded_terms = set(query.split())
        for word in query.split():
            for syn in wordnet.synsets(word):
                expanded_terms.update(lemma.name() for lemma in syn.lemmas())
        
        pattern = re.compile("|".join(map(re.escape, expanded_terms)), re.IGNORECASE)
        combined = {}
        for chunk in self.code_chunks:
            code = chunk.get("code", "")
            file_path = chunk.get("file_path", "")
            if pattern.search(code) or pattern.search(file_path):
                chunk_id = chunk.get("chunk_id")
                combined[chunk_id] = {
                    "score": 0.3,  # Fixed score per match
                    "metadata": chunk,
                    "sources": {"synonym"}
                }
        return combined

    def llm_search(self, query: str, k: int = 10) -> Dict[str, Dict]:
        if not query or not isinstance(query, str):
            return {}

        # Try to enrich the query with LLM, but handle the case where it's not available
        try:
            if hasattr(self.embedding_model, 'basic_llm'):
                enriched_query = self.embedding_model.basic_llm(query)
            else:
                print("LLM enrichment not available, using original query")
                enriched_query = query
        except Exception as e:
            print(f"LLM enrichment warning: {e}")
            enriched_query = query

        try:
            query_embedding = self.embedding_model.generate_embeddings([enriched_query])
            # Changed 'k' to 'n_results' as per ChromaDB API
            results = self.collection.query(query_embedding, include=["metadatas", "documents"], n_results=k)
        except Exception as e:
            print(f"LLM search error: {e}")
            return {}

        combined = {}
        # Handle case where results might be empty or not structured as expected
        if results and "metadatas" in results and len(results["metadatas"]) > 0:
            metadatas = results["metadatas"][0]
            distances = results.get("distances", [[]])[0] if results.get("distances") else [1.0] * len(metadatas)
            
            for meta, distance in zip(metadatas, distances):
                chunk_id = meta.get("chunk_id")
                combined[chunk_id] = {
                    "score": 1.0 / (distance + 1e-6),
                    "metadata": meta,
                    "sources": {"llm"}
                }
        return combined

    def combined_search(
        self,
        query: str,
        k: int = 10,
        vector_weight: float = 1.0,
        keyword_weight: float = 0.7,
        synonym_weight: float = 0.3,
        llm_weight: float = 0.9
    ) -> List[Dict]:
        vector_results = self.vector_search(query, k)
        keyword_results = self.keyword_search(query)
        synonym_results = self.synonym_search(query)
        llm_results = self.llm_search(query, k)

        combined_scores = {}

        def merge_results(results: Dict[str, Dict], weight: float):
            for chunk_id, data in results.items():
                weighted_score = data["score"] * weight
                entry = combined_scores.get(chunk_id)
                if entry:
                    entry["score"] += weighted_score
                    entry["sources"].update(data["sources"])
                else:
                    combined_scores[chunk_id] = {
                        "score": weighted_score,
                        "metadata": data["metadata"],
                        "sources": set(data["sources"])
                    }

        merge_results(vector_results, vector_weight)
        merge_results(keyword_results, keyword_weight)
        merge_results(synonym_results, synonym_weight)
        merge_results(llm_results, llm_weight)

        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x["score"],
            reverse=True
        )[:k]
        
        # Convert sources set to list for JSON serialization
        for res in sorted_results:
            res["sources"] = list(res["sources"])
        return sorted_results


if __name__ == "__main__":
    import sys
    import os

    if len(sys.argv) > 1:
        chunks_filepath = sys.argv[1]
    else:
        chunks_filepath = input("Enter path to JSON chunks file: ").strip()

    if not os.path.exists(chunks_filepath):
        print(f"Error: File '{chunks_filepath}' not found.")
        sys.exit(1)

    chroma_client = chromadb.PersistentClient(path="./chromadb_store")
    collection = chroma_client.get_or_create_collection(name="code_embeddings")
    search_engine = CodeSearchEngine(collection, CodeEmbeddingModel(), chunks_filepath)

    while True:
        query = input("\nEnter search query (or 'quit'): ").strip()
        if query.lower() == 'quit':
            break
            
        results = search_engine.combined_search(query, k=5)
        print(f"\nFound {len(results)} results:")
        print("-" * 80)
        for i, res in enumerate(results, 1):
            meta = res["metadata"]
            line_info = meta.get("line_numbers") or f"{meta.get('start_line', '?')}-{meta.get('end_line', '?')}"
            print(f"\n#{i} [Score: {res['score']:.2f}]")
            print(f"File: {meta.get('file_path', '?')}")
            print(f"Lines: {line_info}")
            print(f"Language: {meta.get('language', '?')}")
            print("Sources:", ", ".join(res["sources"]))
            print("-" * 50)