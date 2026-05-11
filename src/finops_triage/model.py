from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


def build_text(row: dict[str, Any] | pd.Series) -> str:
    getter = row.get
    return " | ".join(
        [
            f"descricao: {getter('description', '')}",
            f"produto: {getter('product', '')}",
            f"canal: {getter('channel', '')}",
            f"sentimento: {getter('sentiment', '')}",
            f"reabertura: {getter('reopened', False)}",
        ]
    )


def train_model(
    rows: list[dict[str, Any]],
    model_path: str | Path,
    metrics_path: str | Path,
) -> dict[str, Any]:
    df = pd.DataFrame(rows)
    x = df.apply(build_text, axis=1)
    y = df["target_queue"]
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )
    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    strip_accents="unicode",
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=4500,
                ),
            ),
            (
                "clf",
                LogisticRegression(max_iter=1000, class_weight="balanced"),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    y_pred = pipeline.predict(x_test)
    labels = sorted(y.unique())
    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
        "labels": labels,
        "classification_report": classification_report(
            y_test,
            y_pred,
            labels=labels,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
        "top_terms": top_terms(pipeline, top_n=7),
    }
    model_path = Path(model_path)
    metrics_path = Path(metrics_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def load_model(model_path: str | Path) -> Pipeline:
    return joblib.load(model_path)


def load_metrics(metrics_path: str | Path) -> dict[str, Any]:
    path = Path(metrics_path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def predict(model: Pipeline, ticket: dict[str, Any]) -> dict[str, Any]:
    text = build_text(ticket)
    probabilities = model.predict_proba([text])[0]
    classes = list(model.classes_)
    ranking = sorted(
        [
            {"queue": str(queue), "probability": round(float(prob), 4)}
            for queue, prob in zip(classes, probabilities)
        ],
        key=lambda item: item["probability"],
        reverse=True,
    )
    winner = ranking[0]
    return {
        "queue": winner["queue"],
        "confidence": winner["probability"],
        "alternatives": ranking[:4],
    }


def top_terms(model: Pipeline, top_n: int = 7) -> dict[str, list[str]]:
    vectorizer: TfidfVectorizer = model.named_steps["tfidf"]
    classifier: LogisticRegression = model.named_steps["clf"]
    feature_names = np.array(vectorizer.get_feature_names_out())
    result: dict[str, list[str]] = {}
    for class_name, coef in zip(classifier.classes_, classifier.coef_):
        indexes = np.argsort(coef)[-top_n:][::-1]
        result[str(class_name)] = [str(feature_names[index]) for index in indexes]
    return result
