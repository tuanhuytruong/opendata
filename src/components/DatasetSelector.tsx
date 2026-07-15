import React, { useState, useRef } from 'react';
import { Database, Upload, AlertCircle, CheckCircle2, RefreshCw, FileText } from 'lucide-react';
import { Dataset } from '../types';
import { defaultDatasets } from '../data/defaultDatasets';
import { parseCSV } from '../utils/dataAnalysis';

interface DatasetSelectorProps {
  activeDataset: Dataset;
  onSelectDataset: (dataset: Dataset) => void;
  onUploadDataset: (dataset: Dataset) => void;
}

export default function DatasetSelector({
  activeDataset,
  onSelectDataset,
  onUploadDataset
}: DatasetSelectorProps) {
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const processFile = (file: File) => {
    if (!file.name.endsWith('.csv')) {
      setError('Invalid file type. Please upload a standard comma-separated .csv file.');
      setSuccess(null);
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        if (!text) throw new Error('Could not read file content');
        
        const parsed = parseCSV(text);
        if (parsed.columns.length < 2) {
          throw new Error('Dataset must contain at least 2 columns (e.g., an X-axis label and a Y-axis metric).');
        }
        if (parsed.data.length === 0) {
          throw new Error('Dataset does not contain any valid rows.');
        }

        const uploadedDataset: Dataset = {
          id: `custom-${Date.now()}`,
          name: file.name.replace('.csv', ''),
          description: `Custom uploaded file containing ${parsed.data.length} records across ${parsed.columns.length} attributes.`,
          category: 'Uploaded Dataset',
          columns: parsed.columns,
          numericColumns: parsed.numericColumns,
          data: parsed.data
        };

        onUploadDataset(uploadedDataset);
        setSuccess(`Successfully loaded: ${file.name} (${parsed.data.length} rows, ${parsed.numericColumns.length} numerical metrics)`);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Error parsing CSV file. Ensure it is comma-delimited.');
        setSuccess(null);
      }
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Database className="w-5 h-5 text-indigo-600" />
          <h2 className="text-lg font-semibold font-display text-slate-800">Select Dataset</h2>
        </div>
        <span className="text-xs font-mono px-2.5 py-1 bg-slate-50 text-slate-500 rounded-full border border-slate-200">
          {activeDataset.category}
        </span>
      </div>

      <p className="text-sm text-slate-500 mb-6">
        Choose from our curated industry datasets to immediately inspect patterns, or upload your own tabular records.
      </p>

      {/* Preset Dataset Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        {defaultDatasets.map((ds) => {
          const isActive = ds.id === activeDataset.id;
          return (
            <button
              key={ds.id}
              onClick={() => {
                onSelectDataset(ds);
                setSuccess(null);
                setError(null);
              }}
              className={`text-left p-4 rounded-xl border transition-all relative overflow-hidden group ${
                isActive
                  ? 'border-indigo-600 bg-indigo-50/30 ring-1 ring-indigo-600/30'
                  : 'border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-semibold text-sm text-slate-800 font-display block group-hover:text-indigo-600 transition-colors">
                  {ds.name}
                </span>
                {isActive && (
                  <CheckCircle2 className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                )}
              </div>
              <span className="text-xs text-slate-500 line-clamp-2 mt-1.5 leading-relaxed">
                {ds.description}
              </span>
            </button>
          );
        })}
      </div>

      {/* Upload Box */}
      <div
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={triggerFileInput}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
          dragActive
            ? 'border-indigo-500 bg-indigo-50/20 scale-[0.99]'
            : 'border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-slate-300'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleChange}
          className="hidden"
        />
        <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <p className="text-sm font-medium text-slate-700">
          Drag & drop your CSV file here, or <span className="text-indigo-600 underline">browse</span>
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Supports standard comma-delimited tabular .csv records
        </p>
      </div>

      {/* Upload Feedback Messages */}
      {error && (
        <div className="flex items-start gap-2.5 p-3.5 bg-rose-50 border border-rose-100 text-rose-700 rounded-xl mt-4 text-xs leading-normal animate-fade-in">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="flex items-start gap-2.5 p-3.5 bg-emerald-50 border border-emerald-100 text-emerald-800 rounded-xl mt-4 text-xs leading-normal animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500 mt-0.5" />
          <span>{success}</span>
        </div>
      )}
    </div>
  );
}
