import { AreaChart, BarChart3, ChartNoAxesCombined, CircleDot, LineChart, PieChart, ScatterChart } from 'lucide-react';
import { ChartType } from '../types';
import { Language } from '../i18n';

const icons: Record<string, typeof BarChart3> = { bar: BarChart3, line: LineChart, area: AreaChart, pie: PieChart, donut: CircleDot, scatter: ScatterChart, stacked_bar: ChartNoAxesCombined };
const labels: Record<string, { en: string; vi: string }> = { bar: { en: 'Bar', vi: 'Cột' }, line: { en: 'Line', vi: 'Đường' }, area: { en: 'Area', vi: 'Miền' }, pie: { en: 'Pie', vi: 'Tròn' }, donut: { en: 'Donut', vi: 'Vành khuyên' }, scatter: { en: 'Scatter', vi: 'Phân tán' }, stacked_bar: { en: 'Stacked bar', vi: 'Cột chồng' } };
export default function ChartTypeSelect({ value, options, onChange, language }: { value: ChartType; options: ChartType[]; onChange: (type: ChartType) => void; language: Language }) {
 const Icon = icons[value] ?? BarChart3;
 return <label className="chart-type-select"> <span className="sr-only">Chart type</span><Icon aria-hidden="true" size={15}/><select aria-label={language === 'vi' ? 'Loại biểu đồ' : 'Chart type'} value={value} onChange={e => onChange(e.target.value as ChartType)}>{options.map(type => { const TypeIcon = icons[type] ?? BarChart3; return <option key={type} value={type}>{labels[type]?.[language] ?? type} {TypeIcon ? '' : ''}</option>; })}</select></label>;
}
