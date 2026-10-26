import type { JSONContent } from '@tiptap/core';
import type {BorderStyle} from './borders';
export type DocNode = JSONContent;
export type Page = { size: 'A4' | 'Letter'; orientation: 'portrait' | 'landscape'; top: number; right: number; bottom: number; left: number; header: string; footer: string; pageNumbers: boolean; border?:BorderStyle; borderColor?:string; headerContent?:DocNode; footerContent?:DocNode; headerDistance?:number; footerDistance?:number };
export type DocumentData = { version: 1; title: string; content: DocNode; page: Page };
export const defaultPage: Page = { size: 'A4', orientation: 'portrait', top: 25.4, right: 25.4, bottom: 25.4, left: 25.4, header: '', footer: '', pageNumbers: false,border:'none',borderColor:'#364a63' };
export const blankDocument = (): DocumentData => ({version:1,title:'Untitled',content:{type:'doc',content:[{type:'paragraph'}]},page:{...defaultPage}});
export const pageDimensions = (p: Page): [number, number] => { const d: [number,number] = p.size === 'A4' ? [210,297] : [215.9,279.4]; return p.orientation === 'landscape' ? [d[1],d[0]] : d; };
export const mmToTwip = (mm: number) => Math.round(mm / 25.4 * 1440);
export const mmToPt = (mm: number) => mm / 25.4 * 72;
export function textOf(n: DocNode): string { return n.text ?? (n.content ?? []).map(textOf).join(n.type === 'doc' ? '\n' : ''); }
export function validateDocument(value: unknown): value is DocumentData {
  const d = value as DocumentData;
  return !!d && d.version === 1 && typeof d.title === 'string' && d.content?.type === 'doc' && !!d.page && ['A4','Letter'].includes(d.page.size) && ['portrait','landscape'].includes(d.page.orientation) && ['top','right','bottom','left'].every(k => Number.isFinite(d.page[k as 'top']) && d.page[k as 'top'] >= 0 && d.page[k as 'top'] <= 100);
}
export const FONTS = ['Noto Serif', 'Noto Sans', 'Noto Sans Mono', 'Noto Sans Hebrew', 'Noto Serif Hebrew', 'David Libre', 'Taamey David CLM', 'Taamey Frank CLM', 'Noto Rashi Hebrew', 'Heebo', 'Times New Roman', 'Arial', 'Arial Narrow', 'Rockwell', 'Poor Richard', 'Harrington'];
