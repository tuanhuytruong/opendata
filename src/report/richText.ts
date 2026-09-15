import type { RichTextAlign, RichTextDocument, RichTextNode, RichTextSize } from './model';

export type TextBlockKind = 'header' | 'text' | 'note';

export const richTextFromText = (text: string, level?: 1 | 2 | 3): RichTextDocument => ({
  type: 'doc',
  content: [{
    type: level ? 'heading' : 'paragraph',
    ...(level ? { attrs: { level, textAlign: 'left' as RichTextAlign } } : {}),
    content: text ? [{ type: 'text', text }] : [],
  }],
});

const inlineText = (node: RichTextNode): string => {
  if (!('content' in node)) return node.type === 'hardBreak' ? '\n' : '';
  return (node.content ?? []).map(child => child.type === 'text' ? child.text : inlineText(child as RichTextNode)).join('');
};

export const richTextPlainText = (document: RichTextDocument): string => document.content.map(inlineText).join('\n').trim();

export const richTextNodeText = (node: RichTextNode): string => inlineText(node);

export const updateRichTextText = (document: RichTextDocument, text: string, kind: TextBlockKind, level: 1 | 2 | 3 = 2): RichTextDocument => {
  const lines = text.split(/\r?\n/);
  return {
    type: 'doc',
    content: lines.map(line => ({
      type: kind === 'header' ? 'heading' as const : 'paragraph' as const,
      ...(kind === 'header' ? { attrs: { level, textAlign: 'left' as RichTextAlign } } : {}),
      content: line ? [{ type: 'text' as const, text: line }] : [],
    })),
  };
};

export const setDocumentAlignment = (document: RichTextDocument, alignment: RichTextAlign): RichTextDocument => ({
  ...document,
  content: document.content.map(node => 'content' in node && (node.type === 'paragraph' || node.type === 'heading')
    ? { ...node, attrs: { ...(node.attrs ?? {}), textAlign: alignment } }
    : node),
});

export const setDocumentHeading = (document: RichTextDocument, level: 1 | 2 | 3 | null): RichTextDocument => ({
  ...document,
  content: document.content.map(node => {
    if (!('content' in node) || (node.type !== 'paragraph' && node.type !== 'heading')) return node;
    if (level === null) return { type: 'paragraph' as const, attrs: { textAlign: node.attrs?.textAlign ?? 'left' }, content: node.content };
    return { type: 'heading' as const, attrs: { level, textAlign: node.attrs?.textAlign ?? 'left' }, content: node.content };
  }),
});

export const toggleInlineMark = (document: RichTextDocument, mark: 'bold' | 'italic' | 'underline' | 'fontSize', size?: RichTextSize): RichTextDocument => ({
  ...document,
  content: document.content.map(node => {
    if (!('content' in node) || (node.type !== 'paragraph' && node.type !== 'heading')) return node;
    return {
      ...node,
      content: (node.content ?? []).map(inline => {
        const marks = inline.marks ?? [];
        if (mark === 'fontSize') {
          if (!size) return inline;
          const withoutSize = marks.filter(item => item.type !== 'fontSize');
          return { ...inline, marks: [...withoutSize, { type: 'fontSize' as const, attrs: { size } }] };
        }
        const present = marks.some(item => item.type === mark);
        return { ...inline, marks: present ? marks.filter(item => item.type !== mark) : [...marks, { type: mark }] };
      }),
    };
  }),
});

export const toggleList = (document: RichTextDocument, listType: 'bulletList' | 'orderedList'): RichTextDocument => {
  const allParagraphs = document.content.every(node => 'content' in node && (node.type === 'paragraph' || node.type === 'heading'));
  if (!allParagraphs) return document;
  return { type: 'doc', content: [{ type: listType, content: document.content.map(node => ({ type: 'listItem' as const, content: [node] })) }] };
};
