import type {Editor} from '@tiptap/core';
import {NIQQUD_MARKS,applyManualMark,captureNiqqudRange,applyNiqqudChanges,stripNiqqud} from './niqqud';

export function createNiqqudTools(editor:Editor,notify:(message:string)=>void){
 const panel=document.createElement('section');panel.className='niqqud-panel';panel.hidden=true;panel.setAttribute('aria-label','Hebrew vowel keyboard');
 const label=document.createElement('strong');label.textContent='Niqqud · ניקוד';panel.append(label);
 for(const [mark,name] of NIQQUD_MARKS){const button=document.createElement('button');button.type='button';button.textContent=(mark==='ׁ'||mark==='ׂ'?'ש':'א')+mark;button.lang='he';button.title=name;button.setAttribute('aria-label',`Add ${name}`);button.addEventListener('pointerdown',e=>e.preventDefault());button.addEventListener('click',()=>{try{applyManualMark(editor,mark);}catch(error){notify(String(error));}});panel.append(button);}
 const clear=document.createElement('button');clear.type='button';clear.textContent='Clear letter vowels';clear.addEventListener('pointerdown',e=>e.preventDefault());clear.addEventListener('click',()=>{try{applyManualMark(editor,'');}catch(error){notify(String(error));}});panel.append(clear);
 const help=document.createElement('span');help.textContent='Place the cursor after a letter or select it. Dagesh on ו gives shuruk.';panel.append(help);
 document.querySelector('.workspace')!.before(panel);
 return {
   toggle(){panel.hidden=!panel.hidden;return !panel.hidden;},
   remove(){try{const capture=captureNiqqudRange(editor);applyNiqqudChanges(editor,capture,stripNiqqud(capture.text));}catch(error){notify(String(error));}}
 };
}
