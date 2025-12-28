#!/usr/bin/env python3
"""
Migration script to merge duplicate concepts in the knowledge graph.

This script finds and merges concepts that are synonyms/abbreviations of each other,
such as "ai", "AI", and "artificial intelligence".

Usage:
    python -m scripts.merge_duplicate_concepts --user-id <USER_ID> [--dry-run]
"""

import argparse
import asyncio
from collections import defaultdict

import structlog

from synaptiq.storage.fuseki import FusekiStore
from synaptiq.ontology.conflict_resolver import COMMON_SYNONYMS

logger = structlog.get_logger(__name__)


async def find_duplicate_concepts(fuseki: FusekiStore, user_id: str) -> dict[str, list[str]]:
    """
    Find concepts that are synonyms of each other.
    
    Returns:
        Dict mapping canonical label -> list of duplicate URIs to merge into it
    """
    # Get all concepts
    sparql = """
    SELECT ?concept ?label
    WHERE {
        ?concept a syn:Concept ;
                 syn:label ?label .
    }
    """
    results = await fuseki.query(user_id, sparql)
    
    # Build label -> URIs mapping
    label_to_uris: dict[str, list[str]] = defaultdict(list)
    for r in results:
        label = r.get("label", "").lower().strip()
        uri = r.get("concept", "")
        if label and uri:
            label_to_uris[label].append(uri)
    
    # Find groups of synonyms
    canonical_to_duplicates: dict[str, list[str]] = {}
    processed_labels = set()
    
    for label in label_to_uris.keys():
        if label in processed_labels:
            continue
        
        # Check if this label has synonyms
        synonyms_in_graph = []
        for synonym in COMMON_SYNONYMS.get(label, []):
            synonym_lower = synonym.lower()
            if synonym_lower in label_to_uris and synonym_lower != label:
                synonyms_in_graph.append(synonym_lower)
        
        if synonyms_in_graph:
            # Use the longest label as canonical
            all_labels = [label] + synonyms_in_graph
            canonical = max(all_labels, key=len)
            
            # Collect all URIs except the canonical one
            canonical_uris = label_to_uris[canonical]
            duplicate_uris = []
            for syn_label in all_labels:
                if syn_label != canonical:
                    duplicate_uris.extend(label_to_uris[syn_label])
                processed_labels.add(syn_label)
            
            if duplicate_uris and canonical_uris:
                canonical_to_duplicates[canonical] = {
                    "canonical_uri": canonical_uris[0],
                    "duplicate_uris": duplicate_uris,
                }
            
            processed_labels.add(canonical)
    
    return canonical_to_duplicates


async def merge_concepts(
    fuseki: FusekiStore,
    user_id: str,
    canonical_label: str,
    canonical_uri: str,
    duplicate_uris: list[str],
    dry_run: bool = False,
) -> None:
    """
    Merge duplicate concepts into the canonical one.
    
    1. Redirect all relationships from duplicates to canonical
    2. Add duplicate labels as altLabels on canonical
    3. Delete duplicate concepts
    """
    from synaptiq.ontology.namespaces import get_sparql_prefixes, build_user_graph_uri
    
    graph_uri = build_user_graph_uri(user_id)
    prefixes = get_sparql_prefixes()
    
    logger.info(
        "Merging concepts",
        canonical=canonical_label,
        canonical_uri=canonical_uri,
        duplicates=len(duplicate_uris),
        dry_run=dry_run,
    )
    
    for dup_uri in duplicate_uris:
        # Get the duplicate's label to preserve as altLabel
        label_results = await fuseki.query(user_id, f"""
        SELECT ?label
        WHERE {{
            <{dup_uri}> syn:label ?label .
        }}
        """)
        dup_label = label_results[0].get("label", "") if label_results else ""
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would merge '{dup_label}' ({dup_uri}) into canonical")
            continue
        
        # 1. Add duplicate label as altLabel on canonical
        if dup_label:
            add_alt_label = f"""
            {prefixes}
            INSERT DATA {{
                GRAPH <{graph_uri}> {{
                    <{canonical_uri}> syn:altLabel "{dup_label}" .
                }}
            }}
            """
            await fuseki._execute_update(add_alt_label)
        
        # 2. Redirect outgoing relationships from duplicate to canonical
        redirect_outgoing = f"""
        {prefixes}
        WITH <{graph_uri}>
        DELETE {{ <{dup_uri}> ?p ?o }}
        INSERT {{ <{canonical_uri}> ?p ?o }}
        WHERE {{
            <{dup_uri}> ?p ?o .
            FILTER(?p NOT IN (rdf:type, syn:label, syn:altLabel))
        }}
        """
        await fuseki._execute_update(redirect_outgoing)
        
        # 3. Redirect incoming relationships to duplicate to point to canonical
        redirect_incoming = f"""
        {prefixes}
        WITH <{graph_uri}>
        DELETE {{ ?s ?p <{dup_uri}> }}
        INSERT {{ ?s ?p <{canonical_uri}> }}
        WHERE {{
            ?s ?p <{dup_uri}> .
        }}
        """
        await fuseki._execute_update(redirect_incoming)
        
        # 4. Delete the duplicate concept (can't use WITH + DELETE WHERE)
        delete_duplicate = f"""
        {prefixes}
        DELETE {{
            GRAPH <{graph_uri}> {{ <{dup_uri}> ?p ?o . }}
        }}
        WHERE {{
            GRAPH <{graph_uri}> {{ <{dup_uri}> ?p ?o . }}
        }}
        """
        await fuseki._execute_update(delete_duplicate)
        
        logger.info(f"  Merged '{dup_label}' into '{canonical_label}'")


async def get_all_users(fuseki: FusekiStore) -> list[str]:
    """
    Get all user IDs by querying for named graphs.
    
    Returns:
        List of user IDs
    """
    # Query for all named graphs
    sparql = """
    SELECT DISTINCT ?g
    WHERE {
        GRAPH ?g { ?s ?p ?o }
    }
    """
    
    try:
        results = await fuseki.query_raw(sparql)
        user_ids = []
        
        for r in results:
            graph_uri = r.get("g", "")
            # Extract user ID from graph URI pattern: .../users/{user_id}/graph
            if "/users/" in graph_uri and graph_uri.endswith("/graph"):
                parts = graph_uri.split("/users/")
                if len(parts) > 1:
                    user_part = parts[1].replace("/graph", "")
                    if user_part and user_part != "ontology":
                        user_ids.append(user_part)
        
        return list(set(user_ids))  # Deduplicate
    except Exception as e:
        logger.error("Failed to get user list", error=str(e))
        return []


async def main(user_id: str = None, all_users: bool = False, dry_run: bool = False):
    """Run the migration."""
    fuseki = FusekiStore()
    
    # Get list of users to process
    if all_users:
        users = await get_all_users(fuseki)
        if not users:
            logger.warning("No users found in the system!")
            return
        logger.info(f"Found {len(users)} users to process: {users}")
    elif user_id:
        users = [user_id]
    else:
        logger.error("Must specify either --user-id or --all")
        return
    
    total_merged = 0
    
    for uid in users:
        logger.info(f"\n{'='*60}\nProcessing user: {uid}\n{'='*60}")
        
        duplicates = await find_duplicate_concepts(fuseki, uid)
        
        if not duplicates:
            logger.info(f"No duplicate concepts found for user {uid}")
            continue
        
        logger.info(f"Found {len(duplicates)} groups of duplicates for user {uid}")
        
        for canonical_label, data in duplicates.items():
            await merge_concepts(
                fuseki,
                uid,
                canonical_label,
                data["canonical_uri"],
                data["duplicate_uris"],
                dry_run=dry_run,
            )
        
        total_merged += len(duplicates)
    
    logger.info(f"\n{'='*60}\nMigration complete! {total_merged} groups merged across {len(users)} users\n{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge duplicate concepts in knowledge graph")
    parser.add_argument("--user-id", help="Specific user ID to process")
    parser.add_argument("--all", action="store_true", dest="all_users", help="Process all users in the system")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    
    args = parser.parse_args()
    
    if not args.user_id and not args.all_users:
        parser.error("Must specify either --user-id or --all")
    
    asyncio.run(main(user_id=args.user_id, all_users=args.all_users, dry_run=args.dry_run))
