# FinOps Triage Studio

Aplicacao web local para simular a triagem de chamados em operacoes financeiras. O projeto combina backend Python, SQLite, classificacao com scikit-learn, recuperacao de runbooks com LangChain e analise generativa opcional via OpenAI.

> Os dados do projeto sao sinteticos e existem apenas para demonstracao tecnica.

## Destaques

- Dashboard operacional com volume, SLA, reabertura, autosservico e distribuicao por fila.
- Classificador supervisionado para sugerir a fila responsavel por cada chamado.
- Base de conhecimento em JSON com runbooks operacionais simulados.
- RAG com LangChain usando `TFIDFRetriever` para recuperar procedimentos relevantes.
- Integracao opcional com OpenAI para gerar resumo, prioridade, proximos passos e resposta sugerida.
- Fallback local por regras quando `OPENAI_API_KEY` nao esta configurada.
- API HTTP simples servida por Python, sem dependencia de framework web externo.

## Fluxo

```text
Chamado do cliente
        |
Backend normaliza os campos recebidos
        |
Modelo scikit-learn sugere a fila operacional
        |
LangChain recupera runbooks relacionados ao caso
        |
OpenAI, quando configurada, gera uma analise estruturada
        |
Resultado e salvo no SQLite e exibido no dashboard
```

## Stack

- Python
- SQLite
- Pandas e NumPy
- scikit-learn
- LangChain
- OpenAI API opcional
- HTML, CSS e JavaScript

## Como rodar localmente

Clone o repositorio e entre na pasta do projeto:

```powershell
git clone <url-do-repositorio>
cd "FinOps Triage Studio"
```

Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependencias:

```powershell
python -m pip install -r requirements.txt
```

Opcionalmente, configure a chave da OpenAI:

```powershell
Copy-Item .env.example .env
notepad .env
```

Exemplo de `.env`:

```text
OPENAI_API_KEY=sua-chave-real
OPENAI_MODEL=gpt-4.1-mini
```

O arquivo `.env` fica fora do Git. Sem a chave, o app continua funcionando em modo local.

Inicie a aplicacao:

```powershell
python app.py
```

Acesse:

```text
http://127.0.0.1:8000
```

Para recriar banco e modelo:

```powershell
python app.py --reset
```

## API

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/api/health` | Retorna status da aplicacao e da integracao OpenAI. |
| `GET` | `/api/metrics` | Retorna indicadores do dashboard. |
| `GET` | `/api/tickets` | Lista chamados salvos no SQLite. |
| `POST` | `/api/analyze` | Analisa um novo chamado e salva o resultado. |
| `POST` | `/api/retrain` | Retreina o classificador com os dados atuais. |

Exemplo de chamada para analise:

```json
{
  "channel": "App",
  "segment": "Varejo",
  "product": "Cartao",
  "request_type": "Transacao nao reconhecida",
  "description": "Cliente informa que nao reconhece uma compra no cartao e pede analise urgente.",
  "value": 780,
  "sentiment": "Negativo",
  "reopened": false,
  "auto_service_candidate": false
}
```

## Arquitetura

```text
.
|-- app.py
|-- knowledge/
|   `-- runbooks.json
|-- src/
|   `-- finops_triage/
|       |-- analytics.py
|       |-- model.py
|       |-- openai_client.py
|       |-- retrieval.py
|       |-- sample_data.py
|       |-- server.py
|       `-- storage.py
|-- web/
|   |-- app.js
|   |-- index.html
|   `-- styles.css
|-- docs/
|   `-- explicacao_tecnica.md
|-- .env.example
|-- .gitignore
`-- requirements.txt
```

## Modelo e RAG

O classificador usa `TfidfVectorizer` e `LogisticRegression` para sugerir uma fila operacional. O treino acontece com chamados sinteticos gerados em `sample_data.py`, e as metricas sao salvas em `runtime/model_metrics.json`.

A etapa de RAG transforma os runbooks de `knowledge/runbooks.json` em documentos LangChain. O `TFIDFRetriever` compara o texto do chamado com esses documentos e envia os runbooks mais relevantes para a etapa de analise.

Quando `OPENAI_API_KEY` esta configurada, `openai_client.py` usa `ChatOpenAI` com saida estruturada por Pydantic. Quando a chave nao existe, a aplicacao usa uma resposta local baseada nos runbooks recuperados.

## Dados e seguranca

- O projeto nao usa dados reais de clientes.
- O banco local e os artefatos de runtime ficam em `runtime/`, pasta ignorada pelo Git.
- A chave da OpenAI deve ficar em `.env`, tambem ignorado pelo Git.
- A resposta do sistema e uma recomendacao operacional; decisoes sensiveis devem passar por revisao humana.

## Limites

- A base de treino e sintetica.
- Nao ha autenticacao ou controle de permissao.
- Nao ha integracao real com CRM, core bancario ou sistema de chamados.
- Nao ha avaliacao humana persistida para medir qualidade das recomendacoes.
- Nao ha monitoramento de drift do modelo.

## Possiveis evolucoes

- Conectar a um sistema real de chamados usando dados anonimizados.
- Adicionar avaliacao humana para comparar sugestao e decisao final.
- Substituir o retriever TF-IDF por embeddings e banco vetorial.
- Criar autenticacao e perfis de acesso.
- Monitorar performance do modelo ao longo do tempo.
