import { useEffect, useMemo, useRef, useState } from 'react';
import { LoaderCircle, TriangleAlert } from 'lucide-react';

import { ChartRequest, ChartResult, DatasetProfile } from '../types';
import { Language, text } from '../i18n';
import { formatChartValue } from '../formatting';
import { executedChartArtifact } from '../domain/artifact';

type Props = {
  result: ChartResult;
  request: ChartRequest;
  profile: DatasetProfile;
  language: Language;
  onPin: (id: string, chart: ChartResult, request: ChartRequest) => void;
  onViewRecords: (chart: ChartResult, request: ChartRequest) => void;
  artifactId: string;
};

/** Editable draft; downstream actions operate only on the last validated response. */
export default function ChartCompanionTable({ result: initialResult, request: initialRequest, profile, language, onPin, onViewRecords, artifactId }: Props) {
  const [request, setRequest] = useState(initialRequest);
  const [result, setResult] = useState(initialResult);
  const [filterColumn, setFilterColumn] = useState('');
  const [filterValue, setFilterValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(0);
  const filterable = useMemo(() => profile.columns.filter(column => column.kind !== 'id' && column.kind !== 'unknown'), [profile]);
  const metrics = useMemo(() => profile.columns.filter(column => column.kind === 'num'), [profile]);
  const dimensions = useMemo(() => profile.columns.filter(column => column.kind === 'cat' || column.kind === 'time'), [profile]);
  const inputFingerprint = JSON.stringify({ request: initialRequest, result: initialResult.request ?? initialResult.rows });

  useEffect(() => { setRequest(initialRequest); setResult(initialResult); setError(null); }, [inputFingerprint]);
  const refresh = (next: ChartRequest) => {
    setRequest(next); setLoading(true); setError(null); const id = ++sequence.current;
    fetch(`/api/runs/${profile.run_id}/chart?language=${language}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(next) })
      .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || text(language, 'chartRejected')); return body as ChartResult; })
      .then(body => { if (id === sequence.current) setResult(body); })
      .catch(reason => { if (id === sequence.current) setError(reason instanceof Error ? reason.message : text(language, 'chartUpdateFailed')); })
      .finally(() => { if (id === sequence.current) setLoading(false); });
  };
  const addFilter = () => {
    if (!filterColumn || !filterValue.trim()) return;
    const column = filterable.find(item => item.name === filterColumn);
    if (!column) return;
    const filter = column.kind === 'time'
      ? { column: filterColumn, operator: 'date_range' as const, values: [filterValue.trim(), filterValue.trim()] }
      : { column: filterColumn, operator: 'equals' as const, value: filterValue.trim() };
    refresh({ ...request, filters: [...request.filters.filter(item => item.column !== filterColumn), filter] });
    setFilterValue('');
  };
  const removeFilter = (index: number) => refresh({ ...request, filters: request.filters.filter((_, itemIndex) => itemIndex !== index) });
  const artifact = executedChartArtifact(`${artifactId}-table`, profile.run_id, request, result);
  const actionsEnabled = !loading && !error && artifact !== null;
  const metric = result.metric_display_name ?? result.metric;
  const dimension = result.dimension;
  const total = result.rows.reduce((sum, row) => sum + Math.max(0, Number(row.value)), 0);
  return <aside className="chart-companion-table" aria-label={`${metric} by ${dimension} data table`}>
    <header><div><p className="section-eyebrow">Data table</p><h3>{metric} by {dimension}</h3></div>{loading && <span className="chart-status"><LoaderCircle size={14} className="animate-spin"/>{text(language, 'updating')}</span>}</header>
    <div className="chart-controls chart-table-controls"><label>{text(language, 'metric')}<select aria-label="Table metric" value={request.metric} disabled={loading} onChange={event => refresh({ ...request, metric: event.target.value })}>{metrics.map(column => <option value={column.name} key={column.name}>{column.name}</option>)}</select></label><label>{text(language, 'dimension')}<select aria-label="Table dimension" value={request.dimension} disabled={loading} onChange={event => refresh({ ...request, dimension: event.target.value })}>{dimensions.map(column => <option value={column.name} key={column.name}>{column.name}</option>)}</select></label><label>{text(language, 'type')}<select aria-label="Table aggregation" value={request.aggregation} disabled={loading} onChange={event => refresh({ ...request, aggregation: event.target.value as ChartRequest['aggregation'] })}><option value="sum">Sum</option><option value="avg">Average</option><option value="count">Count</option></select></label><label>Top N<select aria-label="Table Top N" value={request.limit} disabled={loading} onChange={event => refresh({ ...request, limit: Number(event.target.value) })}>{[5, 10, 12, 20, 30].map(limit => <option value={limit} key={limit}>{limit}</option>)}</select></label></div>
    <div className="chart-filter-row"><select aria-label="Filter column" value={filterColumn} onChange={event => setFilterColumn(event.target.value)}><option value="">Filter column</option>{filterable.map(column => <option value={column.name} key={column.name}>{column.name}</option>)}</select><input aria-label="Filter value" value={filterValue} onChange={event => setFilterValue(event.target.value)} placeholder="Value"/><button type="button" onClick={addFilter} disabled={!filterColumn || !filterValue.trim() || loading}>Add filter</button></div>
    {request.filters.length > 0 && <div className="chart-filter-chips">{request.filters.map((filter, index) => <span key={`${filter.column}-${index}`}>{filter.column} {filter.operator} {filter.value ?? filter.values?.join(' – ')} <button type="button" aria-label={`Remove ${filter.column} filter`} onClick={() => removeFilter(index)}>×</button></span>)}</div>}
    {error && <p className="chart-error"><TriangleAlert size={15}/>{error}</p>}
    <div className="chart-companion-scroll"><table><thead><tr><th>#</th><th>{dimension}</th><th>{metric}</th><th>%</th></tr></thead><tbody>{result.rows.map((row, index) => <tr key={`${row.label}-${index}`}><td>{index + 1}</td><td title={row.display_label ?? row.label}>{row.display_label ?? row.label}</td><td>{formatChartValue(Number(row.value), language)}</td><td>{total > 0 ? `${(Number(row.value) / total * 100).toFixed(1)}%` : '—'}</td></tr>)}</tbody></table></div>
    <footer className="chart-actions"><button type="button" disabled={!actionsEnabled} onClick={() => artifact && onPin(artifact.artifactId, artifact.result, artifact.request)}>{text(language, 'addReport')}</button><button type="button" disabled={!actionsEnabled} onClick={() => artifact && onViewRecords(artifact.result, artifact.request)}>{text(language, 'viewRecords')}</button></footer>
  </aside>;
}
