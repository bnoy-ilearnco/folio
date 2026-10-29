import type {DocNode} from './model';
import {cssQuoted} from './language';

// Davka's older faces encode Hebrew as Latin characters. Only the Unicode
// editions can render the Unicode text that Folio stores. Never copy the fonts.
export const DAVKA_UNICODE_FONTS:Record<string,string>={
  'Davka David':'UniDavka David',
  'Davka Rashi':'UniDavka Rashi',
  'Davka Stam':'UniDavka Stam',
};
export async function installedDavkaFonts():Promise<Record<string,string>>{
  if(typeof FontFace==='undefined')return {};
  const found:Record<string,string>={};
  await Promise.all(Object.entries(DAVKA_UNICODE_FONTS).map(async([source,family])=>{
    try{await new FontFace(family,`local(${cssQuoted(family)})`).load();found[source]=family;}catch{/* Use the bundled substitute. */}
  }));
  return found;
}

// CSS has no horizontal scaling for an ordinary, wrapping inline run. Match
// its total advance with tracking; retain the exact scale separately for files.
export async function prepareImportedFonts(root:DocNode):Promise<void>{
  const loads=new Set<string>();
  function collect(n:DocNode){for(const m of n.marks??[])if(m.type==='textStyle'&&m.attrs?.characterScale)loads.add(`${m.attrs.fontSize||'11pt'} ${cssQuoted(m.attrs.fontFamily||'Noto Serif Hebrew')}`);n.content?.forEach(collect);}
  collect(root);
  await Promise.all([...loads].map(font=>document.fonts.load(font,'שָׁלוֹם').catch(()=>[])));
  await document.fonts.ready;
  const canvas=document.createElement('canvas'),context=canvas.getContext('2d');
  if(!context)return;
  function visit(n:DocNode){
    for(const mark of n.marks??[]){
      const a=mark.attrs;
      if(mark.type!=='textStyle'||!a?.characterScale||!n.text)continue;
      const size=parseFloat(a.fontSize)||11;
      context!.font=`${n.marks?.some(m=>m.type==='italic')?'italic ':''}${n.marks?.some(m=>m.type==='bold')?'bold ':''}${size*96/72}px ${cssQuoted(a.fontFamily||'Noto Serif Hebrew')}`;
      const count=Array.from(n.text.replace(/[\p{M}\u200e\u200f]/gu,'')).length;
      a.scaleTracking=count?Math.round(context!.measureText(n.text).width*72/96*(Number(a.characterScale)/100-1)/count*10000)/10000:0;
    }
    n.content?.forEach(visit);
  }
  visit(root);
}
