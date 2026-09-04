import { useEffect, useMemo, useRef, useState } from 'react';
import { LoaderCircle, TriangleAlert } from 'lucide-react';
import { ChartInstance, ChartRequest, ChartResult, DatasetProfile } from '../types';
import { Language, text } from '../i18n';
import ValidatedChart from './ValidatedChart';
import ChartTypeSelect from './ChartTypeSelect';

interface Props { instance: ChartInstance; profile: DatasetProfile; language: Language; onPin: (id: string, chart: ChartResult, request: ChartRequest) => void; onViewRecords?: (chart: ChartResult, request: ChartRequest) => void; }
const LIMITS = [5, 10, 12, 20, 30];
const boundedLimit = (value: number) => Number.isInteger(value) && value >= 1 && value <= 30 ? value : 12;

export default function ExecutiveChartCard({ instance, profile, language, onPin, onViewRecords }: Props) {
 const dimensions = useMemo(() => profile.columns.filter(c => c.kind === 'cat' || c.kind === 'time'), [profile]);
 const metrics = useMemo(() => profile.columns.filter(c => c.kind === 'num'), [profile]);
 const [request, setRequest] = useState<ChartRequest>(instance.request);
 const [result, setResult] = useState<ChartResult | null>(instance.result ?? null);
 const [loading, setLoading] = useState(false);
 const [pinning, setPinning] = useState(false);
 const [error, setError] = useState<string | null>(null);
 const [customLimitMode, setCustomLimitMode] = useState(() => !LIMITS.includes(instance.request.limit));
 const sequence = useRef(0);
 useEffect(() => { setRequest(instance.request); setResult(instance.result ?? null); setError(null); setCustomLimitMode(!LIMITS.includes(instance.request.limit)); }, [instance.id, profile.run_id]);
 const fingerprint = JSON.stringify({ run: profile.run_id, language, request });
 useEffect(() => {
   if (result && JSON.stringify(request) === JSON.stringify(instance.request)) return;
   const controller = new AbortController(); const id = ++sequence.current;
   setLoading(true); setError(null);
   fetch(`/api/runs/${profile.run_id}/chart?language=${language}`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(request), signal: controller.signal })
     .then(async r => { const body = await r.json(); if (!r.ok) throw new Error(body.detail || text(language,'chartRejected')); return body as ChartResult; })
     .then(body => { if (id === sequence.current) setResult(body); })
     .catch(reason => { if (id === sequence.current && (reason as Error).name !== 'AbortError') setError(reason instanceof Error ? reason.message : text(language,'chartUpdateFailed')); })
     .finally(() => { if (id === sequence.current) setLoading(false); });
   return () => controller.abort();
 }, [fingerprint]);
 const updateRequest = (next: ChartRequest) => { setResult(null); setRequest(next); };
 const grouped = Boolean(request.secondary_dimension);
 const types: ChartRequest['chart_type'][] = request.x_metric ? ['scatter'] : grouped ? ['bar', 'stacked_bar'] : ['bar', 'line', 'area', 'pie', 'donut'];
 const updateType = (chart_type: ChartRequest['chart_type']) => updateRequest({ ...request, chart_type, x_metric: chart_type === 'scatter' ? metrics.find(x => x.name !== request.metric)?.name : undefined });
 const pin = async () => { if (!result || loading || pinning) return; setPinning(true); try { onPin(instance.id, result, request); } finally { window.setTimeout(() => setPinning(false), 300); } };
 const viewRecords = () => { if (result && !loading) onViewRecords?.(result, request); };
 const dimensionIsTime = profile.columns.find(column => column.name === request.dimension)?.kind === 'time';
 const limitName = dimensionIsTime ? 'Periods' : 'Top N';
 const selectedLimit = customLimitMode ? 'custom' : String(request.limit);
 return <article className={`executive-chart-card role-${instance.role}`}><header className="chart-card-header"><div><p className="section-eyebrow">{instance.role === 'trend' ? text(language,'primaryTrend') : text(language,'customChart')}</p><h2>{result?.title ?? instance.title}</h2></div>{loading && <span className="chart-status"><LoaderCircle size={14} className="animate-spin"/>{text(language,'updating')}</span>}</header><div className="chart-controls"><label>{text(language,'metric')}<select value={request.metric} onChange={e => updateRequest({...request, metric:e.target.value})}>{metrics.map(x=><option key={x.name}>{x.name}</option>)}</select></label><label>{text(language,'dimension')}<select value={request.dimension} onChange={e => updateRequest({...request, dimension:e.target.value})}>{dimensions.map(x=><option key={x.name}>{x.name}</option>)}</select></label><label>{text(language,'type')}<ChartTypeSelect value={types.includes(request.chart_type) ? request.chart_type : types[0]} options={types} onChange={updateType} language={language}/></label><label>{limitName}<select value={selectedLimit} onChange={e => { const custom = e.target.value === 'custom'; setCustomLimitMode(custom); updateRequest({...request, limit: custom ? boundedLimit(request.limit) : boundedLimit(Number(e.target.value))}); }}><option value={5}>{limitName} 5</option><option value={10}>{limitName} 10</option><option value={12}>{limitName} 12</option><option value={20}>{limitName} 20</option><option value={30}>{limitName} 30</option><option value="custom">Custom (1–30)</option></select>{customLimitMode && <input aria-label={`Custom ${limitName}`} type="number" min="1" max="30" step="1" value={request.limit} onChange={e => updateRequest({...request, limit: boundedLimit(Number(e.target.value))})}/>}</label></div>{error && <p className="chart-error"><TriangleAlert size={16}/>{error}</p>}<div className="chart-visual">{result ? <ValidatedChart result={result} language={language}/> : <p>{text(language,'chartConfigure')}</p>}</div>{result && <footer className="chart-actions"><button disabled={loading || pinning} onClick={pin}>{pinning ? text(language,'saving') : text(language,'addReport')}</button>{onViewRecords && <button disabled={loading} onClick={viewRecords}>{text(language,'viewRecords')}</button>}</footer>}</article>;
}
