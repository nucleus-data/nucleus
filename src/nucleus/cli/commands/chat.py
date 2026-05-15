"""``nucleus chat`` — AI Copilot single-turn chat command (v0.2, Beta).

Per ADR-015 §1 + nucleus_cli_spec.md §3.8 (eighth command, Beta tier).
Delegates all logic to :func:`nucleus.intelligence.chat`.

Architecture ref: ``nucleus_architecture_v4.1.md`` §7.2 + ADR-015
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from nucleus.errors import NucleusError
from nucleus.intelligence.copilot import CopilotReply, chat as _chat


def chat(
    question: Annotated[
        str,
        typer.Argument(
            help='The question to ask the Copilot, e.g. "Why did my last run fail?"',
        ),
    ],
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="Override provider: [bold]anthropic[/bold] | openai | ollama.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Override model id (provider-specific; checked against provider docs).",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output the full CopilotReply as JSON instead of plain text.",
        ),
    ] = False,
) -> None:
    """Ask the AI Copilot a question about your Nucleus project.

    Auto-injects project metadata as context (asset graph summary, recent
    errors). Enforces opt-in privacy gate (ADR-015 §4) and a pre-flight
    cost ceiling before any bytes leave the laptop.

    Set the relevant API key env var before using a cloud provider:
      [bold]ANTHROPIC_API_KEY[/bold]   — for the default Anthropic provider
      [bold]OPENAI_API_KEY[/bold]       — for OpenAI
      [bold]OLLAMA_HOST[/bold]          — for local Ollama (default: http://localhost:11434)

    Per [bold]nucleus_cli_spec.md §3.8[/bold]. Beta tier (ADR-005 §2):
    single-turn synchronous; multi-turn and streaming deferred to v0.3+.

    [bold]Examples[/bold]

        nucleus chat "Why did my last run fail?"
        nucleus chat "How do I ingest a CSV file?" --provider ollama
        nucleus chat "Show me the asset graph" --json
    """
    try:
        reply: CopilotReply = _chat(
            question,
            project_root=Path.cwd(),
            provider=provider,
            model=model,
        )
    except NucleusError as err:
        # UX audit Rec #3 (2026-05-15): bracket-prefix the NE-code so users
        # can grep NE4001 / NE4002 etc. directly from terminal output.
        code_tag = getattr(err, "error_code", "") or "NE3001"
        typer.echo(f"Error [{code_tag}]: {err.user_message}", err=True)
        if err.fix_hint:
            typer.echo(f"Fix:   {err.fix_hint}", err=True)
        typer.echo(f"Docs:  {err.docs_url}", err=True)
        raise typer.Exit(code=1) from err

    if json_output:
        payload = {
            "_schema_version": 1,
            "text": reply.text,
            "suggested_command": reply.suggested_command,
            "tokens_in": reply.tokens_in,
            "tokens_out": reply.tokens_out,
            "cost_usd": reply.cost_usd,
            "provider": reply.provider,
            "model": reply.model,
        }
        sys.stdout.write(json.dumps(payload) + "\n")
        return

    # Plain-text output: render markdown via rich.
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    console.print(Markdown(reply.text))
    if reply.suggested_command:
        typer.echo(f"\nSuggested: {reply.suggested_command}")
