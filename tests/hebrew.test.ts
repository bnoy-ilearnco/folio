import {describe,it,expect} from 'vitest';
import JSZip from 'jszip';
import {mkdirSync,writeFileSync} from 'node:fs';
import {blankDocument,textOf,type DocumentData} from '../src/model';
import {resolveDirection,resolvedAlignment} from '../src/language';
import {exportOdt,importOdt} from '../src/formats/odt';
import {exportDocx,importDocx} from '../src/formats/docx';
export function hebrewFixture():DocumentData {
  const d=blankDocument();d.title='כתיבה בעברית';d.page.header='מסמך בעברית';d.page.footer='טיוטה';d.page.pageNumbers=true;
  const p=(text:string,dir='rtl',language='he')=>({type:'paragraph',attrs:{dir,language,textAlign:'start',indent:5},content:[{type:'text',text,marks:[{type:'textStyle',attrs:{fontFamily:'Noto Sans Hebrew',fontSize:'14pt'}}]}]});
  d.content.content=[{type:'heading',attrs:{dir:'rtl',language:'he',level:1,textAlign:'start'},content:[{type:'text',text:'שלום עולם — מסמך בעברית'}]},p('שָׁלוֹם עוֹלָם! פגישה ביום 23/10/2026 בשעה 14:30.'),p('עברית עם English text ומספרים 123 (בדיקה).'),{type:'bulletList',attrs:{dir:'rtl'},content:[{type:'listItem',attrs:{dir:'rtl'},content:[p('פריט ראשון')]},{type:'listItem',attrs:{dir:'rtl'},content:[p('פריט שני')]}]},p('English paragraph with עברית and 123.','ltr','en')];return d;
}
describe('Hebrew language and direction',()=>{
  it('detects the first strong character without treating digits or niqqud as direction',()=>{expect(resolveDirection({type:'paragraph',content:[{type:'text',text:'123 — שָׁלוֹם English'}]})).toBe('rtl');expect(resolveDirection({type:'paragraph',content:[{type:'text',text:'English עם עברית'}]})).toBe('ltr');expect(resolveDirection({type:'paragraph',attrs:{dir:'rtl'},content:[{type:'text',text:'English first'}]})).toBe('rtl');expect(resolvedAlignment({attrs:{dir:'rtl',textAlign:'start'}})).toBe('right');});
  it('preserves Hebrew text, fonts, language, direction, and start indentation in ODT',async()=>{const d=hebrewFixture();const bytes=await exportOdt(d);const zip=await JSZip.loadAsync(bytes);const xml=await zip.file('content.xml')!.async('string');expect(xml).toContain('style:writing-mode="rl-tb"');expect(xml).toContain('style:font-name-complex=');expect(xml).toContain('style:language-complex="he"');const r=await importOdt(bytes);expect(textOf(r.document.content)).toBe(textOf(d.content));const p=r.document.content.content?.[1];expect(p?.attrs).toMatchObject({dir:'rtl',language:'he',textAlign:'right',indent:5});expect(r.document.content.content?.at(-1)?.attrs?.dir).toBe('ltr');mkdirSync('examples',{recursive:true});writeFileSync('examples/hebrew.odt',bytes);});
  it('writes DOCX bidi paragraphs, Hebrew runs, complex-script fonts, and language',async()=>{const d=hebrewFixture();const bytes=await exportDocx(d);const zip=await JSZip.loadAsync(bytes);const xml=await zip.file('word/document.xml')!.async('string');expect(xml).toContain('<w:bidi');expect(xml).toContain('<w:rtl');expect(xml).toContain('w:cs="Noto Sans Hebrew"');expect(xml).toContain('he-IL');const r=await importDocx(bytes);expect(textOf(r.document.content)).toContain('שָׁלוֹם עוֹלָם');expect(r.document.content.content?.[1].attrs).toMatchObject({dir:'rtl',language:'he',indent:expect.closeTo(5,1)});expect(r.document.content.content?.at(-1)?.attrs?.dir).toBe('ltr');writeFileSync('examples/hebrew.docx',bytes);});
});
