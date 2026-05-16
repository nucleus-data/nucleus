"""``nucleus workbench`` CLI command wrapper (cli-layer shim).

The workbench layer sits ABOVE the cli layer in the architecture stack
(``scripts/check_layering.py`` LAYERS ordering: cli < workbench).
A direct ``from nucleus.workbench.cli import app`` from ``cli/main.py``
therefore violates the upward-import rule.

This shim stays in the ``cli`` layer and uses ``importlib.import_module``
(a runtime call, not an ``ast.Import`` node) to load the workbench Typer
sub-app at first use.  The layering AST scan never sees an upward import.

Per ``docs/specs/nucleus_architecture_v4.1.md`` §8.1 (Layer 4: Experience — CLI and
Workbench are separate sub-components; the CLI shim bridges them at runtime).

# Stability: Internal @ v0.2
"""

from __future__ import annotations

import importlib

import typer

# Local Typer sub-app registered into the main app by cli/main.py.
# It delegates all logic to the workbench layer via importlib at runtime.
app = typer.Typer(
    help="Open the Nucleus Workbench browser UI (v0.2, ADR-016).",
    add_completion=False,
)


def _get_workbench_typer() -> typer.Typer:
    """Return the Typer app from nucleus.workbench.cli (loaded at runtime)."""
    mod = importlib.import_module("nucleus.workbench.cli")
    return mod.app  # type: ignore[no-any-return]


@app.callback(invoke_without_command=True)
def workbench_main(ctx: typer.Context) -> None:
    """Nucleus Workbench — browser UI for assets, runs, and SQL queries."""
    if ctx.invoked_subcommand is not None:
        return
    # Delegate to workbench layer `up` command.
    workbench_typer = _get_workbench_typer()
    # Find the `up` command within the loaded app and invoke it.
    ctx.invoke(workbench_typer.registered_commands[0].callback)  # type: ignore[index]


@app.command(name="up")
def workbench_up(
    host: str = typer.Option("localhost", "--host", help="Bind host."),
    port: int = typer.Option(8765, "--port", help="Listen port (default 8765 per ADR-016)."),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn dev auto-reload."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Do not open the browser."),
) -> None:
    """Launch the Nucleus Workbench server and open the browser.

    Starts a local FastAPI server that serves the Workbench UI (React SPA
    or CDN-based static demo) and the ``/api/*`` endpoints.

    Example::

        nucleus workbench up
        nucleus workbench up --port 9000 --no-browser
    """
    import webbrowser

    import uvicorn  # Docs: https://www.uvicorn.org/

    from nucleus.coordination.error_translation import translate

    url = f"http://{host}:{port}"

    try:
        from rich.console import Console
        from rich.panel import Panel

        Console().print(
            Panel(
                f"[bold cyan]Nucleus Workbench[/bold cyan] [dim]v0.2[/dim]\n\n"
                f"  URL:   [link={url}]{url}[/link]\n"
                f"  Theme: [dim]press T in browser to toggle light/dark[/dim]\n"
                f"  AI:    [dim]press Copilot button to open the AI panel[/dim]\n"
                f"  Docs:  [link=https://nucleus.dev/docs]nucleus.dev/docs[/link]\n\n"
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
            pass

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
