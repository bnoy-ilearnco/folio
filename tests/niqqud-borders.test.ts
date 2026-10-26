import {describe,it,expect} from 'vitest';
import {Editor} from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import {ParagraphLayout} from '../src/extensions';
import {NIQQUD_MARKS,withMark,stripNiqqud,applyNiqqudChanges,captureNiqqudRange} from '../src/niqqud';
import {blankDocument} from '../src/model';
import {BORDER_STYLES,borderSettings} from '../src/borders';
import {exportOdt,importOdt} from '../src/formats/odt';
import {exportDocx,importDocx} from '../src/formats/docx';
import {pdfDefinition} from '../src/formats/pdf';
import {mkdirSync,writeFileSync} from 'node:fs';

describe('Hebrew niqqud editing',()=>{
 it('supports every vowel and replaces vowel families without duplicating points',()=>{
   for(const [mark] of NIQQUD_MARKS){const letter=mark==='ׁ'||mark==='ׂ'?'ש':'א';expect(withMark(letter,mark)).toContain(mark);}
   expect(withMark('שָׁ','ַ')).toBe('שַׁ');expect(withMark('שַׁ','ׂ')).toBe('שַׂ');expect(withMark('שַׂ','')).toBe('ש');expect(()=>withMark('English','ָ')).toThrow();
 });
 it('keeps rich text and paragraph structure and rejects any consonant change',()=>{
   const editor=new Editor({extensions:[StarterKit,ParagraphLayout],content:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'שלום',marks:[{type:'bold'}]},{type:'text',text:' עולם'}]},{type:'paragraph',content:[{type:'text',text:'English 123'}]}]}});
   editor.commands.selectAll();const capture=captureNiqqudRange(editor);expect(capture.text).toBe('שלום עולם\nEnglish 123');
   expect(()=>applyNiqqudChanges(editor,capture,'אחר')).toThrow();applyNiqqudChanges(editor,capture,'שָׁלוֹם עוֹלָם\nEnglish 123');
   expect(stripNiqqud(editor.getText())).toBe('שלום עולם\n\nEnglish 123');expect(editor.getJSON().content?.[0].content?.[0].marks).toContainEqual({type:'bold'});expect(editor.getJSON().content).toHaveLength(2);editor.commands.undo();expect(editor.state.doc.eq(capture.document)).toBe(true);editor.destroy();
 });
});
describe('Page borders',()=>{
 it('round-trips all presets through ODT and DOCX without changing text margins',async()=>{
   for(const border of BORDER_STYLES){const document=blankDocument();document.page={...document.page,border,borderColor:'#2255aa',top:24,right:20,bottom:22,left:18};document.content.content=[{type:'paragraph',attrs:{language:'he',dir:'rtl'},content:[{type:'text',text:'שָׁלוֹם עוֹלָם'}]}];
     for(const [save,open] of [[exportOdt,importOdt],[exportDocx,importDocx]] as const){const result=await open(await save(document));expect(result.document.page.border).toBe(border);expect(result.document.page.borderColor).toBe(border==='none'?'#364a63':'#2255aa');for(const side of ['top','right','bottom','left'] as const)expect(result.document.page[side]).toBeCloseTo(document.page[side],1);}
     if(border==='double'){mkdirSync('examples',{recursive:true});writeFileSync('examples/borders.odt',await exportOdt(document));writeFileSync('examples/borders.docx',await exportDocx(document));}
   }
 });
 it('uses validated colors and draws PDF backgrounds for each border style',()=>{
   const document=blankDocument();document.page.border='double';document.page.borderColor='invalid';expect(borderSettings(document.page).color).toBe('#364a63');expect(pdfDefinition(document).background.canvas).toHaveLength(2);document.page.border='dashed';expect(pdfDefinition(document).background.canvas[0].dash).toEqual({length:5,space:3});
 });
});
