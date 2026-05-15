/**
 * relativeTime — render an ISO 8601 timestamp as a human-friendly "Xm ago" /
 * "Yh ago" / "Zd ago" label. UX audit Rec #6 (2026-05-15) — matches Unity
 * Catalog "Updated" and Snowsight "Last Modified" columns.
 *
 * Intentionally a single hand-rolled function — pulling in dayjs / luxon /
 * date-fns would balloon the offline bundle promise (ADR-016 §3 Fork B).
 *
 * # Stability: Internal @ v0.2
 */

const MINUTE = 60_000;
const HOUR = 3_600_000;
const DAY = 86_400_000;
const WEEK = 7 * DAY;
const MONTH = 30 * DAY;
const YEAR = 365 * DAY;

/**
 * Return a short relative-time label like ``3m ago`` / ``2h ago`` /
 * ``5d ago``. Falls back to the ISO date when the input is null or
 * unparseable.
 *
 * @param isoOrNull An ISO 8601 timestamp string, or null/undefined when the
 *   field has never been populated (e.g. an asset that has never been
 *   materialised).
 * @param now Override for tests; defaults to the wall clock.
 */
export function relativeTime(
  isoOrNull: string | null | undefined,
  now: number = Date.now(),
): string {
  if (!isoOrNull) {
    return '—';
  }
  const parsed = Date.parse(isoOrNull);
  if (Number.isNaN(parsed)) {
    return '—';
  }
  const diff = Math.max(0, now - parsed);

  if (diff < 60_000) {
    return 'just now';
  }
  if (diff < HOUR) {
    const m = Math.floor(diff / MINUTE);
    return `${m}m ago`;
  }
  if (diff < DAY) {
    const h = Math.floor(diff / HOUR);
    return `${h}h ago`;
  }
  if (diff < WEEK) {
    const d = Math.floor(diff / DAY);
    return `${d}d ago`;
  }
  if (diff < MONTH) {
    const w = Math.floor(diff / WEEK);
    return `${w}w ago`;
  }
  if (diff < YEAR) {
    const mo = Math.floor(diff / MONTH);
    return `${mo}mo ago`;
  }
  const y = Math.floor(diff / YEAR);
  return `${y}y ago`;
}

/**
 * Return an absolute-time label (``2026-05-15 18:42 UTC``) suitable for a
 * hover tooltip on top of the relative one. Falls back to the input when
 * unparseable.
 */
export function absoluteTime(isoOrNull: string | null | undefined): string {
  if (!isoOrNull) {
    return '';
  }
  const parsed = Date.parse(isoOrNull);
  if (Number.isNaN(parsed)) {
    return isoOrNull;
  }
  // Use ISO-derived UTC string for stability across timezones.
  const d = new Date(parsed);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const min = String(d.getUTCMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} ${hh}:${min} UTC`;
}
