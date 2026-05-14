# ruff: noqa: ARG002
"""Tests for ``nucleus chat`` — nucleus_cli_spec.md §3.8 + ADR-015 §1.

Exercises the chat command surface end-to-end:

- ``--help`` exits 0 and lists the chat command
- Chat command appears in the root ``nucleus --help`` listing
- Happy path: mocked Copilot returns a CopilotReply; CLI exits 0 with text
- ``--provider`` flag forwards to the Copilot
- ``--model`` flag forwards to the Copilot
- ``--json`` flag emits JSON-serializable structure with every reply field
- Error path: NucleusError raised by Copilot → exit 1; NE code + user_message
  + fix_hint + docs_url all reach stderr
- Error path: docs_url-only fallback (when fix_hint is empty)
- No external library classnames in user-facing strings
- Suggested command renders after the markdown body in plain-text mode

The chat command imports ``chat as _chat`` from ``nucleus.intelligence.copilot``
inside ``src/nucleus/cli/commands/chat.py``; per AGENTS.md §11.10 the patch
target is the imported binding (``nucleus.cli.commands.chat._chat``), NOT the
upstream module — patching the upstream symbol would not redirect the import
that the CLI already resolved at module load time.

Docs:
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
- unittest.mock.patch: https://docs.python.org/3/library/unittest.mock.html
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from nucleus.cli.main import app
from nucleus.errors import (
    NucleusBudgetExceededError,
    NucleusConfigError,
    NucleusCopilotAuthError,
    NucleusCopilotRateLimitError,
)
from nucleus.intelligence.copilot import CopilotReply

_FORBIDDEN_CLASSNAMES = (
    "litellm",
    "LiteLLM",
    "anthropic.",
    "openai.",
    "ollama.",
    "API_KEY",
    "Traceback (most recent call last)",
    "dagster._",
    "duckdb._",
    "polars._",
    "pyiceberg._",
)

# mix_stderr=False so we can assert separately on stdout vs stderr —
# the chat command writes user-facing errors to stderr per cli_spec §5.4.
runner = CliRunner(mix_stderr=False)


def _make_reply(
    *,
    text: str = "Hello from the Copilot.",
    suggested_command: str | None = None,
    tokens_in: int = 100,
    tokens_out: int = 50,
    cost_usd: float = 0.0042,
    provider: str = "anthropic",
    model: str = "claude-3-5-haiku-20241022",
) -> CopilotReply:
    """Build a frozen CopilotReply for use as a mock return value."""
    return CopilotReply(
        text=text,
        suggested_command=suggested_command,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        provider=provider,
        model=model,
    )


@pytest.fixture
def in_tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test inside an isolated tmp directory.

    Required because the chat command passes ``project_root=Path.cwd()`` to
    the Copilot, and the Copilot's opt-in gate writes to
    ``<project_root>/.nucleus/copilot_opt_in``. Hermetic tests must keep
    every write inside ``tmp_path``.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ============================================================================
# Help surface
# ============================================================================


class TestHelp:
    """The chat command must be discoverable via help."""

    def test_chat_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0, f"unexpected exit:\n{result.stdout}"

    def test_chat_help_mentions_provider_flag(self) -> None:
        result = runner.invoke(app, ["chat", "--help"])
        assert "--provider" in result.stdout

    def test_chat_help_mentions_json_flag(self) -> None:
        result = runner.invoke(app, ["chat", "--help"])
        assert "--json" in result.stdout

    def test_chat_command_appears_in_root_help(self) -> None:
        """``nucleus --help`` must list the chat command alongside v0.1 commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "chat" in result.stdout, (
            f"'chat' missing from root help; output was:\n{result.stdout}"
        )


# ============================================================================
# Happy path
# ============================================================================


class TestHappyPath:
    """Mocked Copilot replies render cleanly to stdout and exit 0."""

    def test_exit_code_zero(self, in_tmp_dir: Path) -> None:
        reply = _make_reply(text="The asset materialised at 12:01.")
        with patch("nucleus.cli.commands.chat._chat", return_value=reply):
            result = runner.invoke(app, ["chat", "Why did my run fail?"])
        assert result.exit_code == 0, f"unexpected: {result.stdout} | {result.stderr}"

    def test_text_appears_in_stdout(self, in_tmp_dir: Path) -> None:
        reply = _make_reply(text="The asset materialised at 12:01.")
        with patch("nucleus.cli.commands.chat._chat", return_value=reply):
            result = runner.invoke(app, ["chat", "Why did my run fail?"])
        assert "materialised" in result.stdout

    def test_question_forwarded_to_copilot(self, in_tmp_dir: Path) -> None:
        reply = _make_reply()
        with patch("nucleus.cli.commands.chat._chat", return_value=reply) as mock_chat:
            runner.invoke(app, ["chat", "What is asset raw.users?"])
        assert mock_chat.call_count == 1
        args, _kwargs = mock_chat.call_args
        assert args[0] == "What is asset raw.users?"

    def test_default_provider_is_none_when_unspecified(self, in_tmp_dir: Path) -> None:
        """Without --provider, the CLI passes provider=None so the Copilot uses config."""
        reply = _make_reply()
        with patch("nucleus.cli.commands.chat._chat", return_value=reply) as mock_chat:
            runner.invoke(app, ["chat", "anything"])
        assert mock_chat.call_args.kwargs["provider"] is None
        assert mock_chat.call_args.kwargs["model"] is None

    def test_provider_flag_overrides_config(self, in_tmp_dir: Path) -> None:
        reply = _make_reply(provider="ollama")
        with patch("nucleus.cli.commands.chat._chat", return_value=reply) as mock_chat:
            result = runner.invoke(app, ["chat", "anything", "--provider", "ollama"])
        assert result.exit_code == 0
        assert mock_chat.call_args.kwargs["provider"] == "ollama"

    def test_model_flag_overrides_config(self, in_tmp_dir: Path) -> None:
        reply = _make_reply()
        with patch("nucleus.cli.commands.chat._chat", return_value=reply) as mock_chat:
            result = runner.invoke(
                app, ["chat", "anything", "--model", "gpt-4o-mini"]
            )
        assert result.exit_code == 0
        assert mock_chat.call_args.kwargs["model"] == "gpt-4o-mini"

    def test_project_root_is_cwd(self, in_tmp_dir: Path) -> None:
        """The CLI passes ``Path.cwd()`` as project_root so opt-in writes locally."""
        reply = _make_reply()
        with patch("nucleus.cli.commands.chat._chat", return_value=reply) as mock_chat:
            runner.invoke(app, ["chat", "anything"])
        passed_root = mock_chat.call_args.kwargs["project_root"]
        assert isinstance(passed_root, Path)
        assert passed_root.resolve() == in_tmp_dir.resolve()

    def test_suggested_command_rendered_after_text(self, in_tmp_dir: Path) -> None:
        reply = _make_reply(
            text="Run the asset to refresh data.",
            suggested_command="nucleus run raw.orders",
        )
        with patch("nucleus.cli.commands.chat._chat", return_value=reply):
            result = runner.invoke(app, ["chat", "How do I refresh?"])
        assert result.exit_code == 0
        assert "nucleus run raw.orders" in result.stdout
        text_index = result.stdout.find("refresh data")
        cmd_index = result.stdout.find("nucleus run raw.orders")
        assert 0 <= text_index < cmd_index, (
            "suggested command must render AFTER reply text"
        )

    def test_no_suggested_command_when_none(self, in_tmp_dir: Path) -> None:
        reply = _make_reply(text="No action needed.", suggested_command=None)
        with patch("nucleus.cli.commands.chat._chat", return_value=reply):
            result = runner.invoke(app, ["chat", "What now?"])
        assert "Suggested:" not in result.stdout


# ============================================================================
# --json output
# ============================================================================


class TestJsonOutput:
    """``--json`` emits a single line of valid JSON with every CopilotReply field."""

    def test_json_output_parses(self, in_tmp_dir: Path) -> None:
        reply = _make_reply(
            text="Pipeline failed because of a schema mismatch.",
            suggested_command="nucleus run raw.users",
            tokens_in=42,
            tokens_out=21,
            cost_usd=0.0001,
            provider="anthropic",
            model="claude-3-5-haiku-20241022",
        )
        with patch("nucleus.cli.commands.chat._chat", return_value=reply):
            result = runner.invoke(app, ["chat", "Why did it fail?", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout.strip())
        assert isinstance(payload, dict)

    def test_json_output_contains_all_reply_fields(self, in_tmp_dir: Path) -> None:
        reply = _make_reply(
            text="Body text.",
            suggested_command="nucleus run raw.x",
            tokens_in=10,
            tokens_out=5,
            cost_usd=0.0,
            provider="ollama",
            model="llama3.1:8b",
        )
        with patch("nucleus.cli.commands.chat._chat", return_value=reply):
            result = runner.invoke(app, ["chat", "anything", "--json"])
        payload = json.loads(result.stdout.strip())
        assert payload["text"] == "Body text."
        assert payload["suggested_command"] == "nucleus run raw.x"
        assert payload["tokens_in"] == 10
        assert payload["tokens_out"] == 5
        assert payload["cost_usd"] == 0.0
        assert payload["provider"] == "ollama"
        assert payload["model"] == "llama3.1:8b"

    def test_json_output_carries_schema_version(self, in_tmp_dir: Path) -> None:
        """Per ADR-015 the JSON envelope carries a schema version for forward-compat."""
        reply = _make_reply()
        with patch("nucleus.cli.commands.chat._chat", return_value=reply):
            result = runner.invoke(app, ["chat", "anything", "--json"])
        payload = json.loads(result.stdout.strip())
        assert "_schema_version" in payload
        assert isinstance(payload["_schema_version"], int)


# ============================================================================
# Error path
# ============================================================================


class TestErrorPaths:
    """NucleusError raised by the Copilot exits 1 with a clean rendering."""

    def test_auth_error_exits_one(self, in_tmp_dir: Path) -> None:
        err = NucleusCopilotAuthError(
            user_message="The Copilot provider rejected your credentials.",
            fix_hint="Set ANTHROPIC_API_KEY and re-run.",
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        assert result.exit_code == 1

    def test_auth_error_user_message_in_stderr(self, in_tmp_dir: Path) -> None:
        err = NucleusCopilotAuthError(
            user_message="The Copilot provider rejected your credentials.",
            fix_hint="Set ANTHROPIC_API_KEY and re-run.",
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        assert "rejected your credentials" in result.stderr

    def test_auth_error_fix_hint_in_stderr(self, in_tmp_dir: Path) -> None:
        err = NucleusCopilotAuthError(
            user_message="Auth failed.",
            fix_hint="Set ANTHROPIC_API_KEY and re-run.",
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        assert "Set ANTHROPIC_API_KEY" in result.stderr

    def test_auth_error_docs_url_in_stderr(self, in_tmp_dir: Path) -> None:
        err = NucleusCopilotAuthError(
            user_message="Auth failed.", fix_hint=""
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        assert "nucleus.dev/errors" in result.stderr

    def test_rate_limit_error_routes_through_same_handler(
        self, in_tmp_dir: Path
    ) -> None:
        err = NucleusCopilotRateLimitError(
            user_message="Rate limit exceeded.",
            fix_hint="Wait and retry, or switch to --provider ollama.",
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        assert result.exit_code == 1
        assert "Rate limit exceeded" in result.stderr
        assert "ollama" in result.stderr

    def test_budget_exceeded_routes_cleanly(self, in_tmp_dir: Path) -> None:
        err = NucleusBudgetExceededError(
            user_message="Estimated cost $0.5000 exceeds the ceiling $0.10.",
            fix_hint="Raise copilot.cost_ceiling_usd or shorten the question.",
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "long question"])
        assert result.exit_code == 1
        assert "exceeds the ceiling" in result.stderr

    def test_config_error_when_optin_declined(self, in_tmp_dir: Path) -> None:
        """Opt-in declined surfaces as NucleusConfigError exit 1."""
        err = NucleusConfigError(
            user_message="Copilot opt-in declined. No data was sent.",
            fix_hint=(
                "Re-run `nucleus chat` and accept the prompt, "
                "or set `copilot.opt_in: true` in nucleus_project.yaml."
            ),
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        assert result.exit_code == 1
        assert "opt-in declined" in result.stderr

    def test_no_forbidden_classnames_in_error(self, in_tmp_dir: Path) -> None:
        """Error rendering must never leak external library identifiers."""
        err = NucleusCopilotAuthError(
            user_message="Auth failed.", fix_hint="Set the API key."
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        combined = result.stdout + result.stderr
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in combined, (
                f"forbidden term {term!r} leaked: {combined!r}"
            )

    def test_error_with_empty_fix_hint_omits_fix_line(
        self, in_tmp_dir: Path
    ) -> None:
        """When fix_hint is empty, the rendered output must not show a stray 'Fix:' line."""
        err = NucleusCopilotAuthError(
            user_message="Auth failed.", fix_hint=""
        )
        with patch("nucleus.cli.commands.chat._chat", side_effect=err):
            result = runner.invoke(app, ["chat", "anything"])
        assert result.exit_code == 1
        assert "Auth failed" in result.stderr
        for line in result.stderr.splitlines():
            assert not line.startswith("Fix:"), (
                f"empty fix_hint should not render a 'Fix:' line; got: {line!r}"
            )


# ============================================================================
# Hermetic guarantees
# ============================================================================


class TestHermeticity:
    """The CLI must never reach the live LLM provider during tests."""

    def test_no_real_network_call(self, in_tmp_dir: Path) -> None:
        """A failing mock proves the test isn't silently hitting a real provider."""
        sentinel = MagicMock(side_effect=AssertionError("real Copilot called!"))
        with patch("nucleus.cli.commands.chat._chat", sentinel):
            runner.invoke(app, ["chat", "anything"])
        sentinel.assert_called_once()  # runner.invoke catches the assertion
