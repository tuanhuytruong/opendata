import { ChartRequest, ChartResult } from './types';

/** Prefer the executed server request: result count is not a requested top-N. */
export function toRequest(chart: ChartResult): ChartRequest {
  if (chart.request) return structuredClone(chart.request);
  return {
    dimension: chart.dimension, metric: chart.metric,
    aggregation: chart.aggregation as ChartRequest['aggregation'], chart_type: chart.chart_type,
    secondary_dimension: chart.secondary_dimension, x_metric: chart.x_metric, secondary_metric: chart.secondary_metric,
    limit_per_secondary: chart.limit_per_secondary,
    limit: chart.limit ?? Math.min(30, Math.max(1, chart.result_count || 12)),
    filters: structuredClone(chart.filters),
  };
}
