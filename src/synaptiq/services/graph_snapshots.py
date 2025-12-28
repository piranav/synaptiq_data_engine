"""
Graph Snapshot Service for tracking knowledge graph growth over time.

Stores daily snapshots of graph metrics in MongoDB to enable:
- Growth percentage calculations
- Historical trends visualization
- Data for insights ("Your graph has grown X% this week")
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from motor.motor_asyncio import AsyncIOMotorCollection

from synaptiq.storage.mongodb import MongoDBStore

logger = structlog.get_logger(__name__)


class GraphSnapshotService:
    """
    Service for capturing and retrieving graph metrics snapshots.
    
    Snapshots are stored in MongoDB with user_id indexing for fast retrieval.
    """
    
    COLLECTION_NAME = "graph_snapshots"
    RETENTION_DAYS = 30  # Keep 30 days of history
    
    def __init__(self, mongodb: Optional[MongoDBStore] = None):
        """Initialize with MongoDB store."""
        self._mongodb = mongodb
        self._collection: Optional[AsyncIOMotorCollection] = None
    
    @property
    def mongodb(self) -> MongoDBStore:
        """Lazy initialize MongoDB store."""
        if self._mongodb is None:
            self._mongodb = MongoDBStore()
        return self._mongodb
    
    async def _get_collection(self) -> AsyncIOMotorCollection:
        """Get or create the snapshots collection with proper indexes."""
        if self._collection is None:
            db = self.mongodb.database
            self._collection = db[self.COLLECTION_NAME]
            
            # Create indexes for efficient queries
            await self._collection.create_index(
                [("user_id", 1), ("timestamp", -1)],
                name="user_timestamp_idx"
            )
            await self._collection.create_index(
                [("timestamp", 1)],
                expireAfterSeconds=self.RETENTION_DAYS * 24 * 60 * 60,
                name="ttl_idx"
            )
        
        return self._collection
    
    async def capture_snapshot(
        self,
        user_id: str,
        concepts_count: int,
        connections_count: int,
        sources_count: int,
    ) -> dict[str, Any]:
        """
        Capture a snapshot of current graph metrics.
        
        Args:
            user_id: User identifier
            concepts_count: Number of concepts
            connections_count: Number of relationships between concepts
            sources_count: Number of sources
            
        Returns:
            The created snapshot document
        """
        collection = await self._get_collection()
        
        snapshot = {
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc),
            "concepts_count": concepts_count,
            "connections_count": connections_count,
            "sources_count": sources_count,
        }
        
        result = await collection.insert_one(snapshot)
        snapshot["_id"] = str(result.inserted_id)
        
        logger.info(
            "Graph snapshot captured",
            user_id=user_id,
            concepts=concepts_count,
            connections=connections_count,
        )
        
        return snapshot
    
    async def get_latest_snapshot(self, user_id: str) -> Optional[dict[str, Any]]:
        """
        Get the most recent snapshot for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Latest snapshot or None
        """
        collection = await self._get_collection()
        
        cursor = collection.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(1)
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            return doc
        
        return None
    
    async def get_snapshot_at_date(
        self,
        user_id: str,
        target_date: datetime
    ) -> Optional[dict[str, Any]]:
        """
        Get the snapshot closest to a target date.
        
        Args:
            user_id: User identifier
            target_date: Date to find snapshot for
            
        Returns:
            Closest snapshot at or before target_date, or None
        """
        collection = await self._get_collection()
        
        # Find snapshot at or before target date
        cursor = collection.find({
            "user_id": user_id,
            "timestamp": {"$lte": target_date}
        }).sort("timestamp", -1).limit(1)
        
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            return doc
        
        return None
    
    async def calculate_growth(
        self,
        user_id: str,
        current_stats: dict[str, int],
        days: int = 7
    ) -> dict[str, Any]:
        """
        Calculate growth percentage compared to a previous snapshot.
        
        Args:
            user_id: User identifier
            current_stats: Current graph stats (concepts_count, connections_count, sources_count)
            days: Number of days to look back (default 7)
            
        Returns:
            Dict with growth percentages for each metric
        """
        target_date = datetime.now(timezone.utc) - timedelta(days=days)
        old_snapshot = await self.get_snapshot_at_date(user_id, target_date)
        
        def calc_percent(current: int, old: int) -> Optional[float]:
            if old == 0:
                return 100.0 if current > 0 else 0.0
            return round(((current - old) / old) * 100, 1)
        
        if old_snapshot is None:
            # No historical data, can't calculate growth
            return {
                "concepts_growth_percent": None,
                "connections_growth_percent": None,
                "sources_growth_percent": None,
                "has_history": False,
                "comparison_days": days,
            }
        
        return {
            "concepts_growth_percent": calc_percent(
                current_stats.get("concepts_count", 0),
                old_snapshot.get("concepts_count", 0)
            ),
            "connections_growth_percent": calc_percent(
                current_stats.get("connections_count", 0),
                old_snapshot.get("connections_count", 0)
            ),
            "sources_growth_percent": calc_percent(
                current_stats.get("sources_count", 0),
                old_snapshot.get("sources_count", 0)
            ),
            "has_history": True,
            "comparison_days": days,
            "comparison_date": old_snapshot.get("timestamp"),
        }
    
    async def close(self):
        """Close MongoDB connection."""
        if self._mongodb:
            await self._mongodb.close()
