# Documentação técnica

## Arquitetura

O projeto roda como uma aplicação web local.

```text
Browser
  |
  | HTTP
  v
Servidor Python com http.server
  |
  |-- SQLite: tickets e análises
  |-- scikit-learn: modelo de classificação
  |-- TF-IDF: transformação do texto
  |-- Runbooks JSON: base de conhecimento operacional
  |-- LangChain: retriever RAG e chamada ao modelo
  |-- OpenAI via LangChain: análise generativa estruturada
```

## Fluxo de um chamado

1. Usuário preenche um chamado na tela.
2. Backend monta um objeto com canal, produto, tipo, descrição, valor e sentimento.
3. O modelo classifica a fila mais provável.
4. O sistema recupera runbooks semelhantes usando `TFIDFRetriever` do LangChain.
5. O `ChatOpenAI` recebe o chamado, a predição e os runbooks recuperados.
6. A resposta volta em JSON estruturado.
7. O resultado aparece na tela e é salvo no SQLite.

## Modelo de classificação

O modelo usa a descrição do chamado e alguns metadados operacionais. O campo "tipo" fica visível para a operação, mas não entra como principal atalho de classificação no baseline, para a métrica não ficar artificialmente fácil.

O modelo usa:

- `TfidfVectorizer` para transformar texto em números;
- `LogisticRegression` para classificar a fila operacional;
- `train_test_split` com estratificação para separar treino e teste;
- `accuracy` e `f1_macro` para avaliar.

Por que esse modelo?

Para uma primeira versão, ele é uma boa escolha porque é simples, rápido, explicável e serve como baseline. Antes de usar embeddings ou modelos mais caros, faz sentido ter uma base comparável.

## RAG com LangChain

O projeto usa RAG para evitar que o modelo generativo responda apenas de forma genérica. Antes da geração, os runbooks operacionais em `knowledge/runbooks.json` são transformados em `Document` do LangChain.

O módulo `src/finops_triage/retrieval.py` usa `TFIDFRetriever.from_documents(...)` para criar o retriever. Na análise de um chamado, o texto do ticket é comparado com os runbooks e os documentos mais relevantes são enviados para a etapa generativa.

Essa escolha mantém o projeto simples e explicável: o retriever ainda usa TF-IDF por baixo, mas a orquestração fica no padrão LangChain. Em uma evolução futura, esse retriever poderia ser trocado por embeddings e banco vetorial sem mudar a ideia central do fluxo.

## OpenAI via LangChain

O módulo `src/finops_triage/openai_client.py` usa `ChatOpenAI` do LangChain para chamar o modelo configurado em `OPENAI_MODEL`.

A resposta é validada por um modelo Pydantic com `with_structured_output`, garantindo campos previsíveis para a interface:

- `resumo`;
- `prioridade`;
- `racional`;
- `acoes_recomendadas`;
- `resposta_cliente`;
- `pontos_de_controle`.

A chave pode vir de um arquivo `.env` local na raiz do projeto:

```text
OPENAI_API_KEY=sua-chave-real
OPENAI_MODEL=gpt-4.1-mini
```

Também pode vir do ambiente da sessão atual do PowerShell:

```powershell
$env:OPENAI_API_KEY="sua-chave"
$env:OPENAI_MODEL="gpt-4.1-mini"
python app.py
```

O código não grava a chave automaticamente. Se usar `.env`, o arquivo fica local e deve continuar fora do Git.

Se a chave não existir ou a chamada falhar, o sistema usa uma resposta local por regras. Isso deixa o app demonstrável mesmo offline.

## Diferenciais técnicos

- Tem backend e frontend separados.
- Tem banco local persistente.
- Tem endpoints de API.
- Treina e salva modelo.
- Aceita entrada nova do usuário.
- Salva análises novas.
- Usa RAG com LangChain.
- Usa OpenAI via LangChain quando configurada.
- Tem fallback local.
- Mostra métricas e explicabilidade.

## Limites

- A base inicial é sintética.
- Não existe autenticação.
- Não há controle de permissão por perfil.
- Não há monitoramento de drift.
- Não há avaliação humana persistida com nota de qualidade.

## Evoluções futuras

- Conectar a um CRM real ou sistema de chamados.
- Criar avaliação humana para comparar sugestão versus decisão final.
- Adicionar anonimização de dados antes do treino.
- Medir impacto por squad, canal, produto e tipo de chamado.
- Criar validação temporal para simular comportamento em produção.
- Monitorar queda de performance do modelo ao longo do tempo.
