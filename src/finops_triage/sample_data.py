from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Scenario:
    request_type: str
    queue: str
    products: tuple[str, ...]
    sla_hours: int
    risk_base: int
    auto_service: bool
    templates: tuple[str, ...]


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        request_type="Transacao nao reconhecida",
        queue="Contestacao e Fraude",
        products=("Cartao", "Pix", "Conta Corrente"),
        sla_hours=8,
        risk_base=5,
        auto_service=False,
        templates=(
            "Cliente informa que nao reconhece uma movimentacao de R$ {value} no {product}.",
            "Relato de possivel fraude envolvendo {product}, com valor aproximado de R$ {value}.",
            "Cliente pede bloqueio e analise porque identificou transacao suspeita no {product}.",
        ),
    ),
    Scenario(
        request_type="Contestacao de compra",
        queue="Contestacao e Fraude",
        products=("Cartao",),
        sla_hours=16,
        risk_base=4,
        auto_service=False,
        templates=(
            "Cliente quer contestar uma compra no cartao no valor de R$ {value}.",
            "Relato de desacordo comercial em compra feita no cartao.",
        ),
    ),
    Scenario(
        request_type="Segunda via ou comprovante",
        queue="Segunda Via e Comprovantes",
        products=("Cartao", "Conta Corrente", "Financiamento"),
        sla_hours=24,
        risk_base=1,
        auto_service=True,
        templates=(
            "Cliente precisa de segunda via relacionada ao produto {product}.",
            "Pedido de comprovante para consulta e acompanhamento do produto {product}.",
        ),
    ),
    Scenario(
        request_type="Atualizacao cadastral",
        queue="Cadastro e Documentos",
        products=("Conta Corrente", "Cartao", "Investimentos"),
        sla_hours=24,
        risk_base=2,
        auto_service=True,
        templates=(
            "Cliente precisa atualizar dados cadastrais para continuar usando {product}.",
            "Solicitacao de ajuste cadastral com documento pendente no produto {product}.",
        ),
    ),
    Scenario(
        request_type="Acesso ao canal digital",
        queue="Canais Digitais",
        products=("App", "Internet Banking", "Token"),
        sla_hours=12,
        risk_base=2,
        auto_service=True,
        templates=(
            "Cliente nao consegue acessar o {product} e informa erro na autenticacao.",
            "Pedido de desbloqueio para voltar a usar o canal digital {product}.",
        ),
    ),
    Scenario(
        request_type="Renegociacao",
        queue="Credito e Renegociacao",
        products=("Credito Pessoal", "Financiamento", "Cartao"),
        sla_hours=36,
        risk_base=3,
        auto_service=False,
        templates=(
            "Cliente busca renegociacao de contrato relacionado a {product}.",
            "Solicitacao de acordo financeiro para regularizar o produto {product}.",
        ),
    ),
    Scenario(
        request_type="Revisao de limite",
        queue="Credito e Renegociacao",
        products=("Cartao", "Credito Pessoal"),
        sla_hours=48,
        risk_base=2,
        auto_service=False,
        templates=(
            "Cliente solicita revisao de limite para o produto {product}.",
            "Pedido de aumento de limite com justificativa de uso recorrente em {product}.",
        ),
    ),
    Scenario(
        request_type="Cancelamento",
        queue="Retencao e Cancelamento",
        products=("Cartao", "Seguro", "Conta Corrente"),
        sla_hours=24,
        risk_base=3,
        auto_service=False,
        templates=(
            "Cliente solicita cancelamento do produto {product}.",
            "Pedido de encerramento do produto {product} por nao reconhecer beneficio atual.",
        ),
    ),
    Scenario(
        request_type="Portabilidade ou ajuste operacional",
        queue="Operacoes de Conta",
        products=("Conta Corrente", "Salario", "Financiamento"),
        sla_hours=36,
        risk_base=2,
        auto_service=False,
        templates=(
            "Cliente solicita ajuste operacional de portabilidade no produto {product}.",
            "Demanda de alteracao operacional vinculada a {product}.",
        ),
    ),
)

CHANNELS = ("App", "Internet Banking", "WhatsApp", "Central", "Agencia")
SEGMENTS = ("Varejo", "Prime", "Alta Renda", "Empresas")


def generate_tickets(n_rows: int = 600, seed: int = 7) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    scenario_weights = np.array([0.10, 0.08, 0.17, 0.12, 0.17, 0.10, 0.08, 0.10, 0.08])
    scenario_weights = scenario_weights / scenario_weights.sum()
    channel_weights = np.array([0.33, 0.15, 0.23, 0.21, 0.08])
    segment_weights = np.array([0.58, 0.22, 0.12, 0.08])
    start = datetime(2026, 1, 2, 8, 0)

    rows: list[dict[str, Any]] = []
    for index in range(n_rows):
        scenario = SCENARIOS[int(rng.choice(len(SCENARIOS), p=scenario_weights))]
        product = str(rng.choice(scenario.products))
        channel = str(rng.choice(CHANNELS, p=channel_weights))
        segment = str(rng.choice(SEGMENTS, p=segment_weights))
        value = _money_value(rng, scenario.queue, product)
        reopened = bool(rng.random() < min(0.05 + scenario.risk_base * 0.035, 0.27))
        sentiment_score = float(
            np.clip(
                rng.normal(0.66, 0.18)
                - scenario.risk_base * 0.045
                - (0.16 if reopened else 0)
                - (0.06 if channel == "Central" else 0),
                0.02,
                0.98,
            )
        )
        sentiment = _sentiment(sentiment_score)
        priority, risk_score = _priority(scenario, value, sentiment_score, reopened, segment)
        auto_service = bool(scenario.auto_service and priority != "Alta" and not reopened)
        resolution_hours = _resolution_time(rng, scenario.sla_hours, priority, auto_service, reopened)
        breached = resolution_hours > scenario.sla_hours
        created_at = start + timedelta(
            days=int(rng.integers(0, 115)),
            hours=int(rng.integers(0, 12)),
            minutes=int(rng.integers(0, 60)),
        )

        description = _description(rng, scenario, product, value, channel)
        if reopened:
            description += " A demanda ja foi reaberta anteriormente."
        if sentiment == "Negativo":
            description += " O cliente demonstra insatisfacao com a experiencia."
        if auto_service:
            description += " O caso parece elegivel para uma jornada digital simples."

        rows.append(
            {
                "ticket_id": f"FIN-{index + 1:05d}",
                "created_at": created_at.isoformat(timespec="minutes"),
                "channel": channel,
                "segment": segment,
                "product": product,
                "request_type": scenario.request_type,
                "description": description,
                "value": round(value, 2),
                "sentiment": sentiment,
                "sentiment_score": round(sentiment_score, 3),
                "reopened": reopened,
                "sla_hours": scenario.sla_hours,
                "resolution_hours": round(resolution_hours, 2),
                "sla_breached": breached,
                "auto_service_candidate": auto_service,
                "target_queue": scenario.queue,
                "priority_label": priority,
                "risk_score": risk_score,
                "status": _status(reopened, breached, auto_service),
                "predicted_queue": None,
                "confidence": None,
                "ai_summary": None,
            }
        )

    return sorted(rows, key=lambda row: row["created_at"])


def _money_value(rng: np.random.Generator, queue: str, product: str) -> float:
    if queue == "Contestacao e Fraude":
        value = rng.lognormal(mean=7.0, sigma=0.85)
    elif queue == "Credito e Renegociacao":
        value = rng.lognormal(mean=8.0, sigma=0.78)
    elif product in {"Financiamento", "Seguro"}:
        value = rng.lognormal(mean=7.2, sigma=0.55)
    else:
        value = rng.lognormal(mean=5.2, sigma=0.65)
    return float(np.clip(value, 40, 30000))


def _description(
    rng: np.random.Generator,
    scenario: Scenario,
    product: str,
    value: float,
    channel: str,
) -> str:
    if rng.random() < 0.24:
        template = str(
            rng.choice(
                (
                    "Cliente solicita orientacao para continuidade da demanda no produto {product}.",
                    "Contato recebido pelo canal {channel} com pedido de acompanhamento sobre {product}.",
                    "Cliente relata dificuldade na jornada e pede retorno sobre {product}.",
                )
            )
        )
    else:
        template = str(rng.choice(scenario.templates))
    formatted_value = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return template.format(product=product, value=formatted_value, channel=channel)


def _sentiment(score: float) -> str:
    if score <= 0.35:
        return "Negativo"
    if score <= 0.65:
        return "Neutro"
    return "Positivo"


def _priority(
    scenario: Scenario,
    value: float,
    sentiment_score: float,
    reopened: bool,
    segment: str,
) -> tuple[str, int]:
    score = scenario.risk_base
    if reopened:
        score += 2
    if value >= 3000:
        score += 1
    if sentiment_score <= 0.35:
        score += 1
    if segment in {"Alta Renda", "Empresas"} and scenario.risk_base >= 3:
        score += 1

    if score >= 6:
        return "Alta", score
    if score >= 4:
        return "Media", score
    return "Baixa", score


def _resolution_time(
    rng: np.random.Generator,
    sla_hours: int,
    priority: str,
    auto_service: bool,
    reopened: bool,
) -> float:
    base = rng.gamma(shape=2.0, scale=max(sla_hours / 3.2, 1.0))
    if auto_service:
        base *= 0.48
    if priority == "Alta":
        base *= 0.95
    if priority == "Baixa":
        base *= 0.82
    if reopened:
        base *= 1.7
    return float(np.clip(base, 0.2, 180))


def _status(reopened: bool, breached: bool, auto_service: bool) -> str:
    if reopened:
        return "Reaberto"
    if breached:
        return "Fora do prazo"
    if auto_service:
        return "Resolvido digitalmente"
    return "Resolvido"
