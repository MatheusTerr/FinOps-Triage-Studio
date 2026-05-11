# FinOps Triage Studio

Aplicação web local para simular a triagem de chamados em operações financeiras. O projeto combina backend Python, SQLite, classificação com scikit-learn, recuperação de runbooks com LangChain e análise generativa opcional via OpenAI.

> Os dados do projeto são sintéticos e existem apenas para demonstração técnica.

## Destaques

- Dashboard operacional com volume, SLA, reabertura, autosserviço e distribuição por fila.
- Classificador supervisionado para sugerir a fila responsável por cada chamado.
- Base de conhecimento em JSON com runbooks operacionais simulados.
- RAG com LangChain usando `TFIDFRetriever` para recuperar procedimentos relevantes.
- Integração opcional com OpenAI para gerar resumo, prioridade, próximos passos e resposta sugerida.
- Fallback local por regras quando `OPENAI_API_KEY` não está configurada.
- API HTTP simples servida por Python, sem dependência de framework web externo.

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
OpenAI, quando configurada, gera uma análise estruturada
        |
Resultado é salvo no SQLite e exibido no dashboard
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

Clone o repositório e entre na pasta do projeto:

```powershell
git clone <url-do-repositorio>
cd "FinOps Triage Studio"
```

Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

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

Inicie a aplicação:

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

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/health` | Retorna status da aplicação e da integração OpenAI. |
| `GET` | `/api/metrics` | Retorna indicadores do dashboard. |
| `GET` | `/api/tickets` | Lista chamados salvos no SQLite. |
| `POST` | `/api/analyze` | Analisa um novo chamado e salva o resultado. |
| `POST` | `/api/retrain` | Retreina o classificador com os dados atuais. |

Exemplo de chamada para análise:

```json
{
  "channel": "App",
  "segment": "Varejo",
  "product": "Cartão",
  "request_type": "Transação não reconhecida",
  "description": "Cliente informa que não reconhece uma compra no cartão e pede análise urgente.",
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

O classificador usa `TfidfVectorizer` e `LogisticRegression` para sugerir uma fila operacional. O treino acontece com chamados sintéticos gerados em `sample_data.py`, e as métricas são salvas em `runtime/model_metrics.json`.

A etapa de RAG transforma os runbooks de `knowledge/runbooks.json` em documentos LangChain. O `TFIDFRetriever` compara o texto do chamado com esses documentos e envia os runbooks mais relevantes para a etapa de análise.

Quando `OPENAI_API_KEY` está configurada, `openai_client.py` usa `ChatOpenAI` com saída estruturada por Pydantic. Quando a chave não existe, a aplicação usa uma resposta local baseada nos runbooks recuperados.

## Dados e segurança

- O projeto não usa dados reais de clientes.
- O banco local e os artefatos de runtime ficam em `runtime/`, pasta ignorada pelo Git.
- A chave da OpenAI deve ficar em `.env`, também ignorado pelo Git.
- A resposta do sistema é uma recomendação operacional; decisões sensíveis devem passar por revisão humana.

## Limites

- A base de treino é sintética.
- Não há autenticação ou controle de permissão.
- Não há integração real com CRM, core bancário ou sistema de chamados.
- Não há avaliação humana persistida para medir qualidade das recomendações.
- Não há monitoramento de drift do modelo.

## Possíveis evoluções

- Conectar a um sistema real de chamados usando dados anonimizados.
- Adicionar avaliação humana para comparar sugestão e decisão final.
- Substituir o retriever TF-IDF por embeddings e banco vetorial.
- Criar autenticação e perfis de acesso.
- Monitorar performance do modelo ao longo do tempo.
