import { Bar, BarChart, Cell, CartesianGrid, LabelList, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { ChartResult, ChartRow } from '../types';
import type { Language } from '../i18n';
import { chartCategoryLabel, formatChartValue } from '../formatting';
import type { ReportChartPresentation } from './model';

const PALETTE = ['#4f46e5', '#0f766e', '#c2410c', '#be185d', '#0284c7', '#65a30d', '#9333ea', '#ea580c', '#475569', '#db2777'];

type Props = { result: ChartResult; language: Language; className?: string };

function fallbackPresentation(result: ChartResult): ReportChartPresentation {
  const rows = result.rows.map(row => ({
    label: row.label,
    displayLabel: row.display_label ?? row.label,
    value: Number.isFinite(Number(row.value)) ? Number(row.value) : 0,
    formattedValue: formatChartValue(Number(row.value), 'en'),
    compactFormattedValue: formatChartValue(Number(row.value), 'en'),
    ...(row.secondary_label ? { secondaryLabel: row.secondary_label } : {}),
    ...(row.secondary_value != null ? { secondaryValue: Number(row.secondary_value), secondaryFormattedValue: formatChartValue(Number(row.secondary_value), 'en'), secondaryCompactFormattedValue: formatChartValue(Number(row.secondary_value), 'en') } : {}),
  }));
  const values = rows.map(row => row.value);
  const maximum = Math.max(1, ...values, 0);
  const magnitude = 10 ** Math.floor(Math.log10(maximum));
  const ceiling = Math.ceil((maximum * 1.08) / magnitude) * magnitude;
  const horizontal = result.chart_type === 'bar' && (rows.length > 7 || rows.some(row => String(row.displayLabel ?? row.label).length > 16));
  return {
    title: result.title,
    chartType: result.chart_type,
    orientation: horizontal ? 'horizontal' : 'vertical',
    metricLabel: result.metric_display_name ?? result.metric,
    dimensionLabel: result.dimension,
    rows,
    requestedLimit: Math.max(1, Math.min(30, result.requested_limit ?? result.limit ?? rows.length)),
    returnedCount: result.result_count ?? rows.length,
    domain: [0, ceiling],
    ticks: [0, ceiling / 4, ceiling / 2, ceiling * .75, ceiling].map(value => ({ value, label: formatChartValue(value, 'en') })),
    paletteMode: result.chart_type === 'pie' || result.chart_type === 'donut' ? 'categorical' : result.secondary_dimension ? 'grouped' : 'single-series',
    locale: 'en',
  };
}

const labelFor = (row: { displayLabel?: string; label: string }) => row.displayLabel ?? row.label;

export default function ReportChart({ result, language, className = '' }: Props) {
  const presentation = (result.presentation as ReportChartPresentation | undefined) ?? fallbackPresentation(result);
  const rows = presentation.rows.map(row => ({ ...row, displayLabel: labelFor(row) }));
  const format = (value: number) => formatChartValue(value, language);
  const isShare = presentation.chartType === 'pie' || presentation.chartType === 'donut';
  const isLine = presentation.chartType === 'line' || presentation.chartType === 'area';
  const horizontal = presentation.orientation === 'horizontal' && ['bar', 'pareto', 'stacked_bar'].includes(presentation.chartType);
  const height = horizontal ? Math.max(220, rows.length * (rows.length > 10 ? 30 : 36) + 54) : 300;
  const tooltip = <Tooltip formatter={(value: number) => [format(Number(value)), presentation.metricLabel]} labelFormatter={(_, payload) => labelFor((payload?.[0]?.payload ?? {}) as ChartRow)} />;

  const content = isShare ? <PieChart>
    <Tooltip formatter={(value: number) => [format(Number(value)), presentation.metricLabel]} />
    <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 11 }} />
    <Pie data={rows} dataKey="value" nameKey="displayLabel" outerRadius="68%" innerRadius={presentation.chartType === 'donut' ? '42%' : 0}>
      {rows.map((_, index) => <Cell key={`report-share-${index}`} fill={PALETTE[index % PALETTE.length]} />)}
    </Pie>
  </PieChart> : horizontal ? <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 72, left: 8, bottom: 8 }}>
    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
    <XAxis type="number" domain={presentation.domain} tickFormatter={format} tick={{ fontSize: 10, fontFamily: 'var(--font-sans)' }} />
    <YAxis type="category" dataKey="displayLabel" width={176} tickFormatter={value => chartCategoryLabel(String(value), 176, rows.length, true)} tick={{ fontSize: 10, fontFamily: 'var(--font-sans)' }} />
    {tooltip}
    <Bar dataKey="value" fill={presentation.paletteMode === 'single-series' ? PALETTE[0] : undefined} radius={[0, 3, 3, 0]}>
      {rows.map((row, index) => <Cell key={`report-bar-${index}`} fill={presentation.paletteMode === 'single-series' ? PALETTE[0] : PALETTE[index % PALETTE.length]} />)}
      <LabelList dataKey="compactFormattedValue" position="right" fill="#334155" fontSize={10} />
    </Bar>
  </BarChart> : isLine ? <LineChart data={rows} margin={{ top: 12, right: 20, left: 8, bottom: 48 }}>
    <CartesianGrid strokeDasharray="3 3" vertical={false} />
    <XAxis dataKey="displayLabel" interval={rows.length > 8 ? 'preserveStartEnd' : 0} angle={rows.length > 7 ? -35 : 0} textAnchor={rows.length > 7 ? 'end' : 'middle'} height={rows.length > 7 ? 58 : 30} tickFormatter={value => chartCategoryLabel(String(value), 120, rows.length)} tick={{ fontSize: 10, fontFamily: 'var(--font-sans)' }} />
    <YAxis domain={presentation.domain} tickFormatter={format} tick={{ fontSize: 10, fontFamily: 'var(--font-sans)' }} width={54} />
    {tooltip}
    <Line type="monotone" dataKey="value" stroke={PALETTE[0]} strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }}>
      <LabelList dataKey="formattedValue" position="top" fill="#334155" fontSize={10} />
    </Line>
  </LineChart> : <BarChart data={rows} margin={{ top: 12, right: 12, left: 8, bottom: rows.length > 7 ? 56 : 28 }}>
    <CartesianGrid strokeDasharray="3 3" vertical={false} />
    <XAxis dataKey="displayLabel" interval={rows.length > 8 ? 'preserveStartEnd' : 0} angle={rows.length > 7 ? -35 : 0} textAnchor={rows.length > 7 ? 'end' : 'middle'} height={rows.length > 7 ? 58 : 30} tickFormatter={value => chartCategoryLabel(String(value), 120, rows.length)} tick={{ fontSize: 10, fontFamily: 'var(--font-sans)' }} />
    <YAxis domain={presentation.domain} tickFormatter={format} tick={{ fontSize: 10, fontFamily: 'var(--font-sans)' }} width={54} />
    {tooltip}
    <Bar dataKey="value" fill={presentation.paletteMode === 'single-series' ? PALETTE[0] : undefined} radius={[3, 3, 0, 0]}>
      {rows.map((row, index) => <Cell key={`report-column-${index}`} fill={presentation.paletteMode === 'single-series' ? PALETTE[0] : PALETTE[index % PALETTE.length]} />)}
      <LabelList dataKey="formattedValue" position="top" fill="#334155" fontSize={10} />
    </Bar>
  </BarChart>;

  return <div className={`report-chart-wrapper ${horizontal ? 'report-chart-wrapper-horizontal' : ''} ${className}`} style={{ height }} role="img" aria-label={`${presentation.title}. ${rows.map(row => `${labelFor(row)}: ${row.formattedValue}`).join('; ')}`}>
    <ResponsiveContainer width="100%" height="100%">{content}</ResponsiveContainer>
  </div>;
}
