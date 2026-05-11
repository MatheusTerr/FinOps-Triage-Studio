# Documentacao tecnica

## Arquitetura

O projeto roda como uma aplicacao web local.

```text
Browser
  |
  | HTTP
  v
Servidor Python com http.server
  |
  |-- SQLite: tickets e analises
  |-- scikit-learn: modelo de classificacao
  |-- TF-IDF: transformacao do texto
  |-- Runbooks JSON: base de conhecimento operacional
  |-- LangChain: retriever RAG e chamada ao modelo
  |-- OpenAI via LangChain: analise generativa estruturada
```

## Fluxo de um chamado

1. Usuario preenche um chamado na tela.
2. Backend monta um objeto com canal, produto, tipo, descricao, valor e sentimento.
3. O modelo classifica a fila mais provavel.
4. O sistema recupera runbooks semelhantes usando `TFIDFRetriever` do LangChain.
5. O `ChatOpenAI` recebe o chamado, a predicao e os runbooks recuperados.
6. A resposta volta em JSON estruturado.
7. O resultado aparece na tela e e salvo no SQLite.

## Modelo de classificacao

O modelo usa a descricao do chamado e alguns metadados operacionais. O campo "tipo" fica visivel para a operacao, mas nao entra como principal atalho de classificacao no baseline, para a metrica nao ficar artificialmente facil.

O modelo usa:

- `TfidfVectorizer` para transformar texto em numeros;
- `LogisticRegression` para classificar a fila operacional;
- `train_test_split` com estratificacao para separar treino e teste;
- `accuracy` e `f1_macro` para avaliar.

Por que esse modelo?

Para uma primeira versao, ele e uma boa escolha porque e simples, rapido, explicavel e serve como baseline. Antes de usar embeddings ou modelos mais caros, faz sentido ter uma base comparavel.

## RAG com LangChain

O projeto usa RAG para evitar que o modelo generativo responda apenas de forma generica. Antes da geracao, os runbooks operacionais em `knowledge/runbooks.json` sao transformados em `Document` do LangChain.

O modulo `src/finops_triage/retrieval.py` usa `TFIDFRetriever.from_documents(...)` para criar o retriever. Na analise de um chamado, o texto do ticket e comparado com os runbooks e os documentos mais relevantes sao enviados para a etapa generativa.

Essa escolha mantem o projeto simples e explicavel: o retriever ainda usa TF-IDF por baixo, mas a orquestracao fica no padrao LangChain. Em uma evolucao futura, esse retriever poderia ser trocado por embeddings e banco vetorial sem mudar a ideia central do fluxo.

## OpenAI via LangChain

O modulo `src/finops_triage/openai_client.py` usa `ChatOpenAI` do LangChain para chamar o modelo configurado em `OPENAI_MODEL`.

A resposta e validada por um modelo Pydantic com `with_structured_output`, garantindo campos previsiveis para a interface:

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

Tambem pode vir do ambiente da sessao atual do PowerShell:

```powershell
$env:OPENAI_API_KEY="sua-chave"
$env:OPENAI_MODEL="gpt-4.1-mini"
python app.py
```

O codigo nao grava a chave automaticamente. Se usar `.env`, o arquivo fica local e deve continuar fora do Git.

Se a chave nao existir ou a chamada falhar, o sistema usa uma resposta local por regras. Isso deixa o app demonstravel mesmo offline.

## Diferenciais tecnicos

- Tem backend e frontend separados.
- Tem banco local persistente.
- Tem endpoints de API.
- Treina e salva modelo.
- Aceita entrada nova do usuario.
- Salva analises novas.
- Usa RAG com LangChain.
- Usa OpenAI via LangChain quando configurada.
- Tem fallback local.
- Mostra metricas e explicabilidade.

## Limites

- A base inicial e sintetica.
- Nao existe autenticacao.
- Nao ha controle de permissao por perfil.
- Nao ha monitoramento de drift.
- Nao ha avaliacao humana persistida com nota de qualidade.

## Evolucoes futuras

- Conectar a um CRM real ou sistema de chamados.
- Criar avaliacao humana para comparar sugestao versus decisao final.
- Adicionar anonimização de dados antes do treino.
- Medir impacto por squad, canal, produto e tipo de chamado.
- Criar validacao temporal para simular comportamento em producao.
- Monitorar queda de performance do modelo ao longo do tempo.
