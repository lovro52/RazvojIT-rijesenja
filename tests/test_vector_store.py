from app.services import vector_store


class FakeEmbedder:
    def encode(self, documents, convert_to_numpy=True):
        import numpy as np

        return np.asarray([[0.1, 0.2] for _ in documents])


class FakeCollection:
    def __init__(self):
        self.deleted = []
        self.upserted = None
        self.query_arguments = None

    def delete(self, **kwargs):
        self.deleted.append(kwargs)

    def upsert(self, **kwargs):
        self.upserted = kwargs

    def count(self):
        return 2

    def query(self, **kwargs):
        self.query_arguments = kwargs
        return {
            "ids": [["a", "b"]],
            "distances": [[0.1, 0.95]],
            "documents": [["first", "second"]],
            "metadatas": [[{"source": "logs.csv"}, {"source": "logs.csv"}]],
        }


def test_reindex_deletes_every_old_vector_for_source(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(vector_store, "_collection", collection)
    monkeypatch.setattr(vector_store, "_embedder", FakeEmbedder())

    count = vector_store.index_records(
        [{"message": "incident", "incident_index": 7, "record_type": "incident"}],
        "logs.csv",
    )

    assert count == 1
    assert collection.deleted == [{"where": {"source": "logs.csv"}}]
    assert collection.upserted["ids"] == ["logs.csv:incident:7"]


def test_search_is_source_scoped_and_applies_threshold(monkeypatch):
    collection = FakeCollection()
    monkeypatch.setattr(vector_store, "_collection", collection)
    monkeypatch.setattr(vector_store, "_embedder", FakeEmbedder())

    response = vector_store.semantic_search(
        "scan", top_k=5, source_file="logs.csv", min_similarity=0.2
    )

    assert collection.query_arguments["where"] == {"source": "logs.csv"}
    assert [item["id"] for item in response["results"]] == ["a"]
