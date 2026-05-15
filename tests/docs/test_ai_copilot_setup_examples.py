"""Static checks for ``docs/cookbook/ai-copilot-setup.md``.

Validates referenced NE codes against ``src/nucleus/errors.py``, rejects the
historic NE600x placeholder typo, parses YAML fenced blocks under ``copilot``,
and whitelists ``export`` shell variable names to LiteLLM / Nucleus-documented keys.

Promotion: cookbook added 2026-05-15 (v0.2.0 GA hardening).
Architecture: ``nucleus_architecture_v4.1.md`` §7.x + ADR-015.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from nucleus.errors import (
    NucleusBudgetExceededError,
    NucleusConfigError,
    NucleusCopilotAuthError,
    NucleusCopilotContentFilterError,
    NucleusCopilotProviderError,
    NucleusCopilotRateLimitError,
    NucleusTimeoutError,
)


_COOKBOOK = Path(__file__).resolve().parents[2] / "docs" / "cookbook" / "ai-copilot-setup.md"

_ALLOWED_EXPORT_VARS = frozenset(
    {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OLLAMA_HOST",
        "AZURE_API_KEY",
        "AZURE_API_BASE",
        "AZURE_API_VERSION",
        # Optional Azure auth paths on LiteLLM Azure page (see cookbook + upstream docs).
        "AZURE_AD_TOKEN",
        "AZURE_API_TYPE",
        # Third-party backends cited in cookbook + LiteLLM provider index.
        "GROQ_API_KEY",
        "TOGETHERAI_API_KEY",
        "MISTRAL_API_KEY",
    }
)

_EXPECTED_CODES = frozenset(
    {
        NucleusCopilotAuthError.error_code,
        NucleusCopilotRateLimitError.error_code,
        NucleusCopilotProviderError.error_code,
        NucleusCopilotContentFilterError.error_code,
        NucleusBudgetExceededError.error_code,
        NucleusTimeoutError.error_code,
        NucleusConfigError.error_code,
    }
)


def _cookbook_text() -> str:
    assert _COOKBOOK.is_file(), f"Missing cookbook: {_COOKBOOK}"
    return _COOKBOOK.read_text(encoding="utf-8")


def test_cookbook_no_ne600_placeholder_band() -> None:
    txt = _cookbook_text()
    matches = set(re.findall(r"\bNE6\d{3}\b", txt))
    assert matches == set(), (
        "Copilot troubleshooting uses Intelligence band NE4001–NE4005 plus NE3005/NE5001; "
        "NE600x is obsolete placeholder text — remove it from the cookbook. "
        f"Found {sorted(matches)!r}"
    )


def test_cookbook_error_codes_track_errors_py() -> None:
    txt = _cookbook_text()
    found = set(re.findall(r"\b(NE\d{4})\b", txt))

    unknown = found - _EXPECTED_CODES
    assert not unknown, f"Cites unknown NE codes: {sorted(unknown)!r}"

    missing_from_doc = sorted(_EXPECTED_CODES - found)
    assert missing_from_doc == [], (
        "Cookbook troubleshooting must reference every Copilot-adjacent code "
        "we assert here — restore missing docs for: "
        f"{missing_from_doc!r}"
    )


@pytest.mark.parametrize(
    "code, classname",
    [
        ("NE4001", "NucleusCopilotAuthError"),
        ("NE4002", "NucleusCopilotRateLimitError"),
        ("NE4003", "NucleusCopilotProviderError"),
        ("NE4004", "NucleusCopilotContentFilterError"),
        ("NE4005", "NucleusBudgetExceededError"),
        ("NE3005", "NucleusTimeoutError"),
        ("NE5001", "NucleusConfigError"),
    ],
)
def test_cookbook_documents_each_error_row(code: str, classname: str) -> None:
    txt = _cookbook_text()
    needle = f"**{code}** `{classname}`"
    assert needle in txt, f"Cookbook troubleshooting row anchor missing: {needle}"


def test_export_environment_variables_are_whitelisted() -> None:
    txt = _cookbook_text()
    exports = re.findall(r"(?m)^export\s+([A-Z][A-Z0-9_]*)\s*=", txt)
    unknown = sorted(set(exports) - _ALLOWED_EXPORT_VARS)
    assert not unknown, f"Cookbook export lines mention unknown vars: {unknown}"


def test_yaml_snippets_under_copilot_parse() -> None:
    txt = _cookbook_text()
    snippets = re.findall(r"```yaml\s*\n(.*?)```", txt, flags=re.DOTALL)
    assert snippets, "Expected at least one fenced yaml block"

    parsed_any = False
    for snippet in snippets:
        data = yaml.safe_load(snippet)
        if isinstance(data, dict) and isinstance(data.get("copilot"), dict):
            parsed_any = True
            copilot = data["copilot"]
            assert isinstance(copilot, dict)
            assert "provider" in copilot or "model" in copilot or "opt_in" in copilot

    assert parsed_any, (
        "At least one yaml fence should define a top-level `copilot:` map so users can copy-paste."
    )
