import {test,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {FONT_COLLECTION} from '../src/font-catalog';
import {blankDocument,textOf} from '../src/model';
import {exportOdt,importOdt} from '../src/formats/odt';
import {exportDocx,importDocx} from '../src/formats/docx';
test('collection binaries and original licenses match their pinned upstream files',()=>{
 const entries=JSON.parse(readFileSync('public/fonts/collection/manifest.json','utf8'));
 for(const item of entries)expect(createHash('sha256').update(readFileSync('public/fonts/collection/'+item.file)).digest('hex')).toBe(item.sha256);
 for(const font of FONT_COLLECTION)for(const file of font.files)expect(entries.some((e:any)=>'/fonts/collection/'+e.file===file.path)).toBe(true);
});
test('all collection family names and pointed Hebrew survive ODT and DOCX',async()=>{
 const d=blankDocument();d.content.content=FONT_COLLECTION.map(f=>({type:'paragraph',attrs:{dir:'rtl',language:'he'},content:[{type:'text',text:'שָׁלוֹם — Publishing 123',marks:[{type:'textStyle',attrs:{fontFamily:f.family,fontSize:'20pt'}}]}]}));
 for(const [save,open] of [[exportOdt,importOdt],[exportDocx,importDocx]] as const){const result=await open(await save(d));expect(textOf(result.document.content)).toBe(textOf(d.content));expect(JSON.stringify(result.document.content)).toEqual(expect.stringContaining('שָׁלוֹם'));for(const f of FONT_COLLECTION)expect(JSON.stringify(result.document.content)).toContain(f.family);}
});
