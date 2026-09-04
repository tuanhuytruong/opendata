import { useEffect, useMemo, useRef, useState } from 'react';
import { LoaderCircle, TriangleAlert } from 'lucide-react';
import { ChartInstance, ChartRequest, ChartResult, DatasetProfile } from '../types';
import { Language, text } from '../i18n';
import ValidatedChart from './ValidatedChart';
import ChartTypeSelect from './ChartTypeSelect';

interface Props { instance: ChartInstance; profile: DatasetProfile; language: Language; onPin: (id: string, chart: ChartResult, request: ChartRequest) => void; onViewRecords?: (chart: ChartResult, request: ChartRequest) => void; }

export default function ExecutiveChartCard({ instance, profile, language, onPin, onViewRecords }: Props) {
 const dimensions = useMemo(() => profile.columns.filter(c => c.kind === 'cat' || c.kind === 'time'), [profile]);
 const metrics = useMemo(() => profile.columns.filter(c => c.kind === 'num'), [profile]);
 const [request, setRequest] = useState<ChartRequest>(instance.request);
 const [result, setResult] = useState<ChartResult | null>(instance.result ?? null);
 const [loading, setLoading] = useState(false);
 const [pinning, setPinning] = useState(false);
 const [error, setError] = useState<string | null>(null);
 const sequence = useRef(0);
 useEffect(() => { setRequest(instance.request); setResult(instance.result ?? null); setError(null); }, [instance.id, profile.run_id]);
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
 // Clearing the old result synchronously with any edit prevents an action from
 // pairing a newly selected request with rows returned for the prior request.
 const updateRequest = (next: ChartRequest) => { setResult(null); setRequest(next); };
 const grouped = Boolean(request.secondary_dimension);
 const types: ChartRequest['chart_type'][] = request.x_metric ? ['scatter'] : grouped ? ['bar', 'stacked_bar'] : ['bar', 'line', 'area', 'pie', 'donut'];
 const updateType = (chart_type: ChartRequest['chart_type']) => updateRequest({ ...request, chart_type, x_metric: chart_type === 'scatter' ? metrics.find(x => x.name !== request.metric)?.name : undefined, limit: ['pie','donut'].includes(chart_type) ? Math.min(request.limit, 5) : request.limit });
 const pin = async () => { if (!result || loading || pinning) return; setPinning(true); try { onPin(instance.id, result, request); } finally { window.setTimeout(() => setPinning(false), 300); } };
 const viewRecords = () => { if (result && !loading) onViewRecords?.(result, request); };
 return <article className={`executive-chart-card role-${instance.role}`}><header className="chart-card-header"><div><p className="section-eyebrow">{instance.role === 'trend' ? text(language,'primaryTrend') : text(language,'customChart')}</p><h2>{result?.title ?? instance.title}</h2></div>{loading && <span className="chart-status"><LoaderCircle size={14} className="animate-spin"/>{text(language,'updating')}</span>}</header><div className="chart-controls"><label>{text(language,'metric')}<select value={request.metric} onChange={e => updateRequest({...request, metric:e.target.value})}>{metrics.map(x=><option key={x.name}>{x.name}</option>)}</select></label><label>{text(language,'dimension')}<select value={request.dimension} onChange={e => updateRequest({...request, dimension:e.target.value})}>{dimensions.map(x=><option key={x.name}>{x.name}</option>)}</select></label><label>{text(language,'type')}<ChartTypeSelect value={types.includes(request.chart_type) ? request.chart_type : types[0]} options={types} onChange={updateType} language={language}/></label>{['pie','donut'].includes(request.chart_type) && <label>{text(language,'limit')}<select value={request.limit} onChange={e=>updateRequest({...request, limit:Number(e.target.value)})}><option value={5}>Top 5</option><option value={10}>Top 10</option></select></label>}</div>{error && <p className="chart-error"><TriangleAlert size={16}/>{error}</p>}<div className="chart-visual">{result ? <ValidatedChart result={result} language={language}/> : <p>{text(language,'chartConfigure')}</p>}</div>{result && <footer className="chart-actions"><button disabled={loading || pinning} onClick={pin}>{pinning ? text(language,'saving') : text(language,'addReport')}</button>{onViewRecords && <button disabled={loading} onClick={viewRecords}>{text(language,'viewRecords')}</button>}</footer>}</article>;
}
