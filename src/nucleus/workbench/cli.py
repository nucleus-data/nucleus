"""Typer entry for ``nucleus workbench`` commands.

Per ``docs/decisions/ADR-016-workbench-mvp.md`` §3 (Fork B).
``nucleus_architecture_v4.1.md`` §8.1 — Layer 4 Experience.

Sub-commands:
    nucleus workbench up   — launch uvicorn + open browser (default)

Wired into ``nucleus.cli.main`` via:
    app.add_typer(workbench_app, name="workbench", ...)

# Stability: Internal @ v0.2
"""

from __future__ import annotations

import webbrowser

import typer
import uvicorn  # Docs: https://www.uvicorn.org/

from nucleus.coordination.error_translation import translate

app = typer.Typer(
    help="Run the Nucleus Workbench (FastAPI + React SPA).",
    add_completion=False,
)

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 8765


@app.command(name="up")
def workbench_up(
    host: str = typer.Option(
        _DEFAULT_HOST,
        "--host",
        help="Bind host.",
    ),
    port: int = typer.Option(
        _DEFAULT_PORT,
        "--port",
        help="Listen port (default 8765 per ADR-016).",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable uvicorn dev auto-reload.",
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Do not open the browser automatically.",
    ),
) -> None:
    """Launch the Nucleus Workbench server and open the browser.

    Starts a local FastAPI server that serves the Workbench UI (React SPA
    or CDN-based static demo) and the ``/api/*`` endpoints.

    Example::

        nucleus workbench up
        nucleus workbench up --port 9000 --no-browser
    """
    url = f"http://{host}:{port}"

    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console()
        console.print(
            Panel(
                f"[bold cyan]Nucleus Workbench[/bold cyan] [dim]v0.2[/dim]\n\n"
                f"  URL:   [link={url}]{url}[/link]\n"
                f"  Theme: [dim]press T in the browser to toggle light/dark[/dim]\n"
                f"  AI:    [dim]press the sparkle icon to open the Copilot panel[/dim]\n"
                f"  Docs:  [link=http://nucleus.dev/docs]nucleus.dev/docs[/link]\n\n"
                f"  [dim]Press Ctrl+C to stop.[/dim]",
                title="[bold]nucleus workbench up[/bold]",
                border_style="cyan",
            )
        )
    except ImportError:
        typer.echo(f"Nucleus Workbench running at {url}")
        typer.echo("Press Ctrl+C to stop.")

    if not no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # Non-fatal; user sees the URL in the panel above.

    try:
        uvicorn.run(
            "nucleus.workbench.app:create_app",
            host=host,
            port=port,
            reload=reload,
            factory=True,
        )
    except Exception as exc:
        err = translate(exc)
        typer.secho(err.rendered(), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from err


@app.callback(invoke_without_command=True)
def workbench_main(ctx: typer.Context) -> None:
    """Nucleus Workbench — browser UI for assets, runs, and SQL queries."""
    if ctx.invoked_subcommand is None:
        # Default action when called with no sub-command: run `up`.
        ctx.invoke(workbench_up)
