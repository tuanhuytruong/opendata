import React, { useState, useEffect, useMemo } from 'react';
import { Sparkles, BarChart3, HelpCircle, FileSpreadsheet, RotateCcw, AlertCircle, ArrowUpRight, ArrowDownRight, Minus, TrendingUp, Info } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, AreaChart, Area, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

import { Dataset, ChartConfig, AIAnalysis } from './types';
import { defaultDatasets } from './data/defaultDatasets';
import { calculateColumnStats, calculateRegressionLine } from './utils/dataAnalysis';
import DatasetSelector from './components/DatasetSelector';
import ChartCustomizer, { PALETTES } from './components/ChartCustomizer';
import InsightPanel from './components/InsightPanel';
import DataGrid from './components/DataGrid';
import PdfExporter from './components/PdfExporter';

export default function App() {
  // Datasets State
  const [datasets, setDatasets] = useState<Dataset[]>(defaultDatasets);
  const [activeDataset, setActiveDataset] = useState<Dataset>(defaultDatasets[0]);

  // Chart Config State
  const [chartConfig, setChartConfig] = useState<ChartConfig>({
    type: 'line',
    xAxisColumn: defaultDatasets[0].columns[0],
    yAxisColumn: defaultDatasets[0].numericColumns[0],
    colorPalette: 'indigo',
    showGrid: true,
    showLegend: true,
    showTrendline: false
  });

  // AI Analysis State
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [isDemoMode, setIsDemoMode] = useState(false);

  // Synchronize axes when active dataset changes
  useEffect(() => {
    setChartConfig({
      ...chartConfig,
      xAxisColumn: activeDataset.columns[0] || '',
      yAxisColumn: activeDataset.numericColumns[0] || ''
    });
    // Reset report until generated for new dataset
    setAnalysis(null);
    setAnalysisError(null);
  }, [activeDataset]);

  // Merge trendlines if toggled
  const chartData = useMemo(() => {
    if (!chartConfig.showTrendline || !chartConfig.yAxisColumn) {
      return activeDataset.data;
    }
    const regressionPoints = calculateRegressionLine(activeDataset.data, chartConfig.yAxisColumn);
    return activeDataset.data.map((row, idx) => ({
      ...row,
      _trendline: regressionPoints[idx]?.trend || 0
    }));
  }, [activeDataset.data, chartConfig.yAxisColumn, chartConfig.showTrendline]);

  // Local Statistical Indicators for Active Columns
  const localStats = useMemo(() => {
    if (!chartConfig.yAxisColumn) return null;
    return calculateColumnStats(activeDataset.data, chartConfig.yAxisColumn);
  }, [activeDataset.data, chartConfig.yAxisColumn]);

  const activeColorPalette = useMemo(() => {
    return PALETTES.find(p => p.value === chartConfig.colorPalette) || PALETTES[0];
  }, [chartConfig.colorPalette]);

  // Trigger full-stack AI Analysis
  const handleRunAnalysis = async () => {
    setLoadingAnalysis(true);
    setAnalysisError(null);
    setIsDemoMode(false);

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          datasetName: activeDataset.name,
          datasetDescription: activeDataset.description,
          columns: activeDataset.columns,
          numericColumns: activeDataset.numericColumns,
          dataRows: activeDataset.data
        })
      });

      const result = await response.json();

      if (!response.ok) {
        // Fallback to offline analysis if API Key is not set yet
        if (response.status === 403 && result.isDemoMode) {
          setAnalysis(result.fallbackData);
          setIsDemoMode(true);
        } else {
          throw new Error(result.error || result.details || 'Analysis failed');
        }
      } else {
        setAnalysis(result);
      }
    } catch (err: any) {
      console.error(err);
      setAnalysisError(err.message || 'Error occurred connecting to the backend analysis engine.');
    } finally {
      setLoadingAnalysis(false);
    }
  };

  // Submit contextual chat prompt
  const handleAskQuestion = async (question: string): Promise<string> => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        datasetName: activeDataset.name,
        columns: activeDataset.columns,
        numericColumns: activeDataset.numericColumns,
        dataRows: activeDataset.data,
        messages: [
          { sender: 'user', text: question }
        ]
      })
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || result.details || 'Chat query failed');
    }

    if (result.isDemoMode) {
      setIsDemoMode(true);
    }

    return result.reply || result.text;
  };

  // Update rows inside active dataset
  const handleUpdateData = (newData: Record<string, any>[]) => {
    const updatedDataset = {
      ...activeDataset,
      data: newData
    };
    setActiveDataset(updatedDataset);
    // Persist changes to global list in case we switch back
    setDatasets(prev => prev.map(ds => ds.id === activeDataset.id ? updatedDataset : ds));
  };

  // Reset active dataset values
  const handleResetDataset = () => {
    const original = defaultDatasets.find(ds => ds.id === activeDataset.id);
    if (original) {
      setActiveDataset({ ...original });
      setDatasets(prev => prev.map(ds => ds.id === activeDataset.id ? { ...original } : ds));
    }
  };

  // Custom formatted tooltip render
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-900 border border-slate-800 text-white rounded-xl p-3.5 shadow-xl text-xs space-y-1.5 leading-relaxed font-mono">
          <p className="font-bold font-sans text-slate-300 border-b border-slate-800 pb-1 mb-1 text-[11px] uppercase tracking-wider">{label}</p>
          {payload.map((pld: any, index: number) => (
            <p key={index} style={{ color: pld.color }}>
              <span className="text-slate-400">{pld.name}:</span>{' '}
              <span className="font-semibold text-slate-100">
                {typeof pld.value === 'number' ? pld.value.toLocaleString() : pld.value}
              </span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex">
      {/* Sidebar Navigation */}
      <aside className="w-20 bg-white border-r border-slate-200 hidden md:flex flex-col items-center py-8 gap-8 shrink-0 sticky top-0 h-screen z-30">
        <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-indigo-100">
          V
        </div>
        
        <div className="flex flex-col gap-5 items-center w-full px-2 mt-4">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-xl" title="Analytics Dashboard">
            <BarChart3 className="w-5.5 h-5.5" />
          </div>
          
          <a 
            href="#grid" 
            className="p-3 text-slate-400 hover:text-indigo-600 hover:bg-slate-50 rounded-xl transition-all"
            title="Raw Data Grid"
          >
            <FileSpreadsheet className="w-5.5 h-5.5" />
          </a>

          <button 
            onClick={handleResetDataset}
            className="p-3 text-slate-400 hover:text-indigo-600 hover:bg-slate-50 rounded-xl transition-all"
            title="Reset Dataset to Default"
          >
            <RotateCcw className="w-5.5 h-5.5" />
          </button>
        </div>

        <div className="mt-auto p-3 text-slate-400 hover:text-indigo-500 cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-700 flex items-center justify-center text-xs font-semibold border border-slate-200">
            HT
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Navigation Header */}
        <header className="border-b border-slate-200 bg-white/80 backdrop-blur-md sticky top-0 z-40">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-indigo-600 rounded-xl flex md:hidden items-center justify-center shadow-md shadow-indigo-600/20 text-white">
                <BarChart3 className="w-5.5 h-5.5" />
              </div>
              <div>
                <h1 className="text-xl font-bold font-display text-slate-900 tracking-tight flex items-center gap-2">
                  Market Intelligence Dashboard
                </h1>
                <p className="text-[11px] text-slate-500 font-medium">Real-time trend analysis and automated reporting</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <a 
                href="#grid" 
                className="flex items-center gap-1.5 px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-xs text-slate-600 hover:text-slate-900 font-semibold rounded-lg transition-all shadow-sm"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                <span>Data Grid</span>
              </a>
            </div>
          </div>
        </header>

        {/* Main Container */}
        <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          
          {/* Row 1: Quick Indicators & Core Visualizer Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            
            {/* Main Visualizer Panel */}
            <div className="lg:col-span-8 flex flex-col gap-6">
              
              {/* dynamic statistics summaries computed locally */}
              {localStats && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 animate-fade-in">
                  
                  {/* Metric Summary Card: Deep Indigo */}
                  <div className="bg-indigo-950 rounded-2xl p-5 text-white flex flex-col justify-between shadow-sm relative overflow-hidden group min-h-[125px]">
                    <div className="absolute inset-0 bg-gradient-to-br from-indigo-950 via-slate-950 to-indigo-900 opacity-95 z-0" />
                    <div className="relative z-10 flex flex-col justify-between h-full">
                      <div>
                        <span className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider block">Average (Mean)</span>
                        <span className="text-2xl font-extrabold font-display mt-1 block tracking-tight text-white">
                          {localStats.avg.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                        </span>
                      </div>
                      <span className="text-[10px] text-indigo-200/80 mt-1 block leading-tight">Aggregated average score</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between min-h-[125px]">
                    <div>
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Aggregate Sum</span>
                      <span className="text-2xl font-extrabold font-display text-slate-800 mt-1 block font-mono tracking-tight">
                        {localStats.sum.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 mt-1 block leading-tight">Sum cumulative metrics</span>
                  </div>

                  <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between min-h-[125px]">
                    <div>
                      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Variance Bounds</span>
                      <span className="text-xl font-bold font-display text-slate-800 mt-1 block tracking-tight">
                        {localStats.min.toLocaleString()} - {localStats.max.toLocaleString()}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 mt-1 block leading-tight">Trough & Peak boundaries</span>
                  </div>

                  {/* Optimization Trajectory Card */}
                  <div className={`rounded-2xl border p-5 flex flex-col justify-between shadow-sm min-h-[125px] ${
                    localStats.trendPercentage > 0 
                      ? 'bg-emerald-50/70 border-emerald-100 text-emerald-950' 
                      : localStats.trendPercentage < 0 
                      ? 'bg-rose-50/70 border-rose-100 text-rose-950' 
                      : 'bg-slate-50 border-slate-200 text-slate-800'
                  }`}>
                    <div>
                      <span className={`text-[10px] font-bold uppercase tracking-wider block ${
                        localStats.trendPercentage > 0 ? 'text-emerald-600' : localStats.trendPercentage < 0 ? 'text-rose-600' : 'text-slate-400'
                      }`}>Overall Trajectory</span>
                      <div className="flex items-center gap-1 mt-1">
                        {localStats.trendPercentage > 0 ? (
                          <ArrowUpRight className="w-5 h-5 text-emerald-500 shrink-0" />
                        ) : localStats.trendPercentage < 0 ? (
                          <ArrowDownRight className="w-5 h-5 text-rose-500 shrink-0" />
                        ) : (
                          <Minus className="w-5 h-5 text-slate-400 shrink-0" />
                        )}
                        <span className="text-2xl font-extrabold font-display tracking-tight">
                          {localStats.trendPercentage > 0 ? '+' : ''}{localStats.trendPercentage.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <span className={`text-[10px] mt-1 block ${
                      localStats.trendPercentage > 0 ? 'text-emerald-600/80' : localStats.trendPercentage < 0 ? 'text-rose-600/80' : 'text-slate-400'
                    }`}>Calculated drift bounds</span>
                  </div>

                </div>
              )}

              {/* Interactive Recharts Canvas */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm flex flex-col h-[400px]">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold font-display text-slate-800">{activeDataset.name} Trends</h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Plotting <strong className="text-indigo-600 font-semibold">{chartConfig.yAxisColumn}</strong> against <strong className="text-slate-700">{chartConfig.xAxisColumn}</strong>
                    </p>
                  </div>
                  {chartConfig.showTrendline && (
                    <span className="flex items-center gap-1.5 text-[11px] font-medium text-slate-500 bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-full font-mono">
                      <TrendingUp className="w-3.5 h-3.5 text-indigo-500" />
                      <span>Fit Regression Line</span>
                    </span>
                  )}
                </div>

                {/* Chart container */}
                <div className="flex-1 w-full text-xs">
                  <ResponsiveContainer width="100%" height="100%">
                    {chartConfig.type === 'line' ? (
                      <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                        {chartConfig.showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />}
                        <XAxis dataKey={chartConfig.xAxisColumn} stroke="#94a3b8" fontSize={10} tickLine={false} />
                        <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} />
                        <Tooltip content={<CustomTooltip />} />
                        {chartConfig.showLegend && <Legend verticalAlign="top" height={36} iconType="circle" />}
                        <Line
                          name={chartConfig.yAxisColumn}
                          type="monotone"
                          dataKey={chartConfig.yAxisColumn}
                          stroke={activeColorPalette.primary}
                          strokeWidth={2.5}
                          dot={{ r: 4, strokeWidth: 1.5, fill: '#fff' }}
                          activeDot={{ r: 6 }}
                        />
                        {chartConfig.showTrendline && (
                          <Line
                            name="Trendline (y=mx+b)"
                            type="monotone"
                            dataKey="_trendline"
                            stroke="#64748b"
                            strokeWidth={1.5}
                            strokeDasharray="5 5"
                            dot={false}
                          />
                        )}
                      </LineChart>
                    ) : chartConfig.type === 'bar' ? (
                      <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                        {chartConfig.showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />}
                        <XAxis dataKey={chartConfig.xAxisColumn} stroke="#94a3b8" fontSize={10} tickLine={false} />
                        <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} />
                        <Tooltip content={<CustomTooltip />} />
                        {chartConfig.showLegend && <Legend verticalAlign="top" height={36} iconType="circle" />}
                        <Bar
                          name={chartConfig.yAxisColumn}
                          dataKey={chartConfig.yAxisColumn}
                          fill={activeColorPalette.primary}
                          radius={[4, 4, 0, 0]}
                          maxBarSize={50}
                        />
                        {chartConfig.showTrendline && (
                          <Line
                            name="Trendline (y=mx+b)"
                            type="monotone"
                            dataKey="_trendline"
                            stroke="#64748b"
                            strokeWidth={1.5}
                            strokeDasharray="5 5"
                            dot={false}
                          />
                        )}
                      </BarChart>
                    ) : chartConfig.type === 'area' ? (
                      <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorArea" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={activeColorPalette.primary} stopOpacity={0.3} />
                            <stop offset="95%" stopColor={activeColorPalette.primary} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        {chartConfig.showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />}
                        <XAxis dataKey={chartConfig.xAxisColumn} stroke="#94a3b8" fontSize={10} tickLine={false} />
                        <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} />
                        <Tooltip content={<CustomTooltip />} />
                        {chartConfig.showLegend && <Legend verticalAlign="top" height={36} iconType="circle" />}
                        <Area
                          name={chartConfig.yAxisColumn}
                          type="monotone"
                          dataKey={chartConfig.yAxisColumn}
                          stroke={activeColorPalette.primary}
                          strokeWidth={2}
                          fillOpacity={1}
                          fill="url(#colorArea)"
                        />
                        {chartConfig.showTrendline && (
                          <Line
                            name="Trendline (y=mx+b)"
                            type="monotone"
                            dataKey="_trendline"
                            stroke="#64748b"
                            strokeWidth={1.5}
                            strokeDasharray="5 5"
                            dot={false}
                          />
                        )}
                      </AreaChart>
                    ) : (
                      <ScatterChart margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                        {chartConfig.showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />}
                        <XAxis type="category" dataKey={chartConfig.xAxisColumn} name="Segment" stroke="#94a3b8" fontSize={10} />
                        <YAxis type="number" dataKey={chartConfig.yAxisColumn} name="Metric" stroke="#94a3b8" fontSize={10} />
                        <Tooltip content={<CustomTooltip />} />
                        {chartConfig.showLegend && <Legend verticalAlign="top" height={36} iconType="circle" />}
                        <Scatter
                          name={chartConfig.yAxisColumn}
                          data={chartData}
                          fill={activeColorPalette.primary}
                        />
                        {chartConfig.showTrendline && (
                          <Line
                            name="Trendline (y=mx+b)"
                            type="monotone"
                            data={chartData}
                            dataKey="_trendline"
                            stroke="#64748b"
                            strokeWidth={1.5}
                            strokeDasharray="5 5"
                            dot={false}
                          />
                        )}
                      </ScatterChart>
                    )}
                  </ResponsiveContainer>
                </div>
              </div>

            </div>

            {/* Right Panel: Chart Settings & PDF Exporter */}
            <div className="lg:col-span-4 flex flex-col gap-6">
              <ChartCustomizer
                dataset={activeDataset}
                config={chartConfig}
                onChangeConfig={setChartConfig}
              />

              <PdfExporter
                dataset={activeDataset}
                analysis={analysis}
                chartConfig={chartConfig}
              />
            </div>

          </div>

          {/* Row 2: Dataset Selection & AI Narrative Insights Side-by-Side */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            
            {/* Dataset Selector (Left Column) */}
            <div className="lg:col-span-5">
              <DatasetSelector
                activeDataset={activeDataset}
                onSelectDataset={setActiveDataset}
                onUploadDataset={(newDs) => {
                  setDatasets(prev => [newDs, ...prev]);
                  setActiveDataset(newDs);
                }}
              />
            </div>

            {/* AI Reasoning Insights & Chat (Right Column) */}
            <div className="lg:col-span-7">
              <InsightPanel
                dataset={activeDataset}
                analysis={analysis}
                loading={loadingAnalysis}
                error={analysisError}
                isDemoMode={isDemoMode}
                onRefreshAnalysis={handleRunAnalysis}
                onAskQuestion={handleAskQuestion}
              />
            </div>

          </div>

          {/* Row 3: Raw Editable Data Table Grid */}
          <div id="grid" className="scroll-mt-24 animate-fade-in">
            <DataGrid
              dataset={activeDataset}
              onUpdateData={handleUpdateData}
              onResetDataset={handleResetDataset}
            />
          </div>

        </main>

        {/* Footer credits */}
        <footer className="bg-white border-t border-slate-200 py-6 mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-slate-400">
              &copy; 2026 Data Analyzer & Trend Visualizer. Formatted vector PDF compiled on user device.
            </p>
            <div className="flex items-center gap-1 text-[11px] text-slate-400 font-mono">
              <Info className="w-3.5 h-3.5 text-indigo-500" />
              <span>Bento Dashboard Visual Grid Engine</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
