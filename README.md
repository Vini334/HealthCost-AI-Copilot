# HealthCost AI Copilot

Assistente conversacional inteligente para auditoria e otimização de custos de planos de saúde, utilizando RAG avançado e arquitetura multi-agentes.

## Sobre o Projeto

O HealthCost AI Copilot é uma ferramenta de GenAI que permite a auditores e consultores de benefícios:

- **Analisar contratos** de planos de saúde de forma inteligente
- **Processar dados de sinistralidade** (custos, procedimentos, tendências)
- **Obter insights acionáveis** para renegociação com operadoras
- **Conversar em linguagem natural** sobre documentos e dados específicos de cada cliente

O sistema atua como um **copiloto técnico-consultivo**, não substituindo o profissional, mas acelerando análises e aumentando a consistência das entregas.

## Stack Tecnológico

| Componente | Tecnologia |
|------------|------------|
| **Backend** | Python + FastAPI |
| **Orquestração IA** | LangChain / LlamaIndex |
| **LLM & Embeddings** | Azure OpenAI |
| **Busca Vetorial** | Azure AI Search |
| **Armazenamento** | Azure Blob Storage |
| **Banco de Dados** | Azure Cosmos DB |
| **Hospedagem** | Azure Container Apps |
| **Containerização** | Docker |
| **CI/CD** | GitHub Actions |

## Funcionalidades Principais

1. **Ingestão de Documentos** - Upload e processamento de contratos (PDF) e dados de custos (CSV/Excel)
2. **Busca Semântica** - Recuperação inteligente de informações nos contratos
3. **Análise de Dados** - Agregações, tendências e identificação de drivers de custo
4. **Sistema Multi-Agentes** - Agentes especializados para diferentes tipos de análise
5. **Recomendações** - Sugestões acionáveis para renegociação baseadas em evidências
6. **Rastreabilidade** - Histórico de conversas e logs de execução

## Estrutura do Projeto

```
copilot_auditoria/
├── docs/                    # Documentação do projeto
│   ├── ARCHITECTURE.md      # Arquitetura técnica detalhada
│   ├── ROADMAP.md           # Fases de desenvolvimento
│   ├── SETUP.md             # Guia de configuração
│   ├── DOCKER.md            # Guia de containerização
│   └── AGENTS.md            # Documentação dos agentes
├── src/                     # Código fonte (a ser criado)
│   ├── api/                 # Endpoints FastAPI
│   ├── agents/              # Sistema multi-agentes
│   ├── ingestion/           # Processamento de documentos
│   ├── search/              # Integração Azure AI Search
│   └── utils/               # Utilitários
├── tests/                   # Testes automatizados
├── docker/                  # Configurações Docker
├── .env.example             # Exemplo de variáveis de ambiente
├── docker-compose.yml       # Orquestração de containers
├── requirements.txt         # Dependências Python
├── PRD.md                   # Documento de requisitos do produto
└── README.md                # Este arquivo
```

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [PRD.md](PRD.md) | Requisitos detalhados do produto |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitetura técnica e fluxos |
| [ROADMAP.md](docs/ROADMAP.md) | Fases e entregas do desenvolvimento |
| [SETUP.md](docs/SETUP.md) | Como configurar o ambiente |
| [DOCKER.md](docs/DOCKER.md) | Containerização e deploy |
| [AGENTS.md](docs/AGENTS.md) | Sistema multi-agentes |

## Início Rápido

```bash
# Clonar o repositório
git clone <url-do-repositorio>
cd copilot_auditoria

# Copiar e configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais Azure

# Subir ambiente com Docker
docker-compose up -d

# Acessar a API
curl http://localhost:8000/health
```

> Consulte [docs/SETUP.md](docs/SETUP.md) para instruções detalhadas.

## Casos de Uso

### 1. Entender Cláusulas Contratuais
> "Como funciona o reajuste anual desse contrato?"

### 2. Analisar Drivers de Custo
> "Quais são os principais drivers de custo nos últimos 12 meses?"

### 3. Cruzar Contrato e Dados
> "O contrato permite coparticipação nesses procedimentos caros?"

### 4. Apoiar Renegociação
> "O que faria sentido renegociar com a operadora?"

## Objetivos de Aprendizado

Este projeto foi desenvolvido com foco em:

- Dominar serviços Azure (OpenAI, AI Search, Blob Storage, Cosmos DB, Container Apps)
- Aprender arquitetura de sistemas multi-agentes
- Praticar RAG (Retrieval Augmented Generation) avançado
- Implementar boas práticas de desenvolvimento com Python/FastAPI
- Entender containerização e deploy em nuvem

## Status do Projeto

**Fase atual:** Configuração inicial e documentação

Consulte [docs/ROADMAP.md](docs/ROADMAP.md) para acompanhar o progresso.

## Licença

Projeto pessoal para fins educacionais.
