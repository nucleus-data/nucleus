# typed: false
# frozen_string_literal: true

# Nucleus — Homebrew formula draft for v0.2.0.
#
# This formula installs the Nucleus Python CLI into an isolated virtualenv
# under HOMEBREW_PREFIX/Cellar/nucleus and shims `nucleus` onto $PATH.
#
# DRAFT STATUS — pre-publish:
#   * `sha256` is a placeholder. Founder must regenerate at release time
#     using:  shasum -a 256 nucleus-data-0.2.0.tar.gz
#   * The Python `resource` blocks for transitive deps are NOT enumerated
#     here (16 direct + ~80 transitive deps). Regenerate them with:
#         pipx install homebrew-pypi-poet
#         poet -f nucleus-data > nucleus-resources.rb
#     then paste the output between the marked block below.
#     See: https://github.com/tdsmith/homebrew-pypi-poet
#
# Docs:
#   Formula Cookbook:        https://docs.brew.sh/Formula-Cookbook
#   Python for Formula Authors: https://docs.brew.sh/Python-for-Formula-Authors
#
# IMPORTANT: PyPI distribution name is `nucleus-data` (the bare `nucleus`
# name is squatted on PyPI — see ../pypi/PUBLISH_RUNBOOK.md). The Homebrew
# formula name remains `nucleus` because the user-facing CLI binary is
# `nucleus`. This is conventional; cf. `brew install poetry` shipping the
# `poetry` PyPI package, but the formula is still named `poetry`.

class Nucleus < Formula
  include Language::Python::Virtualenv

  desc "Ship data products from a laptop — local-first SDK + CLI for Iceberg pipelines"
  homepage "https://github.com/nucleus-data/nucleus"
  url "https://github.com/nucleus-data/nucleus/releases/download/v0.2.0/nucleus-data-0.2.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "Apache-2.0"
  head "https://github.com/nucleus-data/nucleus.git", branch: "main"

  # Python 3.11 matches the project's `requires-python = ">=3.11,<3.13"` floor.
  # Per Homebrew Python policy we depend on the keg-only python@3.11 and use
  # virtualenv_install_with_resources to avoid polluting Homebrew's site-packages.
  depends_on "python@3.11"

  # ---------------------------------------------------------------------------
  # Python resource blocks — REGENERATE BEFORE PUBLISH
  # ---------------------------------------------------------------------------
  # Run on a clean machine after PyPI publish:
  #     pipx install homebrew-pypi-poet
  #     pipx install nucleus-data==0.2.0
  #     poet nucleus-data
  # Paste the output of `poet` between the markers below; commit; re-run
  # `brew audit --strict --new --online ./packaging/brew/nucleus.rb`.

  # ===== POET-GENERATED-START =====
  # NOTE: this block is intentionally empty in the v0.2.0 draft. Without
  # `resource` blocks Homebrew will fall through to a vendored install
  # via the wheel resource below, which works for a draft pass but is
  # NOT acceptable for homebrew-core submission. Submission to
  # homebrew-core requires every transitive dep to be a `resource`.
  # ===== POET-GENERATED-END =====

  def install
    # virtualenv_install_with_resources reads every `resource` block above
    # plus the main `url` and installs them into libexec/, then exposes
    # entry-point scripts (defined in pyproject.toml [project.scripts])
    # as bin/nucleus. See: https://docs.brew.sh/Python-for-Formula-Authors
    virtualenv_install_with_resources
  end

  test do
    # Smoke: the entry point must execute and report the expected version.
    assert_match "0.2.0", shell_output("#{bin}/nucleus --version")

    # Smoke: `nucleus init` must scaffold a project without errors.
    system bin/"nucleus", "init", "smoke-demo"
    assert_predicate testpath/"smoke-demo/nucleus.yaml", :exist?
  end
end
