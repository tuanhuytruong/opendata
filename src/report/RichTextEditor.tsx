import { useEffect, useRef } from 'react';
import type { RichTextAlign, RichTextDocument, RichTextNode, RichTextSize } from './model';
import { richTextPlainText } from './richText';

export type RichTextEditorProps = {
  document: RichTextDocument;
  onChange: (next: RichTextDocument) => void;
  onBlur?: () => void;
  readOnly?: boolean;
  className?: string;
};

const escapeHtml = (value: string) => value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
const inlineHtml = (inline: { type: 'text'; text: string; marks?: Array<{ type: string; attrs?: { size?: string } }> }) => {
  let html = escapeHtml(inline.text).replace(/\n/g, '<br>');
  for (const mark of inline.marks ?? []) {
    if (mark.type === 'bold') html = `<strong>${html}</strong>`;
    if (mark.type === 'italic') html = `<em>${html}</em>`;
    if (mark.type === 'underline') html = `<u>${html}</u>`;
    if (mark.type === 'fontSize') html = `<span class="report-rich-size-${mark.attrs?.size ?? 'base'}">${html}</span>`;
  }
  return html;
};
const nodeHtml = (node: any): string => {
  if (node.type === 'hardBreak') return '<br>';
  if (node.type === 'text') return inlineHtml(node);
  const children = (node.content ?? []).map(nodeHtml).join('');
  if (node.type === 'heading') return `<h${node.attrs?.level ?? 2} style="text-align:${node.attrs?.textAlign ?? 'left'}">${children}</h${node.attrs?.level ?? 2}>`;
  if (node.type === 'paragraph') return `<p style="text-align:${node.attrs?.textAlign ?? 'left'}">${children || '<br>'}</p>`;
  if (node.type === 'bulletList') return `<ul>${children}</ul>`;
  if (node.type === 'orderedList') return `<ol>${children}</ol>`;
  if (node.type === 'listItem') return `<li>${children}</li>`;
  return '';
};
const richTextFromHtml = (html: string): RichTextDocument => {
  const parser = new DOMParser();
  const parsed = parser.parseFromString(`<div>${html}</div>`, 'text/html');
  const root = parsed.body.firstElementChild;
  if (!root) return { type: 'doc', content: [] };

  type Mark = { type: 'bold' | 'italic' | 'underline' } | { type: 'fontSize'; attrs: { size: RichTextSize } };
  const inlineNodes = (parent: Node, inherited: Mark[] = []): Array<{ type: 'text'; text: string; marks?: Mark[] }> => {
    const output: Array<{ type: 'text'; text: string; marks?: Mark[] }> = [];
    parent.childNodes.forEach(child => {
      if (child.nodeType === Node.TEXT_NODE) {
        const text = child.textContent ?? '';
        if (text) output.push({ type: 'text', text, ...(inherited.length ? { marks: inherited } : {}) });
        return;
      }
      if (!(child instanceof HTMLElement)) return;
      if (child.tagName === 'BR') {
        output.push({ type: 'text', text: '\n', ...(inherited.length ? { marks: inherited } : {}) });
        return;
      }
      const marks = [...inherited];
      if (child.tagName === 'STRONG' || child.tagName === 'B') marks.push({ type: 'bold' });
      if (child.tagName === 'EM' || child.tagName === 'I') marks.push({ type: 'italic' });
      if (child.tagName === 'U') marks.push({ type: 'underline' });
      const size = [...child.classList].find(value => value.startsWith('report-rich-size-'))?.slice('report-rich-size-'.length) as RichTextSize | undefined;
      if (size && ['sm', 'base', 'lg', 'xl'].includes(size)) marks.push({ type: 'fontSize', attrs: { size } });
      output.push(...inlineNodes(child, marks));
    });
    return output;
  };
  const blockNodes = (parent: Element): RichTextNode[] => {
    const output: RichTextNode[] = [];
    parent.childNodes.forEach(child => {
      if (!(child instanceof HTMLElement)) {
        if ((child.textContent ?? '').trim()) output.push({ type: 'paragraph', content: [{ type: 'text', text: child.textContent ?? '' }] });
        return;
      }
      const tag = child.tagName.toLowerCase();
      if (tag === 'p' || tag === 'h1' || tag === 'h2' || tag === 'h3') {
        const level = tag === 'p' ? undefined : Number(tag.slice(1)) as 1 | 2 | 3;
        const textAlign = ['left', 'center', 'right'].includes(child.style.textAlign) ? child.style.textAlign as 'left' | 'center' | 'right' : undefined;
        output.push({ type: level ? 'heading' : 'paragraph', ...(level || textAlign ? { attrs: { ...(level ? { level } : {}), ...(textAlign ? { textAlign } : {}) } } : {}), content: inlineNodes(child) });
        return;
      }
      if (tag === 'ul' || tag === 'ol') {
        output.push({ type: tag === 'ul' ? 'bulletList' : 'orderedList', content: [...child.children].filter(item => item.tagName.toLowerCase() === 'li').map(item => ({ type: 'listItem' as const, content: blockNodes(item) })) });
        return;
      }
      output.push(...blockNodes(child));
    });
    return output;
  };
  const content = blockNodes(root);
  return { type: 'doc', content: content.length ? content : [{ type: 'paragraph', content: inlineNodes(root) }] };
};

export default function RichTextEditor({ document, onChange, onBlur, readOnly = false, className = '' }: RichTextEditorProps) {
  const ref = useRef<HTMLDivElement>(null);
  const lastHtml = useRef('');
  useEffect(() => {
    const element = ref.current;
    if (!element || element === window.document.activeElement) return;
    const html = document.content.map(nodeHtml).join('');
    if (html !== lastHtml.current) {
      element.innerHTML = html;
      lastHtml.current = html;
    }
  }, [document]);
  return <div
    ref={ref}
    className={`report-rich-editor ${className}`}
    contentEditable={!readOnly}
    suppressContentEditableWarning
    role="textbox"
    aria-multiline="true"
    aria-label="Report text"
    onInput={event => {
      const html = event.currentTarget.innerHTML;
      lastHtml.current = html;
      onChange(richTextFromHtml(html));
    }}
    onBlur={onBlur}
  />;
}

export function RichTextToolbar({
  onCommand,
  disabled = false,
}: {
  onCommand: (command: 'bold' | 'italic' | 'underline' | 'bulletList' | 'orderedList' | 'heading' | 'paragraph' | RichTextAlign | RichTextSize) => void;
  disabled?: boolean;
}) {
  const buttons: Array<[string, Parameters<typeof onCommand>[0], string]> = [
    ['B', 'bold', 'Bold'], ['I', 'italic', 'Italic'], ['U', 'underline', 'Underline'],
    ['H', 'heading', 'Heading'], ['¶', 'paragraph', 'Paragraph'], ['•', 'bulletList', 'Bulleted list'], ['1.', 'orderedList', 'Numbered list'],
    ['L', 'left', 'Align left'], ['C', 'center', 'Align center'], ['R', 'right', 'Align right'],
    ['S', 'sm', 'Small text'], ['M', 'base', 'Base text'], ['L', 'lg', 'Large text'], ['XL', 'xl', 'Extra large text'],
  ];
  return <div className="report-rich-toolbar" role="toolbar" aria-label="Text formatting">
    {buttons.map(([label, command, title]) => <button type="button" key={`${command}-${title}`} title={title} aria-label={title} disabled={disabled} onMouseDown={event => event.preventDefault()} onClick={() => onCommand(command)}>{label}</button>)}
  </div>;
}

export function RichTextPreview({ document }: { document: RichTextDocument }) {
  return <RichTextNodes document={document} />;
}

function RichTextNodes({ document }: { document: RichTextDocument }) {
  return <div className="report-rich-preview" aria-label={richTextPlainText(document)}>{document.content.map((node, index) => <RichTextNodeView key={`${node.type}-${index}`} node={node} />)}</div>;
}

function RichTextNodeView({ node }: { node: RichTextNode }) {
  const raw = node as unknown as { type: string; text?: string; marks?: Array<{ type: string; attrs?: { size?: string } }>; attrs?: { textAlign?: 'left' | 'center' | 'right'; level?: 1 | 2 | 3 }; content?: RichTextNode[] };
  if (raw.type === 'hardBreak') return <br />;
  if (raw.type === 'text') return <span className={(raw.marks ?? []).map(mark => mark.type === 'fontSize' ? `report-rich-size-${mark.attrs?.size ?? 'base'}` : `report-mark-${mark.type}`).join(' ')}>{raw.text}</span>;
  const content = (raw.content ?? []).map((child, index) => <RichTextNodeView key={`${child.type}-${index}`} node={child} />);
  const style = raw.attrs?.textAlign ? { textAlign: raw.attrs.textAlign } as const : undefined;
  if (raw.type === 'heading') { const Tag = `h${raw.attrs?.level ?? 2}` as 'h1' | 'h2' | 'h3'; return <Tag style={style}>{content}</Tag>; }
  if (raw.type === 'paragraph') return <p style={style}>{content}</p>;
  if (raw.type === 'bulletList') return <ul>{content}</ul>;
  if (raw.type === 'orderedList') return <ol>{content}</ol>;
  return <li>{content}</li>;
}

export function richTextCommandLabel(command: string): string {
  return command === 'sm' || command === 'base' || command === 'lg' || command === 'xl' ? `font size ${command}` : command;
}