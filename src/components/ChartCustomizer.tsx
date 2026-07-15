import React from 'react';
import { Sliders, Eye, TrendingUp, Grid, BarChart3, LineChart, AreaChart, CircleDot } from 'lucide-react';
import { ChartConfig, Dataset } from '../types';

interface ChartCustomizerProps {
  dataset: Dataset;
  config: ChartConfig;
  onChangeConfig: (config: ChartConfig) => void;
}

const PALETTES = [
  { name: 'Indigo Core', value: 'indigo', primary: '#4f46e5', light: '#e0e7ff' },
  { name: 'Emerald Peak', value: 'emerald', primary: '#10b981', light: '#d1fae5' },
  { name: 'Violet Pulse', value: 'violet', primary: '#8b5cf6', light: '#ede9fe' },
  { name: 'Amber Glow', value: 'amber', primary: '#f59e0b', light: '#fef3c7' },
  { name: 'Rose Impact', value: 'rose', primary: '#f43f5e', light: '#ffe4e6' }
];

export default function ChartCustomizer({
  dataset,
  config,
  onChangeConfig
}: ChartCustomizerProps) {
  
  const updateField = (field: keyof ChartConfig, value: any) => {
    onChangeConfig({
      ...config,
      [field]: value
    });
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm h-full">
      <div className="flex items-center gap-2 mb-4">
        <Sliders className="w-5 h-5 text-indigo-600" />
        <h2 className="text-lg font-semibold font-display text-slate-800">Chart Settings</h2>
      </div>

      <p className="text-sm text-slate-500 mb-6">
        Tailor the parameters of your dynamic trends chart to capture high-impact correlations.
      </p>

      {/* Chart Types */}
      <div className="mb-5">
        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Chart Type
        </label>
        <div className="grid grid-cols-4 gap-2">
          {[
            { id: 'line', label: 'Line', icon: LineChart },
            { id: 'bar', label: 'Bar', icon: BarChart3 },
            { id: 'area', label: 'Area', icon: AreaChart },
            { id: 'scatter', label: 'Scatter', icon: CircleDot }
          ].map((type) => {
            const Icon = type.icon;
            const isSelected = config.type === type.id;
            return (
              <button
                key={type.id}
                onClick={() => updateField('type', type.id)}
                className={`flex flex-col items-center justify-center p-2.5 rounded-xl border transition-all ${
                  isSelected
                    ? 'border-indigo-600 bg-indigo-50/20 text-indigo-700 font-medium'
                    : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-700'
                }`}
              >
                <Icon className="w-4.5 h-4.5 mb-1" />
                <span className="text-[11px]">{type.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Axis Configuration */}
      <div className="grid grid-cols-2 gap-4 mb-5">
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            X-Axis (Labels)
          </label>
          <select
            value={config.xAxisColumn}
            onChange={(e) => updateField('xAxisColumn', e.target.value)}
            className="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-700 focus:outline-none focus:border-indigo-500"
          >
            {dataset.columns.map(col => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Y-Axis (Metrics)
          </label>
          <select
            value={config.yAxisColumn}
            onChange={(e) => updateField('yAxisColumn', e.target.value)}
            className="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-700 focus:outline-none focus:border-indigo-500"
          >
            {dataset.numericColumns.map(col => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Color Palettes */}
      <div className="mb-6">
        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Color Palette
        </label>
        <div className="flex flex-wrap gap-2">
          {PALETTES.map((p) => {
            const isSelected = config.colorPalette === p.value;
            return (
              <button
                key={p.value}
                onClick={() => updateField('colorPalette', p.value)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-all ${
                  isSelected
                    ? 'border-indigo-600 bg-indigo-50/20 text-indigo-800 font-medium'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                }`}
              >
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: p.primary }}
                />
                <span>{p.name}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Visual Toggles */}
      <div>
        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
          Visual Overlays
        </label>
        <div className="space-y-2.5">
          <button
            onClick={() => updateField('showGrid', !config.showGrid)}
            className={`flex items-center justify-between w-full p-3 rounded-xl border text-sm transition-all ${
              config.showGrid
                ? 'border-slate-200 bg-slate-50/50 text-slate-800'
                : 'border-slate-200 bg-white text-slate-400/70'
            }`}
          >
            <div className="flex items-center gap-2">
              <Grid className={`w-4 h-4 ${config.showGrid ? 'text-indigo-600' : 'text-slate-300'}`} />
              <span className="font-medium text-xs">Show Grid Lines</span>
            </div>
            <div className={`w-8 h-4 rounded-full relative transition-colors ${config.showGrid ? 'bg-indigo-600' : 'bg-slate-200'}`}>
              <span className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-transform ${config.showGrid ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
            </div>
          </button>

          <button
            onClick={() => updateField('showLegend', !config.showLegend)}
            className={`flex items-center justify-between w-full p-3 rounded-xl border text-sm transition-all ${
              config.showLegend
                ? 'border-slate-200 bg-slate-50/50 text-slate-800'
                : 'border-slate-200 bg-white text-slate-400/70'
            }`}
          >
            <div className="flex items-center gap-2">
              <Eye className={`w-4 h-4 ${config.showLegend ? 'text-indigo-600' : 'text-slate-300'}`} />
              <span className="font-medium text-xs">Show Chart Legend</span>
            </div>
            <div className={`w-8 h-4 rounded-full relative transition-colors ${config.showLegend ? 'bg-indigo-600' : 'bg-slate-200'}`}>
              <span className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-transform ${config.showLegend ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
            </div>
          </button>

          <button
            onClick={() => updateField('showTrendline', !config.showTrendline)}
            className={`flex items-center justify-between w-full p-3 rounded-xl border text-sm transition-all ${
              config.showTrendline
                ? 'border-slate-200 bg-slate-50/50 text-slate-800'
                : 'border-slate-200 bg-white text-slate-400/70'
            }`}
          >
            <div className="flex items-center gap-2">
              <TrendingUp className={`w-4 h-4 ${config.showTrendline ? 'text-indigo-600' : 'text-slate-300'}`} />
              <span className="font-medium text-xs">Fit Regression Trendline</span>
            </div>
            <div className={`w-8 h-4 rounded-full relative transition-colors ${config.showTrendline ? 'bg-indigo-600' : 'bg-slate-200'}`}>
              <span className={`w-3 h-3 rounded-full bg-white absolute top-0.5 transition-transform ${config.showTrendline ? 'translate-x-4.5' : 'translate-x-0.5'}`} />
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
export { PALETTES };
