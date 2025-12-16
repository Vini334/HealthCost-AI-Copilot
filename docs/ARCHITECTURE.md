# Arquitetura Técnica

Este documento descreve a arquitetura do HealthCost AI Copilot, incluindo componentes, fluxos de dados e decisões técnicas.

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTE (Frontend)                              │
│                         Interface de Chat / API REST                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY (FastAPI)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   /chat     │  │  /upload    │  │  /clients   │  │  /conversations     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE ORQUESTRAÇÃO                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      ORCHESTRATOR AGENT                              │    │
│  │         Coordena o fluxo entre agentes especializados               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│           │                │                │                │              │
│           ▼                ▼                ▼                ▼              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Retrieval  │  │  Contract   │  │    Cost     │  │ Negotiation │        │
│  │   Agent     │  │  Analyst    │  │  Insights   │  │   Advisor   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           ▼                           ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   AZURE AI SEARCH   │   │   AZURE OPENAI      │   │   AZURE COSMOS DB   │
│   (Busca Vetorial)  │   │   (LLM/Embeddings)  │   │   (Histórico/Logs)  │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
           │
           ▼
┌─────────────────────┐
│ AZURE BLOB STORAGE  │
│ (Documentos/Dados)  │
└─────────────────────┘
```

## Componentes Principais

### 1. API Gateway (FastAPI)

Responsável por expor os endpoints REST e gerenciar autenticação/autorização.

**Endpoints principais:**

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Health check da aplicação |
| `/api/v1/chat` | POST | Enviar mensagem para o copiloto |
| `/api/v1/upload/contract` | POST | Upload de contrato (PDF) |
| `/api/v1/upload/costs` | POST | Upload de dados de custos (CSV/Excel) |
| `/api/v1/clients` | GET/POST | Gerenciar clientes |
| `/api/v1/clients/{id}/contracts` | GET | Listar contratos de um cliente |
| `/api/v1/conversations` | GET | Histórico de conversas |

### 2. Sistema de Ingestão

Pipeline para processamento de documentos e dados.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Upload     │───▶│  Validação   │───▶│ Processamento│───▶│  Indexação   │
│   (API)      │    │  (Formato)   │    │  (Extração)  │    │  (Vetorial)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

**Para Contratos (PDF):**
1. Upload via API
2. Validação de formato e tamanho
3. Armazenamento no Blob Storage
4. Extração de texto (PyPDF2/pdfplumber)
5. Chunking inteligente por seções/cláusulas
6. Geração de embeddings (Azure OpenAI)
7. Indexação no Azure AI Search com metadados

**Para Dados de Custos (CSV/Excel):**
1. Upload via API
2. Validação de estrutura/colunas
3. Armazenamento no Blob Storage
4. Parsing e normalização
5. Armazenamento estruturado para consultas

### 3. Azure AI Search

Banco vetorial com capacidades de busca híbrida.

**Estrutura do Índice:**

```json
{
  "name": "contracts-index",
  "fields": [
    { "name": "id", "type": "Edm.String", "key": true },
    { "name": "client_id", "type": "Edm.String", "filterable": true },
    { "name": "contract_id", "type": "Edm.String", "filterable": true },
    { "name": "content", "type": "Edm.String", "searchable": true },
    { "name": "content_vector", "type": "Collection(Edm.Single)", "dimensions": 1536 },
    { "name": "section", "type": "Edm.String", "filterable": true, "facetable": true },
    { "name": "page_number", "type": "Edm.Int32", "filterable": true },
    { "name": "chunk_index", "type": "Edm.Int32" },
    { "name": "metadata", "type": "Edm.String" }
  ],
  "vectorSearch": {
    "algorithms": [{ "name": "hnsw", "kind": "hnsw" }],
    "profiles": [{ "name": "vector-profile", "algorithm": "hnsw" }]
  }
}
```

**Tipos de Busca:**
- **Vetorial:** Busca semântica por similaridade de embeddings
- **Keyword:** Busca tradicional por palavras-chave
- **Híbrida:** Combinação de vetorial + keyword com re-ranking

### 4. Sistema Multi-Agentes

Arquitetura de agentes especializados coordenados por um orquestrador.

```
                    ┌─────────────────────┐
                    │  ORCHESTRATOR AGENT │
                    │  - Analisa intent   │
                    │  - Roteia tarefas   │
                    │  - Consolida resp.  │
                    └─────────────────────┘
                              │
        ┌─────────────┬───────┴───────┬─────────────┐
        ▼             ▼               ▼             ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   RETRIEVAL   │ │   CONTRACT    │ │     COST      │ │  NEGOTIATION  │
│     AGENT     │ │    ANALYST    │ │   INSIGHTS    │ │    ADVISOR    │
├───────────────┤ ├───────────────┤ ├───────────────┤ ├───────────────┤
│ - Busca docs  │ │ - Interpreta  │ │ - Analisa     │ │ - Gera reco-  │
│ - Filtra      │ │   cláusulas   │ │   custos      │ │   mendações   │
│   contexto    │ │ - Explica     │ │ - Identifica  │ │ - Prioriza    │
│ - Rankeia     │ │   regras      │ │   tendências  │ │   pontos      │
│   resultados  │ │ - Resume      │ │ - Compara     │ │ - Estima      │
│               │ │               │ │   períodos    │ │   impacto     │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

Ver [AGENTS.md](AGENTS.md) para detalhes de cada agente.

### 5. Azure Cosmos DB

Armazena dados que requerem persistência e consultas estruturadas.

**Collections:**

| Collection | Propósito |
|------------|-----------|
| `conversations` | Histórico de conversas por cliente/contrato |
| `messages` | Mensagens individuais com metadados |
| `audit_logs` | Logs de execução para rastreabilidade |
| `clients` | Cadastro de clientes |
| `contracts_metadata` | Metadados dos contratos indexados |

### 6. Azure Blob Storage

Armazenamento de arquivos originais.

**Estrutura de Containers:**

```
healthcost-storage/
├── contracts/
│   └── {client_id}/
│       └── {contract_id}/
│           └── contract.pdf
├── costs/
│   └── {client_id}/
│       └── {year}/
│           └── costs_data.csv
└── processed/
    └── {client_id}/
        └── {contract_id}/
            └── chunks.json
```

## Fluxo de Dados

### Fluxo de Upload de Contrato

```
1. Usuário faz upload do PDF
         │
         ▼
2. API valida formato e tamanho
         │
         ▼
3. Arquivo salvo no Blob Storage
         │
         ▼
4. Job de processamento iniciado
         │
         ▼
5. Extração de texto do PDF
         │
         ▼
6. Chunking por seções/cláusulas
         │
         ▼
7. Para cada chunk:
   - Gerar embedding (Azure OpenAI)
   - Extrair metadados (página, seção)
         │
         ▼
8. Indexar no Azure AI Search
         │
         ▼
9. Atualizar status no Cosmos DB
         │
         ▼
10. Notificar conclusão ao usuário
```

### Fluxo de Conversa (Chat)

```
1. Usuário envia mensagem
   (com client_id e contract_id)
         │
         ▼
2. Orchestrator Agent recebe
         │
         ▼
3. Análise de intent da pergunta
         │
         ▼
4. Seleção de agentes necessários
         │
         ▼
5. Execução paralela/sequencial:
   ├── Retrieval Agent busca contexto
   ├── Contract Analyst interpreta
   ├── Cost Insights analisa dados
   └── Negotiation Advisor recomenda
         │
         ▼
6. Consolidação das respostas
         │
         ▼
7. Geração da resposta final (LLM)
         │
         ▼
8. Persistência no histórico
         │
         ▼
9. Retorno ao usuário
```

## Decisões Técnicas

### Por que Azure AI Search?

- **Busca híbrida nativa:** Combina vetorial + keyword sem configuração extra
- **Integração Azure:** Funciona bem com Azure OpenAI e outros serviços
- **Escalabilidade:** Gerenciado, sem preocupação com infraestrutura
- **Filtros avançados:** Suporta filtros por metadados essenciais para multi-tenancy

### Por que LangChain/LlamaIndex?

- **Abstração de LLMs:** Facilita trocar provedores se necessário
- **Agents framework:** Suporte nativo para multi-agentes
- **Tools:** Sistema de ferramentas bem documentado
- **RAG patterns:** Implementações prontas de padrões comuns

### Por que FastAPI?

- **Async nativo:** Ideal para I/O intensivo (chamadas a APIs Azure)
- **Documentação automática:** OpenAPI/Swagger gerados automaticamente
- **Type hints:** Validação e documentação via Pydantic
- **Performance:** Um dos frameworks Python mais rápidos

### Por que Cosmos DB?

- **Flexibilidade:** Schema-less para evolução do modelo de dados
- **Particionamento:** Ideal para dados por cliente (multi-tenancy)
- **Integração:** Nativo do ecossistema Azure

## Considerações de Segurança

### Multi-tenancy
- Dados sempre filtrados por `client_id`
- Isolation a nível de query no AI Search
- Partition key no Cosmos DB por cliente

### Autenticação
- API protegida por API Key (MVP)
- Evolução para Azure AD B2C (futuro)

### Dados Sensíveis
- Contratos e dados de custos são confidenciais
- Armazenamento encriptado no Blob Storage
- Conexões via HTTPS/TLS

## Estrutura de Código

```
src/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── routes/
│   │   ├── chat.py          # Endpoints de chat
│   │   ├── upload.py        # Endpoints de upload
│   │   └── clients.py       # Endpoints de clientes
│   └── middleware/
│       └── auth.py          # Autenticação
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py      # Agente orquestrador
│   ├── retrieval.py         # Agente de busca
│   ├── contract_analyst.py  # Agente de contratos
│   ├── cost_insights.py     # Agente de custos
│   └── negotiation.py       # Agente de negociação
├── ingestion/
│   ├── __init__.py
│   ├── pdf_processor.py     # Processamento de PDFs
│   ├── chunker.py           # Chunking de documentos
│   └── data_processor.py    # Processamento de CSV/Excel
├── search/
│   ├── __init__.py
│   ├── indexer.py           # Indexação no AI Search
│   └── retriever.py         # Busca semântica
├── storage/
│   ├── __init__.py
│   ├── blob.py              # Azure Blob Storage
│   └── cosmos.py            # Azure Cosmos DB
├── models/
│   ├── __init__.py
│   ├── schemas.py           # Pydantic schemas
│   └── entities.py          # Entidades de domínio
├── config/
│   ├── __init__.py
│   └── settings.py          # Configurações
└── utils/
    ├── __init__.py
    └── logging.py           # Logging estruturado
```

## Próximos Passos

Consulte [ROADMAP.md](ROADMAP.md) para o plano de implementação.
