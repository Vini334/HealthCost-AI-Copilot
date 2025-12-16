# Sistema Multi-Agentes

Este documento detalha a arquitetura e funcionamento do sistema multi-agentes do HealthCost AI Copilot.

## O que são Agentes de IA?

Agentes são sistemas de IA que podem:
1. **Perceber** o ambiente (receber inputs)
2. **Raciocinar** sobre o que fazer (processar com LLM)
3. **Agir** usando ferramentas (executar ações)
4. **Aprender** com feedback (melhorar respostas)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGENTE DE IA                                    │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │   INPUT     │───▶│   LLM       │───▶│  DECISÃO    │───▶│   AÇÃO      │   │
│  │  (Pergunta) │    │ (Raciocínio)│    │ (Qual tool?)│    │ (Execução)  │   │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘   │
│         ▲                                                        │          │
│         │                                                        │          │
│         └────────────────────────────────────────────────────────┘          │
│                              LOOP DE FEEDBACK                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agentes vs Chatbots Tradicionais

| Aspecto | Chatbot Tradicional | Agente |
|---------|---------------------|--------|
| **Execução** | Resposta única | Loop até completar tarefa |
| **Ferramentas** | Não usa | Usa ferramentas externas |
| **Autonomia** | Baixa | Alta |
| **Complexidade** | Perguntas simples | Tarefas multi-step |

---

## Por que Multi-Agentes?

### Problema: Agente Único Generalista

```
┌─────────────────────────────────────────┐
│          AGENTE GENERALISTA             │
│                                         │
│  - Precisa saber TUDO                   │
│  - Prompt gigante                       │
│  - Difícil de manter                    │
│  - Performance inconsistente            │
│  - Difícil debugar                      │
└─────────────────────────────────────────┘
```

### Solução: Agentes Especializados

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SISTEMA MULTI-AGENTES                              │
│                                                                              │
│         ┌─────────────────────────────────────────────┐                     │
│         │            ORCHESTRATOR AGENT               │                     │
│         │         (Coordena especialistas)            │                     │
│         └─────────────────────────────────────────────┘                     │
│                              │                                               │
│         ┌────────────┬───────┴───────┬────────────┐                         │
│         ▼            ▼               ▼            ▼                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │ RETRIEVAL  │ │ CONTRACT   │ │   COST     │ │NEGOTIATION │               │
│  │   AGENT    │ │  ANALYST   │ │ INSIGHTS   │ │  ADVISOR   │               │
│  │            │ │            │ │            │ │            │               │
│  │ Especialista│ │Especialista│ │Especialista│ │Especialista│               │
│  │ em busca   │ │em contratos│ │ em dados   │ │em negócio  │               │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Benefícios

1. **Especialização:** Cada agente faz uma coisa bem
2. **Manutenibilidade:** Prompts menores e focados
3. **Testabilidade:** Testar agentes isoladamente
4. **Escalabilidade:** Adicionar novos agentes facilmente
5. **Observabilidade:** Rastrear qual agente fez o quê

---

## Arquitetura do Sistema

```
                         ┌─────────────────────────┐
                         │    PERGUNTA DO USUÁRIO  │
                         │ "Quais os principais    │
                         │  drivers de custo?"     │
                         └───────────┬─────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR AGENT                                  │
│                                                                             │
│  1. Analisa intent da pergunta                                             │
│  2. Decide: precisa de COST INSIGHTS (dados) + RETRIEVAL (contexto)        │
│  3. Executa agentes em paralelo                                            │
│  4. Consolida respostas                                                    │
│  5. Gera resposta final                                                    │
└────────────────────────────────────────────────────────────────────────────┘
                    │                              │
                    ▼                              ▼
    ┌───────────────────────┐      ┌───────────────────────┐
    │    RETRIEVAL AGENT    │      │   COST INSIGHTS       │
    │                       │      │       AGENT           │
    │  Busca: "drivers de   │      │                       │
    │  custo" no contrato   │      │  Análise de dados:    │
    │                       │      │  - Top procedimentos  │
    │  Retorna: cláusulas   │      │  - Tendências         │
    │  sobre cobertura      │      │  - Concentração       │
    └───────────────────────┘      └───────────────────────┘
                    │                              │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌───────────────────────────┐
                    │     RESPOSTA FINAL        │
                    │                           │
                    │  "Os principais drivers   │
                    │   de custo são:           │
                    │   1. Internações (45%)    │
                    │   2. Exames (25%)         │
                    │   3. Consultas (15%)      │
                    │                           │
                    │   O contrato na cláusula  │
                    │   X permite copartici-    │
                    │   pação para internações" │
                    └───────────────────────────┘
```

---

## Agentes Detalhados

### 1. Orchestrator Agent

O "maestro" que coordena todos os outros agentes.

#### Responsabilidades
- Analisar a intent/objetivo da pergunta do usuário
- Decidir quais agentes especializados acionar
- Coordenar execução (paralela ou sequencial)
- Consolidar respostas dos agentes
- Gerar resposta final coerente

#### Fluxo de Decisão

```
Pergunta recebida
       │
       ▼
┌──────────────────┐
│ Análise de Intent│
└────────┬─────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│              MAPEAMENTO INTENT → AGENTES               │
├────────────────────────────────────────────────────────┤
│ "Como funciona X no contrato?"                         │
│   → Retrieval + Contract Analyst                       │
│                                                        │
│ "Quais os maiores custos?"                             │
│   → Cost Insights                                      │
│                                                        │
│ "O contrato cobre procedimento X?"                     │
│   → Retrieval + Contract Analyst + Cost Insights       │
│                                                        │
│ "O que devo renegociar?"                               │
│   → Retrieval + Cost Insights + Negotiation Advisor    │
└────────────────────────────────────────────────────────┘
```

#### Exemplo de Prompt

```python
ORCHESTRATOR_SYSTEM_PROMPT = """
Você é o orquestrador de um sistema de análise de planos de saúde.

Sua função é:
1. Analisar a pergunta do usuário
2. Decidir quais agentes especializados precisam ser acionados
3. Coordenar a execução
4. Consolidar as respostas em uma resposta final

Agentes disponíveis:
- retrieval: Busca informações em contratos
- contract_analyst: Interpreta cláusulas contratuais
- cost_insights: Analisa dados de custos/sinistralidade
- negotiation_advisor: Gera recomendações de renegociação

Sempre justifique sua decisão de quais agentes usar.
"""
```

---

### 2. Retrieval Agent

Especialista em busca e recuperação de informações nos documentos.

#### Responsabilidades
- Receber query de busca
- Executar busca semântica no Azure AI Search
- Filtrar por client_id e contract_id
- Rankear resultados por relevância
- Retornar chunks mais relevantes com metadados

#### Tools Disponíveis

```python
@tool
def search_contracts(
    query: str,
    client_id: str,
    contract_id: str,
    top_k: int = 5
) -> List[SearchResult]:
    """
    Busca semântica em contratos indexados.

    Args:
        query: Texto da busca
        client_id: ID do cliente
        contract_id: ID do contrato
        top_k: Número de resultados

    Returns:
        Lista de chunks relevantes com metadados
    """
    pass

@tool
def hybrid_search(
    query: str,
    client_id: str,
    contract_id: str,
    semantic_weight: float = 0.7
) -> List[SearchResult]:
    """
    Busca híbrida (semântica + keyword).
    """
    pass
```

#### Exemplo de Output

```json
{
  "results": [
    {
      "content": "CLÁUSULA 8 - REAJUSTE ANUAL\n8.1 O reajuste anual será aplicado...",
      "metadata": {
        "page": 12,
        "section": "CLÁUSULA 8 - REAJUSTE ANUAL",
        "relevance_score": 0.92
      }
    }
  ]
}
```

---

### 3. Contract Analyst Agent

Especialista em interpretação de cláusulas contratuais.

#### Responsabilidades
- Receber chunks de contrato
- Interpretar linguagem jurídica/técnica
- Explicar em linguagem de negócios
- Identificar implicações práticas
- Citar seções e páginas

#### Exemplo de Prompt

```python
CONTRACT_ANALYST_PROMPT = """
Você é um especialista em análise de contratos de planos de saúde.

Dado o contexto do contrato abaixo, responda à pergunta do usuário:
- Explique em linguagem clara e acessível
- Cite a seção/cláusula e página de onde veio a informação
- Destaque implicações práticas para o cliente
- Se houver ambiguidade, mencione

Contexto do contrato:
{context}

Pergunta: {question}
"""
```

#### Exemplo de Interação

**Input:**
- Contexto: Cláusula de reajuste anual (chunks)
- Pergunta: "Como funciona o reajuste?"

**Output:**
```
## Reajuste Anual (Cláusula 8, página 12)

O contrato prevê reajuste anual baseado em dois componentes:

1. **Índice de inflação médica (VCMH):** Aplicado automaticamente
   na data de aniversário do contrato.

2. **Sinistralidade:** Se a sinistralidade ultrapassar 75%,
   a operadora pode aplicar reajuste adicional de até 15%.

### Implicações práticas:
- O reajuste mínimo esperado é o VCMH (~12% historicamente)
- Se os custos do cliente estiverem altos, pode haver reajuste extra
- A cláusula 8.3 permite negociação se houver melhoria na sinistralidade
```

---

### 4. Cost Insights Agent

Especialista em análise de dados de custos e sinistralidade.

#### Responsabilidades
- Acessar dados estruturados de custos
- Executar análises e agregações
- Identificar tendências e padrões
- Gerar visualizações (quando aplicável)
- Fornecer insights acionáveis

#### Tools Disponíveis

```python
@tool
def get_cost_summary(
    client_id: str,
    period: str = "last_12_months"
) -> CostSummary:
    """
    Retorna resumo de custos por categoria.
    """
    pass

@tool
def get_top_procedures(
    client_id: str,
    top_n: int = 10,
    period: str = "last_12_months"
) -> List[Procedure]:
    """
    Retorna procedimentos mais custosos.
    """
    pass

@tool
def get_cost_trend(
    client_id: str,
    category: str = None,
    granularity: str = "monthly"
) -> TrendData:
    """
    Retorna evolução de custos ao longo do tempo.
    """
    pass

@tool
def compare_periods(
    client_id: str,
    period1: str,
    period2: str
) -> Comparison:
    """
    Compara custos entre dois períodos.
    """
    pass

@tool
def calculate_sinistralidade(
    client_id: str,
    period: str = "last_12_months"
) -> float:
    """
    Calcula taxa de sinistralidade.
    """
    pass
```

#### Exemplo de Output

```
## Análise de Custos - Últimos 12 meses

### Distribuição por Categoria
| Categoria | Valor (R$) | % do Total |
|-----------|------------|------------|
| Internações | 450.000 | 45% |
| Exames | 250.000 | 25% |
| Consultas | 150.000 | 15% |
| Medicamentos | 100.000 | 10% |
| Outros | 50.000 | 5% |

### Top 5 Procedimentos
1. Cirurgia cardíaca - R$ 120.000 (12%)
2. Internação UTI - R$ 95.000 (9.5%)
3. Ressonância magnética - R$ 45.000 (4.5%)
...

### Tendência
- Custos cresceram 18% vs mesmo período ano anterior
- Internações aumentaram 25% (principal driver)
- Sinistralidade atual: 82% (acima da meta de 75%)
```

---

### 5. Negotiation Advisor Agent

Especialista em recomendações estratégicas de renegociação.

#### Responsabilidades
- Analisar contexto de contrato + custos
- Identificar oportunidades de renegociação
- Priorizar pontos por impacto financeiro
- Estimar economia potencial
- Sugerir argumentos de negociação

#### Inputs Esperados

- Resumo do contrato (cláusulas principais)
- Dados de custos (sinistralidade, drivers)
- Contexto de mercado (opcional)

#### Exemplo de Output

```
## Recomendações de Renegociação

### Prioridade Alta

1. **Coparticipação em Exames de Alto Custo**
   - Situação atual: Sem coparticipação
   - Recomendação: Implementar 20% de coparticipação para exames > R$500
   - Impacto estimado: Economia de R$ 50.000/ano
   - Argumento: Sinistralidade acima de 80%, prática comum no mercado

2. **Rede de Prestadores**
   - Situação atual: Rede ampla
   - Recomendação: Migrar para rede referenciada
   - Impacto estimado: Redução de 15% em custos
   - Argumento: Manter qualidade com custo otimizado

### Prioridade Média

3. **Carência para Novos Procedimentos**
   - Situação atual: Carência zero
   - Recomendação: Implementar carência de 90 dias para eletivos
   ...

### Pontos de Atenção
- Evitar reduzir cobertura de urgência/emergência
- Manter atendimento oncológico sem coparticipação
```

---

## Padrões de Comunicação

### Estrutura de Mensagens entre Agentes

```python
@dataclass
class AgentMessage:
    """Mensagem trocada entre agentes."""

    sender: str           # ID do agente remetente
    receiver: str         # ID do agente destinatário
    message_type: str     # "request", "response", "error"
    content: dict         # Payload da mensagem
    context: dict         # Contexto compartilhado
    timestamp: datetime
    trace_id: str         # Para rastreabilidade
```

### Contexto Compartilhado

```python
@dataclass
class SharedContext:
    """Contexto compartilhado entre agentes."""

    client_id: str
    contract_id: str
    conversation_id: str
    user_query: str
    retrieved_chunks: List[str]
    cost_data: Optional[dict]
    previous_responses: List[str]
```

---

## Implementação com LangChain

### Estrutura Base de um Agente

```python
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI

class BaseAgent:
    """Classe base para todos os agentes."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: List[BaseTool],
        llm: AzureChatOpenAI
    ):
        self.name = name
        self.tools = tools
        self.llm = llm

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}")
        ])

        agent = create_openai_functions_agent(llm, tools, prompt)
        self.executor = AgentExecutor(agent=agent, tools=tools)

    async def run(self, input: str, context: SharedContext) -> AgentResponse:
        """Executa o agente."""
        result = await self.executor.ainvoke({
            "input": input,
            "context": context.dict()
        })
        return AgentResponse(
            agent_name=self.name,
            output=result["output"],
            trace=result.get("intermediate_steps", [])
        )
```

### Orchestrator com LangGraph (Opcional)

```python
from langgraph.graph import StateGraph, END

class OrchestratorGraph:
    """Orquestrador usando LangGraph para fluxo complexo."""

    def __init__(self, agents: Dict[str, BaseAgent]):
        self.agents = agents
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(OrchestratorState)

        # Nodes
        graph.add_node("analyze_intent", self._analyze_intent)
        graph.add_node("retrieval", self._run_retrieval)
        graph.add_node("contract_analysis", self._run_contract_analyst)
        graph.add_node("cost_analysis", self._run_cost_insights)
        graph.add_node("negotiation", self._run_negotiation)
        graph.add_node("consolidate", self._consolidate)

        # Edges (fluxo)
        graph.add_edge("analyze_intent", "route")
        graph.add_conditional_edges(
            "route",
            self._route_to_agents,
            {
                "retrieval_only": "retrieval",
                "cost_only": "cost_analysis",
                "full_analysis": "retrieval"  # Paralelo
            }
        )
        graph.add_edge("retrieval", "contract_analysis")
        graph.add_edge("contract_analysis", "consolidate")
        graph.add_edge("cost_analysis", "consolidate")
        graph.add_edge("consolidate", END)

        return graph.compile()
```

---

## Observabilidade

### Logging por Agente

```python
import structlog

logger = structlog.get_logger()

class AgentLogger:
    """Logger especializado para agentes."""

    def log_start(self, agent_name: str, input: str, trace_id: str):
        logger.info(
            "agent_started",
            agent=agent_name,
            input_preview=input[:100],
            trace_id=trace_id
        )

    def log_tool_call(self, agent_name: str, tool: str, args: dict):
        logger.info(
            "tool_called",
            agent=agent_name,
            tool=tool,
            args=args
        )

    def log_complete(self, agent_name: str, output: str, duration_ms: int):
        logger.info(
            "agent_completed",
            agent=agent_name,
            output_preview=output[:100],
            duration_ms=duration_ms
        )
```

### Métricas

```python
# Métricas a coletar por agente
metrics = {
    "agent_invocations_total": Counter,      # Total de chamadas
    "agent_duration_seconds": Histogram,      # Latência
    "agent_errors_total": Counter,            # Erros
    "tool_calls_total": Counter,              # Uso de tools
    "tokens_used_total": Counter              # Consumo de tokens
}
```

---

## Testes de Agentes

### Testes Unitários

```python
import pytest
from unittest.mock import Mock

class TestRetrievalAgent:

    @pytest.fixture
    def agent(self):
        mock_search = Mock()
        mock_search.return_value = [
            {"content": "Cláusula de teste", "page": 1}
        ]
        return RetrievalAgent(search_client=mock_search)

    def test_search_returns_results(self, agent):
        result = agent.run(
            query="reajuste anual",
            client_id="test",
            contract_id="contract-1"
        )
        assert len(result.chunks) > 0

    def test_filters_by_client(self, agent):
        # Verificar que filtro de client_id é aplicado
        pass
```

### Testes de Integração

```python
class TestMultiAgentFlow:

    @pytest.fixture
    def orchestrator(self):
        return Orchestrator(
            agents={
                "retrieval": RetrievalAgent(...),
                "contract_analyst": ContractAnalyst(...),
                "cost_insights": CostInsights(...),
                "negotiation": NegotiationAdvisor(...)
            }
        )

    async def test_full_negotiation_flow(self, orchestrator):
        """Testa fluxo completo de análise para renegociação."""
        result = await orchestrator.run(
            query="O que devo renegociar com a operadora?",
            client_id="test-client",
            contract_id="contract-1"
        )

        # Verifica que todos os agentes relevantes foram chamados
        assert "retrieval" in result.agents_called
        assert "cost_insights" in result.agents_called
        assert "negotiation_advisor" in result.agents_called

        # Verifica qualidade da resposta
        assert "Recomendações" in result.output
        assert "Impacto estimado" in result.output
```

---

## Referências

- [LangChain Agents](https://python.langchain.com/docs/modules/agents/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Azure OpenAI Function Calling](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling)
- [Multi-Agent Systems](https://www.anthropic.com/research/multi-agent-systems)
