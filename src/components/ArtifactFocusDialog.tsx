import { useEffect, useRef, useState } from 'react';
import { Maximize2, X } from 'lucide-react';

import { ChartResult, ChartRow } from '../types';
import { Language } from '../i18n';
import ValidatedChart from './ValidatedChart';

interface Props {
  title: string;
  chart?: ChartResult;
  rows: ChartRow[];
  insight: string;
  caveats: string[];
  language: Language;
}

export default function ArtifactFocusDialog({ title, chart, rows, insight, caveats, language }: Props) {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const close = () => setOpen(false);

  useEffect(() => {
    if (!open) return;
    closeButton.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
      if (event.key !== 'Tab') return;
      const dialog = document.querySelector<HTMLElement>('[data-artifact-focus-dialog]');
      const focusable = dialog ? [...dialog.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')].filter(element => !element.hasAttribute('disabled')) : [];
      if (!focusable.length) return;
      const first = focusable[0]; const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => { window.removeEventListener('keydown', onKeyDown); opener.current?.focus(); };
  }, [open]);

  return <><button ref={opener} type="button" onClick={() => setOpen(true)} className="artifact-focus-trigger"><Maximize2 className="w-3.5 h-3.5" />{language === 'vi' ? 'Tập trung' : 'Focus'}</button>{open && <div className="artifact-focus-backdrop" onMouseDown={event => { if (event.currentTarget === event.target) close(); }} role="presentation"><section data-artifact-focus-dialog role="dialog" aria-modal="true" aria-labelledby="artifact-focus-title" className="artifact-focus-dialog"><header><div><p className="section-eyebrow">{language === 'vi' ? 'Kết quả đã xác thực' : 'Validated result'}</p><h2 id="artifact-focus-title">{title}</h2></div><button ref={closeButton} type="button" className="artifact-focus-close" onClick={close} aria-label={language === 'vi' ? 'Đóng' : 'Close'}><X /></button></header>{insight && <p className="artifact-focus-insight">{insight}</p>}{chart ? <div className="artifact-focus-chart"><ValidatedChart result={chart} language={language} /></div> : <FocusTable rows={rows} language={language}/>} {caveats.map(caveat => <p className="artifact-focus-caveat" key={caveat}>{caveat}</p>)}</section></div>}</>;
}

function FocusTable({ rows, language }: { rows: ChartRow[]; language: Language }) {
  const secondary = rows.some(row => row.secondary_label);
  return <div className="artifact-focus-table"><table><thead><tr><th>{language === 'vi' ? 'Nhãn' : 'Label'}</th>{secondary && <th>{language === 'vi' ? 'Nhóm phụ' : 'Secondary group'}</th>}<th>{language === 'vi' ? 'Giá trị' : 'Value'}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.label}-${index}`}><td>{row.display_label ?? row.label}</td>{secondary && <td>{row.secondary_label ?? '—'}</td>}<td>{row.formatted_value ?? row.value.toLocaleString()}</td></tr>)}</tbody></table></div>;
}
