from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_community.retrievers import TFIDFRetriever
from langchain_core.documents import Document
from sklearn.metrics.pairwise import cosine_similarity

from .model import build_text


def load_runbooks(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def retrieve_runbooks(
    ticket: dict[str, Any],
    runbooks: list[dict[str, Any]],
    top_k: int = 3,
    preferred_queue: str | None = None,
) -> list[dict[str, Any]]:
    query = build_text(ticket)
    documents = [_runbook_to_document(item) for item in runbooks]
    retriever = TFIDFRetriever.from_documents(
        documents,
        k=len(documents),
        tfidf_params={"strip_accents": "unicode", "lowercase": True},
    )
    retrieved_docs = retriever.invoke(query)
    scores = _document_scores(retriever, query)
    ranked = [_document_to_runbook(doc, scores) for doc in retrieved_docs]

    if preferred_queue:
        preferred = [item for item in ranked if item.get("queue") == preferred_queue]
        others = [item for item in ranked if item.get("queue") != preferred_queue]
        ranked = preferred + others

    return ranked[:top_k]


def _runbook_to_document(runbook: dict[str, Any]) -> Document:
    content = "\n".join(
        [
            f"Titulo: {runbook['title']}",
            f"Fila: {runbook['queue']}",
            f"Resumo: {runbook['summary']}",
            "Acoes: " + " ".join(runbook["actions"]),
            "Controles: " + " ".join(runbook["controls"]),
        ]
    )
    return Document(
        page_content=content,
        metadata={
            "id": runbook["id"],
            "queue": runbook["queue"],
            "title": runbook["title"],
            "summary": runbook["summary"],
            "actions": runbook["actions"],
            "controls": runbook["controls"],
        },
    )


def _document_scores(retriever: TFIDFRetriever, query: str) -> dict[str, float]:
    query_vector = retriever.vectorizer.transform([query])
    scores = cosine_similarity(query_vector, retriever.tfidf_array).flatten()
    return {
        str(document.metadata["id"]): round(float(score), 3)
        for document, score in zip(retriever.docs, scores)
    }


def _document_to_runbook(document: Document, scores: dict[str, float]) -> dict[str, Any]:
    item = dict(document.metadata)
    item["score"] = scores.get(str(item["id"]), 0.0)
    item["retrieval"] = "langchain_tfidf"
    return item
