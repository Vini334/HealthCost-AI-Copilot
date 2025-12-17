# Roadmap de Desenvolvimento

Este documento detalha as fases de desenvolvimento do HealthCost AI Copilot, com entregas específicas e critérios de conclusão.

## Visão Geral das Fases

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  FASE 1     FASE 2     FASE 3     FASE 4     FASE 4.5    FASE 5     FASE 6               │
│  Setup      Ingestão   Agentes    Interface  Frontend    Deploy     Evolução             │
│  ━━━━━━     ━━━━━━━━   ━━━━━━━    ━━━━━━━━━  ━━━━━━━━    ━━━━━━     ━━━━━━━              │
│  Infra      MVP        Multi-     Chat       Web UI      Container  Métricas             │
│  Azure      Search     Agent      API        SPA         Apps       Refine               │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Fase 1: Configuração de Infraestrutura

**Objetivo:** Preparar ambiente de desenvolvimento e provisionar recursos Azure.

### Entregas

#### 1.1 Ambiente de Desenvolvimento Local
- [x] Estrutura de diretórios do projeto
- [x] Configuração do ambiente Python (pyproject.toml ou requirements.txt)
- [x] Configuração do Docker e docker-compose
- [x] Arquivo .env.example com variáveis necessárias
- [x] Pre-commit hooks (linting, formatting)

#### 1.2 Recursos Azure
- [x] Resource Group criado
- [x] Azure OpenAI provisionado
  - [x] Deployment de modelo GPT-4 ou GPT-4o
  - [x] Deployment de modelo de embeddings (text-embedding-ada-002 ou text-embedding-3-small)
- [x] Azure AI Search provisionado
  - [ ] Índice de contratos criado (será criado na Fase 2)
- [x] Azure Blob Storage provisionado
  - [x] Containers criados (contracts, costs, processed)
- [x] Azure Cosmos DB provisionado
  - [x] Database e collections criadas

#### 1.3 Projeto Base
- [x] FastAPI app inicial (health check funcionando)
- [x] Configuração de settings com Pydantic
- [x] Logging estruturado configurado
- [x] Testes básicos rodando

### Critérios de Conclusão
- `docker-compose up` sobe a aplicação
- `/health` retorna 200
- Conexões com Azure validadas

---

## Fase 2: Sistema de Ingestão e Busca

**Objetivo:** Implementar pipeline de ingestão de documentos e busca vetorial.

### Entregas

#### 2.1 Upload e Armazenamento
- [x] Endpoint POST `/api/v1/upload/contract` (PDF)
- [x] Endpoint POST `/api/v1/upload/costs` (CSV/Excel)
- [x] Validação de formatos e tamanhos
- [x] Upload para Azure Blob Storage
- [x] Registro de metadados no Cosmos DB

#### 2.2 Processamento de Contratos
- [x] Extração de texto de PDFs (PyPDF2/pdfplumber)
- [x] Chunking inteligente
  - [x] Por páginas
  - [x] Por seções/cláusulas (regex patterns)
  - [x] Overlap entre chunks
- [x] Extração de metadados (número de página, seção detectada)

#### 2.3 Indexação Vetorial
- [x] Geração de embeddings via Azure OpenAI
- [x] Indexação no Azure AI Search
- [x] Metadados incluídos (client_id, contract_id, page, section)

#### 2.4 Busca Semântica
- [x] Função de busca vetorial
- [x] Função de busca híbrida (vetorial + keyword)
- [x] Filtros por client_id e contract_id
- [x] Re-ranking de resultados

#### 2.5 Processamento de Dados de Custos
- [x] Parser de CSV/Excel
- [x] Validação de colunas esperadas
- [x] Normalização de dados
- [x] Armazenamento estruturado

### Critérios de Conclusão
- Upload de PDF funciona e indexa no AI Search
- Busca retorna chunks relevantes
- Dados de custos são parseados corretamente

---

## Fase 3: Sistema Multi-Agentes

**Objetivo:** Implementar agentes especializados e orquestração.

### Entregas

#### 3.1 Framework de Agentes
- [x] Classe base para agentes
- [x] Sistema de tools/functions
- [x] Gerenciamento de contexto
- [x] Logging de execução por agente

#### 3.2 Retrieval Agent
- [x] Recebe query e contexto (client_id, contract_id)
- [x] Executa busca híbrida
- [x] Filtra e rankeia resultados
- [x] Retorna chunks relevantes com metadados

#### 3.3 Contract Analyst Agent
- [x] Recebe chunks e pergunta
- [x] Interpreta cláusulas contratuais
- [x] Explica em linguagem de negócios
- [x] Cita seções e páginas

#### 3.4 Cost Insights Agent
- [x] Acessa dados de custos do cliente
- [x] Tools para análises:
  - [x] Agregação por categoria
  - [x] Evolução temporal
  - [x] Top procedimentos
  - [x] Comparação de períodos
- [x] Gera insights sobre tendências

#### 3.5 Negotiation Advisor Agent
- [x] Recebe contexto de contrato + custos
- [x] Identifica oportunidades de renegociação
- [x] Prioriza pontos por impacto
- [x] Estima economia potencial

#### 3.6 Orchestrator Agent
- [x] Análise de intent da pergunta
- [x] Decisão de quais agentes acionar
- [x] Coordenação de execução (paralela/sequencial)
- [x] Consolidação de respostas
- [x] Geração de resposta final

### Critérios de Conclusão
- Pergunta sobre contrato aciona Retrieval + Contract Analyst
- Pergunta sobre custos aciona Cost Insights
- Pergunta sobre renegociação coordena múltiplos agentes
- Respostas incluem evidências e referências

---

## Fase 4: Interface Conversacional

**Objetivo:** Implementar API de chat completa com histórico.

### Entregas

#### 4.1 Endpoint de Chat
- [x] POST `/api/v1/chat`
- [x] Request: message, client_id, contract_id, conversation_id (opcional)
- [x] Response: answer, sources, agent_trace (debug)

#### 4.2 Gerenciamento de Conversas
- [x] Criar nova conversa
- [x] Continuar conversa existente
- [x] Listar conversas por cliente
- [x] Histórico de mensagens

#### 4.3 Contexto de Conversa
- [x] Memória de curto prazo (últimas N mensagens)
- [x] Resumo de conversa longa
- [x] Referência a mensagens anteriores

#### 4.4 Formatação de Respostas
- [x] Markdown para formatação rica
- [x] Citações de fontes (página, seção)
- [x] Tabelas para dados numéricos
- [x] Destaque de recomendações

#### 4.5 API de Clientes e Contratos
- [x] CRUD de clientes
- [x] Listagem de contratos por cliente
- [x] Status de processamento de documentos

### Critérios de Conclusão
- Chat funciona end-to-end
- Histórico persiste entre sessões
- Respostas são bem formatadas com fontes

---

## Fase 4.5: Frontend Web

**Objetivo:** Criar interface web para demonstração e uso do sistema.

### Entregas

#### 4.5.1 Estrutura do Frontend
- [ ] SPA em HTML/CSS/JS vanilla
- [ ] Integração com FastAPI (arquivos estáticos)
- [ ] Tema escuro com paleta EY (preto, cinza, amarelo)
- [ ] Layout responsivo

#### 4.5.2 Sidebar de Navegação
- [ ] Lista de clientes com seleção
- [ ] Lista de contratos do cliente (opcional)
- [ ] Histórico de conversas agrupado por data
- [ ] Indicador visual de seleção ativa

#### 4.5.3 Área de Chat
- [ ] Interface estilo ChatGPT
- [ ] Renderização de Markdown nas respostas
- [ ] Citações de fontes (página, seção)
- [ ] Indicador de "digitando..." durante resposta
- [ ] Auto-scroll para novas mensagens

#### 4.5.4 Modal de Novo Cliente
- [ ] Formulário simples (nome do cliente)
- [ ] Validação de campos
- [ ] Feedback de sucesso/erro
- [ ] Atualização automática da lista

#### 4.5.5 Modal de Upload de Documentos
- [ ] Seleção de tipo (Contrato PDF / Planilha de Custos)
- [ ] Drag & drop ou seleção de arquivo
- [ ] Vinculação ao cliente selecionado
- [ ] Barra de progresso do upload
- [ ] Status de processamento (Enviando → Processando → Indexando → Concluído)
- [ ] Feedback de sucesso/erro

#### 4.5.6 Integração com API
- [ ] Consumo dos endpoints existentes
- [ ] Tratamento de erros da API
- [ ] Loading states apropriados

### Critérios de Conclusão
- Interface acessível em http://localhost:8000
- Criar cliente, fazer upload e conversar funciona end-to-end
- Visual clean e moderno com tema EY
- Responsivo em diferentes tamanhos de tela

---

## Fase 5: Deploy e Observabilidade

**Objetivo:** Containerizar e fazer deploy no Azure Container Apps.

### Entregas

#### 5.1 Containerização
- [ ] Dockerfile otimizado (multi-stage)
- [ ] docker-compose para desenvolvimento
- [ ] Imagem publicada no Azure Container Registry

#### 5.2 CI/CD
- [ ] GitHub Actions workflow
  - [ ] Lint e testes
  - [ ] Build da imagem
  - [ ] Push para ACR
  - [ ] Deploy para Container Apps

#### 5.3 Azure Container Apps
- [ ] Ambiente criado
- [ ] App configurada
- [ ] Variáveis de ambiente (secrets)
- [ ] Scaling configurado
- [ ] Health checks

#### 5.4 Observabilidade
- [ ] Logging estruturado (JSON)
- [ ] Application Insights integrado
- [ ] Métricas customizadas:
  - [ ] Tempo de resposta por agente
  - [ ] Tokens utilizados
  - [ ] Taxa de sucesso
- [ ] Alertas básicos

#### 5.5 Documentação de Deploy
- [ ] Guia de deploy manual
- [ ] Troubleshooting comum
- [ ] Runbook de operações

### Critérios de Conclusão
- Aplicação rodando no Container Apps
- CI/CD funcionando
- Logs e métricas visíveis no Azure

---

## Fase 6: Evolução e Refinamentos

**Objetivo:** Melhorar qualidade, performance e experiência.

### Entregas

#### 6.1 Qualidade de Respostas
- [ ] Avaliação de respostas (manual inicialmente)
- [ ] Ajuste de prompts dos agentes
- [ ] Few-shot examples para casos comuns
- [ ] Tratamento de edge cases

#### 6.2 Performance
- [ ] Profiling de latência
- [ ] Otimização de chunking
- [ ] Cache de embeddings frequentes
- [ ] Paralelização de agentes

#### 6.3 UX/Features Adicionais
- [ ] Sugestões de perguntas
- [ ] Feedback do usuário (thumbs up/down)
- [ ] Export de relatórios
- [ ] Comparação entre contratos

#### 6.4 Testes e Cobertura
- [ ] Testes unitários (>70% cobertura)
- [ ] Testes de integração
- [ ] Testes end-to-end
- [ ] Dataset de avaliação

### Critérios de Conclusão
- Respostas consistentes e precisas
- Latência < 10s para perguntas comuns
- Usuário consegue realizar os 4 casos de uso principais

---

## Tracking de Progresso

| Fase | Status | Início | Conclusão |
|------|--------|--------|-----------|
| Fase 1 - Setup | Concluída | 15/12/2025 | 15/12/2025 |
| Fase 2 - Ingestão | Concluída | 16/12/2025 | 16/12/2025 |
| Fase 3 - Agentes | Concluída | 16/12/2025 | 16/12/2025 |
| Fase 4 - Interface | Concluída | 16/12/2025 | 16/12/2025 |
| Fase 4.5 - Frontend | Em andamento | 16/12/2025 | - |
| Fase 5 - Deploy | Não iniciada | - | - |
| Fase 6 - Evolução | Não iniciada | - | - |

---

## Dependências entre Fases

```
Fase 1 ──▶ Fase 2 ──▶ Fase 3 ──▶ Fase 4 ──▶ Fase 4.5 ──▶ Fase 5 ──▶ Fase 6
```

- **Fase 2** depende de **Fase 1** (infraestrutura Azure)
- **Fase 3** depende de **Fase 2** (precisa de busca funcionando)
- **Fase 4** depende de **Fase 3** (precisa de agentes)
- **Fase 4.5** depende de **Fase 4** (precisa da API de chat)
- **Fase 5** depende de **Fase 4.5** (deploy do frontend + backend)
- **Fase 6** é contínua após MVP funcional

---

## Notas

- Este roadmap é um guia, não um cronograma rígido
- Priorize funcionalidade sobre perfeição no MVP
- Documente aprendizados durante o desenvolvimento
- Atualize este documento conforme o projeto evolui
