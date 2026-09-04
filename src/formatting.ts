import { ColumnKind } from './types';
import { Language } from './i18n';

const locale = (language: Language) => language === 'vi' ? 'vi-VN' : 'en-US';
export const formatNumber = (value: number, language: Language, compact = false) => new Intl.NumberFormat(locale(language), {
  notation: compact ? 'compact' : 'standard', maximumFractionDigits: compact ? 1 : 2,
}).format(Number(value));
/** One compact format contract for axes, labels, and chart tooltips. */
export const formatChartValue = (value: number, language: Language) => formatNumber(value, language, true);

export const formatDataCell = (value: unknown, kind: ColumnKind, language: Language) => {
  const text = String(value ?? '');
  if (kind === 'num') { const number = Number(text.replaceAll(',', '')); return Number.isFinite(number) ? formatNumber(number, language) : text; }
  if (kind === 'time') {
    const match = text.match(/^(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}:\d{2}))?$/);
    if (match) return match[2] && match[2] !== '00:00:00' ? `${match[1]} ${match[2]}` : match[1];
  }
  return text;
};
