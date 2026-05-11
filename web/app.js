const state = {
  metrics: null,
  loading: false,
};

const presets = {
  fraude: {
    channel: "Central",
    segment: "Prime",
    product: "Pix",
    request_type: "Transacao nao reconhecida",
    value: "2450",
    sentiment: "Negativo",
    reopened: true,
    auto_service_candidate: false,
    description:
      "Cliente informa que nao reconhece um Pix realizado de madrugada. Diz que ja tentou bloquear pelo app, esta muito preocupado e pede retorno urgente.",
  },
  digital: {
    channel: "App",
    segment: "Varejo",
    product: "Internet Banking",
    request_type: "Acesso ao canal digital",
    value: "0",
    sentiment: "Neutro",
    reopened: false,
    auto_service_candidate: true,
    description:
      "Cliente nao consegue acessar o internet banking apos troca de aparelho. Informa erro no token e precisa desbloquear o acesso.",
  },
  credito: {
    channel: "WhatsApp",
    segment: "Empresas",
    product: "Financiamento",
    request_type: "Renegociacao",
    value: "8700",
    sentiment: "Neutro",
    reopened: false,
    auto_service_candidate: false,
    description:
      "Cliente solicita renegociacao de financiamento e pergunta quais alternativas existem para regularizar o contrato sem prometer condicao especifica.",
  },
};

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("refresh-button").addEventListener("click", loadDashboard);
  document.getElementById("triage-form").addEventListener("submit", analyzeTicket);
  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.addEventListener("click", () => applyPreset(button.dataset.preset));
  });
  loadDashboard();
});

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function loadDashboard() {
  state.metrics = await api("/api/metrics");
  renderOpenAI(state.metrics.openai);
  renderKpis(state.metrics.kpis);
  renderBars("queue-bars", state.metrics.queue_counts, "count");
  renderBars("channel-bars", state.metrics.channel_breach, "percent");
  drawLineChart(document.getElementById("volume-chart"), state.metrics.daily_volume);
  renderRecent(state.metrics.recent);
  renderModel(state.metrics.model);
}

function renderOpenAI(openai) {
  const node = document.getElementById("openai-status");
  node.textContent = openai.configured
    ? `conectado (${openai.model})`
    : `modo local - ${openai.reason || "chave ausente"}`;
}

function renderKpis(kpis) {
  const items = [
    ["Chamados", kpis.total ?? "-"],
    ["Prazo violado", `${kpis.breach_rate ?? "-"}%`],
    ["Tempo medio", `${kpis.avg_resolution ?? "-"}h`],
    ["Reabertura", `${kpis.reopen_rate ?? "-"}%`],
    ["Autosservico", `${kpis.auto_service_rate ?? "-"}%`],
  ];
  document.getElementById("kpis").innerHTML = items
    .map(([label, value]) => `<article class="kpi"><span>${label}</span><strong>${value}</strong></article>`)
    .join("");
}

function renderBars(id, rows, type) {
  const node = document.getElementById(id);
  const max = Math.max(...rows.map((item) => item.value), 1);
  node.innerHTML = rows
    .map((item) => {
      const width = Math.max((item.value / max) * 100, 4);
      const value = type === "percent" ? `${item.value}%` : item.value;
      return `
        <div class="bar-item">
          <span>${item.label}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <strong>${value}</strong>
        </div>
      `;
    })
    .join("");
}

function drawLineChart(canvas, rows) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  if (!rows.length) return;

  const padding = 36;
  const values = rows.map((item) => item.value);
  const max = Math.max(...values, 1);
  const stepX = (width - padding * 2) / Math.max(rows.length - 1, 1);
  const points = rows.map((item, index) => {
    const x = padding + index * stepX;
    const y = height - padding - (item.value / max) * (height - padding * 2);
    return { x, y, label: item.label, value: item.value };
  });

  ctx.strokeStyle = "#d9e0e7";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = padding + i * ((height - padding * 2) / 3);
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  ctx.strokeStyle = "#0f766e";
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) ctx.moveTo(point.x, point.y);
    else ctx.lineTo(point.x, point.y);
  });
  ctx.stroke();

  ctx.fillStyle = "#0f766e";
  points.forEach((point) => {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.fillStyle = "#667085";
  ctx.font = "12px Arial";
  ctx.fillText(rows[0].label, padding, height - 10);
  ctx.fillText(rows[rows.length - 1].label, width - padding - 38, height - 10);
  ctx.fillText(String(max), 8, padding + 4);
}

function renderRecent(rows) {
  const body = document.getElementById("recent-table");
  body.innerHTML = rows
    .map((row) => {
      const queue = row.predicted_queue || row.target_queue || "-";
      const confidence = row.confidence ? `${Math.round(row.confidence * 100)}%` : "-";
      return `
        <tr>
          <td>${row.ticket_id}</td>
          <td>${row.request_type}</td>
          <td>${row.product}</td>
          <td>${queue}</td>
          <td>${row.priority_label}</td>
          <td>${confidence}</td>
        </tr>
      `;
    })
    .join("");
}

function renderModel(model) {
  document.getElementById("accuracy").textContent = model.accuracy ? model.accuracy.toFixed(2) : "-";
  document.getElementById("f1").textContent = model.f1_macro ? model.f1_macro.toFixed(2) : "-";
  const terms = model.top_terms || {};
  document.getElementById("top-terms").innerHTML = Object.entries(terms)
    .map(([queue, words]) => {
      const chips = words.map((word) => `<span>${word}</span>`).join("");
      return `<div class="term-group"><strong>${queue}</strong>${chips}</div>`;
    })
    .join("");
}

function applyPreset(name) {
  const preset = presets[name];
  const form = document.getElementById("triage-form");
  Object.entries(preset).forEach(([key, value]) => {
    const field = form.elements[key];
    if (!field) return;
    if (field.type === "checkbox") field.checked = Boolean(value);
    else field.value = value;
  });
}

async function analyzeTicket(event) {
  event.preventDefault();
  const button = document.getElementById("analyze-button");
  button.disabled = true;
  button.textContent = "Analisando...";
  try {
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    payload.value = Number(payload.value || 0);
    payload.reopened = form.elements.reopened.checked;
    payload.auto_service_candidate = form.elements.auto_service_candidate.checked;
    payload.save = true;

    const result = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderAnalysis(result);
    await loadDashboard();
  } catch (error) {
    alert(`Falha ao analisar: ${error.message}`);
  } finally {
    button.disabled = false;
    button.textContent = "Analisar chamado";
  }
}

function renderAnalysis(result) {
  document.getElementById("empty-result").classList.add("hidden");
  document.getElementById("analysis-result").classList.remove("hidden");

  const ticket = result.ticket;
  const prediction = result.prediction;
  const memo = result.memo;
  const confidence = Math.round((prediction.confidence || 0) * 100);

  document.getElementById("result-ticket").textContent = `${ticket.ticket_id} · ${memo.source}`;
  document.getElementById("result-queue").textContent = prediction.queue;
  const priority = document.getElementById("result-priority");
  priority.textContent = memo.prioridade;
  priority.className = `priority-pill ${memo.prioridade.toLowerCase()}`;
  document.getElementById("confidence-fill").style.width = `${confidence}%`;
  document.getElementById("confidence-text").textContent = `${confidence}%`;
  document.getElementById("memo-summary").textContent = memo.resumo;
  document.getElementById("customer-response").textContent = memo.resposta_cliente;
  renderList("memo-reasons", memo.racional);
  renderList("memo-actions", memo.acoes_recomendadas);
  document.getElementById("runbook-list").innerHTML = result.runbooks
    .map((item) => `<span class="chip">${item.id} · ${item.score}</span>`)
    .join("");
}

function renderList(id, items) {
  document.getElementById(id).innerHTML = (items || [])
    .map((item) => `<li>${item}</li>`)
    .join("");
}
