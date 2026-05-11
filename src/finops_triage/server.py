from __future__ import annotations

import json
import mimetypes
import os
import shutil
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .analytics import dashboard_metrics
from .model import load_metrics, load_model, predict, train_model
from .openai_client import generate_triage_memo, openai_status
from .retrieval import load_runbooks, retrieve_runbooks
from .sample_data import generate_tickets
from .storage import (
    connect,
    count_tickets,
    init_db,
    list_tickets,
    next_ticket_id,
    replace_tickets,
    save_analysis,
    training_rows,
)


class AppState:
    def __init__(self, root: Path):
        self.root = root
        self.runtime_dir = root / "runtime"
        self.db_path = self.runtime_dir / "triage.db"
        self.model_path = self.runtime_dir / "queue_model.joblib"
        self.metrics_path = self.runtime_dir / "model_metrics.json"
        self.runbooks_path = root / "knowledge" / "runbooks.json"
        self.web_dir = root / "web"
        self.model = None
        self.runbooks: list[dict[str, Any]] = []

    def bootstrap(self, reset: bool = False) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if reset and self.runtime_dir.exists():
            shutil.rmtree(self.runtime_dir)
            self.runtime_dir.mkdir(parents=True, exist_ok=True)

        with connect(self.db_path) as conn:
            init_db(conn)
            if count_tickets(conn) == 0:
                replace_tickets(conn, generate_tickets())
            if reset or not self.model_path.exists() or not self.metrics_path.exists():
                train_model(training_rows(conn), self.model_path, self.metrics_path)

        self.model = load_model(self.model_path)
        self.runbooks = load_runbooks(self.runbooks_path)

    def retrain(self) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            metrics = train_model(training_rows(conn), self.model_path, self.metrics_path)
        self.model = load_model(self.model_path)
        return metrics


def run_server(root: Path, host: str, port: int, reset: bool = False) -> None:
    state = AppState(root=root)
    state.bootstrap(reset=reset)

    class Handler(FinOpsHandler):
        app_state = state

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"FinOps Triage Studio rodando em http://{host}:{port}")
    print("Pressione Ctrl+C para parar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


class FinOpsHandler(BaseHTTPRequestHandler):
    app_state: AppState

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json({"ok": True, "openai": openai_status()})
            return
        if parsed.path == "/api/metrics":
            self._metrics()
            return
        if parsed.path == "/api/tickets":
            query = parse_qs(parsed.query)
            limit = int(query.get("limit", ["80"])[0])
            with connect(self.app_state.db_path) as conn:
                self._json({"tickets": list_tickets(conn, limit=limit)})
            return
        if parsed.path in {"/", "/index.html"}:
            self._static("index.html")
            return
        self._static(parsed.path.lstrip("/"))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            self._analyze()
            return
        if parsed.path == "/api/retrain":
            self._json({"metrics": self.app_state.retrain()})
            return
        self._json({"error": "Not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("FINOPS_VERBOSE"):
            super().log_message(format, *args)

    def _metrics(self) -> None:
        with connect(self.app_state.db_path) as conn:
            tickets = list_tickets(conn, limit=None)
        metrics = dashboard_metrics(tickets, load_metrics(self.app_state.metrics_path), openai_status())
        self._json(metrics)

    def _analyze(self) -> None:
        body = self._read_json()
        now = datetime.now().isoformat(timespec="minutes")
        with connect(self.app_state.db_path) as conn:
            ticket = {
                "ticket_id": body.get("ticket_id") or next_ticket_id(conn),
                "created_at": now,
                "channel": body.get("channel") or "App",
                "segment": body.get("segment") or "Varejo",
                "product": body.get("product") or "Conta Corrente",
                "request_type": body.get("request_type") or "Solicitacao geral",
                "description": body.get("description") or "",
                "value": float(body.get("value") or 0),
                "sentiment": body.get("sentiment") or "Neutro",
                "sentiment_score": _sentiment_score(body.get("sentiment") or "Neutro"),
                "reopened": bool(body.get("reopened")),
                "sla_hours": int(body.get("sla_hours") or 24),
                "resolution_hours": 0,
                "sla_breached": False,
                "auto_service_candidate": bool(body.get("auto_service_candidate")),
                "target_queue": None,
                "priority_label": "A validar",
                "risk_score": 0,
                "status": "Novo",
                "predicted_queue": None,
                "confidence": None,
                "ai_summary": None,
            }

            prediction = predict(self.app_state.model, ticket)
            ticket["predicted_queue"] = prediction["queue"]
            ticket["confidence"] = prediction["confidence"]
            runbooks = retrieve_runbooks(
                ticket,
                self.app_state.runbooks,
                preferred_queue=prediction["queue"],
            )
            memo = generate_triage_memo(ticket, prediction, runbooks)
            ticket["priority_label"] = memo["prioridade"]
            ticket["ai_summary"] = memo["resumo"]

            response = {
                "ticket": ticket,
                "prediction": prediction,
                "runbooks": runbooks,
                "memo": memo,
            }
            if body.get("save", True):
                save_analysis(conn, ticket, response)
        self._json(response)

    def _static(self, relative_path: str) -> None:
        candidate = (self.app_state.web_dir / relative_path).resolve()
        web_root = self.app_state.web_dir.resolve()
        if not (candidate == web_root or str(candidate).startswith(str(web_root) + os.sep)):
            self._json({"error": "Invalid path"}, status=400)
            return
        if not candidate.exists() or not candidate.is_file():
            self._json({"error": "Not found"}, status=404)
            return
        content_type, _ = mimetypes.guess_type(str(candidate))
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.end_headers()
        self.wfile.write(candidate.read_bytes())

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _sentiment_score(sentiment: str) -> float:
    return {"Negativo": 0.2, "Neutro": 0.55, "Positivo": 0.82}.get(sentiment, 0.55)
