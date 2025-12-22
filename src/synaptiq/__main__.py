"""
Entry point for running the CLI as a module.

Usage:
    python -m synaptiq <command>
"""

from synaptiq.cli.commands import cli

if __name__ == "__main__":
    cli()


