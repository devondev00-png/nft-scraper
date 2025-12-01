#!/usr/bin/env python3
"""
NFT Scout CLI entrypoint
"""

import asyncio
import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from loguru import logger

from src.nft_scout import NFTScout, Chain
from src.nft_scout.config import config

app = typer.Typer(help="NFT Scout - Multi-chain NFT data scraper")
console = Console()


@app.command()
def wallet(
    address: str = typer.Argument(..., help="Wallet address or ENS name"),
    chains: str = typer.Option("ethereum", help="Comma-separated chains (ethereum,polygon,solana)"),
    include_transfers: bool = typer.Option(False, "--include-transfers", help="Include transfer history"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
):
    """Get all NFTs owned by a wallet"""
    chain_list = [Chain.from_string(c.strip()) for c in chains.split(",")]
    
    async def fetch_nfts():
        scout = NFTScout()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Fetching NFTs for {address}...", total=None)
            response = await scout.get_wallet_nfts(
                address,
                chain_list,
                include_transfers=include_transfers,
            )
            progress.update(task, completed=True)
        
        # Display results
        console.print(f"\n[bold green]Found {response.total_count} NFTs[/bold green]")
        
        if response.nfts:
            table = Table(title=f"NFTs for {address}")
            table.add_column("Chain", style="cyan")
            table.add_column("Collection", style="magenta")
            table.add_column("Token ID", style="yellow")
            table.add_column("Name", style="white")
            
            for nft in response.nfts[:20]:  # Show first 20
                table.add_row(
                    nft.chain.value,
                    nft.collection_name or "Unknown",
                    str(nft.token_id)[:20] + "..." if len(str(nft.token_id)) > 20 else str(nft.token_id),
                    nft.name or "Unnamed",
                )
            
            console.print(table)
            
            if response.total_count > 20:
                console.print(f"\n[dim]... and {response.total_count - 20} more[/dim]")
        
        if output:
            import json
            with open(output, "w") as f:
                json.dump([nft.dict() for nft in response.nfts], f, indent=2, default=str)
            console.print(f"\n[green]Saved to {output}[/green]")
    
    asyncio.run(fetch_nfts())


@app.command()
def collection(
    contract: str = typer.Argument(..., help="Collection contract address"),
    chain: str = typer.Option("ethereum", help="Blockchain (ethereum, polygon, solana, etc.)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
):
    """Get all NFTs in a collection"""
    chain_enum = Chain.from_string(chain)
    
    async def fetch_collection():
        scout = NFTScout()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Fetching collection {contract}...", total=None)
            response = await scout.get_collection_nfts(contract, chain_enum)
            progress.update(task, completed=True)
        
        console.print(f"\n[bold green]Found {response.total_count} NFTs in collection[/bold green]")
        
        if response.nfts:
            table = Table(title=f"Collection: {contract}")
            table.add_column("Token ID", style="yellow")
            table.add_column("Name", style="white")
            table.add_column("Owner", style="cyan")
            
            for nft in response.nfts[:20]:
                table.add_row(
                    str(nft.token_id)[:20] + "..." if len(str(nft.token_id)) > 20 else str(nft.token_id),
                    nft.name or "Unnamed",
                    (nft.owner_address or "Unknown")[:20] + "..." if nft.owner_address and len(nft.owner_address) > 20 else (nft.owner_address or "Unknown"),
                )
            
            console.print(table)
        
        if output:
            import json
            with open(output, "w") as f:
                json.dump([nft.dict() for nft in response.nfts], f, indent=2, default=str)
            console.print(f"\n[green]Saved to {output}[/green]")
    
    asyncio.run(fetch_collection())


@app.command()
def stats(
    contract: str = typer.Argument(..., help="Collection contract address"),
    chain: str = typer.Option("ethereum", help="Blockchain"),
):
    """Get collection statistics"""
    chain_enum = Chain.from_string(chain)
    
    async def fetch_stats():
        scout = NFTScout()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Fetching stats for {contract}...", total=None)
            stats = await scout.get_collection_stats(contract, chain_enum)
            progress.update(task, completed=True)
        
        table = Table(title=f"Collection Stats: {stats.name or contract}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Chain", stats.chain.value)
        table.add_row("Name", stats.name or "Unknown")
        table.add_row("Total Supply", str(stats.total_supply) if stats.total_supply else "Unknown")
        table.add_row("Total Owners", str(stats.total_owners) if stats.total_owners else "Unknown")
        table.add_row("Floor Price", f"{stats.floor_price} {stats.floor_price_currency}" if stats.floor_price else "Unknown")
        table.add_row("Total Volume", str(stats.total_volume) if stats.total_volume else "Unknown")
        table.add_row("Verified", "✓" if stats.verified else "✗")
        
        console.print(table)
    
    asyncio.run(fetch_stats())


@app.command()
def serve_webhooks(
    port: int = typer.Option(8000, "--port", "-p", help="Port to run webhook server on"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
):
    """Start webhook server"""
    import uvicorn
    from src.nft_scout.webhooks.app import app as webhook_app
    
    console.print(f"[bold green]Starting webhook server on {host}:{port}[/bold green]")
    console.print(f"[dim]Endpoints:[/dim]")
    console.print(f"  POST /webhook/alchemy")
    console.print(f"  POST /webhook/moralis")
    console.print(f"  POST /webhook/helius")
    console.print(f"  GET  /webhook/events")
    console.print(f"  GET  /health")
    
    uvicorn.run(webhook_app, host=host, port=port)


if __name__ == "__main__":
    app()

