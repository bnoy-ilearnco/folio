import type {DocNode} from './model';
export type TextDirection='auto'|'ltr'|'rtl';
export const HEBREW_FONTS=['Noto Sans Hebrew','Noto Serif Hebrew','David Libre','Noto Rashi Hebrew','Taamey David CLM','Taamey Frank CLM','Heebo'];
export const containsHebrew=(text:string)=>/[\u0590-\u05ff\ufb1d-\ufb4f]/u.test(text);
export function resolveDirection(node:DocNode):'ltr'|'rtl'{
  if(node.attrs?.dir==='rtl'||node.attrs?.dir==='ltr')return node.attrs.dir;
  const text=node.text??(node.content??[]).map(n=>n.text??plainText(n)).join('');
  const first=text.match(/\p{L}/u)?.[0]??'';
  return /[\u0590-\u08ff\ufb1d-\ufdff\ufe70-\ufeff]/u.test(first)?'rtl':'ltr';
}
function plainText(node:DocNode):string{return node.text??(node.content??[]).map(plainText).join('');}
export const resolvedAlignment=(node:DocNode)=>!node.attrs?.textAlign||node.attrs.textAlign==='start'?(resolveDirection(node)==='rtl'?'right':'left'):node.attrs.textAlign;
export function ensureListDirections(node:DocNode):void{for(const child of node.content??[])ensureListDirections(child);if(['bulletList','orderedList','listItem'].includes(node.type??'')){node.attrs={...node.attrs,dir:resolveDirection(node)};}}
export const cssQuoted=(text:string)=>'"'+text.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/[\r\n\f]/g,' ')+'"';
