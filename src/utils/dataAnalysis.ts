/**
 * Mathematical and statistical utilities for data trend analysis
 */

export interface Stats {
  min: number;
  max: number;
  avg: number;
  sum: number;
  count: number;
  trendPercentage: number; // Percentage change from first to last record
}

/**
 * Calculates statistical metrics for a specific column in a dataset
 */
export function calculateColumnStats(data: Record<string, any>[], columnName: string): Stats {
  const values = data
    .map(row => Number(row[columnName]))
    .filter(val => !isNaN(val) && val !== null && val !== undefined);

  if (values.length === 0) {
    return { min: 0, max: 0, avg: 0, sum: 0, count: 0, trendPercentage: 0 };
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const sum = values.reduce((acc, val) => acc + val, 0);
  const avg = sum / values.length;
  const count = values.length;

  const firstVal = values[0];
  const lastVal = values[values.length - 1];
  let trendPercentage = 0;
  if (firstVal !== 0) {
    trendPercentage = ((lastVal - firstVal) / firstVal) * 100;
  } else if (lastVal !== 0) {
    trendPercentage = lastVal > 0 ? 100 : -100;
  }

  return { min, max, avg, sum, count, trendPercentage };
}

/**
 * Fits a linear regression line (y = mx + b) for a given column.
 * Returns an array of points matching the original rows with predicted 'trendline' values.
 */
export function calculateRegressionLine(
  data: Record<string, any>[],
  yColumn: string
): { index: number; trend: number }[] {
  const points = data
    .map((row, index) => ({
      x: index,
      y: Number(row[yColumn]),
    }))
    .filter(pt => !isNaN(pt.y));

  const n = points.length;
  if (n < 2) {
    return data.map((_, idx) => ({ index: idx, trend: 0 }));
  }

  let sumX = 0;
  let sumY = 0;
  let sumXY = 0;
  let sumXX = 0;

  for (const pt of points) {
    sumX += pt.x;
    sumY += pt.y;
    sumXY += pt.x * pt.y;
    sumXX += pt.x * pt.x;
  }

  // Calculate slope (m) and intercept (b)
  const denominator = n * sumXX - sumX * sumX;
  if (denominator === 0) {
    return data.map((_, idx) => ({ index: idx, trend: points[0]?.y || 0 }));
  }

  const slope = (n * sumXY - sumX * sumY) / denominator;
  const intercept = (sumY - slope * sumX) / n;

  return data.map((_, idx) => ({
    index: idx,
    trend: Number((slope * idx + intercept).toFixed(2)),
  }));
}

/**
 * Parses standard CSV text content into a column-row array dataset format
 */
export function parseCSV(csvText: string): { columns: string[]; numericColumns: string[]; data: Record<string, any>[] } {
  const lines = csvText.split(/\r?\n/).filter(line => line.trim() !== '');
  if (lines.length === 0) {
    throw new Error('CSV is empty');
  }

  // Handle headers
  const headers = parseCSVLine(lines[0]).map(h => h.trim().replace(/^["']|["']$/g, ''));
  const rows: Record<string, any>[] = [];

  for (let i = 1; i < lines.length; i++) {
    const cells = parseCSVLine(lines[i]);
    if (cells.length === 0 || (cells.length === 1 && cells[0] === '')) continue;

    const row: Record<string, any> = {};
    headers.forEach((header, index) => {
      const cellVal = cells[index] !== undefined ? cells[index].trim().replace(/^["']|["']$/g, '') : '';
      
      // Attempt numeric conversion
      if (cellVal === '') {
        row[header] = null;
      } else if (!isNaN(Number(cellVal))) {
        row[header] = Number(cellVal);
      } else {
        row[header] = cellVal;
      }
    });
    rows.push(row);
  }

  // Identify which columns are consistently numeric
  const numericColumns: string[] = [];
  headers.forEach(header => {
    let hasNumeric = false;
    let allNumeric = true;

    for (const r of rows) {
      const val = r[header];
      if (val !== null && val !== undefined && val !== '') {
        if (typeof val === 'number') {
          hasNumeric = true;
        } else {
          allNumeric = false;
        }
      }
    }

    if (hasNumeric && allNumeric) {
      numericColumns.push(header);
    }
  });

  return {
    columns: headers,
    numericColumns,
    data: rows,
  };
}

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let currentCell = '';
  let insideQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      insideQuotes = !insideQuotes;
    } else if (char === ',' && !insideQuotes) {
      result.push(currentCell);
      currentCell = '';
    } else {
      currentCell += char;
    }
  }
  result.push(currentCell);
  return result;
}
