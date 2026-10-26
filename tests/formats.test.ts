import {describe,it,expect} from 'vitest';
import JSZip from 'jszip';
import {blankDocument,textOf,type DocumentData} from '../src/model';
import {exportOdt,importOdt} from '../src/formats/odt';
import {exportDocx,importDocx} from '../src/formats/docx';
import {pdfDefinition} from '../src/formats/pdf';
import {openZip} from '../src/formats/xml';
import {writeFileSync,mkdirSync} from 'node:fs';
const text=(s:string)=>({type:'text',text:s});
function fixture():DocumentData{const d=blankDocument();d.title='A document worth keeping';d.page={...d.page,size:'Letter',orientation:'landscape',top:18,right:20,bottom:18,left:20,header:'Project notes',footer:'Draft',pageNumbers:true};d.content={type:'doc',content:[{type:'heading',attrs:{level:1,textAlign:'left'},content:[text('A document worth keeping')]},{type:'paragraph',attrs:{textAlign:'justify',lineHeight:1.5,spaceBefore:4,spaceAfter:12,indent:5,firstLine:3,keepWithNext:true},content:[{type:'text',text:'Thoughtful writing',marks:[{type:'bold'},{type:'italic'},{type:'textStyle',attrs:{fontFamily:'Noto Sans',fontSize:'14pt',color:'#205c9e'}}]},text(' starts with a little space.  Keep your ideas together.'),{type:'hardBreak'},text('A second line, with <tags> & special characters.')]},{type:'bulletList',content:[{type:'listItem',content:[{type:'paragraph',content:[text('Clear formatting')]}]},{type:'listItem',content:[{type:'paragraph',content:[text('Portable documents')]}]}]},{type:'table',content:[{type:'tableRow',content:[{type:'tableHeader',content:[{type:'paragraph',content:[text('Feature')]}]},{type:'tableHeader',content:[{type:'paragraph',content:[text('Status')]}]}]},{type:'tableRow',content:[{type:'tableCell',content:[{type:'paragraph',content:[text('ODT save')]}]},{type:'tableCell',content:[{type:'paragraph',content:[text('Ready to test')]}]}]}]},{type:'pageBreak'},{type:'paragraph',content:[text('A fresh page for the next idea.')]}]};return d;}
describe('ODT interchange',()=>{
  it('preserves ordered list starts, merged cells, header cells, and embedded images',async()=>{
    const d=blankDocument();const para=(s:string)=>({type:'paragraph',content:[text(s)]});
    d.content.content=[{type:'orderedList',attrs:{start:3},content:[{type:'listItem',content:[para('Third item')]},{type:'listItem',content:[para('Fourth item')]}]},{type:'table',content:[{type:'tableRow',content:[{type:'tableHeader',attrs:{colspan:2,rowspan:1},content:[para('Merged heading')]}]},{type:'tableRow',content:[{type:'tableCell',attrs:{colspan:1,rowspan:2},content:[para('Spans two rows')]},{type:'tableCell',content:[para('Right')]}]},{type:'tableRow',content:[{type:'tableCell',content:[para('Lower right')]}]}]},{type:'image',attrs:{src:'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=',width:32,height:32,alt:'One pixel'}}];
    const bytes=await exportOdt(d);const r=await importOdt(bytes);
    expect(r.document.content.content?.[0].attrs?.start).toBe(3);
    const table=r.document.content.content?.[1];expect(table?.content?.[0].content?.[0].type).toBe('tableHeader');expect(table?.content?.[0].content?.[0].attrs?.colspan).toBe(2);expect(table?.content?.[1].content?.[0].attrs?.rowspan).toBe(2);expect(r.document.content.content?.[2].attrs?.alt).toBe('One pixel');
    mkdirSync('examples',{recursive:true});writeFileSync('examples/advanced.odt',bytes);
  });
  it('creates a real ODT package and preserves content, text properties, and layout',async()=>{const original=fixture();const bytes=await exportOdt(original);const zip=await JSZip.loadAsync(bytes);expect(await zip.file('mimetype')!.async('string')).toBe('application/vnd.oasis.opendocument.text');expect(zip.file('META-INF/manifest.xml')).toBeTruthy();expect(new TextDecoder().decode(bytes.slice(30,38))).toBe('mimetype');expect(bytes[8]).toBe(0);const opened=await importOdt(bytes);expect(textOf(opened.document.content)).toBe(textOf(original.content));expect(opened.document.page).toEqual(original.page);expect(opened.document.title).toBe(original.title);expect(opened.document.content.content?.[1].attrs).toMatchObject({textAlign:'justify',spaceBefore:4,spaceAfter:12,indent:5,firstLine:3,keepWithNext:true});expect(opened.document.content.content?.[1].content?.[0].marks).toEqual(expect.arrayContaining([{type:'bold'},{type:'italic'},{type:'textStyle',attrs:{fontFamily:'Noto Sans',fontSize:'14pt',color:'#205c9e'}}]));expect(opened.document.content.content?.some(n=>n.type==='pageBreak')).toBe(true);expect(opened.warnings).toEqual([]);mkdirSync('examples',{recursive:true});writeFileSync('examples/example.odt',bytes);});
  it('rejects a damaged package and oversized input',async()=>{await expect(importOdt(new Uint8Array([1,2,3]))).rejects.toThrow();await expect(openZip(new Uint8Array(30*1024*1024+1))).rejects.toThrow('30 MB');});
  it('rejects XML entity declarations',async()=>{const z=new JSZip();z.file('content.xml','<!DOCTYPE x [<!ENTITY hack SYSTEM "file:///secret">]><x/>');await expect(importOdt(await z.generateAsync({type:'uint8array'}))).rejects.toThrow('XML declarations');});
  it('reports unsupported content rather than hiding conversion loss',async()=>{const z=new JSZip();z.file('content.xml','<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text><text:section><text:p>Retained</text:p></text:section></office:text></office:body></office:document-content>');const r=await importOdt(await z.generateAsync({type:'uint8array'}));expect(textOf(r.document.content)).toBe('Retained');expect(r.warnings.join()).toContain('Section');});
});
describe('DOCX interchange',()=>{
  it('round-trips structural page breaks without adding blank paragraphs',async()=>{
    const d=blankDocument();d.content.content=[{type:'paragraph',content:[text('שָׁלוֹם')]},{type:'paragraph'},{type:'pageBreak'},{type:'paragraph',content:[text('Second page')]}];
    const result=await importDocx(await exportDocx(d));
    expect(result.document.content.content?.map(n=>n.type)).toEqual(['paragraph','paragraph','pageBreak','paragraph']);
    expect(textOf(result.document.content)).toBe(textOf(d.content));
    // A genuine empty Word paragraph with pageBreakBefore must remain empty.
    const zip=await JSZip.loadAsync(await exportDocx(d));
    zip.file('word/document.xml',(await zip.file('word/document.xml')!.async('string')).replace(/<w:pStyle w:val="FolioPageBreak"\s*\/>/,''));
    const external=await importDocx(await zip.generateAsync({type:'uint8array'}));
    expect(external.document.content.content?.map(n=>n.type)).toEqual(['paragraph','paragraph','pageBreak','paragraph','paragraph']);
  });
  it('exports DOCX and reads text, tables, styles, and page settings',async()=>{const d=fixture();const bytes=await exportDocx(d);const z=await JSZip.loadAsync(bytes);expect(z.file('[Content_Types].xml')).toBeTruthy();expect(z.file('word/document.xml')).toBeTruthy();const r=await importDocx(bytes);expect(textOf(r.document.content)).toContain('Thoughtful writing');expect(textOf(r.document.content)).toContain('ODT save');expect(r.document.content.content?.some(n=>n.type==='table')).toBe(true);expect(r.document.page.size).toBe('Letter');expect(r.document.page.orientation).toBe('landscape');expect(r.document.page.top).toBeCloseTo(18,1);expect(r.document.page.header).toBe('Project notes');expect(r.document.page.pageNumbers).toBe(true);mkdirSync('examples',{recursive:true});writeFileSync('examples/example.docx',bytes);});
});
describe('PDF definition',()=>{it('uses document dimensions, margins, explicit page breaks, and footer fields',()=>{const d=fixture();const pdf=pdfDefinition(d);expect(pdf.pageSize.width).toBeCloseTo(792,0);expect(pdf.pageMargins[0]).toBeCloseTo(20*72/25.4);expect(pdf.content.some((n:any)=>n.pageBreak==='before')).toBe(true);expect(pdf.footer(3).text).toBe('Draft  ·  3');expect(pdf.content.some((n:any)=>n.table)).toBe(true);});});

