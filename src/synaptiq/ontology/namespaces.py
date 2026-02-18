"""
URI namespace utilities for the Synaptiq ontology.

Provides consistent URI building functions for all entity types
in the knowledge graph, following the naming conventions:

    Base:        https://synaptiq.ai/
    Ontology:    https://synaptiq.ai/ontology#
    User Graph:  https://synaptiq.ai/users/{user_id}/graph
    Concepts:    https://synaptiq.ai/users/{user_id}/concepts/{slug}
    Chunks:      https://synaptiq.ai/chunks/{uuid}
    Sources:     https://synaptiq.ai/sources/{uuid}
    Definitions: https://synaptiq.ai/users/{user_id}/definitions/{uuid}
"""

import re
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from config.settings import get_settings


@dataclass(frozen=True)
class Namespace:
    """RDF namespace with prefix and URI."""
    
    prefix: str
    uri: str
    
    def __getattr__(self, name: str) -> str:
        """Allow namespace.Property syntax for building URIs."""
        return f"{self.uri}{name}"
    
    def __getitem__(self, name: str) -> str:
        """Allow namespace['property'] syntax for building URIs."""
        return f"{self.uri}{name}"
    
    def term(self, name: str) -> str:
        """Build a URI for a term in this namespace."""
        return f"{self.uri}{name}"


def _get_base_uri() -> str:
    """Get the base URI from settings."""
    try:
        settings = get_settings()
        return settings.ontology_base_uri
    except Exception:
        # Fallback for testing or when settings aren't available
        return "https://synaptiq.ai/"


# Standard namespaces
RDF = Namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("owl", "http://www.w3.org/2002/07/owl#")
XSD = Namespace("xsd", "http://www.w3.org/2001/XMLSchema#")
SKOS = Namespace("skos", "http://www.w3.org/2004/02/skos/core#")
DC = Namespace("dc", "http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("dcterms", "http://purl.org/dc/terms/")

# Synaptiq namespace (ontology terms)
SYNAPTIQ = Namespace("syn", "https://synaptiq.ai/ontology#")

# Synaptiq entity namespaces (built dynamically based on settings)
SYNAPTIQ_USERS = Namespace("synu", "https://synaptiq.ai/users/")
SYNAPTIQ_CHUNKS = Namespace("sync", "https://synaptiq.ai/chunks/")
SYNAPTIQ_SOURCES = Namespace("syns", "https://synaptiq.ai/sources/")


def get_prefixes() -> dict[str, str]:
    """
    Get all namespace prefixes as a dictionary.
    
    Returns:
        Dict mapping prefix names to URIs
    """
    base_uri = _get_base_uri()
    return {
        "rdf": RDF.uri,
        "rdfs": RDFS.uri,
        "owl": OWL.uri,
        "xsd": XSD.uri,
        "skos": SKOS.uri,
        "dc": DC.uri,
        "dcterms": DCTERMS.uri,
        "syn": f"{base_uri}ontology#",
        "synu": f"{base_uri}users/",
        "sync": f"{base_uri}chunks/",
        "syns": f"{base_uri}sources/",
    }


def get_sparql_prefixes() -> str:
    """
    Get SPARQL PREFIX declarations for all namespaces.
    
    Returns:
        String with all PREFIX declarations
    """
    prefixes = get_prefixes()
    return "\n".join(
        f"PREFIX {prefix}: <{uri}>"
        for prefix, uri in prefixes.items()
    )


def slugify(text: str) -> str:
    """
    Convert text to a URL-safe slug.
    
    Args:
        text: Text to slugify
        
    Returns:
        URL-safe slug
    """
    # Lowercase
    slug = text.lower()
    # Replace spaces and special chars with underscores
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    # Remove leading/trailing underscores
    slug = slug.strip("_")
    return slug


def build_user_graph_uri(user_id: str) -> str:
    """
    Build the named graph URI for a user's knowledge graph.
    
    Args:
        user_id: User identifier
        
    Returns:
        Named graph URI: https://synaptiq.ai/users/{user_id}/graph
    """
    base_uri = _get_base_uri()
    return f"{base_uri}users/{user_id}/graph"


def build_ontology_graph_uri() -> str:
    """
    Build the named graph URI for the shared ontology.
    
    Returns:
        Ontology graph URI: https://synaptiq.ai/ontology
    """
    base_uri = _get_base_uri()
    return f"{base_uri}ontology"


def build_concept_uri(user_id: str, concept_label: str) -> str:
    """
    Build a URI for a concept in a user's graph.
    
    Args:
        user_id: User identifier
        concept_label: Concept label (will be slugified)
        
    Returns:
        Concept URI: https://synaptiq.ai/users/{user_id}/concepts/{slug}
    """
    base_uri = _get_base_uri()
    slug = slugify(concept_label)
    return f"{base_uri}users/{user_id}/concepts/{slug}"


def build_chunk_uri(chunk_id: Optional[str] = None) -> str:
    """
    Build a URI for a chunk.
    
    Uses the same chunk_id as Qdrant for cross-store linking.
    
    Args:
        chunk_id: Chunk UUID (generates new if not provided)
        
    Returns:
        Chunk URI: https://synaptiq.ai/chunks/{uuid}
    """
    base_uri = _get_base_uri()
    chunk_id = chunk_id or str(uuid4())
    return f"{base_uri}chunks/{chunk_id}"


def build_source_uri(source_id: Optional[str] = None) -> str:
    """
    Build a URI for a source.
    
    Args:
        source_id: Source UUID (generates new if not provided)
        
    Returns:
        Source URI: https://synaptiq.ai/sources/{uuid}
    """
    base_uri = _get_base_uri()
    source_id = source_id or str(uuid4())
    return f"{base_uri}sources/{source_id}"


def build_definition_uri(user_id: str, definition_id: Optional[str] = None) -> str:
    """
    Build a URI for a definition.
    
    Args:
        user_id: User identifier
        definition_id: Definition UUID (generates new if not provided)
        
    Returns:
        Definition URI: https://synaptiq.ai/users/{user_id}/definitions/{uuid}
    """
    base_uri = _get_base_uri()
    definition_id = definition_id or str(uuid4())
    return f"{base_uri}users/{user_id}/definitions/{definition_id}"


def extract_user_id_from_graph_uri(graph_uri: str) -> Optional[str]:
    """
    Extract user ID from a user graph URI.
    
    Args:
        graph_uri: Named graph URI
        
    Returns:
        User ID if valid user graph URI, None otherwise
    """
    base_uri = _get_base_uri()
    pattern = rf"^{re.escape(base_uri)}users/([^/]+)/graph$"
    match = re.match(pattern, graph_uri)
    return match.group(1) if match else None


def extract_concept_slug_from_uri(concept_uri: str) -> Optional[str]:
    """
    Extract concept slug from a concept URI.
    
    Args:
        concept_uri: Concept URI
        
    Returns:
        Concept slug if valid concept URI, None otherwise
    """
    base_uri = _get_base_uri()
    pattern = rf"^{re.escape(base_uri)}users/[^/]+/concepts/([^/]+)$"
    match = re.match(pattern, concept_uri)
    return match.group(1) if match else None


def extract_chunk_id_from_uri(chunk_uri: str) -> Optional[str]:
    """
    Extract chunk ID from a chunk URI.
    
    Args:
        chunk_uri: Chunk URI
        
    Returns:
        Chunk ID if valid chunk URI, None otherwise
    """
    base_uri = _get_base_uri()
    pattern = rf"^{re.escape(base_uri)}chunks/([^/]+)$"
    match = re.match(pattern, chunk_uri)
    return match.group(1) if match else None


# Source type to RDF class mapping
SOURCE_TYPE_TO_CLASS = {
    "youtube": SYNAPTIQ.term("YouTubeSource"),
    "web_article": SYNAPTIQ.term("WebArticleSource"),
    "note": SYNAPTIQ.term("NoteSource"),
    "podcast": SYNAPTIQ.term("PodcastSource"),
    "pdf": SYNAPTIQ.term("PDFSource"),
}


def get_source_class_uri(source_type: str) -> str:
    """
    Get the RDF class URI for a source type.
    
    Args:
        source_type: Source type string (youtube, web_article, etc.)
        
    Returns:
        RDF class URI for the source type
    """
    return SOURCE_TYPE_TO_CLASS.get(source_type.lower(), SYNAPTIQ.term("Source"))


# Relationship type mapping
RELATIONSHIP_TYPES = {
    "is_a": SYNAPTIQ.term("isA"),
    "isa": SYNAPTIQ.term("isA"),
    "is a": SYNAPTIQ.term("isA"),
    "type_of": SYNAPTIQ.term("isA"),
    "part_of": SYNAPTIQ.term("partOf"),
    "partof": SYNAPTIQ.term("partOf"),
    "part of": SYNAPTIQ.term("partOf"),
    "component_of": SYNAPTIQ.term("partOf"),
    "prerequisite_for": SYNAPTIQ.term("prerequisiteFor"),
    "prerequisite for": SYNAPTIQ.term("prerequisiteFor"),
    "required_for": SYNAPTIQ.term("prerequisiteFor"),
    "needed_for": SYNAPTIQ.term("prerequisiteFor"),
    "related_to": SYNAPTIQ.term("relatedTo"),
    "relatedto": SYNAPTIQ.term("relatedTo"),
    "related to": SYNAPTIQ.term("relatedTo"),
    "associated_with": SYNAPTIQ.term("relatedTo"),
    "opposite_of": SYNAPTIQ.term("oppositeOf"),
    "opposite of": SYNAPTIQ.term("oppositeOf"),
    "antonym_of": SYNAPTIQ.term("oppositeOf"),
    "used_in": SYNAPTIQ.term("usedIn"),
    "usedin": SYNAPTIQ.term("usedIn"),
    "used in": SYNAPTIQ.term("usedIn"),
    "applied_in": SYNAPTIQ.term("usedIn"),
}


def get_relationship_uri(relation_type: str) -> str:
    """
    Get the RDF property URI for a relationship type.
    
    Args:
        relation_type: Relationship type string
        
    Returns:
        RDF property URI for the relationship
    """
    normalized = relation_type.lower().strip()
    return RELATIONSHIP_TYPES.get(normalized, SYNAPTIQ.term("relatedTo"))


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY-TIME SYNONYM RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

COMMON_SYNONYMS: dict[str, list[str]] = {
    # AI / Machine Learning
    "ai": ["artificial intelligence"],
    "artificial intelligence": ["ai"],
    "ml": ["machine learning"],
    "machine learning": ["ml"],
    "dl": ["deep learning"],
    "deep learning": ["dl"],
    "nlp": ["natural language processing"],
    "natural language processing": ["nlp"],
    "cv": ["computer vision"],
    "computer vision": ["cv"],
    "nn": ["neural network", "neural networks"],
    "neural network": ["nn", "neural networks"],
    "neural networks": ["nn", "neural network"],
    "rnn": ["recurrent neural network"],
    "recurrent neural network": ["rnn"],
    "cnn": ["convolutional neural network"],
    "convolutional neural network": ["cnn", "convnet"],
    "llm": ["large language model"],
    "large language model": ["llm"],
    "gpt": ["generative pre-trained transformer"],
    "rl": ["reinforcement learning"],
    "reinforcement learning": ["rl"],
    # Physics
    "gr": ["general relativity"],
    "general relativity": ["gr", "relativity"],
    "qm": ["quantum mechanics"],
    "quantum mechanics": ["qm", "quantum theory", "quantum physics"],
    "qft": ["quantum field theory"],
    "quantum field theory": ["qft"],
    "em": ["electromagnetism"],
    "electromagnetism": ["em"],
    "sr": ["special relativity"],
    "special relativity": ["sr"],
    # Math
    "pde": ["partial differential equation"],
    "ode": ["ordinary differential equation"],
    "linear algebra": ["lin alg"],
    # Computing
    "api": ["application programming interface"],
    "sql": ["structured query language"],
    "db": ["database"],
    "os": ["operating system"],
    "gpu": ["graphics processing unit"],
    "cpu": ["central processing unit"],
}


def expand_synonyms(term: str) -> list[str]:
    """
    Expand a query term into itself plus known synonyms.
    
    Used at query time so that a user asking about "CNNs" also
    searches for "convolutional neural network", etc.
    
    Args:
        term: The search term to expand
        
    Returns:
        List of terms to search for (always includes the original)
    """
    normalized = term.lower().strip()
    # Strip trailing 's' for simple pluralization
    singular = normalized.rstrip("s") if len(normalized) > 3 and normalized.endswith("s") else normalized
    
    candidates = {normalized}
    
    for variant in [normalized, singular]:
        if variant in COMMON_SYNONYMS:
            for syn in COMMON_SYNONYMS[variant]:
                candidates.add(syn.lower())
    
    return list(candidates)

