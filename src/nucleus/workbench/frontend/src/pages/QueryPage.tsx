/**
 * QueryPage — /query route.
 *
 * Monaco-based SQL editor + result table.
 * Updated for Editorial Hero v0.2: includes TopNav.
 *
 * Per ADR-016 §3 — Fork B layout spec.
 */

import TopNav from '../components/TopNav';
import QueryEditor from '../components/QueryEditor';

export default function QueryPage() {
  return (
    <div
      className="page-enter"
      style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg)' }}
    >
      <TopNav />
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <QueryEditor />
      </div>
    </div>
  );
}
