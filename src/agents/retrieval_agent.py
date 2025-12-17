"""
Retrieval Agent - Agente de recuperação de informações.

Este agente é responsável por:
- Receber queries e contexto (client_id, contract_id)
- Executar buscas híbridas no Azure AI Search
- Filtrar e rankear resultados por relevância
- Retornar chunks relevantes com metadados para outros agentes

O Retrieval Agent é tipicamente o primeiro agente a ser chamado
pelo Orchestrator quando uma pergunta requer consulta a documentos.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.context import ContextManager, get_context_manager
from src.agents.execution_logger import (
    AgentExecutionLogger,
    ExecutionTracker,
    get_execution_tracker,
)
from src.agents.search_tools import (
    HybridSearchTool,
    KeywordSearchTool,
    SimilarChunksTool,
    VectorSearchTool,
    register_search_tools,
)
from src.agents.tools import ToolRegistry, get_tool_registry
from src.config.logging import get_logger
from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
)
from src.search.search_service import SearchMode, get_search_service

logger = get_logger(__name__)


# System prompt para o Retrieval Agent
RETRIEVAL_AGENT_SYSTEM_PROMPT = """Você é um agente especializado em recuperação de informações de contratos de planos de saúde.

Seu papel é:
1. Analisar a pergunta do usuário e identificar os termos e conceitos relevantes
2. Formular queries de busca eficientes
3. Executar buscas nos documentos disponíveis
4. Filtrar e selecionar os trechos mais relevantes
5. Retornar os resultados com metadados de localização

Ao buscar informações:
- Use busca híbrida (search_hybrid) para a maioria das consultas
- Use busca por keywords (search_keyword) quando procurar termos técnicos específicos
- Use busca vetorial (search_vector) quando a pergunta for conceitual
- Sempre filtre pelo client_id e contract_id quando fornecidos

Ao retornar resultados:
- Priorize chunks com maior relevância (score)
- Inclua informações de localização (página, seção)
- Agrupe resultados de seções relacionadas quando fizer sentido
- Limite a 5-10 chunks mais relevantes para não sobrecarregar o contexto

Você deve sempre usar as ferramentas disponíveis para buscar informações.
Nunca invente ou assuma informações que não foram encontradas nos documentos."""


class RetrievalAgent(BaseAgent):
    """
    Agente de recuperação de informações.

    Especializado em buscar e recuperar chunks relevantes
    de contratos indexados no Azure AI Search.

    Exemplo:
        agent = RetrievalAgent()
        result = await agent.execute(
            query="Qual o prazo de carência para internação?",
            client_id="cliente-123",
            contract_id="contrato-456",
        )
        # result.structured_output contém os chunks encontrados
    """

    agent_type = AgentType.RETRIEVAL
    agent_name = "retrieval_agent"
    description = (
        "Agente de recuperação que busca informações relevantes "
        "em contratos de planos de saúde usando busca híbrida."
    )
    system_prompt = RETRIEVAL_AGENT_SYSTEM_PROMPT

    # Configurações do LLM para este agente
    use_mini_model = True  # Retrieval usa modelo rápido para decisões de busca
    temperature = 0.1  # Baixa temperatura para respostas mais determinísticas
    max_tokens = 1500

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        context_manager: Optional[ContextManager] = None,
        execution_tracker: Optional[ExecutionTracker] = None,
        auto_register_tools: bool = True,
    ):
        """
        Inicializa o Retrieval Agent.

        Args:
            tool_registry: Registro de ferramentas
            context_manager: Gerenciador de contexto
            execution_tracker: Rastreador de execuções
            auto_register_tools: Se True, registra ferramentas automaticamente
        """
        # Registrar ferramentas de busca se necessário
        registry = tool_registry or get_tool_registry()
        if auto_register_tools:
            self._ensure_tools_registered(registry)

        super().__init__(
            tool_registry=registry,
            context_manager=context_manager,
            execution_tracker=execution_tracker,
        )

        self._logger.info("RetrievalAgent inicializado")

    def _ensure_tools_registered(self, registry: ToolRegistry) -> None:
        """Garante que as ferramentas de busca estão registradas."""
        required_tools = [
            "search_hybrid",
            "search_vector",
            "search_keyword",
            "find_similar_chunks",
        ]

        # Verificar quais ferramentas estão faltando
        existing_tools = registry.list_tools()
        missing_tools = [t for t in required_tools if t not in existing_tools]

        if missing_tools:
            self._logger = get_logger(f"agent.{self.agent_name}")
            self._logger.info(
                "Registrando ferramentas de busca",
                missing_tools=missing_tools,
            )
            register_search_tools(registry)

    def get_tools(self) -> List[str]:
        """Retorna as ferramentas disponíveis para este agente."""
        return [
            "search_hybrid",
            "search_vector",
            "search_keyword",
            "find_similar_chunks",
        ]

    async def process(self, context: AgentContext) -> AgentExecutionResult:
        """
        Processa uma query de recuperação.

        Este método pode funcionar de duas formas:
        1. Modo automático: usa LLM para decidir qual busca fazer
        2. Modo direto: executa busca híbrida diretamente (mais rápido)

        Args:
            context: Contexto de execução com query e filtros

        Returns:
            AgentExecutionResult com chunks encontrados
        """
        exec_logger = self._create_execution_logger(context.execution_id)

        try:
            # Para o Retrieval Agent, geralmente é mais eficiente
            # fazer busca direta ao invés de passar pelo LLM
            use_direct_search = context.metadata.get("direct_search", True)

            if use_direct_search:
                return await self._direct_search(context, exec_logger)
            else:
                return await self._llm_guided_search(context, exec_logger)

        except Exception as e:
            self._logger.error(
                "Erro no processamento do RetrievalAgent",
                error=str(e),
                exc_info=True,
            )
            return exec_logger.finalize(
                status=AgentStatus.FAILED,
                error=str(e),
            )

    async def _direct_search(
        self,
        context: AgentContext,
        exec_logger: AgentExecutionLogger,
    ) -> AgentExecutionResult:
        """
        Executa busca direta sem passar pelo LLM.

        Mais rápido e eficiente para casos simples.

        Args:
            context: Contexto de execução
            exec_logger: Logger de execução

        Returns:
            AgentExecutionResult com chunks
        """
        with exec_logger.step("Executando busca híbrida direta", action="tool_call"):
            # Parâmetros de busca
            query = context.query
            client_id = context.client_id
            document_id = context.contract_id
            top = context.metadata.get("top_k", 10)

            # Usar a ferramenta de busca híbrida
            search_tool = self._tool_registry.get("search_hybrid")

            if search_tool is None:
                # Fallback: usar SearchService diretamente
                search_service = get_search_service()
                response = await search_service.hybrid_search(
                    query=query,
                    client_id=client_id,
                    document_id=document_id,
                    top=top,
                )
                chunks = [r.to_dict() for r in response.results]
                search_time_ms = response.search_time_ms
            else:
                # Usar a ferramenta
                result = await search_tool.execute(
                    query=query,
                    client_id=client_id,
                    document_id=document_id,
                    top=top,
                )
                chunks = result.get("chunks", [])
                search_time_ms = result.get("search_time_ms", 0)

            # Registrar no contexto
            self._context_manager.set_retrieved_chunks(
                context.execution_id,
                chunks,
            )

            # Preparar saída estruturada
            structured_output = {
                "chunks": chunks,
                "chunk_count": len(chunks),
                "query": query,
                "client_id": client_id,
                "document_id": document_id,
                "search_time_ms": search_time_ms,
            }

            # Extrair fontes para citação
            sources = self._extract_sources_from_chunks(chunks)

            # Adicionar fontes ao logger
            for source in sources:
                exec_logger.add_source(source)

            # Gerar resposta textual resumida
            response_text = self._generate_summary(chunks, query)

        return exec_logger.finalize(
            status=AgentStatus.COMPLETED,
            response=response_text,
            structured_output=structured_output,
        )

    async def _llm_guided_search(
        self,
        context: AgentContext,
        exec_logger: AgentExecutionLogger,
    ) -> AgentExecutionResult:
        """
        Executa busca guiada pelo LLM.

        O LLM decide quais buscas fazer e como combinar resultados.
        Mais flexível mas mais lento.

        Args:
            context: Contexto de execução
            exec_logger: Logger de execução

        Returns:
            AgentExecutionResult com chunks
        """
        # Adicionar contexto ao system prompt
        enhanced_context = self._enhance_context(context)

        with exec_logger.step("Análise e busca guiada por LLM", action="think"):
            # Executar o loop de agente padrão
            response = await self._run_agent_loop(
                context=enhanced_context,
                exec_logger=exec_logger,
                max_iterations=8,  # Aumentado para buscas mais complexas
            )

        # Extrair chunks do contexto (foram armazenados pelas ferramentas)
        chunks = self._context_manager.get_shared_data(
            context.execution_id,
            "retrieved_chunks",
            default=[],
        )

        # Se não tiver chunks no shared_data, pegar do contexto
        if not chunks and context.retrieved_chunks:
            chunks = context.retrieved_chunks

        # Preparar saída estruturada
        structured_output = {
            "chunks": chunks,
            "chunk_count": len(chunks),
            "query": context.query,
            "client_id": context.client_id,
            "document_id": context.contract_id,
        }

        sources = self._extract_sources_from_chunks(chunks)

        return exec_logger.finalize(
            status=AgentStatus.COMPLETED,
            response=response,
            structured_output=structured_output,
            sources=sources,
        )

    def _enhance_context(self, context: AgentContext) -> AgentContext:
        """
        Adiciona informações adicionais ao contexto.

        Args:
            context: Contexto original

        Returns:
            Contexto enriquecido
        """
        # Adicionar informações sobre filtros disponíveis à query
        filter_info = []
        if context.client_id:
            filter_info.append(f"client_id: {context.client_id}")
        if context.contract_id:
            filter_info.append(f"document_id: {context.contract_id}")

        if filter_info:
            enhanced_query = (
                f"{context.query}\n\n"
                f"[Filtros de busca: {', '.join(filter_info)}]"
            )

            # Atualizar a última mensagem do usuário
            if context.messages:
                for msg in reversed(context.messages):
                    if msg.role == "user":
                        msg.content = enhanced_query
                        break

        return context

    def _generate_summary(self, chunks: List[Dict[str, Any]], query: str) -> str:
        """
        Gera um resumo textual dos resultados da busca.

        Args:
            chunks: Lista de chunks encontrados
            query: Query original

        Returns:
            Texto resumindo os resultados
        """
        if not chunks:
            return f"Nenhum resultado encontrado para: '{query}'"

        # Resumo básico
        summary_parts = [
            f"Encontrados {len(chunks)} trechos relevantes para: '{query}'\n",
        ]

        # Listar principais fontes
        seen_sources = set()
        for chunk in chunks[:5]:
            source_key = (
                chunk.get("document_id", ""),
                chunk.get("section_title", ""),
            )
            if source_key not in seen_sources:
                seen_sources.add(source_key)

                page = chunk.get("page_number", "?")
                section = chunk.get("section_title", "")
                score = chunk.get("score", 0)

                source_info = f"- Página {page}"
                if section:
                    source_info += f", Seção: {section}"
                source_info += f" (relevância: {score:.2f})"

                summary_parts.append(source_info)

        return "\n".join(summary_parts)

    async def search(
        self,
        query: str,
        client_id: str,
        contract_id: Optional[str] = None,
        mode: SearchMode = SearchMode.HYBRID,
        top: int = 10,
    ) -> Dict[str, Any]:
        """
        Método de conveniência para executar busca diretamente.

        Útil para uso programático sem passar pelo sistema de agentes.

        Args:
            query: Texto da busca
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            mode: Modo de busca
            top: Número máximo de resultados

        Returns:
            Dicionário com chunks e metadados
        """
        search_service = get_search_service()

        response = await search_service.search(
            query=query,
            client_id=client_id,
            document_id=contract_id,
            mode=mode,
            top=top,
        )

        chunks = [r.to_dict() for r in response.results]

        return {
            "chunks": chunks,
            "chunk_count": len(chunks),
            "query": query,
            "mode": mode.value,
            "search_time_ms": response.search_time_ms,
        }

    async def multi_query_search(
        self,
        queries: List[str],
        client_id: str,
        contract_id: Optional[str] = None,
        top_per_query: int = 5,
        deduplicate: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa múltiplas queries e combina resultados.

        Útil para expandir a busca com diferentes formulações
        da mesma pergunta.

        Args:
            queries: Lista de queries a executar
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            top_per_query: Resultados por query
            deduplicate: Se True, remove duplicatas

        Returns:
            Dicionário com chunks combinados
        """
        import asyncio

        search_service = get_search_service()
        all_chunks = []
        seen_ids = set()

        # Executar buscas em paralelo
        tasks = [
            search_service.hybrid_search(
                query=q,
                client_id=client_id,
                document_id=contract_id,
                top=top_per_query,
            )
            for q in queries
        ]

        responses = await asyncio.gather(*tasks)

        # Combinar resultados
        for response in responses:
            for result in response.results:
                if deduplicate and result.id in seen_ids:
                    continue
                seen_ids.add(result.id)
                all_chunks.append(result.to_dict())

        # Re-rankear por score
        all_chunks.sort(
            key=lambda c: c.get("reranker_score") or c.get("score", 0),
            reverse=True,
        )

        return {
            "chunks": all_chunks,
            "chunk_count": len(all_chunks),
            "queries": queries,
            "deduplicated": deduplicate,
        }


# Factory function
def create_retrieval_agent(
    tool_registry: Optional[ToolRegistry] = None,
) -> RetrievalAgent:
    """
    Cria uma instância do RetrievalAgent.

    Args:
        tool_registry: Registry de ferramentas (opcional)

    Returns:
        Instância configurada do RetrievalAgent
    """
    return RetrievalAgent(tool_registry=tool_registry)
