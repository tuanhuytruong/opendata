export interface Dataset {
  id: string;
  name: string;
  description: string;
  category: string;
  columns: string[];
  numericColumns: string[];
  data: Record<string, any>[];
}

export interface ChartConfig {
  type: 'line' | 'bar' | 'area' | 'scatter';
  xAxisColumn: string;
  yAxisColumn: string;
  colorPalette: string; // 'blue' | 'emerald' | 'violet' | 'amber' | 'rose'
  showGrid: boolean;
  showLegend: boolean;
  showTrendline: boolean;
}

export interface MetricSummary {
  name: string;
  value: string | number;
  description: string;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
}

export interface AIAnalysis {
  overview: string;
  keyMetrics: MetricSummary[];
  trendsAnalysis: string;
  recommendations: string[];
  suggestedQuestions: string[];
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
}
