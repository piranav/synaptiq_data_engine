"""
CLI commands for the Synaptiq Data Engine.
"""

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def run_async(coro):
    """Run an async function in sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
@click.version_option(version="0.1.0", prog_name="synaptiq")
def cli():
    """
    Synaptiq Data Engine CLI.
    
    A production-grade data processing pipeline for personal knowledge management.
    """
    pass


@cli.command()
@click.argument("url")
@click.option("--user-id", "-u", required=True, help="User ID for multi-tenant isolation")
@click.option("--async", "async_mode", is_flag=True, default=False, help="Run asynchronously (returns job ID)")
@click.option("--wait", is_flag=True, default=True, help="Wait for completion (sync mode)")
def ingest(url: str, user_id: str, async_mode: bool, wait: bool):
    """
    Ingest a URL into the knowledge base.
    
    Supports YouTube videos and web articles.
    
    Examples:
    
        synaptiq ingest https://youtube.com/watch?v=abc123 -u my_user_id
        
        synaptiq ingest https://example.com/article -u my_user_id --async
    """
    from synaptiq.adapters.base import AdapterFactory
    from synaptiq.core.schemas import Job, JobStatus
    from synaptiq.processors.pipeline import create_default_pipeline
    from synaptiq.storage.mongodb import MongoDBStore
    from synaptiq.storage.qdrant import QdrantStore

    async def _ingest():
        # Detect source type
        source_type = AdapterFactory.detect_source_type(url)
        if source_type is None:
            console.print(f"[red]Error:[/red] Unsupported URL type: {url}")
            console.print("Supported types: YouTube videos, web articles")
            sys.exit(1)

        console.print(f"[blue]Source type:[/blue] {source_type.value}")

        # Initialize stores
        mongo = MongoDBStore()
        qdrant = QdrantStore()

        try:
            await mongo.ensure_indexes()
            await qdrant.ensure_collection()

            # Check if already ingested
            existing_id = await mongo.source_exists(url, user_id)
            if existing_id:
                console.print(f"[yellow]URL already ingested.[/yellow] Document ID: {existing_id}")
                return

            # Get adapter
            adapter = AdapterFactory.get_adapter(url)
            console.print(f"[blue]Adapter:[/blue] {adapter.__class__.__name__}")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # Ingest content
                task = progress.add_task("Ingesting content...", total=None)
                document = await adapter.ingest(url, user_id)
                progress.update(task, description=f"Ingested: {document.source_title}")

                # Save to MongoDB
                progress.update(task, description="Saving to database...")
                await mongo.save_source(document)

                # Process through pipeline
                progress.update(task, description="Processing chunks...")
                pipeline = create_default_pipeline()
                processed_chunks = await pipeline.run(document)

                # Store in Qdrant
                progress.update(task, description="Storing vectors...")
                chunk_count = await qdrant.upsert_chunks(processed_chunks)

                progress.update(task, description="Complete!")

            # Display results
            console.print()
            console.print("[green]✓ Ingestion complete![/green]")
            console.print(f"  Document ID: {document.id}")
            console.print(f"  Title: {document.source_title}")
            console.print(f"  Chunks created: {chunk_count}")
            console.print(f"  Segments: {len(document.content_segments)}")

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            sys.exit(1)

        finally:
            await mongo.close()
            await qdrant.close()

    run_async(_ingest())


@cli.command()
@click.argument("query")
@click.option("--user-id", "-u", required=True, help="User ID")
@click.option("--limit", "-n", default=5, help="Number of results")
@click.option("--source-type", "-t", help="Filter by source type (youtube, web_article)")
@click.option("--definitions", is_flag=True, help="Search only for definitions")
@click.option("--threshold", default=0.5, help="Minimum similarity score (0-1)")
def search(query: str, user_id: str, limit: int, source_type: Optional[str], definitions: bool, threshold: float):
    """
    Search the knowledge base.
    
    Examples:
    
        synaptiq search "What is a tensor?" -u my_user_id
        
        synaptiq search "machine learning" -u my_user_id --limit 10
        
        synaptiq search "neural networks" -u my_user_id --definitions
    """
    from synaptiq.processors.embedder import EmbeddingGenerator
    from synaptiq.storage.qdrant import QdrantStore

    async def _search():
        qdrant = QdrantStore()
        embedder = EmbeddingGenerator()

        try:
            await qdrant.ensure_collection()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Generating query embedding...", total=None)
                query_vector = await embedder.generate_single(query)

                progress.update(task, description="Searching...")
                results = await qdrant.search(
                    query_vector=query_vector,
                    user_id=user_id,
                    limit=limit,
                    source_type=source_type,
                    has_definition=True if definitions else None,
                    score_threshold=threshold,
                )

            if not results:
                console.print("[yellow]No results found.[/yellow]")
                return

            console.print(f"\n[green]Found {len(results)} results:[/green]\n")

            for i, hit in enumerate(results, 1):
                payload = hit["payload"]
                score = hit["score"]

                # Build citation URL
                citation_url = payload.get("source_url", "")
                if payload.get("source_type") == "youtube" and payload.get("timestamp_start_ms"):
                    seconds = payload["timestamp_start_ms"] // 1000
                    citation_url = f"{citation_url}&t={seconds}s"

                console.print(f"[bold cyan]Result {i}[/bold cyan] (score: {score:.3f})")
                console.print(f"[blue]Source:[/blue] {payload.get('source_title', 'Unknown')}")
                console.print(f"[blue]Type:[/blue] {payload.get('source_type', 'unknown')}")
                
                if payload.get("timestamp_start_ms"):
                    start_sec = payload["timestamp_start_ms"] // 1000
                    mins, secs = divmod(start_sec, 60)
                    console.print(f"[blue]Timestamp:[/blue] {mins}:{secs:02d}")

                console.print(f"[blue]URL:[/blue] {citation_url}")
                
                # Truncate text for display
                text = payload.get("text", "")
                if len(text) > 300:
                    text = text[:300] + "..."
                console.print(f"[dim]{text}[/dim]")
                console.print()

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            sys.exit(1)

        finally:
            await qdrant.close()

    run_async(_search())


@cli.command()
@click.option("--user-id", "-u", required=True, help="User ID")
@click.option("--source-type", "-t", help="Filter by source type")
@click.option("--limit", "-n", default=20, help="Number of results")
def sources(user_id: str, source_type: Optional[str], limit: int):
    """
    List ingested sources.
    
    Examples:
    
        synaptiq sources -u my_user_id
        
        synaptiq sources -u my_user_id --source-type youtube
    """
    from synaptiq.storage.mongodb import MongoDBStore

    async def _list_sources():
        mongo = MongoDBStore()

        try:
            sources_list = await mongo.list_sources(
                user_id=user_id,
                source_type=source_type,
                limit=limit,
            )

            if not sources_list:
                console.print("[yellow]No sources found.[/yellow]")
                return

            table = Table(title=f"Sources for {user_id}")
            table.add_column("ID", style="dim")
            table.add_column("Type", style="cyan")
            table.add_column("Title", style="green")
            table.add_column("Ingested", style="blue")

            for source in sources_list:
                ingested_at = source.get("ingested_at", "")
                if hasattr(ingested_at, "strftime"):
                    ingested_at = ingested_at.strftime("%Y-%m-%d %H:%M")

                table.add_row(
                    source["id"][:8] + "...",
                    source.get("source_type", "unknown"),
                    source.get("source_title", "Unknown")[:50],
                    str(ingested_at),
                )

            console.print(table)
            console.print(f"\nTotal: {len(sources_list)} sources")

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            sys.exit(1)

        finally:
            await mongo.close()

    run_async(_list_sources())


@cli.command()
@click.option("--user-id", "-u", required=True, help="User ID")
@click.option("--status", "-s", help="Filter by status (pending, processing, completed, failed)")
@click.option("--limit", "-n", default=20, help="Number of results")
def jobs(user_id: str, status: Optional[str], limit: int):
    """
    List ingestion jobs.
    
    Examples:
    
        synaptiq jobs -u my_user_id
        
        synaptiq jobs -u my_user_id --status pending
    """
    from synaptiq.core.schemas import JobStatus
    from synaptiq.storage.mongodb import MongoDBStore

    async def _list_jobs():
        mongo = MongoDBStore()

        try:
            job_status = None
            if status:
                try:
                    job_status = JobStatus(status)
                except ValueError:
                    console.print(f"[red]Invalid status.[/red] Must be one of: {[s.value for s in JobStatus]}")
                    sys.exit(1)

            jobs_list = await mongo.list_jobs(
                user_id=user_id,
                status=job_status,
                limit=limit,
            )

            if not jobs_list:
                console.print("[yellow]No jobs found.[/yellow]")
                return

            table = Table(title=f"Jobs for {user_id}")
            table.add_column("ID", style="dim")
            table.add_column("Status", style="cyan")
            table.add_column("URL", style="green")
            table.add_column("Chunks", style="blue")
            table.add_column("Created", style="dim")

            for job in jobs_list:
                status_style = {
                    "pending": "yellow",
                    "processing": "blue",
                    "completed": "green",
                    "failed": "red",
                }.get(job.status.value, "white")

                table.add_row(
                    job.id[:8] + "...",
                    f"[{status_style}]{job.status.value}[/{status_style}]",
                    job.source_url[:40] + "..." if len(job.source_url) > 40 else job.source_url,
                    str(job.chunks_processed),
                    job.created_at.strftime("%Y-%m-%d %H:%M"),
                )

            console.print(table)

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            sys.exit(1)

        finally:
            await mongo.close()

    run_async(_list_jobs())


@cli.command()
@click.argument("source_id")
@click.option("--user-id", "-u", required=True, help="User ID")
@click.option("--confirm", is_flag=True, help="Skip confirmation")
def delete(source_id: str, user_id: str, confirm: bool):
    """
    Delete a source and its chunks.
    
    Examples:
    
        synaptiq delete abc123 -u my_user_id --confirm
    """
    from synaptiq.storage.mongodb import MongoDBStore
    from synaptiq.storage.qdrant import QdrantStore

    async def _delete():
        mongo = MongoDBStore()
        qdrant = QdrantStore()

        try:
            # Get source info
            doc = await mongo.get_source(source_id)
            if not doc:
                console.print(f"[red]Source not found:[/red] {source_id}")
                sys.exit(1)

            if doc.user_id != user_id:
                console.print("[red]Not authorized to delete this source.[/red]")
                sys.exit(1)

            # Confirm deletion
            if not confirm:
                console.print(f"[yellow]About to delete:[/yellow]")
                console.print(f"  Title: {doc.source_title}")
                console.print(f"  URL: {doc.source_url}")
                console.print(f"  Type: {doc.source_type.value}")
                
                if not click.confirm("Are you sure?"):
                    console.print("Cancelled.")
                    return

            # Delete from Qdrant
            chunks_deleted = await qdrant.delete_by_document(source_id, user_id)

            # Delete from MongoDB
            await mongo.delete_source(source_id, user_id)

            console.print(f"[green]✓ Deleted source and {chunks_deleted} chunks.[/green]")

        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            sys.exit(1)

        finally:
            await mongo.close()
            await qdrant.close()

    run_async(_delete())


@cli.command()
def init():
    """
    Initialize the storage backends.
    
    Creates MongoDB indexes and Qdrant collection.
    """
    from synaptiq.storage.mongodb import MongoDBStore
    from synaptiq.storage.qdrant import QdrantStore

    async def _init():
        console.print("[blue]Initializing storage backends...[/blue]")

        try:
            # Initialize MongoDB
            console.print("  MongoDB indexes...", end=" ")
            mongo = MongoDBStore()
            await mongo.ensure_indexes()
            console.print("[green]✓[/green]")
            await mongo.close()

            # Initialize Qdrant
            console.print("  Qdrant collection...", end=" ")
            qdrant = QdrantStore()
            await qdrant.ensure_collection()
            info = await qdrant.get_collection_info()
            console.print(f"[green]✓[/green] ({info.get('points_count', 0)} points)")
            await qdrant.close()

            console.print("\n[green]✓ Initialization complete![/green]")

        except Exception as e:
            console.print(f"\n[red]Error:[/red] {str(e)}")
            sys.exit(1)

    run_async(_init())


@cli.command()
def status():
    """
    Check connection status for all backends.
    """
    from synaptiq.storage.mongodb import MongoDBStore
    from synaptiq.storage.qdrant import QdrantStore

    async def _status():
        console.print("[blue]Checking backend status...[/blue]\n")

        # Check MongoDB
        console.print("MongoDB:", end=" ")
        try:
            mongo = MongoDBStore()
            await mongo.db.command("ping")
            console.print("[green]✓ Connected[/green]")
            await mongo.close()
        except Exception as e:
            console.print(f"[red]✗ {str(e)[:50]}[/red]")

        # Check Qdrant
        console.print("Qdrant:", end=" ")
        try:
            qdrant = QdrantStore()
            info = await qdrant.get_collection_info()
            if "error" in info:
                console.print(f"[yellow]! {info['error'][:50]}[/yellow]")
            else:
                console.print(f"[green]✓ Connected ({info.get('points_count', 0)} points)[/green]")
            await qdrant.close()
        except Exception as e:
            console.print(f"[red]✗ {str(e)[:50]}[/red]")

        # Check Redis (for Celery)
        console.print("Redis:", end=" ")
        try:
            import redis
            from config.settings import get_settings
            settings = get_settings()
            r = redis.from_url(settings.redis_url)
            r.ping()
            console.print("[green]✓ Connected[/green]")
        except Exception as e:
            console.print(f"[red]✗ {str(e)[:50]}[/red]")

    run_async(_status())


# Entry point
if __name__ == "__main__":
    cli()


