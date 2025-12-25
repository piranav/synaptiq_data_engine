"""
Query Agent - Main orchestrator for the knowledge retrieval pipeline.

Coordinates intent classification, strategy selection, retrieval execution,
and response synthesis using OpenAI Agents SDK.
"""

import os
from pathlib import Path
from typing import Optional, AsyncIterator
import structlog

from config.settings import get_settings

# Set OPENAI_API_KEY from settings for the OpenAI Agents SDK
# The SDK reads this from the environment, not from a config object
_settings = get_settings()
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _settings.openai_api_key

from agents import Agent, Runner
from agents.result import RunResultStreaming

from synaptiq.storage.fuseki import FusekiStore
from synaptiq.storage.qdrant import QdrantStore
from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.ontology.namespaces import get_sparql_prefixes

from .context import AgentContext
from .schemas import (
    IntentType,
    IntentClassification,
    RetrievalStrategy,
    QueryResponse,
    Citation,
    RetrievalMetadata,
)
from .prompts import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
    RESPONSE_SYNTHESIZER_SYSTEM_PROMPT,
    ORCHESTRATOR_SYSTEM_PROMPT,
)
from .tools import vector_search, get_concept_details
from .sparql_agent import create_sparql_agent, load_ontology_schema
from .session import get_session

logger = structlog.get_logger(__name__)


class QueryAgent:
    """
    Main query agent that orchestrates the retrieval pipeline.
    
    Components:
    1. Intent Classifier - Determines query type
    2. Strategy Selector - Maps intent to retrieval strategy
    3. SPARQL Agent - Queries knowledge graph
    4. Vector Tool - Searches embeddings
    5. Response Synthesizer - Generates final response
    """
    
    def __init__(
        self,
        fuseki_store: Optional[FusekiStore] = None,
        qdrant_store: Optional[QdrantStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize the query agent.
        
        Args:
            fuseki_store: SPARQL client (creates new if not provided)
            qdrant_store: Vector store client (creates new if not provided)
            embedding_generator: Embeddings generator (creates new if not provided)
        """
        self.fuseki = fuseki_store or FusekiStore()
        self.qdrant = qdrant_store or QdrantStore()
        self.embedder = embedding_generator or EmbeddingGenerator()
        
        # Load ontology schema
        self.ontology_schema = load_ontology_schema()
        self.prefixes = get_sparql_prefixes()
        
        # Create sub-agents
        self._init_agents()
        
        logger.info("QueryAgent initialized")
    
    def _init_agents(self):
        """Initialize all sub-agents."""
        # Intent Classifier
        self.intent_classifier = Agent[AgentContext](
            name="Intent Classifier",
            instructions=INTENT_CLASSIFIER_SYSTEM_PROMPT,
            model="gpt-4.1",
            output_type=IntentClassification,
        )
        
        # SPARQL Agent
        self.sparql_agent = create_sparql_agent(
            ontology_schema=self.ontology_schema,
            prefixes=self.prefixes,
        )
        
        # Response Synthesizer
        self.synthesizer = Agent[AgentContext](
            name="Response Synthesizer",
            instructions=RESPONSE_SYNTHESIZER_SYSTEM_PROMPT,
            model="gpt-4.1",
            output_type=QueryResponse,
        )
        
        # Main Orchestrator
        self.orchestrator = Agent[AgentContext](
            name="Query Orchestrator",
            instructions=ORCHESTRATOR_SYSTEM_PROMPT,
            model="gpt-4.1",
            tools=[
                vector_search,
                get_concept_details,
                self.sparql_agent.as_tool(
                    tool_name="query_knowledge_graph",
                    tool_description="Query the user's knowledge graph using SPARQL. Use this for definitions, relationships, and source-based lookups.",
                ),
            ],
        )
    
    def _create_context(self, user_id: str) -> AgentContext:
        """Create agent context for a request."""
        return AgentContext(
            user_id=user_id,
            fuseki_store=self.fuseki,
            qdrant_store=self.qdrant,
            embedding_generator=self.embedder,
            ontology_schema=self.ontology_schema,
        )
    
    def _select_strategy(self, intent: IntentClassification) -> RetrievalStrategy:
        """Map intent to retrieval strategy."""
        mapping = {
            IntentType.DEFINITION: RetrievalStrategy.GRAPH_FIRST,
            IntentType.EXPLORATION: RetrievalStrategy.GRAPH_FIRST,
            IntentType.RELATIONSHIP: RetrievalStrategy.GRAPH_ONLY,
            IntentType.SOURCE_RECALL: RetrievalStrategy.GRAPH_ONLY,
            IntentType.SEMANTIC_SEARCH: RetrievalStrategy.VECTOR_FIRST,
            IntentType.GENERAL: RetrievalStrategy.LLM_ONLY,
        }
        return mapping.get(intent.intent, RetrievalStrategy.HYBRID)
    
    async def _execute_strategy(
        self,
        strategy: RetrievalStrategy,
        query: str,
        context: AgentContext,
        intent: IntentClassification,
    ) -> dict:
        """
        Execute the selected retrieval strategy with fallbacks.
        
        Returns dict with:
        - source: 'graph', 'vector', or 'llm_knowledge'
        - results: Retrieved data
        - fallback_chain: List of sources tried
        """
        fallback_chain = []
        
        if strategy == RetrievalStrategy.LLM_ONLY:
            return {
                "source": "llm_knowledge",
                "results": [],
                "fallback_chain": fallback_chain,
            }
        
        if strategy in (RetrievalStrategy.GRAPH_FIRST, RetrievalStrategy.GRAPH_ONLY):
            # Try graph first
            fallback_chain.append("graph")
            graph_results = await self._query_graph(query, context, intent)
            
            if graph_results:
                return {
                    "source": "graph",
                    "results": graph_results,
                    "fallback_chain": fallback_chain,
                }
            
            # Fallback to vector (unless GRAPH_ONLY)
            if strategy == RetrievalStrategy.GRAPH_FIRST:
                fallback_chain.append("vector")
                vector_results = await self._query_vector(query, context)
                
                if vector_results:
                    return {
                        "source": "vector",
                        "results": vector_results,
                        "fallback_chain": fallback_chain,
                    }
        
        elif strategy == RetrievalStrategy.VECTOR_FIRST:
            # Try vector first
            fallback_chain.append("vector")
            vector_results = await self._query_vector(query, context)
            
            if vector_results:
                # Enrich with graph data
                fallback_chain.append("graph")
                graph_enrichment = await self._enrich_with_graph(
                    vector_results, context, intent
                )
                
                return {
                    "source": "vector",
                    "results": vector_results,
                    "graph_enrichment": graph_enrichment,
                    "fallback_chain": fallback_chain,
                }
            
            # Fallback to graph
            fallback_chain.append("graph")
            graph_results = await self._query_graph(query, context, intent)
            
            if graph_results:
                return {
                    "source": "graph",
                    "results": graph_results,
                    "fallback_chain": fallback_chain,
                }
        
        elif strategy == RetrievalStrategy.HYBRID:
            # Execute both in parallel (simplified - sequential for now)
            fallback_chain.extend(["graph", "vector"])
            
            graph_results = await self._query_graph(query, context, intent)
            vector_results = await self._query_vector(query, context)
            
            if graph_results or vector_results:
                return {
                    "source": "hybrid",
                    "results": {
                        "graph": graph_results,
                        "vector": vector_results,
                    },
                    "fallback_chain": fallback_chain,
                }
        
        # Ultimate fallback: LLM knowledge
        fallback_chain.append("llm_knowledge")
        return {
            "source": "llm_knowledge",
            "results": [],
            "fallback_chain": fallback_chain,
        }
    
    async def _query_graph(
        self,
        query: str,
        context: AgentContext,
        intent: IntentClassification,
    ) -> list[dict]:
        """Query the knowledge graph based on intent and entities."""
        try:
            results = []
            
            # Look up each entity
            for entity in intent.entities:
                concept_uri = await context.fuseki_store.concept_exists(
                    context.user_id, entity
                )
                
                if concept_uri:
                    details = await context.fuseki_store.get_concept_with_definition(
                        context.user_id, concept_uri
                    )
                    relationships = await context.fuseki_store.get_concept_relationships(
                        context.user_id, concept_uri
                    )
                    
                    results.append({
                        "uri": concept_uri,
                        "entity": entity,
                        "details": details,
                        "relationships": relationships,
                    })
            
            return results
            
        except Exception as e:
            logger.error("Graph query failed", error=str(e))
            return []
    
    async def _query_vector(
        self,
        query: str,
        context: AgentContext,
        top_k: int = 5,
    ) -> list[dict]:
        """Query the vector store for similar content."""
        try:
            # Generate query embedding
            query_vector = await context.embedding_generator.generate_single(query)
            
            # Search
            results = await context.qdrant_store.search(
                query_vector=query_vector,
                user_id=context.user_id,
                limit=top_k,
            )
            
            logger.info("Vector search results", count=len(results), results=results)
            
            return results
            
        except Exception as e:
            logger.error("Vector query failed", error=str(e))
            return []
    
    async def _enrich_with_graph(
        self,
        vector_results: list[dict],
        context: AgentContext,
        intent: IntentClassification,
    ) -> list[dict]:
        """Enrich vector results with graph data."""
        enrichments = []
        
        # Extract concepts mentioned in vector results
        for result in vector_results[:3]:  # Limit to top 3
            concepts = result.get("payload", {}).get("concepts", [])
            
            for concept in concepts[:2]:  # Limit concepts per result
                try:
                    concept_uri = await context.fuseki_store.concept_exists(
                        context.user_id, concept
                    )
                    if concept_uri:
                        details = await context.fuseki_store.get_concept_with_definition(
                            context.user_id, concept_uri
                        )
                        if details:
                            enrichments.append({
                                "concept": concept,
                                "details": details,
                            })
                except Exception:
                    pass
        
        return enrichments
    
    def _extract_sources_from_retrieval(
        self,
        retrieval_results: dict,
    ) -> list[dict]:
        """Extract source information from retrieval results."""
        sources = []
        source = retrieval_results.get("source", "")
        results = retrieval_results.get("results", [])
        
        if source == "vector":
            for r in results:
                payload = r.get("payload", {})
                sources.append({
                    "title": payload.get("source_title", ""),
                    "url": payload.get("source_url", ""),
                    "type": payload.get("source_type", ""),
                    "text": payload.get("text", "")[:200],
                    "timestamp": payload.get("timestamp_start_ms"),
                })
        elif source == "graph":
            for r in results:
                details = r.get("details", {})
                sources.append({
                    "title": details.get("sourceTitle", "") or r.get("entity", ""),
                    "url": details.get("sourceUrl", ""),
                    "type": "graph",
                    "text": details.get("definitionText", "")[:200] if details.get("definitionText") else "",
                })
        elif source == "hybrid":
            vector = results.get("vector", [])
            graph = results.get("graph", [])
            for r in vector:
                payload = r.get("payload", {})
                sources.append({
                    "title": payload.get("source_title", ""),
                    "url": payload.get("source_url", ""),
                    "type": payload.get("source_type", ""),
                    "text": payload.get("text", "")[:200],
                })
            for r in graph:
                details = r.get("details", {})
                sources.append({
                    "title": details.get("sourceTitle", "") or r.get("entity", ""),
                    "url": details.get("sourceUrl", ""),
                    "type": "graph",
                    "text": details.get("definitionText", "")[:200] if details.get("definitionText") else "",
                })
        
        return sources
    
    def _enrich_citations(
        self,
        response: QueryResponse,
        retrieval_results: dict,
    ) -> QueryResponse:
        """
        Enrich citations with actual source information from retrieval.
        
        The LLM synthesizer may not correctly populate source titles,
        so we post-process to inject actual source info from retrieval results.
        """
        sources = self._extract_sources_from_retrieval(retrieval_results)
        
        if not sources or not response.citations:
            return response
        
        # Map citations to sources by index
        for i, citation in enumerate(response.citations):
            if i < len(sources):
                src = sources[i]
                # Only replace if LLM didn't provide a good title
                if not citation.title or citation.title == "Unknown" or len(citation.title) < 3:
                    citation.title = src.get("title") or citation.title
                # Always set URL if available and not already set
                if not citation.url and src.get("url"):
                    citation.url = src.get("url")
                # Set source type if not set
                if not citation.source_type or citation.source_type == "unknown":
                    citation.source_type = src.get("type", "unknown")
        
        return response
    
    def _format_synthesis_input(
        self,
        query: str,
        intent: IntentClassification,
        retrieval_results: dict,
    ) -> str:
        """Format input for the response synthesizer."""
        parts = [
            f"## User Query\n{query}",
            f"\n## Intent Classification\n- Type: {intent.intent.value}\n- Entities: {', '.join(intent.entities)}\n- Confidence: {intent.confidence}",
        ]
        
        source = retrieval_results.get("source", "llm_knowledge")
        results = retrieval_results.get("results", [])
        
        if source == "graph":
            parts.append("\n## Graph Results")
            for r in results:
                parts.append(f"\n### Concept: {r.get('entity', 'Unknown')}")
                details = r.get("details", {})
                if details:
                    if details.get("definitionText"):
                        parts.append(f"Definition: {details['definitionText']}")
                    if details.get("sourceTitle"):
                        parts.append(f"Source: {details['sourceTitle']}")
                
                relationships = r.get("relationships", [])
                if relationships:
                    parts.append("Relationships:")
                    for rel in relationships[:5]:
                        parts.append(f"  - {rel.get('relationType', '?')} → {rel.get('relatedLabel', '?')}")
        
        elif source == "vector":
            parts.append("\n## Vector Results")
            for i, r in enumerate(results, 1):
                payload = r.get("payload", {})
                parts.append(f"\n### Result {i} (score: {r.get('score', 0):.2f})")
                parts.append(f"Text: {payload.get('text', '')[:500]}...")
                if payload.get("source_title"):
                    parts.append(f"Source: {payload['source_title']}")
                if payload.get("source_url"):
                    parts.append(f"URL: {payload['source_url']}")
        
        elif source == "hybrid":
            parts.append("\n## Combined Results")
            graph = results.get("graph", [])
            vector = results.get("vector", [])
            
            if graph:
                parts.append("\n### From Knowledge Graph:")
                for r in graph:
                    parts.append(f"- {r.get('entity', 'Unknown')}: {r.get('details', {}).get('definitionText', 'No definition')[:200]}")
            
            if vector:
                parts.append("\n### From Vector Search:")
                for r in vector[:3]:
                    payload = r.get("payload", {})
                    parts.append(f"- {payload.get('text', '')[:200]}...")
        
        elif source == "llm_knowledge":
            parts.append("\n## No Results from Personal Knowledge Base")
            parts.append("Please answer based on general knowledge and indicate that this is not from the user's notes.")
        
        parts.append(f"\n## Retrieval Metadata\n- Source: {source}\n- Fallback Chain: {' → '.join(retrieval_results.get('fallback_chain', []))}")
        
        return "\n".join(parts)
    
    async def query(
        self,
        user_id: str,
        query: str,
        session_id: str,
    ) -> QueryResponse:
        """
        Execute a query against the user's knowledge base.
        
        Args:
            user_id: User identifier
            query: Natural language query
            session_id: Conversation session ID
            
        Returns:
            QueryResponse with answer, citations, and metadata
        """
        logger.info(
            "Query agent processing",
            user_id=user_id,
            query=query[:50],
            session_id=session_id,
        )
        
        # Create context
        context = self._create_context(user_id)
        
        # Get session for conversation history
        session = await get_session(session_id, user_id)
        
        try:
            # Step 1: Classify intent
            intent_result = await Runner.run(
                self.intent_classifier,
                query,
                context=context,
            )
            intent: IntentClassification = intent_result.final_output
            
            logger.info(
                "Intent classified",
                intent=intent.intent.value,
                entities=intent.entities,
                confidence=intent.confidence,
            )
            
            # Step 2: Select strategy
            strategy = self._select_strategy(intent)
            logger.info("Strategy selected", strategy=strategy.value)
            
            # Step 3: Execute retrieval
            retrieval_results = await self._execute_strategy(
                strategy, query, context, intent
            )
            
            logger.info(
                "Retrieval complete",
                source=retrieval_results.get("source"),
                result_count=len(retrieval_results.get("results", [])),
            )
            
            # Step 4: Synthesize response with session for history
            synthesis_input = self._format_synthesis_input(
                query, intent, retrieval_results
            )
            
            response_result = await Runner.run(
                self.synthesizer,
                synthesis_input,
                context=context,
                session=session,
            )
            
            response: QueryResponse = response_result.final_output
            
            # Post-process citations to inject actual source titles from retrieval
            response = self._enrich_citations(response, retrieval_results)
            
            # Add retrieval metadata
            response.retrieval_metadata = RetrievalMetadata(
                retrieval_source=retrieval_results.get("source", "llm_knowledge"),
                fallback_chain=retrieval_results.get("fallback_chain", []),
                has_citations=len(response.citations) > 0,
                confidence=response.confidence,
            )
            
            logger.info(
                "Query complete",
                source_type=response.source_type,
                citation_count=len(response.citations),
                confidence=response.confidence,
            )
            
            return response
            
        except Exception as e:
            logger.error("Query failed", error=str(e))
            # Return a fallback response
            return QueryResponse(
                answer=f"I apologize, but I encountered an error while processing your query. Please try again.",
                citations=[],
                concepts_referenced=[],
                confidence=0.0,
                source_type="error",
                retrieval_metadata=RetrievalMetadata(
                    retrieval_source="error",
                    fallback_chain=[],
                    has_citations=False,
                    confidence=0.0,
                ),
            )
    
    async def query_stream(
        self,
        user_id: str,
        query: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Execute a query with streaming response.
        
        Args:
            user_id: User identifier
            query: Natural language query
            session_id: Conversation session ID
            
        Yields:
            Streaming response chunks
        """
        logger.info(
            "Query agent streaming",
            user_id=user_id,
            query=query[:50],
            session_id=session_id,
        )
        
        # Create context
        context = self._create_context(user_id)
        
        # Get session
        session = await get_session(session_id, user_id)
        
        try:
            # Step 1: Classify intent (non-streaming)
            intent_result = await Runner.run(
                self.intent_classifier,
                query,
                context=context,
            )
            intent: IntentClassification = intent_result.final_output
            
            # Step 2: Select strategy
            strategy = self._select_strategy(intent)
            
            # Step 3: Execute retrieval
            retrieval_results = await self._execute_strategy(
                strategy, query, context, intent
            )
            
            # Step 4: Stream synthesis response
            synthesis_input = self._format_synthesis_input(
                query, intent, retrieval_results
            )
            
            # Use streaming runner
            async with Runner.run_streamed(
                self.orchestrator,  # Use orchestrator for streaming
                synthesis_input,
                context=context,
                session=session,
            ) as stream:
                async for event in stream.stream_events():
                    # Yield text delta events
                    if hasattr(event, 'data') and hasattr(event.data, 'delta'):
                        yield event.data.delta
            
        except Exception as e:
            logger.error("Streaming query failed", error=str(e))
            yield f"Error: {str(e)}"
    
    async def close(self):
        """Close underlying connections."""
        await self.fuseki.close()
        await self.qdrant.close()
        logger.info("QueryAgent closed")
