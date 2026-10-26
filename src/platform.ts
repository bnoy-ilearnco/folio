import { isTauri, invoke } from '@tauri-apps/api/core';
import type {Page} from './model';
export type FileResult={name:string;path:string;bytes:number[]};
export const desktop=isTauri();
export async function openNative():Promise<FileResult|null>{return invoke('open_document');}
export async function resetNative(){if(desktop)await invoke('reset_document');}
export async function saveBytes(bytes:Uint8Array,name:string,format:'odt'|'docx'|'pdf',saveAs=false):Promise<string|null>{
  if(desktop)return invoke('save_document',{bytes:Array.from(bytes),name,format,saveAs});
  const blob=new Blob([bytes as BlobPart],{type:format==='odt'?'application/vnd.oasis.opendocument.text':format==='docx'?'application/vnd.openxmlformats-officedocument.wordprocessingml.document':'application/pdf'});
  const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name+'.'+format;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);return name+'.'+format;
}
export async function printDocument(){if(desktop)await invoke('print_document');else window.print();}
export async function exportNativePdf(name:string,page:Page):Promise<string|null>{return invoke('export_pdf',{name,page});}
