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

export interface ChartConfig {
  type: 'line' | 'bar' | 'area' | 'scatter';
  xAxisColumn: string;
  yAxisColumn: string;
  colorPalette: string;
  showGrid: boolean;
  showLegend: boolean;
  showTrendline: boolean;
}
