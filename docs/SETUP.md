# Guia de Configuração

Este documento explica como configurar o ambiente de desenvolvimento do HealthCost AI Copilot.

## Pré-requisitos

### Software Necessário

| Software | Versão Mínima | Propósito |
|----------|---------------|-----------|
| Python | 3.11+ | Linguagem principal |
| Docker | 24.0+ | Containerização |
| Docker Compose | 2.20+ | Orquestração local |
| Git | 2.40+ | Controle de versão |
| Azure CLI | 2.50+ | Gerenciamento Azure |

### Conta Azure

Você precisará de uma conta Azure com acesso para criar:
- Resource Group
- Azure OpenAI Service
- Azure AI Search
- Azure Blob Storage
- Azure Cosmos DB

> **Nota:** Alguns serviços como Azure OpenAI podem requerer solicitação de acesso prévia.

---

## Configuração Passo a Passo

### 1. Clonar o Repositório

```bash
git clone <url-do-repositorio>
cd copilot_auditoria
```

### 2. Configurar Ambiente Python

#### Opção A: Usando venv (recomendado para desenvolvimento)

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar (Linux/Mac)
source .venv/bin/activate

# Ativar (Windows)
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

#### Opção B: Usando Docker (recomendado para execução)

```bash
# Build e execução
docker-compose up --build
```

### 3. Configurar Variáveis de Ambiente

```bash
# Copiar exemplo
cp .env.example .env

# Editar com suas credenciais
nano .env  # ou seu editor preferido
```

#### Variáveis Necessárias

```env
# ============================================
# AZURE OPENAI
# ============================================
AZURE_OPENAI_ENDPOINT=https://seu-recurso.openai.azure.com/
AZURE_OPENAI_API_KEY=sua-api-key
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# ============================================
# AZURE AI SEARCH
# ============================================
AZURE_SEARCH_ENDPOINT=https://seu-search.search.windows.net
AZURE_SEARCH_API_KEY=sua-api-key
AZURE_SEARCH_INDEX_NAME=contracts-index

# ============================================
# AZURE BLOB STORAGE
# ============================================
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_CONTRACTS=contracts
AZURE_STORAGE_CONTAINER_COSTS=costs
AZURE_STORAGE_CONTAINER_PROCESSED=processed

# ============================================
# AZURE COSMOS DB
# ============================================
COSMOS_ENDPOINT=https://seu-cosmos.documents.azure.com:443/
COSMOS_KEY=sua-key
COSMOS_DATABASE=healthcost
COSMOS_CONTAINER_CONVERSATIONS=conversations
COSMOS_CONTAINER_CLIENTS=clients

# ============================================
# APLICAÇÃO
# ============================================
APP_ENV=development
APP_DEBUG=true
APP_LOG_LEVEL=INFO
API_KEY=sua-api-key-para-proteger-endpoints
```

---

## Provisionamento de Recursos Azure

### Via Azure CLI

#### 1. Login e Setup Inicial

```bash
# Login
az login

# Selecionar subscription
az account set --subscription "sua-subscription"

# Criar Resource Group
az group create \
  --name rg-healthcost-dev \
  --location eastus
```

#### 2. Azure OpenAI

```bash
# Criar recurso OpenAI
az cognitiveservices account create \
  --name openai-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --kind OpenAI \
  --sku S0 \
  --location eastus

# Criar deployment de modelo (após aprovação)
az cognitiveservices account deployment create \
  --name openai-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-05-13" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard

# Criar deployment de embeddings
az cognitiveservices account deployment create \
  --name openai-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --deployment-name text-embedding-3-small \
  --model-name text-embedding-3-small \
  --model-version "1" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard

# Obter endpoint e key
az cognitiveservices account show \
  --name openai-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --query "properties.endpoint"

az cognitiveservices account keys list \
  --name openai-healthcost-dev \
  --resource-group rg-healthcost-dev
```

#### 3. Azure AI Search

```bash
# Criar serviço de busca
az search service create \
  --name search-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --sku Basic \
  --location eastus

# Obter admin key
az search admin-key show \
  --service-name search-healthcost-dev \
  --resource-group rg-healthcost-dev
```

#### 4. Azure Blob Storage

```bash
# Criar storage account
az storage account create \
  --name sthealthcostdev \
  --resource-group rg-healthcost-dev \
  --location eastus \
  --sku Standard_LRS

# Criar containers
az storage container create \
  --name contracts \
  --account-name sthealthcostdev

az storage container create \
  --name costs \
  --account-name sthealthcostdev

az storage container create \
  --name processed \
  --account-name sthealthcostdev

# Obter connection string
az storage account show-connection-string \
  --name sthealthcostdev \
  --resource-group rg-healthcost-dev
```

#### 5. Azure Cosmos DB

```bash
# Criar conta Cosmos DB
az cosmosdb create \
  --name cosmos-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --kind GlobalDocumentDB \
  --default-consistency-level Session

# Criar database
az cosmosdb sql database create \
  --account-name cosmos-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --name healthcost

# Criar containers
az cosmosdb sql container create \
  --account-name cosmos-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --database-name healthcost \
  --name conversations \
  --partition-key-path /client_id

az cosmosdb sql container create \
  --account-name cosmos-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --database-name healthcost \
  --name clients \
  --partition-key-path /id

# Obter endpoint e key
az cosmosdb show \
  --name cosmos-healthcost-dev \
  --resource-group rg-healthcost-dev \
  --query "documentEndpoint"

az cosmosdb keys list \
  --name cosmos-healthcost-dev \
  --resource-group rg-healthcost-dev
```

---

## Verificação da Configuração

### Script de Validação

Após configurar tudo, execute o script de verificação:

```bash
python scripts/verify_config.py
```

O script testa:
- Conexão com Azure OpenAI
- Conexão com Azure AI Search
- Conexão com Azure Blob Storage
- Conexão com Azure Cosmos DB

### Verificação Manual

```bash
# Testar API local
curl http://localhost:8000/health

# Resposta esperada:
# {"status": "healthy", "version": "0.1.0"}
```

---

## Estrutura do .env.example

Crie este arquivo na raiz do projeto:

```env
# ============================================
# AZURE OPENAI
# ============================================
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# ============================================
# AZURE AI SEARCH
# ============================================
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-api-key-here
AZURE_SEARCH_INDEX_NAME=contracts-index

# ============================================
# AZURE BLOB STORAGE
# ============================================
AZURE_STORAGE_CONNECTION_STRING=your-connection-string-here
AZURE_STORAGE_CONTAINER_CONTRACTS=contracts
AZURE_STORAGE_CONTAINER_COSTS=costs
AZURE_STORAGE_CONTAINER_PROCESSED=processed

# ============================================
# AZURE COSMOS DB
# ============================================
COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
COSMOS_KEY=your-key-here
COSMOS_DATABASE=healthcost
COSMOS_CONTAINER_CONVERSATIONS=conversations
COSMOS_CONTAINER_CLIENTS=clients

# ============================================
# APLICAÇÃO
# ============================================
APP_ENV=development
APP_DEBUG=true
APP_LOG_LEVEL=INFO
API_KEY=your-api-key-for-endpoints
```

---

## Troubleshooting

### Erro: "Azure OpenAI resource not found"
- Verifique se o recurso foi criado na região correta
- Confirme que você tem acesso ao Azure OpenAI (requer aprovação)

### Erro: "Invalid API key"
- Regenere a chave no portal Azure
- Verifique se copiou a chave completa (sem espaços)

### Erro: "Index not found" no AI Search
- O índice será criado automaticamente na primeira indexação
- Ou crie manualmente via portal/script

### Erro: "Container not found" no Blob Storage
- Execute os comandos de criação de containers
- Verifique se o nome do storage account está correto

### Docker não conecta aos serviços Azure
- Verifique se as variáveis de ambiente estão no docker-compose.yml
- Use `docker-compose config` para verificar a configuração

---

## Próximos Passos

Após configurar o ambiente:

1. Consulte [DOCKER.md](DOCKER.md) para entender a containerização
2. Consulte [ARCHITECTURE.md](ARCHITECTURE.md) para entender a arquitetura
3. Siga o [ROADMAP.md](ROADMAP.md) para começar o desenvolvimento
