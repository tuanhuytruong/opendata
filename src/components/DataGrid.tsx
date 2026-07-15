import React, { useState } from 'react';
import { Search, Plus, Trash2, Edit2, Check, X, ArrowUpDown, Filter, RotateCcw } from 'lucide-react';
import { Dataset } from '../types';

interface DataGridProps {
  dataset: Dataset;
  onUpdateData: (newData: Record<string, any>[]) => void;
  onResetDataset: () => void;
}

export default function DataGrid({
  dataset,
  onUpdateData,
  onResetDataset
}: DataGridProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterColumn, setFilterColumn] = useState('');
  const [filterCondition, setFilterCondition] = useState<'gt' | 'lt' | 'eq' | 'contains' | ''>('');
  const [filterValue, setFilterValue] = useState('');
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Editing state
  const [editingRowIndex, setEditingRowIndex] = useState<number | null>(null);
  const [editingData, setEditingData] = useState<Record<string, any>>({});

  // Add row input states
  const [newRowData, setNewRowData] = useState<Record<string, any>>({});
  const [showAddRow, setShowAddRow] = useState(false);

  // Sorting logic
  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  // Delete row
  const handleDeleteRow = (indexToDelete: number) => {
    const updated = dataset.data.filter((_, idx) => idx !== indexToDelete);
    onUpdateData(updated);
  };

  // Start cell/row editing
  const handleStartEdit = (row: Record<string, any>, idx: number) => {
    setEditingRowIndex(idx);
    setEditingData({ ...row });
  };

  // Save edited row
  const handleSaveEdit = (idx: number) => {
    const updated = [...dataset.data];
    updated[idx] = { ...editingData };
    onUpdateData(updated);
    setEditingRowIndex(null);
  };

  // Edit cell value change
  const handleEditCellChange = (column: string, val: string) => {
    const isNum = dataset.numericColumns.includes(column);
    setEditingData({
      ...editingData,
      [column]: isNum && val !== '' ? Number(val) : val
    });
  };

  // Add new row logic
  const handleAddRow = (e: React.FormEvent) => {
    e.preventDefault();
    const formattedRow: Record<string, any> = {};
    dataset.columns.forEach(col => {
      const val = newRowData[col] || '';
      const isNum = dataset.numericColumns.includes(col);
      formattedRow[col] = isNum && val !== '' ? Number(val) : (val === '' ? (isNum ? 0 : '') : val);
    });

    onUpdateData([...dataset.data, formattedRow]);
    setNewRowData({});
    setShowAddRow(false);
  };

  const handleNewRowCellChange = (column: string, val: string) => {
    setNewRowData({
      ...newRowData,
      [column]: val
    });
  };

  // Filtering & searching logic combined
  let filteredData = [...dataset.data].map((row, idx) => ({ ...row, _originalIndex: idx }));

  if (searchQuery.trim() !== '') {
    const query = searchQuery.toLowerCase();
    filteredData = filteredData.filter(row => {
      return dataset.columns.some(col => {
        const val = row[col];
        return val !== null && val !== undefined && String(val).toLowerCase().includes(query);
      });
    });
  }

  if (filterColumn && filterCondition && filterValue !== '') {
    const isNum = dataset.numericColumns.includes(filterColumn);
    const targetVal = isNum ? Number(filterValue) : filterValue.toLowerCase();

    filteredData = filteredData.filter(row => {
      const val = row[filterColumn];
      if (val === null || val === undefined) return false;

      if (isNum) {
        const numVal = Number(val);
        if (isNaN(numVal) || isNaN(targetVal as number)) return false;
        if (filterCondition === 'gt') return numVal > (targetVal as number);
        if (filterCondition === 'lt') return numVal < (targetVal as number);
        if (filterCondition === 'eq') return numVal === (targetVal as number);
      } else {
        const strVal = String(val).toLowerCase();
        if (filterCondition === 'contains') return strVal.includes(targetVal as string);
        if (filterCondition === 'eq') return strVal === (targetVal as string);
      }
      return true;
    });
  }

  if (sortColumn) {
    const isNum = dataset.numericColumns.includes(sortColumn);
    filteredData.sort((a, b) => {
      let valA = a[sortColumn];
      let valB = b[sortColumn];

      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;

      if (isNum) {
        return sortDirection === 'asc' ? Number(valA) - Number(valB) : Number(valB) - Number(valA);
      } else {
        return sortDirection === 'asc'
          ? String(valA).localeCompare(String(valB))
          : String(valB).localeCompare(String(valA));
      }
    });
  }

  const clearFilters = () => {
    setFilterColumn('');
    setFilterCondition('');
    setFilterValue('');
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-lg font-semibold font-display text-slate-800">Raw Data Grid</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Displaying {filteredData.length} of {dataset.data.length} records. Double click any row to edit values.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddRow(!showAddRow)}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition-all shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Row</span>
          </button>
          
          <button
            onClick={onResetDataset}
            className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl text-xs font-semibold transition-all"
            title="Reset dataset values to defaults"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Data</span>
          </button>
        </div>
      </div>

      {/* Searching & Advanced Filtering Panels */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mb-4">
        {/* Search */}
        <div className="md:col-span-5 relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search across any row attribute..."
            className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:bg-white transition-colors"
          />
        </div>

        {/* Filter Selection */}
        <div className="md:col-span-7 flex flex-wrap sm:flex-nowrap gap-2 items-center">
          <Filter className="w-4 h-4 text-slate-400 shrink-0" />
          
          <select
            value={filterColumn}
            onChange={(e) => {
              setFilterColumn(e.target.value);
              setFilterCondition('');
            }}
            className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-600 focus:outline-none focus:border-indigo-500"
          >
            <option value="">Choose Column</option>
            {dataset.columns.map(col => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>

          {filterColumn && (
            <select
              value={filterCondition}
              onChange={(e) => setFilterCondition(e.target.value as any)}
              className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-600 focus:outline-none"
            >
              <option value="">Condition</option>
              {dataset.numericColumns.includes(filterColumn) ? (
                <>
                  <option value="gt">Greater Than (&gt;)</option>
                  <option value="lt">Less Than (&lt;)</option>
                  <option value="eq">Equal To (=)</option>
                </>
              ) : (
                <>
                  <option value="contains">Contains text</option>
                  <option value="eq">Equals exact text</option>
                </>
              )}
            </select>
          )}

          {filterColumn && filterCondition && (
            <input
              type={dataset.numericColumns.includes(filterColumn) ? 'number' : 'text'}
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
              placeholder="Value"
              className="text-xs bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2 text-slate-600 focus:outline-none w-24"
            />
          )}

          {(filterColumn || filterValue) && (
            <button
              onClick={clearFilters}
              className="text-xs text-rose-600 hover:underline font-semibold"
            >
              Clear filter
            </button>
          )}
        </div>
      </div>

      {/* Add Row Drawer Form */}
      {showAddRow && (
        <form onSubmit={handleAddRow} className="bg-slate-50/50 border border-slate-100 rounded-2xl p-4 mb-4 animate-fade-in">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Add Custom Record</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-3">
            {dataset.columns.map(col => {
              const isNum = dataset.numericColumns.includes(col);
              return (
                <div key={col}>
                  <label className="block text-[11px] text-slate-400 font-medium truncate mb-1">{col}</label>
                  <input
                    type={isNum ? 'number' : 'text'}
                    step="any"
                    value={newRowData[col] || ''}
                    onChange={(e) => handleNewRowCellChange(col, e.target.value)}
                    placeholder={isNum ? 'Numeric' : 'Text'}
                    className="w-full text-xs bg-white border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:border-indigo-500"
                    required={col === dataset.columns[0]} // Require first column
                  />
                </div>
              );
            })}
            <div className="flex items-end gap-2 col-span-2 sm:col-span-1 mt-2 sm:mt-0">
              <button
                type="submit"
                className="flex-1 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition-all"
              >
                Insert
              </button>
              <button
                type="button"
                onClick={() => setShowAddRow(false)}
                className="px-3 py-1.5 border border-slate-250 hover:bg-slate-100 text-slate-500 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Core Table View */}
      <div className="overflow-x-auto border border-slate-200 rounded-xl">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {dataset.columns.map((col) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100/55 hover:text-slate-700 transition-colors"
                >
                  <div className="flex items-center gap-1">
                    <span>{col}</span>
                    <ArrowUpDown className="w-3 h-3 text-slate-400" />
                  </div>
                </th>
              ))}
              <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right w-24">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 text-sm">
            {filteredData.length === 0 ? (
              <tr>
                <td colSpan={dataset.columns.length + 1} className="px-4 py-8 text-center text-slate-400 text-xs">
                  No records matching search or filtering metrics.
                </td>
              </tr>
            ) : (
              filteredData.map((row, idx) => {
                const isEditing = editingRowIndex === row._originalIndex;

                return (
                  <tr
                    key={idx}
                    className="hover:bg-slate-50/50 transition-colors group"
                  >
                    {dataset.columns.map((col) => (
                      <td key={col} className="px-4 py-2.5 text-slate-700">
                        {isEditing ? (
                          <input
                            type={dataset.numericColumns.includes(col) ? 'number' : 'text'}
                            step="any"
                            value={editingData[col] !== undefined ? editingData[col] : ''}
                            onChange={(e) => handleEditCellChange(col, e.target.value)}
                            className="w-full text-xs bg-white border border-indigo-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 rounded px-1.5 py-0.5"
                          />
                        ) : (
                          <span className={dataset.numericColumns.includes(col) ? 'font-mono text-xs text-slate-600' : 'text-slate-800'}>
                            {row[col] !== null && row[col] !== undefined ? String(row[col]) : '-'}
                          </span>
                        )}
                      </td>
                    ))}

                    <td className="px-4 py-2 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {isEditing ? (
                          <>
                            <button
                              onClick={() => handleSaveEdit(row._originalIndex)}
                              className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
                              title="Save row"
                            >
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => setEditingRowIndex(null)}
                              className="p-1 text-rose-500 hover:bg-rose-50 rounded"
                              title="Cancel edits"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => handleStartEdit(row, row._originalIndex)}
                              className="p-1 text-slate-400 hover:text-indigo-600 hover:bg-slate-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Edit record"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteRow(row._originalIndex)}
                              className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Delete record"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
