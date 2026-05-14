# NE5004 — NucleusEnvironmentError

**Code**: `NE5004`  ·  **Class**: `NucleusEnvironmentError`  ·  **Layer**: L4 Experience  ·  **Stability**: Stable

## What happened

A required component of your local development environment is missing or refused to come up. Nucleus tried to bring up the local runtime via `nucleus up` (or tear it down via `nucleus down`) and could not reach the container runtime, the container exited non-zero, or the storage container never reported itself ready inside the timeout budget.

This is distinct from a configuration problem (`NucleusConfigError`, `NE5001`) — the file you wrote is fine; something the file points at is not running.

## Likely causes

- The container runtime (Docker Desktop or equivalent) is not installed or not on `PATH`.
- The container runtime is installed but not running.
- Port `9000` is already bound by another process.
- `docker compose` returned a non-zero exit code (image pull failure, daemon socket unreachable, etc.).
- The MinIO container started but its readiness endpoint at `http://localhost:9000/minio/health/ready` never responded inside 30 seconds.

## Fix steps

1. Confirm the container runtime is installed and reachable: `docker --version` should exit 0.
2. Confirm the container runtime is actually running (Docker Desktop tray icon, `docker ps` exits 0).
3. Confirm port `9000` is free: stop whatever process is bound to it, or change the host port mapping in the `docker-compose.yaml` shipped by `nucleus init` at your project root.
4. Re-run `nucleus up`. If MinIO still never goes ready, inspect the container logs: `docker compose logs minio` (run from the project root).
5. v0.1 also supports filesystem-only mode — if you do not need S3-compatible storage right now, delete the `docker-compose.yaml` from your project root and `nucleus up` will surface a `NucleusConfigError` directing you to re-run `nucleus init` (the filesystem-only path is reached by simply not invoking `nucleus up` and relying on the local Iceberg catalog).

## Related

- Source: `src/nucleus/errors.py` (`NucleusEnvironmentError`)
- Default fix hint: command-specific (e.g., "Verify Docker is responsive" or "Check container logs and verify port 9000 is free.")
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- Spec: [`nucleus_cli_spec.md` §3.2](../../nucleus_cli_spec.md) (`nucleus up`) · §10 NV #4 (first L4 NE5xxx allocation)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
