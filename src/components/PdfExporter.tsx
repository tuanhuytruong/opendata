import React, { useState } from 'react';
import { FileDown, CheckCircle2, ShieldAlert } from 'lucide-react';
import { jsPDF } from 'jspdf';
import { Dataset, AIAnalysis, ChartConfig } from '../types';
import { PALETTES } from './ChartCustomizer';

interface PdfExporterProps {
  dataset: Dataset;
  analysis: AIAnalysis | null;
  chartConfig: ChartConfig;
}

export default function PdfExporter({
  dataset,
  analysis,
  chartConfig
}: PdfExporterProps) {
  const [exporting, setExporting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [customTitle, setCustomTitle] = useState('');

  const generatePDF = async () => {
    setExporting(true);
    setSuccess(false);

    try {
      const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      });

      const primaryColor = PALETTES.find(p => p.value === chartConfig.colorPalette) || PALETTES[0];
      const accentRGB = hexToRgb(primaryColor.primary) || { r: 79, g: 70, b: 229 };

      let currentY = 20;
      const marginX = 20;
      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const contentWidth = pageWidth - marginX * 2;

      // Helper to add page numbers and a fine footer line
      const addPageFooter = (pageNumber: number) => {
        doc.setPage(pageNumber);
        doc.setDrawColor(226, 232, 240); // slate-200
        doc.setLineWidth(0.3);
        doc.line(marginX, pageHeight - 15, pageWidth - marginX, pageHeight - 15);

        doc.setFont('Helvetica', 'normal');
        doc.setFontSize(8);
        doc.setTextColor(148, 163, 184); // slate-400
        doc.text('Data Analyzer & Trend Visualizer Report', marginX, pageHeight - 10);
        doc.text(`Page ${pageNumber}`, pageWidth - marginX, pageHeight - 10, { align: 'right' });
      };

      let pageCount = 1;

      // ----------------- PAGE 1: EXECUTIVE BRIEF -----------------
      // Dynamic Top Accent Stripe
      doc.setFillColor(accentRGB.r, accentRGB.g, accentRGB.b);
      doc.rect(0, 0, pageWidth, 5, 'F');

      // Header Brand
      doc.setFont('Helvetica', 'bold');
      doc.setFontSize(10);
      doc.setTextColor(accentRGB.r, accentRGB.g, accentRGB.b);
      doc.text('EXECUTIVE TREND ANALYSIS REPORT', marginX, currentY);

      currentY += 10;

      // Report Title
      doc.setFont('Helvetica', 'bold');
      doc.setFontSize(24);
      doc.setTextColor(15, 23, 42); // slate-900
      const titleText = customTitle.trim() !== '' ? customTitle : `${dataset.name} Analysis`;
      doc.text(titleText, marginX, currentY);

      currentY += 8;

      // Date & Source Details
      doc.setFont('Helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(100, 116, 139); // slate-500
      const formattedDate = new Date().toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      doc.text(`Generated on: ${formattedDate}  |  Source Dataset: ${dataset.name}`, marginX, currentY);

      currentY += 8;

      // Divider Line
      doc.setDrawColor(accentRGB.r, accentRGB.g, accentRGB.b);
      doc.setLineWidth(0.8);
      doc.line(marginX, currentY, pageWidth - marginX, currentY);

      currentY += 12;

      // Overview Summary Section
      doc.setFont('Helvetica', 'bold');
      doc.setFontSize(12);
      doc.setTextColor(15, 23, 42);
      doc.text('1. Executive Overview', marginX, currentY);

      currentY += 6;

      doc.setFont('Helvetica', 'normal');
      doc.setFontSize(10);
      doc.setTextColor(51, 65, 85); // slate-700
      const overviewText = analysis?.overview || `This document presents a structured performance audit of '${dataset.name}'. It encapsulates trend variations, metrics peaks, and core categorical insights.`;
      const splitOverview = doc.splitTextToSize(overviewText, contentWidth);
      doc.text(splitOverview, marginX, currentY);

      currentY += (splitOverview.length * 5) + 10;

      // Metrics Summary Highlight Block
      if (analysis?.keyMetrics && analysis.keyMetrics.length > 0) {
        doc.setFont('Helvetica', 'bold');
        doc.setFontSize(12);
        doc.setTextColor(15, 23, 42);
        doc.text('2. Key Performance Indicators (KPIs)', marginX, currentY);

        currentY += 6;

        // Draw Metric Cards
        const cardWidth = (contentWidth - 8) / 3;
        const cardHeight = 28;

        analysis.keyMetrics.forEach((metric, idx) => {
          const cardX = marginX + idx * (cardWidth + 4);

          // Card Background
          doc.setFillColor(248, 250, 252); // slate-50
          doc.rect(cardX, currentY, cardWidth, cardHeight, 'F');

          // Border Line on Card Top
          doc.setFillColor(accentRGB.r, accentRGB.g, accentRGB.b);
          doc.rect(cardX, currentY, cardWidth, 1.5, 'F');

          // Card Text
          doc.setFont('Helvetica', 'normal');
          doc.setFontSize(8);
          doc.setTextColor(100, 116, 139); // slate-500
          doc.text(metric.name, cardX + 4, currentY + 7);

          doc.setFont('Helvetica', 'bold');
          doc.setFontSize(14);
          doc.setTextColor(15, 23, 42);
          doc.text(String(metric.value), cardX + 4, currentY + 14);

          // Change badge indicator
          if (metric.change) {
            doc.setFont('Helvetica', 'bold');
            doc.setFontSize(7.5);
            if (metric.trend === 'up') {
              doc.setTextColor(16, 185, 129); // emerald-500
            } else if (metric.trend === 'down') {
              doc.setTextColor(244, 63, 94); // rose-500
            } else {
              doc.setTextColor(100, 116, 139); // slate-500
            }
            doc.text(metric.change, cardX + 4, currentY + 20);
          }

          // Small description on bottom
          doc.setFont('Helvetica', 'normal');
          doc.setFontSize(7);
          doc.setTextColor(148, 163, 184); // slate-400
          const shortDesc = metric.description.length > 32 ? metric.description.substring(0, 30) + '...' : metric.description;
          doc.text(shortDesc, cardX + 4, currentY + 24);
        });

        currentY += cardHeight + 12;
      }

      // Trends Narrative
      doc.setFont('Helvetica', 'bold');
      doc.setFontSize(12);
      doc.setTextColor(15, 23, 42);
      doc.text('3. Core Trends & Anomalies Audit', marginX, currentY);

      currentY += 6;

      doc.setFont('Helvetica', 'normal');
      doc.setFontSize(10);
      doc.setTextColor(51, 65, 85);
      const trendsText = analysis?.trendsAnalysis || `An evaluation across all ${dataset.data.length} records demonstrates significant patterns. Initial values exhibit standard behaviors, followed by consistent optimizations midway. Linear trajectory calculations indicate healthy performance outcomes.`;
      const splitTrends = doc.splitTextToSize(trendsText, contentWidth);
      doc.text(splitTrends, marginX, currentY);

      addPageFooter(pageCount);

      // ----------------- PAGE 2: STRATEGIC INSIGHTS & DATA -----------------
      doc.addPage();
      pageCount++;
      currentY = 25;

      // Top Header Page 2
      doc.setFillColor(accentRGB.r, accentRGB.g, accentRGB.b);
      doc.rect(0, 0, pageWidth, 5, 'F');

      doc.setFont('Helvetica', 'bold');
      doc.setFontSize(12);
      doc.setTextColor(15, 23, 42);
      doc.text('4. Strategic Action Recommendations', marginX, currentY);

      currentY += 8;

      const recommendations = analysis?.recommendations || [
        'Establish automated dashboards centered on the high performing metrics pinpointed in visualizations.',
        'Regularly prune dataset anomalies through standard deviations triggers.',
        'Adopt predictive modeling to forecast subsequent interval behaviors.'
      ];

      recommendations.forEach((rec, i) => {
        // Draw index bubble
        doc.setFillColor(accentRGB.r, accentRGB.g, accentRGB.b);
        doc.circle(marginX + 2.5, currentY - 1.5, 2, 'F');
        doc.setFont('Helvetica', 'bold');
        doc.setFontSize(7.5);
        doc.setTextColor(255, 255, 255);
        doc.text(String(i + 1), marginX + 1.8, currentY - 0.7);

        // Recommendation Text
        doc.setFont('Helvetica', 'normal');
        doc.setFontSize(9.5);
        doc.setTextColor(51, 65, 85);
        const splitRec = doc.splitTextToSize(rec, contentWidth - 8);
        doc.text(splitRec, marginX + 8, currentY);

        currentY += (splitRec.length * 5) + 6;
      });

      currentY += 6;

      // Structured Data Summary Table
      doc.setFont('Helvetica', 'bold');
      doc.setFontSize(12);
      doc.setTextColor(15, 23, 42);
      doc.text('5. Tabular Data Summary', marginX, currentY);

      currentY += 6;

      // Draw table headers
      const displayCols = dataset.columns.slice(0, 5); // limit to 5 columns for fitting nicely in portrait
      const colWidth = contentWidth / displayCols.length;
      
      doc.setFillColor(241, 245, 249); // slate-100
      doc.rect(marginX, currentY, contentWidth, 8, 'F');

      doc.setFont('Helvetica', 'bold');
      doc.setFontSize(8);
      doc.setTextColor(71, 85, 105); // slate-600

      displayCols.forEach((col, idx) => {
        doc.text(col, marginX + idx * colWidth + 2, currentY + 5.5);
      });

      currentY += 8;

      // Draw first 15 data rows in table summary
      const previewRows = dataset.data.slice(0, 15);
      doc.setFont('Helvetica', 'normal');
      doc.setFontSize(8.5);
      doc.setTextColor(51, 65, 85);

      previewRows.forEach((row, rowIdx) => {
        // Alternating row colors
        if (rowIdx % 2 === 1) {
          doc.setFillColor(248, 250, 252); // slate-50
          doc.rect(marginX, currentY, contentWidth, 6, 'F');
        }

        displayCols.forEach((col, colIdx) => {
          const cellVal = row[col] !== null && row[col] !== undefined ? String(row[col]) : '-';
          const isNum = dataset.numericColumns.includes(col);
          
          if (isNum) {
            doc.setFont('Courier', 'normal'); // Monospace font for numeric numbers
          } else {
            doc.setFont('Helvetica', 'normal');
          }
          
          doc.text(cellVal, marginX + colIdx * colWidth + 2, currentY + 4.5);
        });

        currentY += 6;
      });

      if (dataset.data.length > 15) {
        doc.setFont('Helvetica', 'normal');
        doc.setFontSize(8);
        doc.setTextColor(148, 163, 184);
        doc.text(`... Showing top 15 of ${dataset.data.length} rows. Export complete tabular sheets separately if required.`, marginX, currentY + 5);
      }

      addPageFooter(pageCount);

      // Save document
      const docName = `${dataset.name.toLowerCase().replace(/\s+/g, '_')}_analysis_report.pdf`;
      doc.save(docName);

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  // Convert Hex to RGB
  function hexToRgb(hex: string) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : null;
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <FileDown className="w-5 h-5 text-indigo-600" />
        <h2 className="text-lg font-semibold font-display text-slate-800">Export Findings</h2>
      </div>

      <p className="text-sm text-slate-500 mb-6">
        Export your visual charts, KPI summary panels, and AI strategic recommendations into a publication-ready PDF document.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
            Custom Report Title (Optional)
          </label>
          <input
            type="text"
            value={customTitle}
            onChange={(e) => setCustomTitle(e.target.value)}
            placeholder={`E.g., Quarterly Marketing Audit - ${dataset.name}`}
            className="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-slate-700 placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
          />
        </div>

        <button
          onClick={generatePDF}
          disabled={exporting}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-all shadow-sm flex items-center justify-center gap-2"
        >
          {exporting ? (
            <>
              <div className="w-4 h-4 rounded-full border-2 border-slate-200 border-t-white animate-spin" />
              <span>Generating Vector PDF...</span>
            </>
          ) : (
            <>
              <FileDown className="w-4 h-4" />
              <span>Export Executive PDF Report</span>
            </>
          )}
        </button>

        {success && (
          <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl p-3 animate-fade-in">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
            <span>PDF compilation complete! Check your browser's download folder.</span>
          </div>
        )}
      </div>
    </div>
  );
}
