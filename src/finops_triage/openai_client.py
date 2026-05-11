from __future__ import annotations

import json
import os
from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


DEFAULT_MODEL = "gpt-4.1-mini"
PLACEHOLDER_KEYS = {"sua-chave", "sua-chave-aqui", "sk-sua-chave-aqui"}

SYSTEM_PROMPT = (
    "Voce apoia analistas de operacoes financeiras na triagem de chamados. "
    "Use apenas os dados recebidos e os runbooks fornecidos. "
    "Nao prometa aprovacao, estorno, limite, prazo regulatorio ou decisao financeira. "
    "Para fraude, alto valor, reabertura ou insatisfacao alta, mantenha humano no loop. "
    "Responda em portugues do Brasil, de forma objetiva."
)

USER_PROMPT = """
Analise o chamado abaixo e devolva uma resposta estruturada.

Chamado:
{ticket}

Predicao do modelo de classificacao:
{prediction}

Runbooks recuperados pelo retriever LangChain:
{runbooks}
""".strip()


class TriageMemo(BaseModel):
    resumo: str
    prioridade: Literal["Baixa", "Media", "Alta"]
    racional: list[str]
    acoes_recomendadas: list[str]
    resposta_cliente: str
    pontos_de_controle: list[str]


def openai_status() -> dict[str, Any]:
    api_key = _api_key()
    raw_key = os.getenv("OPENAI_API_KEY", "").strip()
    reason = None
    if not raw_key:
        reason = "OPENAI_API_KEY nao configurada"
    elif not api_key:
        reason = "OPENAI_API_KEY ainda esta com valor de exemplo"

    return {
        "configured": bool(api_key),
        "model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        "reason": reason,
        "framework": "langchain",
    }


def generate_triage_memo(
    ticket: dict[str, Any],
    prediction: dict[str, Any],
    runbooks: list[dict[str, Any]],
) -> dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        return fallback_memo(ticket, prediction, runbooks, reason=openai_status()["reason"])

    model_name = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    try:
        llm = ChatOpenAI(model=model_name, temperature=0, timeout=45, max_retries=1)
        structured_llm = llm.with_structured_output(TriageMemo, method="json_schema")
        chain = _triage_prompt() | structured_llm
        result = chain.invoke(
            {
                "ticket": _json_dump(ticket),
                "prediction": _json_dump(prediction),
                "runbooks": _json_dump(runbooks),
            }
        )
        memo = _memo_to_dict(result)
        memo["source"] = "langchain_openai"
        memo["model"] = model_name
        return memo
    except Exception as exc:
        return fallback_memo(ticket, prediction, runbooks, reason=f"Falha LangChain/OpenAI: {exc}")


def fallback_memo(
    ticket: dict[str, Any],
    prediction: dict[str, Any],
    runbooks: list[dict[str, Any]],
    reason: str,
) -> dict[str, Any]:
    priority = _priority(ticket, prediction)
    actions: list[str] = []
    controls: list[str] = []
    relevant_runbooks = [
        runbook for runbook in runbooks if runbook.get("queue") == prediction.get("queue")
    ] or runbooks[:1]
    for runbook in relevant_runbooks:
        for action in runbook.get("actions", []):
            if action not in actions:
                actions.append(action)
        for control in runbook.get("controls", []):
            if control not in controls:
                controls.append(control)

    if priority == "Alta":
        actions.insert(0, "Encaminhar para revisao humana antes de qualquer encerramento automatico.")

    return {
        "resumo": (
            f"Chamado sobre {ticket.get('request_type')} em {ticket.get('product')}. "
            f"Fila sugerida: {prediction.get('queue')}."
        ),
        "prioridade": priority,
        "racional": [
            f"Confianca do modelo: {round(float(prediction.get('confidence', 0)) * 100)}%.",
            "Analise gerada por regras locais porque a chamada OpenAI nao foi usada.",
            reason,
        ],
        "acoes_recomendadas": actions[:5],
        "resposta_cliente": (
            f"Recebemos sua solicitacao sobre {ticket.get('request_type', 'atendimento')}. "
            "Ela foi direcionada para analise e voce deve acompanhar a atualizacao pelo canal oficial."
        ),
        "pontos_de_controle": controls[:4]
        or ["Validar dados do cliente antes de qualquer decisao operacional."],
        "source": "fallback",
        "model": None,
    }


def _triage_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT),
        ]
    )


def _api_key() -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key in PLACEHOLDER_KEYS:
        return None
    return api_key


def _priority(ticket: dict[str, Any], prediction: dict[str, Any]) -> str:
    score = 0
    text = f"{ticket.get('description', '')} {ticket.get('request_type', '')}".lower()
    if "fraude" in text or "nao reconhe" in text or prediction.get("queue") == "Contestacao e Fraude":
        score += 3
    if ticket.get("reopened"):
        score += 2
    if float(ticket.get("value", 0) or 0) >= 3000:
        score += 1
    if ticket.get("sentiment") == "Negativo":
        score += 1
    if score >= 5:
        return "Alta"
    if score >= 2:
        return "Media"
    return "Baixa"


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _memo_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return dict(result)
