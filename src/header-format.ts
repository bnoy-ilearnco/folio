import type {DocNode} from './model';
import {cssQuoted} from './language';

// Chromium margin boxes accept text formatting, but not a rich DOM fragment.
// Carry the leading header style into PDF/print instead of resetting it to 9pt.
export function headerPrintStyle(doc:DocNode|undefined):string{
 if(!doc)return '';
 const p=doc.content?.[0];let first:DocNode|undefined;
 function walk(n:DocNode){if(!first&&n.type==='text')first=n;for(const child of n.content??[])walk(child);}
 walk(doc);const marks=first?.marks??[];const text=marks.find(m=>m.type==='textStyle')?.attrs??{};
 const family=text.fontFamily??p?.attrs?.paragraphFontFamily;const size=parseFloat(text.fontSize)||Number(p?.attrs?.paragraphFontSize)||9;
 return `font-size:${size}pt;color:${/^#[0-9a-f]{6}$/i.test(text.color??'')?text.color:'#17212b'};${family?`font-family:${cssQuoted(family)};`:''}${marks.some(m=>m.type==='bold')?'font-weight:bold;':''}${marks.some(m=>m.type==='italic')?'font-style:italic;':''}${marks.some(m=>m.type==='underline')?'text-decoration:underline;':''}`;
}
