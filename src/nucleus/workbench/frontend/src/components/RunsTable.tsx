/**
 * RunsTable — sortable table of recent runs using @tanstack/react-table.
 *
 * Docs: https://tanstack.com/table/v8  (@tanstack/react-table==8.20.5)
 */

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import { useState } from 'react';
import { ArrowUpDown } from 'lucide-react';
import type { RunDTO } from '../types';
import { formatDateTime, formatDuration } from '../lib/utils';

interface Props {
  runs: RunDTO[];
  onSelect: (runId: string) => void;
  selectedRunId: string | null;
}

const col = createColumnHelper<RunDTO>();

const STATUS_COLORS: Record<string, string> = {
  success: 'rgba(52,211,153,.15)',
  failure: 'rgba(248,113,113,.15)',
  running: 'rgba(251,191,36,.15)',
};
const STATUS_TEXT: Record<string, string> = {
  success: '#34D399',
  failure: '#F87171',
  running: '#FBBF24',
};

const COLUMNS = [
  col.accessor('asset_key', {
    header: 'Asset',
    cell: (i) => <span style={{ fontWeight: 600, fontFamily: 'monospace', fontSize: 12 }}>{i.getValue()}</span>,
  }),
  col.accessor('status', {
    header: 'Status',
    cell: (i) => {
      const s = i.getValue();
      return (
        <span
          style={{
            background: STATUS_COLORS[s] ?? 'var(--border)',
            color: STATUS_TEXT[s] ?? 'var(--muted)',
            fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 9999,
          }}
        >
          {s}
        </span>
      );
    },
  }),
  col.accessor('started_at', {
    header: 'Started',
    cell: (i) => (
      <span style={{ fontSize: 12, color: 'var(--muted)' }}>{formatDateTime(i.getValue())}</span>
    ),
  }),
  col.accessor('duration_ms', {
    header: 'Duration',
    cell: (i) => {
      const v = i.getValue();
      return <span style={{ fontSize: 12, color: 'var(--muted)' }}>{v != null ? formatDuration(v) : '—'}</span>;
    },
  }),
  col.accessor('rows_written', {
    header: 'Rows',
    cell: (i) => {
      const v = i.getValue();
      return <span style={{ fontSize: 12, color: 'var(--muted)' }}>{v != null ? v.toLocaleString() : '—'}</span>;
    },
  }),
];

export default function RunsTable({ runs, onSelect, selectedRunId }: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data: runs,
    columns: COLUMNS,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (runs.length === 0) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
        No runs recorded yet. Run <code style={{ fontFamily: 'monospace', fontSize: 12 }}>nucleus run &lt;key&gt;</code> to materialize an asset.
      </div>
    );
  }

  return (
    <div style={{ overflow: 'auto', flex: 1 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  onClick={h.column.getToggleSortingHandler()}
                  style={{
                    padding: '8px 12px', textAlign: 'left',
                    fontSize: 11, fontWeight: 600, color: 'var(--muted)',
                    cursor: h.column.getCanSort() ? 'pointer' : 'default',
                    userSelect: 'none', whiteSpace: 'nowrap',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {h.column.getCanSort() && <ArrowUpDown size={11} style={{ opacity: 0.4 }} />}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isSelected = row.original.run_id === selectedRunId;
            return (
              <tr
                key={row.id}
                onClick={() => onSelect(row.original.run_id)}
                style={{
                  borderBottom: '1px solid var(--border)',
                  cursor: 'pointer',
                  background: isSelected ? 'rgba(79,70,229,.08)' : 'transparent',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.background = 'var(--surface)';
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.background = 'transparent';
                }}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} style={{ padding: '7px 12px' }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
