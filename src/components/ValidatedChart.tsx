import { useEffect, useRef, useState } from 'react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartResult, ChartRow } from '../types';
import { Language } from '../i18n';
import { chartCategoryLabel, formatChartValue } from '../formatting';

/** Ordered for adjacent contrast and stable by category row order. */
export const CATEGORY_PALETTE = ['#4f46e5', '#0f766e', '#c2410c', '#be185d', '#0284c7', '#65a30d', '#9333ea', '#ea580c', '#475569', '#db2777'];
const PRIMARY_COLOR = CATEGORY_PALETTE[0];
const CHART_TYPE = { axis: 10, legend: 10, label: 9, tooltip: 12 };

export function numericDomainWithHeadroom(values: number[]): [number, number] {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return [0, 1];
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  if (min >= 0) return [0, max > 0 ? max * 1.2 : 1];
  if (max <= 0) return [min * 1.2, 0];
  return [min * 1.2, max * 1.2];
}

/** Dense trend labels retain endpoints, extrema, plus evenly distributed context. */
export function visibleLabelIndexes(rows: ChartRow[], chartWidth: number): Set<number> {
  const count = rows.length;
  if (count <= Math.max(4, Math.floor(chartWidth / 70))) return new Set(rows.map((_, index) => index));
  const indexes = new Set<number>([0, count - 1]);
  let min = 0; let max = 0;
  rows.forEach((row, index) => { if (row.value < rows[min].value) min = index; if (row.value > rows[max].value) max = index; });
  indexes.add(min); indexes.add(max);
  const target = Math.min(7, Math.max(4, Math.floor(chartWidth / 120)));
  for (let step = 1; step < target - 1; step += 1) indexes.add(Math.round((step * (count - 1)) / (target - 1)));
  return indexes;
}

function labelFor(row: ChartRow) { return row.display_label ?? row.label; }
function useChartWidth() {
  const ref = useRef<HTMLDivElement>(null); const [width, setWidth] = useState(640);
  useEffect(() => { const node = ref.current; if (!node) return; const observer = new ResizeObserver(entries => setWidth(Math.max(1, Math.round(entries[0].contentRect.width)))); observer.observe(node); return () => observer.disconnect(); }, []);
  return [ref, width] as const;
}

export default function ValidatedChart({ result, language, report = false }: { result: ChartResult; language: Language; report?: boolean }) {
  const [containerRef, chartWidth] = useChartWidth();
  const metric = result.metric_display_name ?? result.metric;
  const compact = (value: number) => formatChartValue(value, language);
  const tooltip = (value: number) => [compact(Number(value)), metric];
  const labels = result.rows.map(labelFor);
  const values = result.rows.map(row => Number(row.value));
  const domain = numericDomainWithHeadroom(values);
  const longCategories = result.sort_mode === 'ranking' && labels.some(item => item.length > 16);
  const horizontal = result.chart_type === 'bar' && longCategories;
  const chartHeight = horizontal ? Math.max(report ? 220 : 300, result.rows.length * 32 + 48) : undefined;
  const trend = result.chart_type === 'line' || result.chart_type === 'area';
  const selectedLabels = visibleLabelIndexes(result.rows, chartWidth);
  const tickLabel = (value: unknown) => chartCategoryLabel(String(value ?? ''), chartWidth - (horizontal ? 180 : 70), result.rows.length, horizontal);
  const valueLabel = (props: { value?: number; index?: number; x?: number; y?: number; width?: number | string; height?: number | string }) => {
    if (trend && !selectedLabels.has(props.index ?? -1)) return null;
    const x = Number(props.x ?? 0) + Number(props.width ?? 0) / 2;
    const y = Number(props.y ?? 0) - 6;
    return <text x={x} y={Math.max(12, y)} textAnchor="middle" className="validated-chart-label">{compact(Number(props.value ?? 0))}</text>;
  };
  const accessibleLabel = `${result.title}. ${result.rows.map(row => `${labelFor(row)}: ${compact(row.value)}`).join('; ')}`;
  const grouped = Boolean(result.secondary_dimension) && result.rows.some(row => row.secondary_label);
  const seriesLabels = [...new Set(result.rows.map(row => String(row.secondary_label ?? '')))].filter(Boolean);
  const pivot = result.rows.reduce<Record<string, Record<string, number | undefined>>>((acc, row) => { const key = labelFor(row); acc[key] = acc[key] ?? {}; acc[key][String(row.secondary_label ?? '')] = row.value; return acc; }, {});
  const pivotData = Object.entries(pivot).map(([label, values]) => ({ display_label: label, ...seriesLabels.reduce<Record<string, number>>((acc, name) => { acc[name] = Number(values[name] ?? 0); return acc; }, {}) }));
  const common = <><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="display_label" interval={result.rows.length > Math.max(6, Math.floor(chartWidth / 72)) ? 'preserveStartEnd' : 0} angle={result.sort_mode === 'chronological' || result.rows.length > 7 ? -35 : 0} textAnchor={result.sort_mode === 'chronological' || result.rows.length > 7 ? 'end' : 'middle'} height={result.sort_mode === 'chronological' || result.rows.length > 7 ? 58 : 34} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} tickFormatter={tickLabel} /><YAxis domain={domain} tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} width={58} /><Tooltip formatter={tooltip} labelFormatter={(_, payload) => labelFor(payload[0]?.payload as ChartRow)} contentStyle={{ fontSize: CHART_TYPE.tooltip, fontFamily: 'var(--font-sans)' }} /></>;
  const content = result.chart_type === 'pie' || result.chart_type === 'donut' ? <PieChart><Tooltip formatter={tooltip} contentStyle={{ fontSize: CHART_TYPE.tooltip, fontFamily: 'var(--font-sans)' }} /><Legend verticalAlign="bottom" wrapperStyle={{ fontSize: CHART_TYPE.legend, fontFamily: 'var(--font-sans)' }} /><Pie data={result.rows} dataKey="value" nameKey="display_label" outerRadius="72%" label={valueLabel} labelLine={false} innerRadius={result.chart_type === 'donut' ? '42%' : 0}>{result.rows.map((_, i) => <Cell key={i} fill={CATEGORY_PALETTE[i % CATEGORY_PALETTE.length]} />)}</Pie></PieChart> : result.chart_type === 'scatter' ? <ScatterChart><CartesianGrid /><XAxis dataKey="x_value" tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} /><YAxis dataKey="value" domain={domain} tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} /><Tooltip formatter={tooltip} contentStyle={{ fontSize: CHART_TYPE.tooltip, fontFamily: 'var(--font-sans)' }} /><Scatter data={result.rows} fill={PRIMARY_COLOR}><LabelList dataKey="value" content={valueLabel} /></Scatter></ScatterChart> : result.chart_type === 'line' ? <LineChart data={result.rows}>{common}<Line type="monotone" dataKey="value" stroke={PRIMARY_COLOR} strokeWidth={2} dot={{ r: 3 }}><LabelList dataKey="value" content={valueLabel} /></Line></LineChart> : result.chart_type === 'area' ? <AreaChart data={result.rows}>{common}<Area type="monotone" dataKey="value" stroke={PRIMARY_COLOR} fill="#c7d2fe"><LabelList dataKey="value" content={valueLabel} /></Area></AreaChart> : horizontal && !grouped ? <BarChart data={result.rows} layout="vertical" margin={{ left: 8, right: 42 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" domain={domain} tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} /><YAxis type="category" dataKey="display_label" width={Math.min(220, Math.max(110, Math.floor(chartWidth * .3)))} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} tickFormatter={tickLabel} /><Tooltip formatter={tooltip} labelFormatter={(_, payload) => labelFor(payload[0]?.payload as ChartRow)} contentStyle={{ fontSize: CHART_TYPE.tooltip, fontFamily: 'var(--font-sans)' }} /><Bar dataKey="value" radius={[0, 4, 4, 0]}>{result.rows.map((_, i) => <Cell key={i} fill={CATEGORY_PALETTE[i % CATEGORY_PALETTE.length]} />)}<LabelList dataKey="value" position="right" content={valueLabel} /></Bar></BarChart> : grouped ? <BarChart data={pivotData} margin={{ top: 12, right: 16 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="display_label" interval={0} angle={-30} textAnchor="end" height={56} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} tickFormatter={(value: string) => chartCategoryLabel(String(value ?? ''), chartWidth - 70, pivotData.length)} /><YAxis domain={domain} tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-sans)' }} width={58} /><Tooltip formatter={tooltip} labelFormatter={(_, payload) => String(payload?.[0]?.payload?.display_label ?? '')} contentStyle={{ fontSize: CHART_TYPE.tooltip, fontFamily: 'var(--font-sans)' }} /><Legend wrapperStyle={{ fontSize: CHART_TYPE.legend, fontFamily: 'var(--font-sans)' }} />{seriesLabels.map((name, i) => <Bar key={name} dataKey={name} stackId={result.chart_type === 'stacked_bar' ? 'stack' : undefined} fill={CATEGORY_PALETTE[i % CATEGORY_PALETTE.length]} radius={[4, 4, 0, 0]} />)}</BarChart> : <BarChart data={result.rows}>{common}<Bar dataKey="value" radius={[4, 4, 0, 0]}>{result.rows.map((_, i) => <Cell key={i} fill={CATEGORY_PALETTE[i % CATEGORY_PALETTE.length]} />)}<LabelList dataKey="value" position="top" content={valueLabel} /></Bar></BarChart>;
  return <div ref={containerRef} className={horizontal ? 'validated-chart horizontal-ranking' : 'validated-chart'} style={chartHeight ? { height: chartHeight } : undefined} role="img" aria-label={accessibleLabel}><ResponsiveContainer width="100%" height="100%">{content}</ResponsiveContainer></div>;
}
