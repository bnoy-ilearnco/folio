import {importDocx} from './docx';
import {FONTS,type DocNode} from '../model';
import {containsHebrew} from '../language';
import {installedDavkaFonts} from '../local-fonts';

export type DwdDiagnostics={warnings:string[];truncated:boolean;reader:string;counts:{main_paragraphs:number;tables:number}};
export function validateDwd(bytes:Uint8Array){
  if(bytes.byteLength>30*1024*1024)throw Error('This version opens files up to 30 MB.');
  if(bytes.length<4)throw Error('The DavkaWriter file is empty or damaged.');
  const version=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength).getUint32(0,true);
  if(!((version>=390&&version<=560)||version===0x7ab7))throw Error('This is not a supported DavkaWriter DWD document.');
}

// A fresh worker per import bounds memory use and discards the document and Python state.
export async function convertDwd(bytes:Uint8Array):Promise<{bytes:Uint8Array;diagnostics:DwdDiagnostics}>{
  validateDwd(bytes);
  const fonts=await installedDavkaFonts();
  return new Promise((resolve,reject)=>{
    const worker=new Worker(new URL(`${import.meta.env.BASE_URL}dwd/worker.js`,location.href));
    const finish=()=>{clearTimeout(timer);worker.terminate();};
    const timer=setTimeout(()=>{finish();reject(Error('DavkaWriter import took too long. The current document has been kept.'));},120_000);
    worker.onerror=()=>{finish();reject(Error('The local DavkaWriter reader could not start. Reopen Folio and try again.'));};
    worker.onmessage=({data})=>{finish();if(data.error)reject(Error(data.error));else resolve(data);};
    const copy=bytes.slice();worker.postMessage({bytes:copy,fonts},[copy.buffer]);
  });
}

export async function importDwd(bytes:Uint8Array){
  const converted=await convertDwd(bytes);
  const result=await importDocx(converted.bytes);
  const warnings=new Set(result.warnings.filter(w=>!w.startsWith('DOCX import supports')));
  let substituted=false;
  function fonts(n:DocNode){
    if(n.text)n.text=n.text.normalize("NFC");
    if(n.type==='paragraph'||n.type==='heading'){
      n.attrs??={};
      // Folio emits bidi only for RTL paragraphs; absence explicitly means LTR.
      if(n.attrs.dir==='auto')n.attrs.dir='ltr';
      if(n.attrs.dir==='rtl'){n.attrs.language='he';if(n.attrs.textAlign==='left')n.attrs.textAlign='right';else if(n.attrs.textAlign==='right')n.attrs.textAlign='left';}
    }
    for(const mark of n.marks??[])if(mark.type==='textStyle'&&mark.attrs?.fontFamily&&!FONTS.includes(mark.attrs.fontFamily)&&!/^UniDavka (David|Rashi|Stam)$/.test(mark.attrs.fontFamily)){
      mark.attrs.fontFamily=containsHebrew(n.text??'')?'Noto Serif Hebrew':'Noto Serif';substituted=true;
    }
    for(const child of n.content??[])fonts(child);
  }
  fonts(result.document.content);for(const kind of ['headerContent','footerContent'] as const)if(result.document.page[kind])fonts(result.document.page[kind]!);
  for(const warning of converted.diagnostics.warnings)warnings.add('DavkaWriter: '+warning);
  if(substituted)warnings.add('Fonts unavailable in Folio were replaced with bundled fonts.');
  warnings.add('DavkaWriter document imported. Review its layout; complex formatting may change. Save as ODT to keep the original DWD file unchanged.');
  return {...result,warnings:[...warnings]};
}
