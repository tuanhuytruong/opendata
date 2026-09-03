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
  profile_status?: 'sampled' | 'complete';
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

export interface StarterView {
  id: string;
  title: string;
  rationale: string;
  request: ChartRequest;
  question?: string;
}

export interface ChartRow {
  label: string;
  display_label?: string;
  secondary_label?: string;
  value: number;
  formatted_value?: string;
  cumulative_pct?: number;
}

export interface ChartResult {
  dimension: string;
  metric: string;
  aggregation: string;
  chart_type: string;
  title: string;
  secondary_dimension?: string;
  filters: Array<{ column: string; operator: 'equals' | 'not_equals' | 'greater_than' | 'greater_or_equal' | 'less_than' | 'less_or_equal'; value: string }>;
  rows: ChartRow[];
  warnings: string[];
  sort_mode?: 'chronological' | 'ranking';
  result_count?: number;
  insight_headline?: string;
  evidence?: string[];
}

export interface ClarificationOption { column: string; label: string; reason: string; role: 'metric' | 'dimension'; }
export interface ChatResult { answer: string; insight: string; scope: string; title?: string; chart?: ChartResult; table: ChartRow[]; caveats: string[]; clarification_options?: ClarificationOption[]; proposals?: StarterView[]; mode: 'analysis' | 'clarification'; planner: 'llm' | 'deterministic'; }


export interface ExecutiveOverview { run_id: string; summary: string; charts: ChartResult[]; warnings: string[]; guardrail: string; }

export interface EDAColumn {
  name: string;
  kind: ColumnKind;
  quality: { non_null_count: number; null_count: number; null_ratio: number; distinct_count: number; distinct_ratio: number };
  numeric_summary?: { valid_count: number; invalid_count: number; min?: number; max?: number; mean?: number; median?: number };
  time_coverage?: { valid_count: number; invalid_count: number; start?: string; end?: string };
  top_categories?: Array<{ value: string; count: number }>;
}

export interface EDAResult {
  coverage: { row_count: number; column_count: number; analyzed_column_count: number; suppressed_sensitive_column_count: number; suppressed_column_count: number };
  columns: EDAColumn[];
  provenance: { dataset_sha256: string; source_type: string; source_label: string; analysis: string; top_category_limit: number };
  guardrails: string[];
}

export interface AnalystProposal {
  id: string;
  title: string;
  rationale: string;
  confidence: 'profile-based';
  request: ChartRequest;
}

export interface AnalystPlan { summary: string; proposals: AnalystProposal[]; guardrail: string; }
