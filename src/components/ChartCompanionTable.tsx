import { ChartResult } from '../types';
import { Language } from '../i18n';
import { formatChartValue } from '../formatting';

export default function ChartCompanionTable({ result, language }: { result: ChartResult; language: Language }) {
  const metric = result.metric_display_name ?? result.metric;
  const dimension = result.dimension;
  const total = result.rows.reduce((sum, row) => sum + Math.max(0, Number(row.value)), 0);
  return <aside className="chart-companion-table" aria-label={`${metric} by ${dimension}`}>
    <header><p className="section-eyebrow">Data table</p><h3>{metric} by {dimension}</h3></header>
    <div className="chart-companion-scroll"><table>
      <thead><tr><th>#</th><th>{dimension}</th><th>{metric}</th><th>%</th></tr></thead>
      <tbody>{result.rows.map((row, index) => <tr key={`${row.label}-${index}`}><td>{index + 1}</td><td title={row.display_label ?? row.label}>{row.display_label ?? row.label}</td><td>{formatChartValue(Number(row.value), language)}</td><td>{total > 0 ? `${(Number(row.value) / total * 100).toFixed(1)}%` : '—'}</td></tr>)}</tbody>
    </table></div>
    {result.result_count != null && result.request?.limit != null && result.result_count < result.request.limit && <p className="chart-availability">{result.result_count} categories available in the current scope.</p>}
  </aside>;
}
