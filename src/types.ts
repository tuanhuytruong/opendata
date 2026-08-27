export type ColumnKind = 'time' | 'num' | 'cat' | 'id' | 'unknown';

export interface ColumnProfile {
  name: string;
  kind: ColumnKind;
  null_count: number;
  null_ratio: number;
  distinct_count: number;
  description: string;
}

export interface DatasetProfile {
  run_id: string;
  file_name: string;
  row_count: number;
  column_count: number;
  usable_column_count: number;
  columns: ColumnProfile[];
  warnings: string[];
  preview: Record<string, string>[];
}

export interface ChartRequest {
  dimension: string;
  metric: string;
  aggregation: 'sum' | 'avg' | 'count';
  chart_type: 'bar' | 'line' | 'area' | 'scatter' | 'pareto' | 'stacked_bar' | 'heatmap';
  secondary_dimension?: string;
  limit: number;
  filters?: Array<{ column: string; operator: 'equals' | 'not_equals' | 'greater_than' | 'greater_or_equal' | 'less_than' | 'less_or_equal'; value: string }>;
}

export interface ChartResult {
  dimension: string;
  metric: string;
  aggregation: string;
  chart_type: string;
  title: string;
  secondary_dimension?: string;
  filters: Array<{ column: string; operator: 'equals' | 'not_equals' | 'greater_than' | 'greater_or_equal' | 'less_than' | 'less_or_equal'; value: string }>;
  rows: Array<{ label: string; secondary_label?: string; value: number; cumulative_pct?: number }>;
  warnings: string[];
}
