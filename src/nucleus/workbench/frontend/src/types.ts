/**
 * Shared DTO types for the Nucleus Workbench.
 *
 * Mirrors the JSON shapes returned by the FastAPI endpoints in
 * `src/nucleus/workbench/api/`.  Keep these in sync with the Python
 * dataclass / Pydantic models when the backend shapes change.
 *
 * Per ADR-016 §3 (Fork B), these are read-only DTOs — no mutations
 * happen on the frontend; all writes go through the API.
 */

/** One registered @nucleus.asset entry from GET /api/assets */
export interface AssetDTO {
  key: string;
  deps: string[];
  schedule: string | null;
  compute: string | null;
  has_contract: boolean;
  checks: CheckDTO[];
}

/** A quality check bound to an asset */
export interface CheckDTO {
  severity: 'error' | 'warn';
  fn_name: string;
}

/** One materialization run from GET /api/runs */
export interface RunDTO {
  run_id: string;
  asset_key: string;
  status: 'success' | 'failure' | 'running';
  started_at: number;       // Unix epoch seconds (UTC)
  duration_ms: number | null;
  rows_written: number | null;
  snapshot_id: string | null;
}

/** Result of POST /api/query */
export interface QueryResultDTO {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
}

/** Request body for POST /api/chat */
export interface ChatRequestDTO {
  question: string;
  project_dir?: string;
  stream?: boolean;
}

/** Response from POST /api/chat */
export interface ChatReplyDTO {
  text: string;
  suggested_command: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  provider: string;
  model: string;
}

/** Structured error response from any /api/* endpoint */
export interface ApiErrorDTO {
  error_code: string;
  user_message: string;
  fix_hint: string;
}

/** Chat message (local UI state, not a server DTO) */
export interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
}

/* ── New DTOs for Editorial Hero v0.2 pages ─────────────────── */

/** GET /api/dashboard/summary — hero stat chips + recent runs */
export interface DashboardSummaryDTO {
  total_assets: number;
  total_rows: number | null;
  checks_green: number;
  checks_total: number;
  last_run_ago_seconds: number | null;
  recent_runs: RunDTO[];
}

/** GET /api/schedules — one entry per scheduled asset */
export interface ScheduleDTO {
  asset_key: string;
  cron_expression: string;
  description: string;
  next_runs: string[];   // ISO-8601 strings (preview)
}

/** GET /api/catalog — paginated asset catalog row */
export interface CatalogRowDTO {
  key: string;
  namespace: string;
  has_schedule: boolean;
  has_contract: boolean;
  check_count: number;
  dep_count: number;
  compute: string | null;
}

/** GET /api/catalog (paged) */
export interface CatalogPageDTO {
  items: CatalogRowDTO[];
  total: number;
  page: number;
  page_size: number;
}

/** GET /api/search?q=... */
export interface SearchResultItemDTO {
  kind: 'asset' | 'run' | 'schedule';
  key: string;
  label: string;
  secondary: string;
  url: string;
}

export interface SearchResultsDTO {
  query: string;
  items: SearchResultItemDTO[];
}

/** POST /api/runs/trigger */
export interface TriggerRunRequestDTO {
  asset_key: string;
}

export interface TriggerRunResponseDTO {
  run_id: string;
  asset_key: string;
  status: string;
  started_at: number;
}
