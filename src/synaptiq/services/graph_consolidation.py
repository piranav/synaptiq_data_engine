"""
Post-ingestion graph consolidation service.

Performs batch cleanup of the knowledge graph to improve quality:
1. Merges duplicate concepts (fuzzy label matching, plurals, case)
2. Removes orphan concepts (no relationships, single-mention)
3. Removes weak relatedTo chains with low confidence
4. Recomputes importance scores after cleanup
"""

from __future__ import annotations

from typing import Any, Optional

import structlog

from synaptiq.ontology.namespaces import (
    SYNAPTIQ,
    build_concept_uri,
    build_user_graph_uri,
    get_sparql_prefixes,
    slugify,
)

logger = structlog.get_logger(__name__)


class GraphConsolidationService:
    """
    Batch cleanup and optimization of the knowledge graph.
    
    Designed to run periodically (e.g., after ingestion batches)
    to keep the graph clean and high-quality.
    """

    def __init__(self, fuseki_store=None):
        self._fuseki = fuseki_store

    @property
    def fuseki(self):
        if self._fuseki is None:
            from synaptiq.storage.fuseki import FusekiStore
            self._fuseki = FusekiStore()
        return self._fuseki

    async def consolidate(self, user_id: str) -> dict[str, Any]:
        """
        Run all consolidation steps for a user's graph.
        
        Returns a summary of actions taken.
        """
        logger.info("Starting graph consolidation", user_id=user_id)
        
        summary = {
            "duplicates_merged": 0,
            "orphans_removed": 0,
            "weak_rels_removed": 0,
        }
        
        # Step 1: Merge duplicate concepts
        merged = await self._merge_duplicate_concepts(user_id)
        summary["duplicates_merged"] = merged
        
        # Step 2: Remove orphan concepts
        orphans = await self._remove_orphan_concepts(user_id)
        summary["orphans_removed"] = orphans
        
        # Step 3: Remove weak relatedTo with low evidence
        weak = await self._remove_weak_relationships(user_id)
        summary["weak_rels_removed"] = weak
        
        # Step 4: Recompute importance scores
        await self._recompute_importance(user_id)
        
        logger.info(
            "Graph consolidation complete",
            user_id=user_id,
            **summary,
        )
        
        return summary

    async def _merge_duplicate_concepts(self, user_id: str) -> int:
        """
        Find and merge concepts that differ only in case, plurals,
        or minor formatting. Uses the concept with the most mentions
        as the canonical version.
        """
        # Get all concepts with their labels and mention counts
        sparql = """
        SELECT ?concept ?label (COUNT(DISTINCT ?chunk) AS ?mentions)
        WHERE {
            ?concept a syn:Concept ;
                     syn:label ?label .
            OPTIONAL {
                {
                    ?concept syn:definedIn ?chunk .
                }
                UNION
                {
                    ?concept syn:mentionedIn ?chunk .
                }
            }
        }
        GROUP BY ?concept ?label
        ORDER BY ?label
        """
        
        results = await self.fuseki.query(user_id, sparql)
        
        if not results:
            return 0
        
        # Group by normalized label (lowercase, stripped, singularized)
        label_groups: dict[str, list[dict]] = {}
        for r in results:
            label = r.get("label", "")
            concept_uri = r.get("concept", "")
            mentions = int(r.get("mentions", "0"))
            
            # Normalize: lowercase, strip, basic singularization
            normalized = label.lower().strip()
            if len(normalized) > 3 and normalized.endswith("s") and not normalized.endswith("ss"):
                singular = normalized[:-1]
            else:
                singular = normalized
            
            # Group by the slug (most aggressive normalization)
            slug = slugify(normalized)
            slug_singular = slugify(singular)
            
            # Use the shorter slug as the canonical key
            group_key = min(slug, slug_singular, key=len) if slug != slug_singular else slug
            
            if group_key not in label_groups:
                label_groups[group_key] = []
            label_groups[group_key].append({
                "uri": concept_uri,
                "label": label,
                "mentions": mentions,
            })
        
        merged_count = 0
        
        for group_key, concepts in label_groups.items():
            if len(concepts) <= 1:
                continue
            
            # Sort by mention count (highest first) - keep the most-mentioned
            concepts.sort(key=lambda c: c["mentions"], reverse=True)
            canonical = concepts[0]
            duplicates = concepts[1:]
            
            logger.info(
                "Merging duplicates",
                canonical=canonical["label"],
                duplicates=[d["label"] for d in duplicates],
            )
            
            for dup in duplicates:
                await self._merge_concept_into(
                    user_id,
                    source_uri=dup["uri"],
                    target_uri=canonical["uri"],
                    source_label=dup["label"],
                )
                merged_count += 1
        
        return merged_count

    async def _merge_concept_into(
        self,
        user_id: str,
        source_uri: str,
        target_uri: str,
        source_label: str,
    ) -> None:
        """
        Merge one concept into another: move all relationships and
        mentions from source to target, then delete source.
        """
        graph_uri = build_user_graph_uri(user_id)
        
        # Move all relationships where source is subject
        move_outgoing = f"""
        {get_sparql_prefixes()}
        WITH <{graph_uri}>
        DELETE {{ <{source_uri}> ?p ?o }}
        INSERT {{ <{target_uri}> ?p ?o }}
        WHERE {{
            <{source_uri}> ?p ?o .
            FILTER(?p IN (
                syn:isA, syn:partOf, syn:prerequisiteFor,
                syn:relatedTo, syn:oppositeOf, syn:usedIn,
                syn:definedIn, syn:mentionedIn, syn:hasDefinition
            ))
        }}
        """
        await self.fuseki._execute_update(move_outgoing)
        
        # Move all relationships where source is object
        move_incoming = f"""
        {get_sparql_prefixes()}
        WITH <{graph_uri}>
        DELETE {{ ?s ?p <{source_uri}> }}
        INSERT {{ ?s ?p <{target_uri}> }}
        WHERE {{
            ?s ?p <{source_uri}> .
            FILTER(?p IN (
                syn:isA, syn:partOf, syn:prerequisiteFor,
                syn:relatedTo, syn:oppositeOf, syn:usedIn
            ))
        }}
        """
        await self.fuseki._execute_update(move_incoming)
        
        # Add the old label as an altLabel on the target
        add_alt = f"""
        {get_sparql_prefixes()}
        INSERT DATA {{
            GRAPH <{graph_uri}> {{
                <{target_uri}> syn:altLabel "{source_label}" .
            }}
        }}
        """
        await self.fuseki._execute_update(add_alt)
        
        # Delete the source concept entirely
        delete_source = f"""
        {get_sparql_prefixes()}
        WITH <{graph_uri}>
        DELETE {{ <{source_uri}> ?p ?o }}
        WHERE {{ <{source_uri}> ?p ?o }}
        """
        await self.fuseki._execute_update(delete_source)

    async def _remove_orphan_concepts(self, user_id: str) -> int:
        """
        Remove concepts that have no relationships and are only
        mentioned in a single chunk (low-value noise).
        """
        # Find concepts with no relationships and at most 1 mention
        sparql = """
        SELECT ?concept ?label
        WHERE {
            ?concept a syn:Concept ;
                     syn:label ?label .
            
            # No relationships to other concepts
            FILTER NOT EXISTS {
                {
                    ?concept ?relOut ?other .
                    ?other a syn:Concept .
                    FILTER(?relOut IN (
                        syn:isA, syn:partOf, syn:prerequisiteFor,
                        syn:relatedTo, syn:oppositeOf, syn:usedIn
                    ))
                }
                UNION
                {
                    ?other ?relIn ?concept .
                    ?other a syn:Concept .
                    FILTER(?relIn IN (
                        syn:isA, syn:partOf, syn:prerequisiteFor,
                        syn:relatedTo, syn:oppositeOf, syn:usedIn
                    ))
                }
            }
            
            # No definition
            FILTER NOT EXISTS {
                ?concept syn:hasDefinition ?def .
            }
        }
        """
        
        results = await self.fuseki.query(user_id, sparql)
        
        if not results:
            return 0
        
        graph_uri = build_user_graph_uri(user_id)
        removed = 0
        
        for r in results:
            concept_uri = r.get("concept", "")
            label = r.get("label", "")
            
            if not concept_uri:
                continue
            
            # Count mentions
            count_sparql = f"""
            SELECT (COUNT(DISTINCT ?chunk) AS ?count)
            WHERE {{
                {{
                    <{concept_uri}> syn:definedIn ?chunk .
                }}
                UNION
                {{
                    <{concept_uri}> syn:mentionedIn ?chunk .
                }}
            }}
            """
            count_results = await self.fuseki.query(user_id, count_sparql)
            mention_count = int((count_results[0].get("count", "0")) if count_results else "0")
            
            # Only remove if mentioned in 1 or fewer chunks
            if mention_count <= 1:
                delete_sparql = f"""
                {get_sparql_prefixes()}
                WITH <{graph_uri}>
                DELETE {{ <{concept_uri}> ?p ?o }}
                WHERE {{ <{concept_uri}> ?p ?o }}
                """
                await self.fuseki._execute_update(delete_sparql)
                
                logger.debug("Removed orphan concept", label=label)
                removed += 1
        
        return removed

    async def _remove_weak_relationships(self, user_id: str) -> int:
        """
        Remove relatedTo relationships that exist between concepts
        with no other connection and low importance scores.
        
        Keeps relatedTo only when both concepts have importance > 2
        or when it's the only relationship type between them.
        """
        # Find relatedTo pairs where both concepts have low importance
        sparql = """
        SELECT ?concept1 ?label1 ?concept2 ?label2
               ?importance1 ?importance2
        WHERE {
            ?concept1 syn:relatedTo ?concept2 .
            ?concept1 a syn:Concept ;
                      syn:label ?label1 .
            ?concept2 a syn:Concept ;
                      syn:label ?label2 .
            
            OPTIONAL { ?concept1 syn:importance ?importance1 }
            OPTIONAL { ?concept2 syn:importance ?importance2 }
            
            # Only remove if both have low importance
            FILTER(
                (!BOUND(?importance1) || ?importance1 < 2) &&
                (!BOUND(?importance2) || ?importance2 < 2)
            )
            
            # Don't remove if they have other relationship types
            FILTER NOT EXISTS {
                ?concept1 ?otherRel ?concept2 .
                FILTER(?otherRel IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor,
                    syn:usedIn, syn:oppositeOf
                ))
            }
        }
        """
        
        results = await self.fuseki.query(user_id, sparql)
        
        if not results:
            return 0
        
        graph_uri = build_user_graph_uri(user_id)
        removed = 0
        
        for r in results:
            concept1 = r.get("concept1", "")
            concept2 = r.get("concept2", "")
            
            if concept1 and concept2:
                delete_sparql = f"""
                {get_sparql_prefixes()}
                WITH <{graph_uri}>
                DELETE {{ <{concept1}> syn:relatedTo <{concept2}> }}
                WHERE {{ <{concept1}> syn:relatedTo <{concept2}> }}
                """
                await self.fuseki._execute_update(delete_sparql)
                removed += 1
        
        return removed

    async def _recompute_importance(self, user_id: str) -> None:
        """
        Recompute importance scores for all concepts after consolidation.
        Delegates to the OntologyWriter's importance computation.
        """
        try:
            from synaptiq.processors.ontology_writer import OntologyWriter
            writer = OntologyWriter(fuseki_store=self.fuseki)
            await writer._update_concept_importance(user_id)
        except Exception as e:
            logger.warning("Failed to recompute importance", error=str(e))
