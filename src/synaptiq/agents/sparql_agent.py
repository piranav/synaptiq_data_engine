"""
SPARQL Agent for knowledge graph queries.

This agent generates and executes SPARQL queries against the user's
knowledge graph based on natural language requests.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from agents import Agent

from .context import AgentContext
from .prompts import SPARQL_AGENT_SYSTEM_PROMPT
from .tools import (
    execute_sparql,
    get_concept_details,
    find_concept_path,
    get_concepts_from_source,
    find_similar_concepts,
)

if TYPE_CHECKING:
    pass


def load_ontology_schema() -> str:
    """Load the synaptiq ontology TTL file."""
    ontology_path = Path(__file__).parent.parent / "ontology" / "synaptiq.ttl"
    
    if ontology_path.exists():
        return ontology_path.read_text()
    
    return "# Ontology not found"


def get_prefixes() -> str:
    """Get SPARQL PREFIX declarations."""
    from synaptiq.ontology.namespaces import get_sparql_prefixes
    return get_sparql_prefixes()


def create_sparql_agent(
    ontology_schema: str | None = None,
    prefixes: str | None = None,
) -> Agent[AgentContext]:
    """
    Create the SPARQL agent with ontology context.
    
    Args:
        ontology_schema: TTL ontology content (loads from file if not provided)
        prefixes: SPARQL prefixes (generates if not provided)
        
    Returns:
        Configured SPARQL agent
    """
    if ontology_schema is None:
        ontology_schema = load_ontology_schema()
    
    if prefixes is None:
        prefixes = get_prefixes()
    
    # Format the system prompt with ontology context
    instructions = SPARQL_AGENT_SYSTEM_PROMPT.format(
        ontology_schema=ontology_schema,
        prefixes=prefixes,
    )
    
    return Agent[AgentContext](
        name="SPARQL Agent",
        instructions=instructions,
        model="gpt-5.2-Codex",
        tools=[
            execute_sparql,
            get_concept_details,
            find_concept_path,
            get_concepts_from_source,
            find_similar_concepts,
        ],
    )
