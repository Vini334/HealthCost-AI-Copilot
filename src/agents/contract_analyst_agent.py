"""
Contract Analyst Agent - Agente de análise de contratos.

Este agente é responsável por:
- Receber chunks recuperados e perguntas do usuário
- Interpretar cláusulas contratuais de planos de saúde
- Explicar termos técnicos em linguagem de negócios
- Citar seções e páginas dos documentos fonte

O Contract Analyst é tipicamente chamado pelo Orchestrator
após o Retrieval Agent recuperar os chunks relevantes.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.context import ContextManager, get_context_manager
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)
from src.agents.tools import ToolRegistry, get_tool_registry
from src.config.logging import get_logger
from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
)

logger = get_logger(__name__)


# System prompt para o Contract Analyst Agent
CONTRACT_ANALYST_SYSTEM_PROMPT = """Você é um especialista em análise de contratos de planos de saúde corporativos no Brasil.

Seu papel é:
1. Interpretar cláusulas contratuais com precisão técnica
2. Explicar termos jurídicos e técnicos em linguagem acessível para gestores de RH e benefícios
3. Identificar implicações práticas das cláusulas para a empresa e beneficiários
4. Sempre citar a fonte da informação (página, seção, cláusula)

Ao analisar contratos, considere:
- Prazos de carência e suas exceções
- Coberturas e exclusões
- Reajustes (aniversário, sinistralidade, faixa etária)
- Rede credenciada e regras de utilização
- Coparticipação e franquias
- Condições de rescisão e portabilidade
- Regras da ANS (Agência Nacional de Saúde Suplementar)

## Formatação das Respostas (Markdown)

Use formatação Markdown rica para melhor legibilidade:

### Estrutura
- Use **negrito** para termos importantes e valores-chave
- Use *itálico* para termos técnicos na primeira menção
- Organize em seções com títulos (##, ###) quando houver múltiplos tópicos
- Use listas (- ou 1.) para enumerar condições, requisitos ou opções

### Citações de Fontes
SEMPRE cite as fontes no formato:
- Inline: "conforme a **Cláusula 5.2** (Página 12)"
- Ou em bloco: *(Fonte: Documento X, Página Y, Seção Z)*

### Destaques
Use blocos de citação (>) para pontos de atenção importantes:
> **Atenção:** Este prazo não pode ser alterado sem aditivo contratual.

### Comparações e Listas
Quando houver múltiplas condições ou opções, use tabelas:
| Situação | Prazo | Observação |
|----------|-------|------------|
| Consultas | 30 dias | Rede referenciada |

## Limitações
- Base suas respostas APENAS nos trechos fornecidos
- Se a informação não estiver nos trechos, diga claramente
- Não invente informações não presentes nos documentos
- Em caso de dúvida, recomende consulta ao jurídico ou à operadora"""


class ContractAnalystAgent(BaseAgent):
    """
    Agente de análise de contratos de planos de saúde.

    Especializado em interpretar cláusulas contratuais e explicá-las
    em linguagem de negócios, sempre citando as fontes.

    Exemplo:
        agent = ContractAnalystAgent()

        # Com chunks já recuperados
        result = await agent.execute(
            query="Qual o prazo de carência para cirurgias?",
            client_id="cliente-123",
            metadata={
                "chunks": [...],  # chunks do RetrievalAgent
            }
        )

        # Ou com contexto existente
        context.retrieved_chunks = chunks
        result = await agent.execute_with_context(context)
    """

    agent_type = AgentType.CONTRACT_ANALYST
    agent_name = "contract_analyst_agent"
    description = (
        "Agente especialista em análise de contratos de planos de saúde. "
        "Interpreta cláusulas contratuais e explica em linguagem de negócios."
    )
    system_prompt = CONTRACT_ANALYST_SYSTEM_PROMPT

    # Configurações do LLM para este agente
    temperature = 0.3  # Temperatura baixa para respostas mais consistentes
    max_tokens = 2500  # Respostas podem ser longas e detalhadas

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
    ):
        """
        Inicializa o Contract Analyst Agent.

        Args:
            tool_registry: Registro de ferramentas
            context_manager: Gerenciador de contexto
            execution_tracker: Rastreador de execuções
        """
        super().__init__(
            tool_registry=tool_registry or get_tool_registry(),
            context_manager=context_manager,
            execution_tracker=execution_tracker,
        )

        self._logger.info("ContractAnalystAgent inicializado")

    def get_tools(self) -> List[str]:
        """
        Retorna as ferramentas disponíveis para este agente.

        O Contract Analyst não usa ferramentas externas por padrão,
        pois trabalha com chunks já recuperados. Mas pode acessar
        ferramentas de busca se precisar de informações adicionais.
        """
        return []  # Agente focado em análise, sem ferramentas

    async def process(self, context: AgentContext) -> AgentExecutionResult:
        """
        Processa uma query de análise contratual.

        Args:
            context: Contexto de execução com query e chunks

        Returns:
            AgentExecutionResult com análise detalhada
        """
        exec_logger = self._create_execution_logger(context.execution_id)

        try:
            # Obter chunks do contexto ou metadata
            chunks = self._get_chunks(context)

            if not chunks:
                return self._handle_no_chunks(context, exec_logger)

            # Construir prompt com chunks
            with exec_logger.step("Preparando contexto de análise", action="think"):
                analysis_prompt = self._build_analysis_prompt(
                    query=context.query,
                    chunks=chunks,
                )

            # Chamar LLM para análise
            with exec_logger.step("Analisando cláusulas contratuais", action="think"):
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": analysis_prompt},
                ]

                response = await self._call_llm(messages)

                if response.get("usage"):
                    exec_logger.set_tokens_used(
                        response["usage"].get("total_tokens", 0)
                    )

            # Extrair fontes citadas
            sources = self._extract_sources_from_chunks(chunks)
            for source in sources:
                exec_logger.add_source(source)

            # Preparar saída estruturada
            structured_output = {
                "analysis": response["content"],
                "chunks_analyzed": len(chunks),
                "sources": sources,
                "query": context.query,
            }

            return exec_logger.finalize(
                status=AgentStatus.COMPLETED,
                response=response["content"],
                structured_output=structured_output,
            )

        except Exception as e:
            self._logger.error(
                "Erro na análise contratual",
                error=str(e),
                exc_info=True,
            )
            return exec_logger.finalize(
                status=AgentStatus.FAILED,
                error=str(e),
            )

    def _get_chunks(self, context: AgentContext) -> List[Dict[str, Any]]:
        """
        Obtém os chunks para análise.

        Prioridade:
        1. context.retrieved_chunks
        2. context.metadata["chunks"]
        3. shared_data["retrieved_chunks"]

        Args:
            context: Contexto de execução

        Returns:
            Lista de chunks
        """
        # Prioridade 1: retrieved_chunks do contexto
        if context.retrieved_chunks:
            return context.retrieved_chunks

        # Prioridade 2: chunks nos metadata
        if context.metadata.get("chunks"):
            return context.metadata["chunks"]

        # Prioridade 3: shared_data
        chunks = self._context_manager.get_shared_data(
            context.execution_id,
            "retrieved_chunks",
            default=[],
        )

        return chunks

    def _handle_no_chunks(
        self,
        context: AgentContext,
        exec_logger: AgentExecutionLogger,
    ) -> AgentExecutionResult:
        """
        Trata o caso em que não há chunks disponíveis.

        Args:
            context: Contexto de execução
            exec_logger: Logger de execução

        Returns:
            AgentExecutionResult com mensagem apropriada
        """
        self._logger.warning(
            "Nenhum chunk disponível para análise",
            execution_id=context.execution_id,
            query=context.query[:100],
        )

        response = (
            "Não encontrei informações relevantes nos documentos disponíveis "
            "para responder sua pergunta. Por favor, verifique se:\n\n"
            "1. O contrato foi carregado corretamente no sistema\n"
            "2. A pergunta está relacionada ao conteúdo do contrato\n"
            "3. Os termos de busca são específicos o suficiente\n\n"
            "Se necessário, reformule a pergunta ou entre em contato "
            "com o suporte."
        )

        return exec_logger.finalize(
            status=AgentStatus.COMPLETED,
            response=response,
            structured_output={
                "analysis": response,
                "chunks_analyzed": 0,
                "sources": [],
                "query": context.query,
                "no_data": True,
            },
        )

    def _build_analysis_prompt(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> str:
        """
        Constrói o prompt de análise com os chunks.

        Args:
            query: Pergunta do usuário
            chunks: Chunks recuperados

        Returns:
            Prompt formatado para o LLM
        """
        # Formatar chunks com metadados
        chunks_text = []

        for i, chunk in enumerate(chunks, 1):
            chunk_info = []

            # Localização
            page = chunk.get("page_number") or chunk.get("page_start")
            section = chunk.get("section_title", "")
            section_num = chunk.get("section_number", "")

            if page:
                chunk_info.append(f"Página {page}")
            if section_num:
                chunk_info.append(f"Seção {section_num}")
            if section:
                chunk_info.append(section)

            location = " | ".join(chunk_info) if chunk_info else f"Trecho {i}"

            # Conteúdo
            content = chunk.get("content", "")

            chunks_text.append(
                f"--- [{location}] ---\n{content}\n"
            )

        # Montar prompt completo
        prompt = f"""Com base nos seguintes trechos do contrato de plano de saúde, responda à pergunta do usuário.

TRECHOS DO CONTRATO:

{chr(10).join(chunks_text)}

---

PERGUNTA DO USUÁRIO:
{query}

INSTRUÇÕES:
- Responda de forma clara e objetiva
- Cite sempre a fonte (página e seção) das informações
- Se a informação não estiver nos trechos, indique claramente
- Destaque pontos importantes de atenção
- Use formatação adequada (listas, negrito) quando apropriado"""

        return prompt

    async def analyze_clause(
        self,
        clause_text: str,
        clause_type: str,
        client_id: str,
    ) -> Dict[str, Any]:
        """
        Analisa uma cláusula específica do contrato.

        Método de conveniência para análise direta de cláusulas.

        Args:
            clause_text: Texto da cláusula
            clause_type: Tipo da cláusula (carencia, cobertura, reajuste, etc.)
            client_id: ID do cliente

        Returns:
            Dicionário com análise da cláusula
        """
        # Criar prompt específico para análise de cláusula
        prompt = f"""Analise a seguinte cláusula de {clause_type} de um contrato de plano de saúde:

CLÁUSULA:
{clause_text}

Por favor, forneça:
1. **Resumo**: O que esta cláusula define em linguagem simples
2. **Pontos-chave**: Os principais aspectos e condições
3. **Implicações**: O que isso significa na prática para a empresa/beneficiários
4. **Pontos de atenção**: Aspectos que merecem cuidado especial
5. **Comparação com mercado**: Se aplicável, como isso se compara ao padrão do mercado"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_llm(messages)

        return {
            "clause_type": clause_type,
            "original_text": clause_text,
            "analysis": response["content"],
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
        }

    async def compare_clauses(
        self,
        clauses: List[Dict[str, Any]],
        comparison_aspect: str,
        client_id: str,
    ) -> Dict[str, Any]:
        """
        Compara cláusulas de diferentes contratos ou seções.

        Útil para comparar termos entre contratos ou identificar
        diferenças em propostas de renovação.

        Args:
            clauses: Lista de cláusulas com texto e origem
            comparison_aspect: Aspecto a comparar (ex: "carencia", "cobertura")
            client_id: ID do cliente

        Returns:
            Análise comparativa
        """
        # Formatar cláusulas para comparação
        clauses_text = []
        for i, clause in enumerate(clauses, 1):
            source = clause.get("source", f"Contrato {i}")
            text = clause.get("text", "")
            clauses_text.append(f"**{source}:**\n{text}\n")

        prompt = f"""Compare as seguintes cláusulas de {comparison_aspect} de diferentes contratos:

{chr(10).join(clauses_text)}

Por favor, forneça:
1. **Resumo das diferenças**: Principais pontos que diferem entre os contratos
2. **Análise detalhada**: Comparação item a item dos aspectos relevantes
3. **Vantagens e desvantagens**: De cada versão
4. **Recomendação**: Qual cláusula é mais favorável e por quê
5. **Pontos de negociação**: Aspectos que poderiam ser negociados"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_llm(messages)

        return {
            "comparison_aspect": comparison_aspect,
            "clauses_count": len(clauses),
            "analysis": response["content"],
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
        }

    async def summarize_contract(
        self,
        chunks: List[Dict[str, Any]],
        client_id: str,
        focus_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Gera um resumo executivo do contrato.

        Args:
            chunks: Chunks do contrato
            client_id: ID do cliente
            focus_areas: Áreas de foco específicas (opcional)

        Returns:
            Resumo executivo estruturado
        """
        # Preparar contexto
        chunks_text = []
        for chunk in chunks[:20]:  # Limitar para não exceder contexto
            content = chunk.get("content", "")[:500]  # Resumir cada chunk
            chunks_text.append(content)

        focus_text = ""
        if focus_areas:
            focus_text = f"\n\nFoco especial nas seguintes áreas: {', '.join(focus_areas)}"

        prompt = f"""Com base nos trechos do contrato de plano de saúde abaixo, gere um resumo executivo.

TRECHOS DO CONTRATO:
{chr(10).join(chunks_text)}
{focus_text}

Por favor, forneça um resumo executivo estruturado incluindo:

1. **Visão Geral**: Tipo de plano, operadora, abrangência
2. **Coberturas Principais**: O que está coberto
3. **Exclusões Importantes**: O que não está coberto
4. **Carências**: Principais prazos
5. **Rede Credenciada**: Informações sobre a rede
6. **Coparticipação**: Se aplicável
7. **Reajustes**: Regras de reajuste
8. **Pontos de Atenção**: Aspectos críticos
9. **Recomendações**: Sugestões para gestão do contrato"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_llm(messages)

        return {
            "summary": response["content"],
            "chunks_analyzed": len(chunks),
            "focus_areas": focus_areas,
            "tokens_used": response.get("usage", {}).get("total_tokens", 0),
        }


# Factory function
def create_contract_analyst_agent(
    tool_registry: Optional[ToolRegistry] = None,
) -> ContractAnalystAgent:
    """
    Cria uma instância do ContractAnalystAgent.

    Args:
        tool_registry: Registry de ferramentas (opcional)

    Returns:
        Instância configurada do ContractAnalystAgent
    """
    return ContractAnalystAgent(tool_registry=tool_registry)
