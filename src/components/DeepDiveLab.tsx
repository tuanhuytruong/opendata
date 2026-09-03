import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, ChevronLeft, ChevronRight, Download, Eye, LoaderCircle, Plus, Search, SlidersHorizontal, TriangleAlert, X } from 'lucide-react';
import { DataColumn, DataFilter, DataQueryResult, DatasetProfile, DeepDiveScope, EDAResult } from '../types';
import { displayNumber, Language, text } from '../i18n';

type Operator = DataFilter['operator'];
const operators: Array<{ value: Operator; label: string }> = [
  { value: 'equals', label: 'equals' }, { value: 'not_equals', label: 'does not equal' },
  { value: 'greater_than', label: 'is greater than' }, { value: 'greater_or_equal', label: 'is at least' },
  { value: 'less_than', label: 'is less than' }, { value: 'less_or_equal', label: 'is at most' },
];
const numericOperators = new Set<Operator>(['greater_than', 'greater_or_equal', 'less_than', 'less_or_equal']);
const presentLabel = (name: string) => name.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());
const safeScopeFilters = (scope: DeepDiveScope | null, profile: DatasetProfile): DataFilter[] => {
  if (!scope) return [];
  const safeFields = new Set(profile.columns.filter(column => column.kind !== 'id' && column.kind !== 'unknown').map(column => column.name));
  const allowedOperators = new Set(operators.map(operator => operator.value));
  return scope.filters.filter(filter => safeFields.has(filter.column) && allowedOperators.has(filter.operator) && typeof filter.value === 'string' && filter.value.trim()).map(filter => ({ ...filter, value: filter.value.trim() }));
};
const compactColumns = (columns: DataColumn[]) => columns.slice(0, 5).map(column => column.name);

export default function DeepDiveLab({ profile, eda, language, sourceScope }: { profile: DatasetProfile; eda: EDAResult | null; language: Language; sourceScope: DeepDiveScope | null }) {
  const [data, setData] = useState<DataQueryResult | null>(null);
  const [search, setSearch] = useState(''); const [filters, setFilters] = useState<DataFilter[]>([]);
  const [page, setPage] = useState(1); const [pageSize, setPageSize] = useState(25);
  const [sortBy, setSortBy] = useState<string | null>(null); const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [filterColumn, setFilterColumn] = useState(''); const [filterOperator, setFilterOperator] = useState<Operator>('equals'); const [filterValue, setFilterValue] = useState('');
  const [visibleColumns, setVisibleColumns] = useState<string[]>([]); const [columnsOpen, setColumnsOpen] = useState(false);
  const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null); const [exporting, setExporting] = useState(false); const [healthOpen, setHealthOpen] = useState(false);
  const requestId = useRef(0);
  const fields = useMemo(() => data?.columns ?? [], [data]);
  const selectedColumns = useMemo(() => fields.filter(field => visibleColumns.includes(field.name)), [fields, visibleColumns]);
  const activeColumn = fields.find(column => column.name === filterColumn);

  useEffect(() => { setFilterColumn(fields[0]?.name ?? ''); }, [profile.run_id, fields]);
  useEffect(() => { setFilters(safeScopeFilters(sourceScope, profile)); setSearch(''); setSortBy(null); setPage(1); }, [sourceScope, profile]);
  useEffect(() => { setPage(1); }, [search, filters, pageSize, profile.run_id]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const id = ++requestId.current; const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), search, sort_direction: sortDirection, filters: JSON.stringify(filters) });
      if (sortBy) params.set('sort_by', sortBy);
      setLoading(true); setError(null);
      fetch(`/api/runs/${profile.run_id}/data?${params}`).then(async response => {
        const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || 'Could not load raw data.'); return payload as DataQueryResult;
      }).then(result => { if (id === requestId.current) setData(result); }).catch(reason => { if (id === requestId.current) setError(reason instanceof Error ? reason.message : 'Could not load raw data.'); }).finally(() => { if (id === requestId.current) setLoading(false); });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [profile.run_id, page, pageSize, search, sortBy, sortDirection, filters]);
  useEffect(() => {
    if (!fields.length) return;
    setVisibleColumns(current => {
      const retained = current.filter(column => fields.some(field => field.name === column));
      return retained.length ? retained : compactColumns(fields);
    });
  }, [fields]);

  const addFilter = () => {
    const value = filterValue.trim(); if (!filterColumn || !value) return;
    if (numericOperators.has(filterOperator) && !Number.isFinite(Number(value.replaceAll(',', '')))) { setError('Numeric comparisons require a number.'); return; }
    if (filters.some(item => item.column === filterColumn && item.operator === filterOperator && item.value === value)) { setError('That filter is already applied.'); return; }
    setError(null); setFilters(current => [...current, { column: filterColumn, operator: filterOperator, value }]); setFilterValue('');
  };
  const toggleSort = (column: string) => { if (sortBy === column) setSortDirection(current => current === 'asc' ? 'desc' : 'asc'); else { setSortBy(column); setSortDirection('asc'); } };
  const toggleColumn = (column: string) => setVisibleColumns(current => current.includes(column) ? (current.length > 1 ? current.filter(item => item !== column) : current) : [...current, column]);
  const exportCsv = async () => {
    const params = new URLSearchParams({ page: '1', page_size: String(pageSize), search, sort_direction: sortDirection, filters: JSON.stringify(filters) }); if (sortBy) params.set('sort_by', sortBy);
    setExporting(true); setError(null); try { const response = await fetch(`/api/runs/${profile.run_id}/data/export?${params}`); if (!response.ok) { const payload = await response.json(); throw new Error(payload.detail || 'Could not export filtered data.'); } const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `opendata-${profile.run_id.slice(0, 8)}-filtered.csv`; anchor.click(); URL.revokeObjectURL(url); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not export filtered data.'); } finally { setExporting(false); }
  };
  const resultLabel = data ? `${displayNumber(data.total, language)} matching row${data.total === 1 ? '' : 's'}` : 'Loading results';
  return <section className="max-w-[1400px] mx-auto space-y-4">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="section-eyebrow">Safe raw data explorer</p><h1 className="font-display text-2xl font-bold">Deep Dive Lab</h1><p className="text-sm text-slate-500 mt-1">Search, filter, sort, and export only presentation-safe fields from this run.</p></div><button type="button" onClick={() => void exportCsv()} disabled={exporting || !data?.total} className="lab-export"><Download className="w-4 h-4" />{exporting ? 'Preparing CSV…' : 'Export filtered CSV'}</button></div>
    {sourceScope && <div className="source-scope"><Eye className="w-4 h-4" /><div><b>Source chart: {sourceScope.title}</b><span>{sourceScope.aggregation.toUpperCase()} {sourceScope.metric} by {sourceScope.dimension}{sourceScope.secondary_dimension ? ` · grouped by ${sourceScope.secondary_dimension}` : ''}. Its validated filters are pre-applied below and rechecked by the data API.</span></div></div>}
    <div className="data-explorer"><div className="data-toolbar"><label className="data-search"><Search className="w-4 h-4" /><span className="sr-only">Search visible data</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search visible data…" /></label><div className="toolbar-actions"><span className="result-count" aria-live="polite">{loading ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : null}{resultLabel}</span><div className="column-chooser"><button type="button" className="column-chooser-trigger" onClick={() => setColumnsOpen(current => !current)} aria-expanded={columnsOpen}><SlidersHorizontal className="w-3.5 h-3.5" />Columns ({selectedColumns.length})</button>{columnsOpen && <div className="column-chooser-menu">{fields.map(field => <label key={field.name}><input type="checkbox" checked={visibleColumns.includes(field.name)} disabled={visibleColumns.length === 1 && visibleColumns.includes(field.name)} onChange={() => toggleColumn(field.name)} />{field.display_name}</label>)}</div>}</div></div></div>
      <div className="filter-builder"><div className="filter-title"><SlidersHorizontal className="w-4 h-4" /><b>Filters</b><span>Validated server-side</span></div><div className="filter-controls"><select value={filterColumn} onChange={event => setFilterColumn(event.target.value)} aria-label="Filter field">{fields.map(field => <option key={field.name} value={field.name}>{field.display_name}</option>)}</select><select value={filterOperator} onChange={event => setFilterOperator(event.target.value as Operator)} aria-label="Filter operator">{operators.map(operator => <option key={operator.value} value={operator.value}>{operator.label}</option>)}</select><input value={filterValue} onChange={event => setFilterValue(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); addFilter(); } }} placeholder={activeColumn?.kind === 'num' && numericOperators.has(filterOperator) ? 'Number' : 'Value'} aria-label="Filter value"/><button type="button" onClick={addFilter} disabled={!filterColumn || !filterValue.trim()} className="planner-secondary"><Plus className="w-4 h-4" />Add filter</button></div>{filters.length > 0 && <div className="filter-chips">{filters.map((filter, index) => { const field = fields.find(item => item.name === filter.column); return <span className="filter-chip" key={`${filter.column}-${filter.operator}-${filter.value}`}>{field?.display_name ?? filter.column} {operators.find(item => item.value === filter.operator)?.label} <b>{filter.value}</b><button type="button" onClick={() => setFilters(current => current.filter((_, itemIndex) => itemIndex !== index))} aria-label={`Remove ${field?.display_name ?? filter.column} filter`}><X className="w-3 h-3" /></button></span>; })}<button type="button" className="clear-filters" onClick={() => setFilters([])}>Clear all</button></div>}</div>
      {error && <div className="lab-error"><TriangleAlert className="w-4 h-4" />{error}</div>}
      <div className="data-table-wrap">{!data && loading ? <div className="lab-state"><LoaderCircle className="w-5 h-5 animate-spin" />Loading safe data…</div> : data && data.rows.length ? <table className="data-table"><thead><tr>{selectedColumns.map((column, index) => <th key={column.name} className={index === 0 ? 'data-primary-cell' : ''}><button type="button" onClick={() => toggleSort(column.name)} aria-label={`Sort by ${column.display_name}`}>{column.display_name}<span className={sortBy === column.name ? 'sort-active' : ''}>{sortBy === column.name ? (sortDirection === 'asc' ? '↑' : '↓') : '↕'}</span></button></th>)}</tr></thead><tbody>{data.rows.map((row, index) => <tr key={`${page}-${index}`}>{selectedColumns.map((column, columnIndex) => <td key={column.name} className={columnIndex === 0 ? 'data-primary-cell' : ''}>{row[column.name] || '—'}</td>)}</tr>)}</tbody></table> : <div className="lab-state"><Search className="w-6 h-6 text-slate-300" /><b>No matching rows</b><p>Try changing the search or removing one of the filters.</p>{(search || filters.length) ? <button type="button" onClick={() => { setSearch(''); setFilters([]); }}>Clear explorer</button> : null}</div>}</div>
      {data && <div className="data-pagination"><span>Page {data.pagination.page} of {data.pagination.page_count}</span><label>Rows <select value={pageSize} onChange={event => setPageSize(Number(event.target.value))}>{[10, 25, 50, 100].map(size => <option key={size}>{size}</option>)}</select></label><button type="button" onClick={() => setPage(current => Math.max(1, current - 1))} disabled={!data.pagination.has_previous}><ChevronLeft className="w-4 h-4" />Previous</button><button type="button" onClick={() => setPage(current => current + 1)} disabled={!data.pagination.has_next}>Next<ChevronRight className="w-4 h-4" /></button></div>}</div>
    <DataHealth eda={eda} language={language} open={healthOpen} onToggle={() => setHealthOpen(current => !current)} />
  </section>;
}
function DataHealth({ eda, language, open, onToggle }: { eda: EDAResult | null; language: Language; open: boolean; onToggle: () => void }) { return <section className="health-context"><button type="button" onClick={onToggle} aria-expanded={open}><span><b>Data health context</b><small>{eda ? `${eda.coverage.analyzed_column_count} safe fields analyzed · ${eda.coverage.suppressed_sensitive_column_count} sensitive fields excluded` : text(language, 'profilePreparing')}</small></span><ChevronDown className={`w-4 h-4 ${open ? 'rotate-180' : ''}`} /></button>{open && (eda ? <div className="health-details"><div className="kpi-grid">{[[displayNumber(eda.coverage.row_count, language), 'Rows'], [String(eda.coverage.analyzed_column_count), 'Safe fields'], [String(eda.coverage.suppressed_sensitive_column_count), 'Sensitive fields hidden'], [`${eda.columns.filter(column => column.quality.null_ratio > .1).length}`, 'Fields >10% missing']].map(([value, label]) => <div key={label} className="kpi-card"><p>{label}</p><b>{value}</b></div>)}</div><div className="health-columns">{eda.columns.slice(0, 12).map(column => <div key={column.name}><b>{presentLabel(column.name)}</b><span>{column.kind} · {(column.quality.null_ratio * 100).toFixed(1)}% null · {displayNumber(column.quality.distinct_count, language)} distinct</span></div>)}</div>{eda.guardrails.slice(0, 2).map(note => <p className="health-note" key={note}>{note}</p>)}</div> : <div className="lab-state"><LoaderCircle className="w-4 h-4 animate-spin" />Preparing data health context…</div>)}</section>; }
