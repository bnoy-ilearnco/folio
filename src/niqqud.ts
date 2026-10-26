import type {Editor} from '@tiptap/core';
import {closeHistory} from '@tiptap/pm/history';
import {NIQQUD_MARKS,isNiqqud,isHebrewMark,stripNiqqud,units,withMark} from './niqqud-core';
export * from './niqqud-core';
export function applyManualMark(editor:Editor,mark:string){
 const {from,to,$from,$to}=editor.state.selection;if($from.parent!==$to.parent)throw Error('Select a single Hebrew letter.');
 const parent=$from.parent;const text=parent.textBetween(0,parent.content.size,'','\ufffc');
 const all=units(text);let unit=from===to?all.find(u=>u.start<$from.parentOffset&&u.end>=$from.parentOffset):all.find(u=>u.start===$from.parentOffset&&[u.start+u.base.length,u.end].includes($to.parentOffset));
 if(!unit||!/[א-ת]/u.test(unit.base))throw Error('Place the cursor after a Hebrew letter, or select one Hebrew letter.');
 const start=$from.start()+unit.start,end=$from.start()+unit.end;const updated=withMark(unit.base+unit.marks,mark);
 const marks=editor.state.doc.nodeAt(start)?.marks??[];editor.view.dispatch(closeHistory(editor.state.tr).replaceWith(start,end,editor.schema.text(updated,marks)));editor.view.dispatch(closeHistory(editor.state.tr));editor.commands.focus();
}
export function captureNiqqudRange(editor:Editor){
 let {from,to}=editor.state.selection;
 if(from===to){const {$from}=editor.state.selection;from=$from.start();to=$from.end();}
 // Include the whole Hebrew cluster if a selection cuts through its marks.
 while(from>1&&isHebrewMark(editor.state.doc.textBetween(from,from+1)))from--;
 while(to<editor.state.doc.content.size&&isHebrewMark(editor.state.doc.textBetween(to,to+1)))to++;
 let text='';const positions:(number|null)[]=[];let first=true;
 editor.state.doc.descendants((node,pos)=>{
   if(!node.isTextblock)return;
   const begin=Math.max(from,pos+1),end=Math.min(to,pos+1+node.content.size);if(begin>=end)return false;
   if(!first){text+='\n';positions.push(null);}first=false;
   node.descendants((part,offset)=>{
     const at=pos+1+offset;
     if(part.isText){const start=Math.max(0,begin-at),stop=Math.min(part.text!.length,end-at);if(start>=stop)return;for(let i=start;i<stop;i++){text+=part.text![i];positions.push(at+i);}}
     else if(part.type.name==='hardBreak'&&at>=begin&&at<end){text+='\n';positions.push(at);}
   });return false;
 });
 if(!/[א-ת]/u.test(text))throw Error('Select Hebrew text, or place the cursor in a Hebrew paragraph.');
 if(text.length>20000)throw Error('Select up to 20,000 characters at a time.');
 return {text,positions,document:editor.state.doc};
}
export function applyNiqqudChanges(editor:Editor,capture:ReturnType<typeof captureNiqqudRange>,result:string){
 if(!editor.state.doc.eq(capture.document))throw Error('The document changed. Select the text again.');
 if(stripNiqqud(capture.text)!==stripNiqqud(result))throw Error('The vowel edit changed source letters; it was not applied.');
 const before=units(capture.text),after=units(result);if(before.length!==after.length)throw Error('The vowel edit could not be aligned safely.');
 const tr=closeHistory(editor.state.tr);
 for(let i=before.length-1;i>=0;i--){const old=before[i],next=after[i];if(old.base!==next.base)throw Error('The vowel edit changed source letters.');if(!/[א-ת]/u.test(old.base)||old.marks===next.marks)continue;const start=capture.positions[old.start],end=capture.positions[old.end-1];if(start==null||end==null)throw Error('The vowel edit crosses a paragraph boundary.');tr.replaceWith(start,end+1,editor.schema.text(next.base+next.marks,editor.state.doc.nodeAt(start)?.marks??[]));}
 editor.view.dispatch(tr);editor.view.dispatch(closeHistory(editor.state.tr));editor.commands.focus();
}
