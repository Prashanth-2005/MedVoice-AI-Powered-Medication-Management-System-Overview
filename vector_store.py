import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

MODEL_NAME = 'all-MiniLM-L6-v2'
DB_PATH = 'medical_kb.json'
INDEX_PATH = 'medical_kb.index'

class MedicalVectorStore:
    _model = None  # Class-level lazy-loaded model

    def __init__(self):
        self.index = None
        self.documents = []
        
    @classmethod
    def get_model(cls):
        if cls._model is None:
            print("Loading AI Model (SentenceTransformer)...")
            cls._model = SentenceTransformer(MODEL_NAME)
        return cls._model

    def load_kb(self):
        if os.path.exists(DB_PATH):
            with open(DB_PATH, 'r') as f:
                self.documents = json.load(f)
        return self.documents

    def build_index(self):
        docs = self.load_kb()
        texts = [f"{d['topic']}: {d['content']}" for d in docs]
        model = self.get_model()
        embeddings = model.encode(texts)
        
        dimensions = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimensions)
        self.index.add(np.array(embeddings).astype('float32'))
        
        # Save index
        faiss.write_index(self.index, INDEX_PATH)
        print(f"Index built with {len(docs)} documents.")

    def search(self, query, k=2):
        if not self.index:
            if os.path.exists(INDEX_PATH):
                self.index = faiss.read_index(INDEX_PATH)
            else:
                self.build_index()
        
        if not self.documents:
            self.load_kb()

        model = self.get_model()
        query_vector = model.encode([query])
        distances, indices = self.index.search(np.array(query_vector).astype('float32'), k)
        
        results = []
        for idx in indices[0]:
            if idx != -1:
                results.append(self.documents[idx])
        return results

if __name__ == "__main__":
    store = MedicalVectorStore()
    store.build_index()
    res = store.search("I missed my blood pressure pill")
    print("Search results:", res)
