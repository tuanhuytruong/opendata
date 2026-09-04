import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartResult, ChartRow } from '../types';
import { Language } from '../i18n';
import { formatChartValue, truncateChartLabel } from '../formatting';

const colors = ['#4f46e5', '#0f766e', '#c2410c', '#be185d', '#0284c7', '#65a30d', '#9333ea', '#ea580c', '#475569', '#db2777'];
const CHART_TYPE = { axis: 10, legend: 10, label: 10, tooltip: 12 };

function labelFor(row: ChartRow) { return row.display_label ?? row.label; }

export default function ValidatedChart({ result, language, report = false }: { result: ChartResult; language: Language; report?: boolean }) {
  const metric = result.metric_display_name ?? result.metric;
  const compact = (value: number) => formatChartValue(value, language);
  const tooltip = (value: number) => [compact(Number(value)), metric];
  const valueLabel = (props: { value?: number }) => compact(Number(props.value ?? 0));
  const labels = result.rows.map(labelFor);
  const longCategories = result.sort_mode === 'ranking' && labels.some(item => item.length > 16);
  const horizontal = result.chart_type === 'bar' && longCategories;
  const chartHeight = horizontal ? Math.max(report ? 220 : 300, result.rows.length * 32 + 48) : undefined;
  const shortLabel = (value: unknown) => truncateChartLabel(String(value ?? ''), horizontal ? 30 : 14);
  const accessibleLabel = `${result.title}. ${result.rows.map(row => `${labelFor(row)}: ${compact(row.value)}`).join('; ')}`;
  const common = <><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="display_label" interval={0} angle={result.sort_mode === 'chronological' ? -35 : 0} textAnchor={result.sort_mode === 'chronological' ? 'end' : 'middle'} height={result.sort_mode === 'chronological' ? 58 : 34} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-mono)' }} tickFormatter={shortLabel} /><YAxis tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-mono)' }} width={58} /><Tooltip formatter={tooltip} labelFormatter={(_, payload) => labelFor(payload[0]?.payload as ChartRow)} contentStyle={{ fontSize: CHART_TYPE.tooltip }} /></>;
  const content = result.chart_type === 'pie' || result.chart_type === 'donut' ? <PieChart><Tooltip formatter={tooltip} contentStyle={{ fontSize: CHART_TYPE.tooltip }} /><Legend verticalAlign="bottom" wrapperStyle={{ fontSize: CHART_TYPE.legend }} /><Pie data={result.rows} dataKey="value" nameKey="display_label" outerRadius="72%" label={valueLabel} innerRadius={result.chart_type === 'donut' ? '42%' : 0}>{result.rows.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}</Pie></PieChart> : result.chart_type === 'scatter' ? <ScatterChart><CartesianGrid /><XAxis dataKey="x_value" tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-mono)' }} /><YAxis dataKey="value" tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-mono)' }} /><Tooltip formatter={tooltip} contentStyle={{ fontSize: CHART_TYPE.tooltip }} /><Scatter data={result.rows} fill={colors[0]}><LabelList dataKey="value" content={valueLabel} /></Scatter></ScatterChart> : result.chart_type === 'line' ? <LineChart data={result.rows}>{common}<Line type="monotone" dataKey="value" stroke={colors[0]} strokeWidth={2} dot={{ r: 3 }}><LabelList dataKey="value" content={valueLabel} /></Line></LineChart> : result.chart_type === 'area' ? <AreaChart data={result.rows}>{common}<Area type="monotone" dataKey="value" stroke={colors[0]} fill="#c7d2fe"><LabelList dataKey="value" content={valueLabel} /></Area></AreaChart> : horizontal ? <BarChart data={result.rows} layout="vertical" margin={{ left: 8, right: 36 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" tickFormatter={compact} tick={{ fontSize: CHART_TYPE.axis, fontFamily: 'var(--font-mono)' }} /><YAxis type="category" dataKey="display_label" width={150} tick={{ fontSize: CHART_TYPE.axis }} tickFormatter={shortLabel} /><Tooltip formatter={tooltip} labelFormatter={(_, payload) => labelFor(payload[0]?.payload as ChartRow)} contentStyle={{ fontSize: CHART_TYPE.tooltip }} /><Bar dataKey="value" fill={colors[0]} radius={[0, 4, 4, 0]}><LabelList dataKey="value" position="right" formatter={compact} /></Bar></BarChart> : <BarChart data={result.rows}>{common}<Bar dataKey="value" fill={colors[0]} radius={[4, 4, 0, 0]}><LabelList dataKey="value" position="top" formatter={compact} /></Bar></BarChart>;
  return <div className={horizontal ? 'validated-chart horizontal-ranking' : 'validated-chart'} style={chartHeight ? { height: chartHeight } : undefined} role="img" aria-label={accessibleLabel}><ResponsiveContainer width="100%" height="100%">{content}</ResponsiveContainer></div>;
}
