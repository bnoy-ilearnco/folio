import {it,expect} from 'vitest';
import {validateDwd} from '../src/formats/dwd';
import {importDocx} from '../src/formats/docx';
import {textOf} from '../src/model';
import JSZip from 'jszip';
import {exportDocx} from '../src/formats/docx';
import {exportOdt,importOdt} from '../src/formats/odt';
import {headerPrintStyle} from '../src/header-format';
import {blankDocument} from '../src/model';

it('validates the DWD signature and size before starting the engine',()=>{
 expect(()=>validateDwd(new Uint8Array())).toThrow('empty or damaged');
 expect(()=>validateDwd(new TextEncoder().encode('Not a DWD file'))).toThrow('not a supported');
 expect(()=>validateDwd(new Uint8Array(30*1024*1024+1))).toThrow('30 MB');
 expect(()=>validateDwd(new Uint8Array([38,2,0,0]))).not.toThrow();
 expect(()=>validateDwd(new Uint8Array([183,122,0,0]))).not.toThrow();
});

it('retains installed Unicode font names, horizontal scale, heading frames and right-anchored tables through save/reopen',async()=>{
 const doc=blankDocument();
 doc.page.border='double';doc.page.borderWidth=6;doc.page.borderInsets=[5,10,5,10];
 doc.content.content=[{type:'paragraph',attrs:{dir:'rtl',language:'he',paragraphBorders:['1.5pt double #123456','none','1pt solid #000000','none'],borderPadding:[1,0,2,0]},content:[{type:'text',text:'שָׁלוֹם',marks:[{type:'textStyle',attrs:{fontFamily:'UniDavka David',fontSize:'18pt',characterScale:87,characterSpacing:0.2}}]}]},
 {type:'table',attrs:{layoutWidth:491,tableAlign:'right'},content:[{type:'tableRow',content:[{type:'tableCell',content:[{type:'paragraph'}]}]}]}];
 for(const reopened of [(await importOdt(await exportOdt(doc))).document,(await importDocx(await exportDocx(doc))).document]){
  const p=reopened.content.content![0];const a=p.content![0].marks!.find(m=>m.type==='textStyle')!.attrs!;
  expect(a.fontFamily).toBe('UniDavka David');expect(a.fontSize).toBe('18pt');expect(a.characterScale).toBe(87);expect(a.characterSpacing).toBe(0.2);
  expect(p.attrs?.paragraphBorders).toEqual(doc.content.content![0].attrs!.paragraphBorders);expect(p.attrs?.borderPadding).toEqual([1,0,2,0]);
  expect(reopened.content.content![1].attrs?.tableAlign).toBe('right');
  expect(reopened.page.borderWidth).toBe(6);expect(reopened.page.borderInsets?.[0]).toBeCloseTo(5,0);expect(reopened.page.borderInsets?.[1]).toBeCloseTo(10,0);
 }
});

it('retains text boxes, note references and note bodies emitted by Folio',async()=>{
 const zip=new JSZip();
 zip.file('word/document.xml',`<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><w:body><w:p><w:r><w:t>מילה</w:t><w:footnoteReference w:id="1"/></w:r><w:r><w:drawing><wps:txbx><w:txbxContent><w:p><w:r><w:t>טקסט בתיבה</w:t></w:r></w:p></w:txbxContent></wps:txbx></w:drawing></w:r></w:p></w:body></w:document>`);
 zip.file('word/footnotes.xml',`<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote w:id="1"><w:p><w:r><w:footnoteRef/><w:t>הֶעָרָה</w:t></w:r></w:p></w:footnote></w:footnotes>`);
 const result=await importDocx(await zip.generateAsync({type:'uint8array'}));
 const text=textOf(result.document.content);expect(text).toContain('מילה[1]');expect(text).toContain('טקסט בתיבה');expect(text).toContain('הֶעָרָה');
 expect(result.warnings.join()).toContain('end of the document');expect(result.warnings.join()).toContain('Text boxes');
});

it('places RTL table cells in their visual order and keeps their widths',async()=>{
 const zip=new JSZip();
 zip.file('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl><w:tblPr><w:bidiVisual/></w:tblPr><w:tblGrid><w:gridCol w:w="1500"/><w:gridCol w:w="3000"/></w:tblGrid><w:tr><w:tc><w:p><w:r><w:t>Right</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Left</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>');
 const result=await importDocx(await zip.generateAsync({type:'uint8array'}));const cells=result.document.content.content![0].content![0].content!;
 expect(cells.map(textOf)).toEqual(['Left','Right']);expect(cells.map(c=>c.attrs?.colwidth)).toEqual([[200],[100]]);
});

it('preserves imported spacing, table appearance and rich headers in ODT and DOCX',async()=>{
 const zip=new JSZip();
 const ns='xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';
 zip.file('word/document.xml',`<w:document ${ns}><w:body><w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="6000"/><w:tblCellMar><w:top w:w="0"/><w:left w:w="60"/><w:bottom w:w="0"/><w:right w:w="60"/></w:tblCellMar></w:tblPr><w:tblGrid><w:gridCol w:w="6000"/></w:tblGrid><w:tr><w:trPr><w:trHeight w:val="700"/></w:trPr><w:tc><w:tcPr><w:shd w:fill="C0C0C0"/><w:tcBorders><w:top w:val="single" w:sz="8" w:color="000000"/><w:left w:val="nil"/></w:tcBorders></w:tcPr><w:p><w:pPr><w:spacing w:line="418" w:lineRule="exact"/><w:rPr><w:sz w:val="36"/></w:rPr></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Taamey David CLM"/><w:sz w:val="36"/></w:rPr><w:t>שָׁלוֹם</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:sectPr><w:headerReference r:id="h"/><w:pgBorders><w:top w:val="thickThinSmallGap" w:sz="16" w:color="000000"/></w:pgBorders></w:sectPr></w:body></w:document>`);
 zip.file('word/_rels/document.xml.rels','<Relationships><Relationship Id="h" Target="header1.xml"/></Relationships>');
 zip.file('word/header1.xml',`<w:hdr ${ns}><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="42"/><w:bdr w:val="single"/></w:rPr><w:t>כותרת</w:t></w:r></w:p></w:hdr>`);
 const original=(await importDocx(await zip.generateAsync({type:'uint8array'}))).document;
 for(const doc of [original,(await importOdt(await exportOdt(original))).document,(await importDocx(await exportDocx(original))).document]){
   const table=doc.content.content![0];const row=table.content![0],cell=row.content![0],paragraph=cell.content![0];
   expect(table.attrs?.layoutWidth).toBe(300);expect(cell.attrs?.colwidth).toEqual([400]);expect(row.attrs?.rowHeight).toBe(35);
   expect(cell.attrs?.cellPadding).toEqual([0,3,0,3]);expect(cell.attrs?.fillColor?.toUpperCase()).toBe('#C0C0C0');expect(cell.attrs?.cellBorders[0]).toBe('1pt solid #000000');
   expect(paragraph.attrs?.lineHeightPt).toBeCloseTo(20.9);expect(paragraph.attrs?.paragraphFontSize).toBe(18);
   expect(doc.page.border).toBe('double');expect(textOf(doc.page.headerContent!)).toBe('כותרת');
   const header=doc.page.headerContent!.content![0];expect(header.attrs?.textAlign).toBe('center');expect(header.content![0].marks?.some(m=>m.type==='bold')).toBe(true);expect(header.content![0].marks?.find(m=>m.type==='textStyle')?.attrs?.boxed).toBe(true);
 }
});

it('does not duplicate the cached page-number result when printing an imported footer',async()=>{
 const zip=new JSZip();const ns='xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';
 zip.file('word/document.xml',`<w:document ${ns}><w:body><w:p/><w:sectPr><w:footerReference r:id="f"/></w:sectPr></w:body></w:document>`);
 zip.file('word/_rels/document.xml.rels','<Relationships><Relationship Id="f" Target="footer.xml"/></Relationships>');
 zip.file('word/footer.xml',`<w:ftr ${ns}><w:p><w:r><w:t>Page </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>`);
 const result=await importDocx(await zip.generateAsync({type:'uint8array'}));expect(result.document.page.pageNumbers).toBe(true);expect(result.document.page.footer).toBe('Page');
 expect(headerPrintStyle({type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'כותרת',marks:[{type:'bold'},{type:'textStyle',attrs:{fontFamily:'Noto Rashi Hebrew',fontSize:'21pt'}}]}]}]})).toContain('font-size:21pt;');
});
