from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


def dashboard_metrics(
    tickets: list[dict[str, Any]],
    model_metrics: dict[str, Any],
    openai_status: dict[str, Any],
) -> dict[str, Any]:
    if not tickets:
        return {
            "kpis": {},
            "queue_counts": [],
            "channel_breach": [],
            "daily_volume": [],
            "recent": [],
            "model": model_metrics,
            "openai": openai_status,
        }

    total = len(tickets)
    breached = sum(1 for item in tickets if item.get("sla_breached"))
    reopened = sum(1 for item in tickets if item.get("reopened"))
    auto_service = sum(1 for item in tickets if item.get("auto_service_candidate"))
    resolution_values = [float(item.get("resolution_hours") or 0) for item in tickets]
    avg_resolution = sum(resolution_values) / max(len(resolution_values), 1)

    queue_counter = Counter(item.get("target_queue") or item.get("predicted_queue") for item in tickets)
    channel_total: dict[str, int] = defaultdict(int)
    channel_breached: dict[str, int] = defaultdict(int)
    daily_counter: Counter[str] = Counter()

    for item in tickets:
        channel = str(item.get("channel"))
        channel_total[channel] += 1
        if item.get("sla_breached"):
            channel_breached[channel] += 1
        day = datetime.fromisoformat(str(item["created_at"])).strftime("%d/%m")
        daily_counter[day] += 1

    return {
        "kpis": {
            "total": total,
            "breach_rate": round(breached / total * 100, 1),
            "avg_resolution": round(avg_resolution, 1),
            "reopen_rate": round(reopened / total * 100, 1),
            "auto_service_rate": round(auto_service / total * 100, 1),
        },
        "queue_counts": [
            {"label": str(label), "value": int(value)}
            for label, value in queue_counter.most_common()
            if label
        ],
        "channel_breach": [
            {
                "label": channel,
                "value": round(channel_breached[channel] / channel_total[channel] * 100, 1),
            }
            for channel in sorted(channel_total)
        ],
        "daily_volume": [
            {"label": day, "value": count}
            for day, count in list(sorted(daily_counter.items()))[-30:]
        ],
        "recent": tickets[:8],
        "model": model_metrics,
        "openai": openai_status,
    }

