import JSZip from 'jszip';
export const escapeXml = (v: unknown) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]!));
export const elements = (e: Element | Document, local: string): Element[] => Array.from(e.getElementsByTagNameNS('*', local));
export const child = (e: Element | undefined | null, local: string): Element | undefined => e ? Array.from(e.children).find(n => n.localName === local) : undefined;
export const children = (e: Element, local?: string): Element[] => Array.from(e.children).filter(n => !local || n.localName === local);
export const attr = (e: Element | undefined | null, name: string): string => e ? (Array.from(e.attributes).find(a => a.localName === name)?.value ?? '') : '';
export function parseXml(s: string) { if (/<!DOCTYPE|<!ENTITY/i.test(s)) throw Error('Document contains unsupported XML declarations.'); const doc = new DOMParser().parseFromString(s, 'application/xml'); if (doc.getElementsByTagName('parsererror').length) throw Error('Document XML is damaged.'); return doc; }
export async function openZip(bytes: Uint8Array): Promise<JSZip> {
  if (bytes.length > 30 * 1024 * 1024) throw Error('This version opens documents up to 30 MB.');
  const zip = await JSZip.loadAsync(bytes);
  const entries = Object.values(zip.files);
  if (entries.length > 2000) throw Error('Document contains too many package entries.');
  let total = 0;
  for (const entry of entries) {
    const size = (entry as unknown as {_data?:{uncompressedSize:number}})._data?.uncompressedSize ?? 0;
    total += size;
    if (size > 30 * 1024 * 1024 || total > 100 * 1024 * 1024) throw Error('Expanded document exceeds the 100 MB limit.');
  }
  return zip;
}
export async function zipXml(zip: JSZip, path: string): Promise<Document> { const entry=zip.file(path); if (!entry) throw Error(`Missing ${path}; this is not a supported document.`); return parseXml(await entry.async('string')); }
export const safeLink = (url: string) => /^(https?:|mailto:|#)/i.test(url) ? url : '';
export const lengthMm = (v: string, fallback = 0) => { const n=parseFloat(v); if (!Number.isFinite(n)) return fallback; return v.endsWith('in') ? n*25.4 : v.endsWith('cm') ? n*10 : v.endsWith('pt') ? n*25.4/72 : n; };
export const lengthPt = (v: string, fallback = 0) => v.endsWith('pt')&&Number.isFinite(parseFloat(v))?parseFloat(v):Math.round(lengthMm(v, fallback*25.4/72)*72/25.4*10000)/10000;
