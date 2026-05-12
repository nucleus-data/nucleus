"""Nucleus CLI — main entry point.

This module exposes the Typer ``app`` that ``pyproject.toml`` wires as
the ``nucleus`` console script. v0.0.0 ships with only ``--version`` and
``--help``; commands grow tier by tier (see ``nucleus_cli_spec.md``).

Typical invocations::

    nucleus --version
    nucleus --help

Future commands (Tier 0 onward) land as additional ``@app.command()``
functions in this same package — most likely as sibling files importing
the shared ``app`` from here.
"""

from __future__ import annotations

import typer

from nucleus import __version__

# The Typer app — this is the symbol ``pyproject.toml`` references as
#   nucleus = "nucleus.cli.main:app"
app = typer.Typer(
    name="nucleus",
    help="Nucleus — modern composable data engineering platform (AI-assisted).",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,  # We render NucleusError ourselves.
)


def _version_callback(value: bool) -> None:
    """Print version and exit when ``--version`` is given."""
    if value:
        typer.echo(f"nucleus {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Nucleus operator CLI. Run ``nucleus --help`` for available commands."""
    # Tier 0+: configure logging here once the _internal.logging module is
    # wired up by the real first command. Stub for now.
    _ = version  # placate ruff ARG001 in scaffold state


if __name__ == "__main__":
    # Enable ``python -m nucleus.cli.main`` for dev convenience.
    app()
