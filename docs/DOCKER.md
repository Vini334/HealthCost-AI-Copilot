# Guia de Docker e Containerização

Este documento explica os conceitos de Docker e como ele é utilizado no projeto HealthCost AI Copilot.

## O que é Docker?

Docker é uma plataforma de containerização que permite empacotar aplicações e suas dependências em unidades isoladas chamadas **containers**.

### Conceitos Fundamentais

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SEU COMPUTADOR                                  │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   Container 1   │  │   Container 2   │  │   Container 3   │              │
│  │   (API Python)  │  │   (Redis)       │  │   (Nginx)       │              │
│  │                 │  │                 │  │                 │              │
│  │  Python 3.11    │  │  Redis 7.0      │  │  Nginx 1.25     │              │
│  │  FastAPI        │  │                 │  │                 │              │
│  │  Dependências   │  │                 │  │                 │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│           │                   │                   │                         │
│           └───────────────────┴───────────────────┘                         │
│                               │                                              │
│                    ┌──────────┴──────────┐                                  │
│                    │    DOCKER ENGINE    │                                  │
│                    └─────────────────────┘                                  │
│                               │                                              │
│                    ┌──────────┴──────────┐                                  │
│                    │  SISTEMA OPERACIONAL │                                 │
│                    │  (Linux/Windows/Mac) │                                 │
│                    └─────────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Glossário

| Termo | Descrição |
|-------|-----------|
| **Imagem** | Template read-only com instruções para criar um container. Como uma "foto" do ambiente. |
| **Container** | Instância executável de uma imagem. O ambiente rodando de verdade. |
| **Dockerfile** | Arquivo de texto com instruções para construir uma imagem. |
| **Registry** | Repositório para armazenar e distribuir imagens (ex: Docker Hub, Azure ACR). |
| **Volume** | Mecanismo para persistir dados fora do container. |
| **Network** | Rede virtual para comunicação entre containers. |

---

## Por que usar Docker?

### Problema: "Funciona na minha máquina"

```
Desenvolvedor A                    Desenvolvedor B
┌─────────────────┐               ┌─────────────────┐
│ Python 3.11.2   │               │ Python 3.10.1   │  ← Versões diferentes
│ pip 23.0        │               │ pip 22.3        │
│ Ubuntu 22.04    │               │ Windows 11      │  ← SOs diferentes
│ Lib X v1.2      │               │ Lib X v1.0      │  ← Dependências diferentes
└─────────────────┘               └─────────────────┘
        │                                 │
        ▼                                 ▼
   "Funciona!"                      "Não funciona!"
```

### Solução: Containers

```
Desenvolvedor A                    Desenvolvedor B
┌─────────────────┐               ┌─────────────────┐
│                 │               │                 │
│  ┌───────────┐  │               │  ┌───────────┐  │
│  │ Container │  │               │  │ Container │  │
│  │ Python 3.11│ │               │  │ Python 3.11│ │  ← Ambiente IDÊNTICO
│  │ FastAPI   │  │               │  │ FastAPI   │  │
│  │ Libs      │  │               │  │ Libs      │  │
│  └───────────┘  │               │  └───────────┘  │
│                 │               │                 │
│ Ubuntu / Mac    │               │ Windows         │
└─────────────────┘               └─────────────────┘
        │                                 │
        ▼                                 ▼
   "Funciona!"                       "Funciona!"
```

### Benefícios

1. **Consistência:** Mesmo ambiente em dev, staging e produção
2. **Isolamento:** Aplicações não interferem umas nas outras
3. **Portabilidade:** Roda em qualquer lugar que tenha Docker
4. **Versionamento:** Imagens são versionadas como código
5. **Escalabilidade:** Fácil criar múltiplas instâncias

---

## Estrutura Docker do Projeto

```
copilot_auditoria/
├── Dockerfile              # Instruções para build da imagem
├── docker-compose.yml      # Orquestração de serviços
├── docker-compose.dev.yml  # Override para desenvolvimento
├── .dockerignore           # Arquivos ignorados no build
└── docker/
    └── entrypoint.sh       # Script de inicialização
```

---

## Dockerfile Explicado

O Dockerfile define como construir a imagem da aplicação.

```dockerfile
# ============================================
# ESTÁGIO 1: Builder
# ============================================
# Usa imagem Python como base
FROM python:3.11-slim as builder

# Define diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema necessárias para compilar pacotes Python
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas requirements primeiro (otimização de cache)
COPY requirements.txt .

# Instala dependências Python em um diretório separado
RUN pip install --user --no-cache-dir -r requirements.txt

# ============================================
# ESTÁGIO 2: Runtime (imagem final)
# ============================================
FROM python:3.11-slim as runtime

# Criar usuário não-root (segurança)
RUN useradd --create-home appuser

WORKDIR /app

# Copia dependências instaladas do estágio builder
COPY --from=builder /root/.local /home/appuser/.local

# Copia código da aplicação
COPY --chown=appuser:appuser . .

# Muda para usuário não-root
USER appuser

# Adiciona dependências ao PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Expõe porta da aplicação
EXPOSE 8000

# Comando para iniciar a aplicação
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Por que Multi-stage Build?

```
Build tradicional                  Multi-stage build
┌─────────────────────┐           ┌─────────────────────┐
│ Imagem Final        │           │ Estágio 1 (builder) │
│                     │           │ - Compiladores      │
│ - Python            │           │ - Headers           │
│ - Compiladores      │           │ - Build tools       │
│ - Headers           │           │ (descartado)        │
│ - Build tools       │           └─────────────────────┘
│ - Código            │                    │
│ - Dependências      │                    ▼
│                     │           ┌─────────────────────┐
│ ~1.5 GB             │           │ Estágio 2 (runtime) │
└─────────────────────┘           │ - Python            │
                                  │ - Código            │
                                  │ - Dependências      │
                                  │                     │
                                  │ ~500 MB             │
                                  └─────────────────────┘
```

---

## Docker Compose Explicado

Docker Compose orquestra múltiplos containers como um único serviço.

```yaml
# docker-compose.yml
version: '3.8'

services:
  # ============================================
  # Serviço principal: API
  # ============================================
  api:
    build:
      context: .                    # Diretório com Dockerfile
      dockerfile: Dockerfile        # Nome do Dockerfile
    ports:
      - "8000:8000"                 # host:container
    environment:
      - APP_ENV=production
    env_file:
      - .env                        # Variáveis de ambiente
    volumes:
      - ./logs:/app/logs            # Persistir logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped         # Reinicia se falhar

  # ============================================
  # Redis (cache - opcional)
  # ============================================
  redis:
    image: redis:7-alpine           # Imagem oficial do Docker Hub
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data            # Volume nomeado para persistência
    restart: unless-stopped

# ============================================
# Volumes nomeados
# ============================================
volumes:
  redis_data:                       # Dados persistem entre restarts
```

### Arquivo de Override para Desenvolvimento

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  api:
    build:
      target: builder               # Usa estágio com mais ferramentas
    volumes:
      - .:/app                      # Monta código local (hot reload)
      - /app/.venv                  # Ignora venv local
    environment:
      - APP_ENV=development
      - APP_DEBUG=true
    command: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Comandos Docker Essenciais

### Imagens

```bash
# Construir imagem
docker build -t healthcost-api:latest .

# Listar imagens
docker images

# Remover imagem
docker rmi healthcost-api:latest

# Remover imagens não utilizadas
docker image prune
```

### Containers

```bash
# Rodar container
docker run -d -p 8000:8000 --name api healthcost-api:latest

# Listar containers rodando
docker ps

# Listar todos (incluindo parados)
docker ps -a

# Parar container
docker stop api

# Iniciar container parado
docker start api

# Remover container
docker rm api

# Ver logs
docker logs api
docker logs -f api  # Follow (tempo real)

# Executar comando dentro do container
docker exec -it api bash
docker exec api python --version
```

### Docker Compose

```bash
# Subir todos os serviços
docker-compose up

# Subir em background (detached)
docker-compose up -d

# Subir com rebuild
docker-compose up --build

# Subir com arquivo de override
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Parar serviços
docker-compose down

# Parar e remover volumes
docker-compose down -v

# Ver logs de todos os serviços
docker-compose logs

# Ver logs de serviço específico
docker-compose logs api

# Escalar serviço
docker-compose up -d --scale api=3

# Executar comando em serviço
docker-compose exec api bash
```

---

## Fluxo de Trabalho de Desenvolvimento

### 1. Primeira Vez (Setup)

```bash
# Clonar repo
git clone <url>
cd copilot_auditoria

# Copiar env
cp .env.example .env
# Editar .env com credenciais

# Build e start
docker-compose up --build
```

### 2. Desenvolvimento Diário

```bash
# Iniciar ambiente
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Em outro terminal, ver logs
docker-compose logs -f api

# Fazer alterações no código
# Hot reload automático com --reload

# Rodar testes
docker-compose exec api pytest

# Parar quando terminar
docker-compose down
```

### 3. Testar Build de Produção

```bash
# Build de produção
docker build -t healthcost-api:test .

# Rodar
docker run -p 8000:8000 --env-file .env healthcost-api:test

# Testar
curl http://localhost:8000/health
```

---

## Boas Práticas

### 1. Otimização de Cache

O Docker usa cache em camadas. Ordene instruções da menos mutável para a mais mutável:

```dockerfile
# BOM - requirements muda menos que código
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# RUIM - qualquer mudança no código invalida cache de dependências
COPY . .
RUN pip install -r requirements.txt
```

### 2. .dockerignore

Evita copiar arquivos desnecessários:

```
# .dockerignore
.git
.gitignore
.env
.venv
__pycache__
*.pyc
*.pyo
.pytest_cache
.coverage
htmlcov
*.md
docs/
tests/
.vscode/
.idea/
```

### 3. Segurança

```dockerfile
# Usar usuário não-root
RUN useradd --create-home appuser
USER appuser

# Não incluir secrets na imagem
# Use variáveis de ambiente ou secrets do orquestrador

# Usar imagens oficiais e slim
FROM python:3.11-slim  # Não python:3.11 (muito grande)
```

### 4. Health Checks

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s      # Intervalo entre checks
  timeout: 10s       # Timeout de cada check
  retries: 3         # Tentativas antes de unhealthy
  start_period: 40s  # Tempo para app iniciar
```

---

## Volumes e Persistência

### Tipos de Volumes

```yaml
services:
  api:
    volumes:
      # Bind mount - mapeia diretório do host
      - ./data:/app/data

      # Volume nomeado - gerenciado pelo Docker
      - app_data:/app/data

      # Volume anônimo - temporário
      - /app/temp

volumes:
  app_data:  # Declaração do volume nomeado
```

### Quando Usar Cada Tipo

| Tipo | Uso | Exemplo |
|------|-----|---------|
| Bind mount | Desenvolvimento, código fonte | `./src:/app/src` |
| Volume nomeado | Dados persistentes em prod | Database, uploads |
| Volume anônimo | Dados temporários | Cache, temp files |

---

## Networking

### Comunicação entre Containers

```yaml
services:
  api:
    networks:
      - backend
    # Acessa redis como: redis://redis:6379

  redis:
    networks:
      - backend

networks:
  backend:
    driver: bridge
```

### Exposição de Portas

```yaml
ports:
  - "8000:8000"      # hostPort:containerPort
  - "127.0.0.1:8000:8000"  # Apenas localhost

expose:
  - "8000"           # Apenas entre containers (não expõe ao host)
```

---

## Deploy para Azure Container Apps

Ver [SETUP.md](SETUP.md) para configuração do Azure Container Registry e Container Apps.

```bash
# Build e tag para ACR
docker build -t healthcostacr.azurecr.io/api:v1.0.0 .

# Login no ACR
az acr login --name healthcostacr

# Push para ACR
docker push healthcostacr.azurecr.io/api:v1.0.0

# Deploy para Container Apps via CLI ou CI/CD
```

---

## Troubleshooting

### Container não inicia

```bash
# Ver logs
docker-compose logs api

# Ver eventos
docker events

# Inspecionar container
docker inspect <container_id>
```

### Porta já em uso

```bash
# Encontrar processo usando a porta
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Usar porta diferente
docker run -p 8001:8000 ...
```

### Falta de espaço

```bash
# Ver uso de disco do Docker
docker system df

# Limpar tudo não utilizado
docker system prune -a

# Limpar apenas volumes
docker volume prune
```

### Container muito lento

```bash
# Verificar recursos
docker stats

# Limitar recursos
docker run --memory=512m --cpus=1 ...
```

---

## Resumo de Comandos

```bash
# Desenvolvimento
docker-compose up -d                    # Iniciar
docker-compose logs -f                  # Ver logs
docker-compose exec api bash            # Acessar shell
docker-compose down                     # Parar

# Build
docker build -t app:tag .               # Build
docker push registry/app:tag            # Push

# Debug
docker ps                               # Listar containers
docker logs container_name              # Ver logs
docker exec -it container_name bash     # Acessar container
docker inspect container_name           # Detalhes
```
