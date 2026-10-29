import JSZip from 'jszip';
import { blankDocument, pageDimensions, type DocNode, type DocumentData } from '../model';
import {ensureListDirections,resolveDirection,resolvedAlignment} from '../language';
import {borderSettings,parseBorder} from '../borders';
import { escapeXml as x, elements, child, children, attr, parseXml, openZip, zipXml, safeLink, lengthMm, lengthPt } from './xml';

const MIME='application/vnd.oasis.opendocument.text';
const ns='xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"';
export async function exportOdt(doc: DocumentData): Promise<Uint8Array> {
  const zip=new JSZip(); zip.file('mimetype',MIME,{compression:'STORE'});
  let tableIndex=0;
  const fontNames=new Map<string,string>();const fontId=(name:string)=>{if(!fontNames.has(name))fontNames.set(name,'Font'+fontNames.size);return fontNames.get(name)!;};fontId('Noto Serif Hebrew');
  const styles: string[]=[]; const styleNames=new Map<string,string>(); const assets: string[]=[];
  const style=(family:string, properties:string) => { const key=family+properties; if(styleNames.has(key))return styleNames.get(key)!; const name='F'+(styles.length+1); styleNames.set(key,name); styles.push(`<style:style style:name="${name}" style:family="${family}"${family==='paragraph'?' style:master-page-name="Standard"':''}>${properties}</style:style>`); return name; };
  function render(n:DocNode):string {
    const a=n.attrs??{}; const nested=()=> (n.content??[]).map(render).join('');
    if(n.type==='text') {
      let props=''; let href='';
      for(const m of n.marks??[]) { const ma=m.attrs??{};
        if(m.type==='bold')props+=' fo:font-weight="bold" style:font-weight-complex="bold"';
        if(m.type==='italic')props+=' fo:font-style="italic" style:font-style-complex="italic"';
        if(m.type==='underline')props+=' style:text-underline-style="solid"';
        if(m.type==='strike')props+=' style:text-line-through-style="solid"';
        if(m.type==='subscript'||m.type==='superscript')props+=` style:text-position="${m.type==='subscript'?'sub':'super'} 58%"`;
        if(m.type==='highlight')props+=` fo:background-color="${x(ma.color??'#fff0a3')}"`;
        if(m.type==='link')href=safeLink(ma.href??'');
        if(m.type==='textStyle') { if(ma.fontFamily)props+=` fo:font-family="${x(ma.fontFamily)}" style:font-name-complex="${fontId(ma.fontFamily)}"`; if(ma.fontSize)props+=` fo:font-size="${x(ma.fontSize)}" style:font-size-complex="${x(ma.fontSize)}"`; if(ma.color)props+=` fo:color="${x(ma.color)}"`;if(ma.boxed)props+=` fo:border="0.75pt solid #000000"`;if(ma.characterScale)props+=` style:text-scale="${Number(ma.characterScale)}%"`;if(ma.characterSpacing)props+=` fo:letter-spacing="${Number(ma.characterSpacing)}pt"`; }
      }
      const value=x(n.text).replace(/ {2,}/g, spaces=>`<text:s text:c="${spaces.length}"/>`).replace(/\t/g,'<text:tab/>').replace(/\n/g,'<text:line-break/>');
      const span=props?`<text:span text:style-name="${style('text',`<style:text-properties${props}/>`)}">${value}</text:span>`:value;
      return href?`<text:a xlink:href="${x(href)}" xlink:type="simple">${span}</text:a>`:span;
    }
    if(n.type==='paragraph'||n.type==='heading') {
      const rtl=resolveDirection(n)==='rtl';
      let p=` style:writing-mode="${rtl?'rl-tb':'lr-tb'}" fo:text-align="${x(resolvedAlignment(n))}" fo:line-height="${a.lineHeightPt?Number(a.lineHeightPt)+'pt':Math.round(Number(a.lineHeight??1.5)*100)+'%'}" fo:margin-top="${Number(a.spaceBefore??0)}pt" fo:margin-bottom="${Number(a.spaceAfter??8)}pt" fo:margin-${rtl?'right':'left'}="${Number(a.indent??0)}mm" fo:text-indent="${Number(a.firstLine??0)}mm"`;
      if(a.minLineHeightPt&&!a.lineHeightPt)p+=` style:line-height-at-least="${Number(a.minLineHeightPt)}pt"`;if(a.endIndent)p+=` fo:margin-${rtl?'left':'right'}="${Number(a.endIndent)}mm"`;
      if(Array.isArray(a.paragraphBorders))for(const [i,side] of ['top','right','bottom','left'].entries()){p+=` fo:border-${side}="${x(a.paragraphBorders[i])}"`;if(a.borderPadding)p+=` fo:padding-${side}="${Number(a.borderPadding[i])}pt"`;}
      if(a.keepWithNext)p+=' fo:keep-with-next="always"';
      const t=(n.type==='heading'?` fo:font-size="${[0,28,21,16,14,12,11][a.level??1]}pt" fo:font-weight="bold"`:'')+(a.language==='he'?` fo:font-family="Noto Sans Hebrew" style:font-name-complex="${fontId('Noto Sans Hebrew')}" fo:language="he" fo:country="IL" style:language-complex="he" style:country-complex="IL"`:a.language==='en'?' fo:language="en" fo:country="US"':'');
      const base=(a.paragraphFontFamily?` fo:font-family="${x(a.paragraphFontFamily)}" style:font-name-complex="${fontId(a.paragraphFontFamily)}"`:'')+(a.paragraphFontSize?` fo:font-size="${Number(a.paragraphFontSize)}pt" style:font-size-complex="${Number(a.paragraphFontSize)}pt"`:'');
      let combined=t;if(a.paragraphFontFamily)combined=combined.replace(/ fo:font-family="[^"]*"| style:font-name-complex="[^"]*"/g,'');if(a.paragraphFontSize)combined=combined.replace(/ fo:font-size="[^"]*"| style:font-size-complex="[^"]*"/g,'');
      const name=style('paragraph',`<style:paragraph-properties${p}/><style:text-properties${combined+base}/>`);
      const tag=n.type==='heading'?'h':'p'; return `<text:${tag} text:style-name="${name}"${tag==='h'?` text:outline-level="${a.level??1}"`:''}>${nested()}</text:${tag}>`;
    }
    if(n.type==='hardBreak')return '<text:line-break/>';
    if(n.type==='pageBreak')return `<text:p text:style-name="PageBreak"/>`;
    if(n.type==='bulletList'||n.type==='orderedList')return `<text:list text:style-name="${n.type==='orderedList'?'Numbered':'Bullets'}">${(n.content??[]).map((item,index)=>`<text:list-item${n.type==='orderedList'&&index===0?` text:start-value="${Number(a.start??1)}"`:''}>${(item.content??[]).map(render).join('')}</text:list-item>`).join('')}</text:list>`;
    if(n.type==='listItem')return `<text:list-item>${nested()}</text:list-item>`;
    if(n.type==='table') {
      const rows=n.content??[];const columns=Math.max(1,...rows.map(row=>(row.content??[]).reduce((sum,c)=>sum+Number(c.attrs?.colspan??1),0)));
      const occupied:number[]=Array(columns).fill(0);
      const body=rows.map(row=>{let col=0;let cells='';for(const cell of row.content??[]){while(occupied[col]>0){cells+='<table:covered-table-cell/>';occupied[col]--;col++;}const span=Number(cell.attrs?.colspan??1),height=Number(cell.attrs?.rowspan??1);cells+=render(cell);for(let i=0;i<span;i++){occupied[col+i]=height-1;if(i>0)cells+='<table:covered-table-cell/>';}col+=span;}while(col<columns){if(occupied[col]>0){cells+='<table:covered-table-cell/>';occupied[col]--;}else cells+='<table:table-cell><text:p/></table:table-cell>';col++;}return `<table:table-row${row.attrs?.rowHeight?` table:style-name="${style('table-row',`<style:table-row-properties style:min-row-height="${Number(row.attrs.rowHeight)}pt"/>`)}"`:""}>${cells}</table:table-row>`;}).join('');
      const widths:number[]=[];for(const cell of rows[0]?.content??[])for(const width of cell.attrs?.colwidth??[])widths.push(Number(width)*0.75);
      const columnsXml=widths.length===columns?widths.map(width=>`<table:table-column table:style-name="${style('table-column',`<style:table-column-properties style:column-width="${width}pt"/>`)}"/>`).join(''):`<table:table-column table:number-columns-repeated="${columns}"/>`;
      const layout=a.layoutWidth?` table:style-name="${style('table',`<style:table-properties style:width="${Number(a.layoutWidth)}pt" table:align="${x(a.tableAlign||'left')}"/>`)}"`:'';
      return `<table:table table:name="Table${++tableIndex}"${layout}>${columnsXml}${body}</table:table>`;
    }
    if(n.type==='tableRow')return `<table:table-row>${nested()}</table:table-row>`;
    if(n.type==='tableCell'||n.type==='tableHeader'){
      let properties='';if(a.fillColor)properties+=` fo:background-color="${x(a.fillColor)}"`;if(a.verticalAlign)properties+=` style:vertical-align="${a.verticalAlign==='middle'?'middle':a.verticalAlign}"`;
      for(const [i,side] of ['top','right','bottom','left'].entries()){if(a.cellPadding)properties+=` fo:padding-${side}="${Number(a.cellPadding[i])}pt"`;if(a.cellBorders)properties+=` fo:border-${side}="${x(a.cellBorders[i])}"`;}
      const cellStyle=properties?style('table-cell',`<style:table-cell-properties${properties}/>`):n.type==='tableHeader'?'FolioHeader':'';
      return `<table:table-cell${cellStyle?` table:style-name="${cellStyle}"`:''} table:number-columns-spanned="${Number(a.colspan??1)}" table:number-rows-spanned="${Number(a.rowspan??1)}">${nested()}</table:table-cell>`;}
    if(n.type==='image' && /^data:image\/(png|jpeg);base64,/.test(a.src??'')) {
      const [,kind,data]=/^data:image\/(png|jpeg);base64,(.*)$/.exec(a.src)!;
      const path=`Pictures/image${assets.length+1}.${kind==='jpeg'?'jpg':'png'}`; zip.file(path,data,{base64:true});assets.push(path);
      return `<text:p><draw:frame text:anchor-type="as-char" svg:width="${Number(a.width??400)*25.4/96}mm" svg:height="${Number(a.height??250)*25.4/96}mm"><draw:image xlink:href="${path}" xlink:type="simple"/><svg:desc>${x(a.alt??'')}</svg:desc></draw:frame></text:p>`;
    }
    if(n.type==='horizontalRule')return '<text:p>────────────────</text:p>';
    return nested();
  }
  const body=render(doc.content);const richHeader=doc.page.headerContent?render(doc.page.headerContent):'';const richFooter=doc.page.footerContent?render(doc.page.footerContent):'';const fontDecls='<office:font-face-decls>'+[...fontNames].map(([family,id])=>`<style:font-face style:name="${id}" svg:font-family="${x(family)}"/>`).join('')+'</office:font-face-decls>'; const [w,h]=pageDimensions(doc.page);const p=doc.page;
  const frame=borderSettings(p),stroke=frame.width*25.4/72;
  const pageMargins=frame.style==='none'?`fo:margin-top="${p.top}mm" fo:margin-right="${p.right}mm" fo:margin-bottom="${p.bottom}mm" fo:margin-left="${p.left}mm"`: (['top','right','bottom','left'] as const).map((side,i)=>`fo:margin-${side}="${frame.insets[i]}mm"`).join(' ')+` fo:border="${frame.width}pt ${frame.style==='single'||frame.style==='bold'?'solid':frame.style} ${frame.color}" ${frame.style==='double'?`style:border-line-width="${frame.width/3}pt ${frame.width/3}pt ${frame.width/3}pt"`:''} `+(['top','right','bottom','left'] as const).map((side,i)=>`fo:padding-${side}="${Math.max(0,p[side]-frame.insets[i]-stroke)}mm"`).join(' ');

  const lists=['<text:list-style style:name="Bullets">','<text:list-style style:name="Numbered">'].map((start,i)=> start+Array.from({length:10},(_,j)=>i?`<text:list-level-style-number text:level="${j+1}" style:num-format="1" style:num-suffix="."/>`:`<text:list-level-style-bullet text:level="${j+1}" text:bullet-char="•"/>`).join('')+'</text:list-style>').join('');
  zip.file('content.xml',`<?xml version="1.0" encoding="UTF-8"?><office:document-content ${ns} office:version="1.3">${fontDecls}<office:automatic-styles>${styles.join('')}<style:style style:name="PageBreak" style:family="paragraph"><style:paragraph-properties fo:break-before="page"/></style:style>${lists}</office:automatic-styles><office:body><office:text>${body}</office:text></office:body></office:document-content>`);
  zip.file('styles.xml',`<?xml version="1.0" encoding="UTF-8"?><office:document-styles ${ns} office:version="1.3">${fontDecls}<office:styles><style:style style:name="FolioHeader" style:family="table-cell"><style:table-cell-properties fo:background-color="#eef2f6"/><style:text-properties fo:font-weight="bold"/></style:style><style:default-style style:family="paragraph"><style:paragraph-properties fo:line-height="150%"/><style:text-properties fo:font-family="Noto Serif" style:font-name-complex="${fontId('Noto Serif Hebrew')}" fo:font-size="11pt" style:font-size-complex="11pt"/></style:default-style></office:styles><office:automatic-styles>${styles.join('')}<style:page-layout style:name="Page"><style:page-layout-properties fo:page-width="${w}mm" fo:page-height="${h}mm" style:print-orientation="${p.orientation}" ${pageMargins}/></style:page-layout></office:automatic-styles><office:master-styles><style:master-page style:name="Standard" style:page-layout-name="Page">${richHeader||p.header?`<style:header>${richHeader||`<text:p>${x(p.header)}</text:p>`}</style:header>`:''}${richFooter||p.footer||p.pageNumbers?`<style:footer>${richFooter||`<text:p>${x(p.footer)}${p.pageNumbers?' <text:page-number text:select-page="current">1</text:page-number>':''}</text:p>`}</style:footer>`:''}</style:master-page></office:master-styles></office:document-styles>`);
  zip.file('meta.xml',`<?xml version="1.0"?><office:document-meta ${ns} xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" office:version="1.3"><office:meta><dc:title>${x(doc.title)}</dc:title><meta:generator>Folio 0.1</meta:generator></office:meta></office:document-meta>`);
  zip.file('META-INF/manifest.xml',`<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3"><manifest:file-entry manifest:full-path="/" manifest:media-type="${MIME}"/>${['content.xml','styles.xml','meta.xml'].map(f=>`<manifest:file-entry manifest:full-path="${f}" manifest:media-type="text/xml"/>`).join('')}${assets.map(f=>`<manifest:file-entry manifest:full-path="${f}" manifest:media-type="image/${f.endsWith('.png')?'png':'jpeg'}"/>`).join('')}</manifest:manifest>`);
  return zip.generateAsync({type:'uint8array',compression:'DEFLATE'});
}

export async function importOdt(bytes:Uint8Array): Promise<{document:DocumentData;warnings:string[]}> {
  const zip=await openZip(bytes); const content=await zipXml(zip,'content.xml');
  if(zip.file('mimetype') && (await zip.file('mimetype')!.async('string')).trim()!==MIME)throw Error('This package is not an OpenDocument text document.');
  const styles=zip.file('styles.xml')?await zipXml(zip,'styles.xml'):parseXml('<root/>');const doc=blankDocument(); const warnings=new Set<string>();
  const styleMap=new Map<string,Element>();[...elements(styles,'style'),...elements(content,'style')].forEach(e=>styleMap.set(attr(e,'name'),e));
  const defaults=elements(styles,'default-style').find(e=>attr(e,'family')==='paragraph');
  function props(name:string,tag:string,seen=new Set<string>()):Record<string,string> { const base:Record<string,string>={}; if(seen.has(name))return base;seen.add(name);const e=styleMap.get(name);const parent=attr(e,'parent-style-name');if(parent)Object.assign(base,props(parent,tag,seen));if(!parent){const d=child(defaults,tag);if(d)Array.from(d.attributes).forEach(a=>base[a.localName]=a.value);}const p=child(e,tag);if(p)Array.from(p.attributes).forEach(a=>base[a.localName]=a.value);return base; }
  function marksFor(name:string): NonNullable<DocNode['marks']> {const p=props(name,'text-properties');const marks:NonNullable<DocNode['marks']>=[];
    if(p['font-weight']==='bold'||Number(p['font-weight'])>=600)marks.push({type:'bold'});if(p['font-style']==='italic')marks.push({type:'italic'});if(p['text-underline-style']&&p['text-underline-style']!=='none')marks.push({type:'underline'});if(p['text-line-through-style']&&p['text-line-through-style']!=='none')marks.push({type:'strike'});if(p['text-position']?.startsWith('super'))marks.push({type:'superscript'});if(p['text-position']?.startsWith('sub'))marks.push({type:'subscript'});
    if(p['background-color']&&p['background-color']!=='transparent')marks.push({type:'highlight',attrs:{color:p['background-color']}});
    const fontFace=p['font-family']??elements(styles,'font-face').find(e=>attr(e,'name')===p['font-name'])?.getAttribute('svg:font-family');
    const a:Record<string,unknown>={};if(p.border&&p.border!=='none')a.boxed=true;if(p['text-scale'])a.characterScale=parseFloat(p['text-scale']);if(p['letter-spacing'])a.characterSpacing=lengthPt(p['letter-spacing']);if(fontFace)a.fontFamily=fontFace.replace(/'/g,'');if(p['font-size'])a.fontSize=p['font-size'];if(p.color)a.color=p.color;if(Object.keys(a).length)marks.push({type:'textStyle',attrs:a});return marks;
  }
  function mergeMarks(base:NonNullable<DocNode['marks']>,extra:NonNullable<DocNode['marks']>){const m=new Map(base.map(v=>[v.type,v]));for(const v of extra){const old=m.get(v.type);m.set(v.type,v.type==='textStyle'?{...v,attrs:{...old?.attrs,...v.attrs}}:v);}return [...m.values()];}
  async function inline(e:Node, inherited:NonNullable<DocNode['marks']>=[]):Promise<DocNode[]> {
    if(e.nodeType===3)return e.textContent?[{type:'text',text:e.textContent,marks:inherited}]:[];
    if(e.nodeType!==1)return [];const el=e as Element;const tag=el.localName;
    if(tag==='line-break')return [{type:'hardBreak'}];if(tag==='s')return [{type:'text',text:' '.repeat(Math.min(1000,Number(attr(el,'c'))||1)),marks:inherited}];if(tag==='tab')return [{type:'text',text:'\t',marks:inherited}];
    if(tag==='image')return [];if(tag==='frame'){const im=elements(el,'image')[0];if(!im)return []; const path=attr(im,'href').replace(/^\.\//,'');if(!/\.(png|jpe?g)$/i.test(path)){warnings.add('Some images use an unsupported format. PNG and JPEG images are supported.');return [];}const f=zip.file(path);if(!f)return [];return [{type:'image',attrs:{src:`data:image/${path.toLowerCase().endsWith('.png')?'png':'jpeg'};base64,${await f.async('base64')}`,alt:elements(el,'desc')[0]?.textContent??'',width:lengthMm(attr(el,'width'),105)*96/25.4,height:lengthMm(attr(el,'height'),66)*96/25.4}}];}
    let marks=mergeMarks(inherited,marksFor(attr(el,'style-name')));if(tag==='a'){const href=safeLink(attr(el,'href'));if(href)marks=mergeMarks(marks,[{type:'link',attrs:{href}}]);}
    if(['note','bookmark','annotation','tracked-changes','change-start','change-end'].includes(tag)){warnings.add('Notes, comments, bookmarks, or tracked changes are not preserved.');if(tag==='note'||tag==='annotation'||tag==='tracked-changes')return [];}
    return (await Promise.all(Array.from(el.childNodes).map(n=>inline(n,marks)))).flat();
  }
  async function blocks(e:Element):Promise<DocNode[]> {
    const out:DocNode[]=[];
    for(const el of children(e)) {const tag=el.localName;
      if(tag==='p'||tag==='h') {const name=attr(el,'style-name');const p=props(name,'paragraph-properties');const attrs:Record<string,unknown>={dir:p['writing-mode']==='rl-tb'?'rtl':p['writing-mode']==='lr-tb'?'ltr':'auto',language:props(name,'text-properties')['language-complex']==='he'||props(name,'text-properties').language==='he'?'he':props(name,'text-properties').language==='en'?'en':'auto',textAlign:p['text-align']==='end'?(p['writing-mode']==='rl-tb'?'left':'right'):p['text-align']??'start',lineHeight:p['line-height']?.endsWith('%')?parseFloat(p['line-height'])/100:1.5,spaceBefore:lengthPt(p['margin-top']??'0pt'),spaceAfter:lengthPt(p['margin-bottom']??'8pt'),indent:lengthMm(p[p['writing-mode']==='rl-tb'?'margin-right':'margin-left']??'0mm'),firstLine:lengthMm(p['text-indent']??'0mm'),keepWithNext:p['keep-with-next']==='always'};
        if(['top','right','bottom','left'].some(side=>p['border-'+side])){attrs.paragraphBorders=['top','right','bottom','left'].map(side=>p['border-'+side]||'none');attrs.borderPadding=['top','right','bottom','left'].map(side=>lengthPt(p['padding-'+side]||'0pt'));}
        const tp=props(name,'text-properties');if(p['line-height']&&!p['line-height'].endsWith('%')&&p['line-height']!=='normal')attrs.lineHeightPt=lengthPt(p['line-height']);if(p['line-height-at-least'])attrs.minLineHeightPt=lengthPt(p['line-height-at-least']);if(tp['font-family'])attrs.paragraphFontFamily=tp['font-family'];if(tp['font-size'])attrs.paragraphFontSize=lengthPt(tp['font-size']);attrs.endIndent=lengthMm(p[p['writing-mode']==='rl-tb'?'margin-left':'margin-right']??'0mm');
        if(p['break-before']==='page')out.push({type:'pageBreak'});
        const runs=(await Promise.all(Array.from(el.childNodes).map(n=>inline(n,marksFor(name))))).flat();
        const imageNodes=runs.filter(n=>n.type==='image');const textNodes=runs.filter(n=>n.type!=='image');if(tag==='h')attrs.level=Math.min(6,Math.max(1,Number(attr(el,'outline-level'))||1));
        if(textNodes.length||!imageNodes.length){if(name!=='PageBreak'||textNodes.length)out.push({type:tag==='h'?'heading':'paragraph',attrs,content:textNodes});}out.push(...imageNodes);
      } else if(tag==='list'){const listStyle=[...elements(content,'list-style'),...elements(styles,'list-style')].find(s=>attr(s,'name')===attr(el,'style-name'));const ordered=!!listStyle&&elements(listStyle,'list-level-style-number').length>0;out.push({type:ordered?'orderedList':'bulletList',attrs:ordered?{start:Number(attr(children(el,'list-item')[0],'start-value'))||1}:undefined,content:await Promise.all(children(el,'list-item').map(async item=>({type:'listItem',content:await blocks(item)})))});
       } else if(tag==='table'){
        const tableProps=props(attr(el,'style-name'),'table-properties');const widths:number[]=[];
        for(const col of children(el,'table-column')){const width=lengthPt(props(attr(col,'style-name'),'table-column-properties')['column-width']??'0pt')/0.75;for(let k=0;k<Math.min(1000,Number(attr(col,'number-columns-repeated'))||1);k++)widths.push(width);}
        const rows=elements(el,'table-row').filter(r=>{let parent=r.parentElement;while(parent&&parent.localName!=='table')parent=parent.parentElement;return parent===el;});const content:DocNode[]=[];
        for(const row of rows){const cells:DocNode[]=[];let column=0;for(const cell of children(row,'table-cell')){
          const cp=props(attr(cell,'style-name'),'table-cell-properties');const colspan=Number(attr(cell,'number-columns-spanned'))||1;const colwidth=widths.slice(column,column+colspan);column+=colspan;
          const appearance:Record<string,unknown>={};if(cp['background-color'])appearance.fillColor=cp['background-color'];if(cp['vertical-align'])appearance.verticalAlign=cp['vertical-align'];
          if(['top','right','bottom','left'].some(side=>cp['padding-'+side]))appearance.cellPadding=['top','right','bottom','left'].map(side=>lengthPt(cp['padding-'+side]??cp.padding??'0pt'));
          if(['top','right','bottom','left'].some(side=>cp['border-'+side]))appearance.cellBorders=['top','right','bottom','left'].map(side=>cp['border-'+side]??'none');
          const body=await blocks(cell);cells.push({type:attr(cell,'style-name')==='FolioHeader'?'tableHeader':'tableCell',attrs:{...appearance,colspan,rowspan:Number(attr(cell,'number-rows-spanned'))||1,...(colwidth.length===colspan&&colwidth.every(w=>w>0)?{colwidth}:{} )},content:body.length?body:[{type:'paragraph'}]});
        }const rp=props(attr(row,'style-name'),'table-row-properties');content.push({type:'tableRow',attrs:rp['min-row-height']?{rowHeight:lengthPt(rp['min-row-height'])}:undefined,content:cells});}
        if(content.length)out.push({type:'table',attrs:{tableAlign:tableProps.align||'left',...(tableProps.width?{layoutWidth:lengthPt(tableProps.width)}:{})},content});
      } else if(['section','list-item','table-header-rows'].includes(tag)) {if(tag==='section')warnings.add('Section-specific layouts are flattened to one document layout.');out.push(...await blocks(el));}
      else if(!['sequence-decls','tracked-changes','forms'].includes(tag)){warnings.add(`Unsupported ODT content (${tag}) may be simplified.`);out.push(...await blocks(el));}
    }return out;
  }
  const body=elements(content,'text').find(e=>e.prefix==='office');if(!body)throw Error('No document body found.');
  doc.content={type:'doc',content:await blocks(body)};if(!doc.content.content?.length)doc.content.content=[{type:'paragraph'}];
  const page=elements(styles,'page-layout-properties')[0];if(page){const w=lengthMm(attr(page,'page-width'),210);const h=lengthMm(attr(page,'page-height'),297);doc.page.size=Math.abs(Math.min(w,h)-215.9)<2?'Letter':'A4';doc.page.orientation=w>h?'landscape':'portrait';for(const k of ['top','right','bottom','left'] as const)doc.page[k]=Math.max(0,Math.min(100,lengthMm(attr(page,'margin-'+k)||attr(page,'margin'),25.4)));if(![210,215.9].some(v=>Math.abs(Math.min(w,h)-v)<2))warnings.add('Custom paper size was mapped to A4.');}
  if(page){const border=attr(page,'border')||attr(page,'border-top');const match=border.match(/^([\d.]+(?:pt|mm|cm|in))\s+(solid|double|dashed|dotted)\s+(#[a-fA-F0-9]{6})$/);if(match){const width=lengthPt(match[1],1);doc.page.border=parseBorder(match[2],width);doc.page.borderColor=match[3];doc.page.borderWidth=width;doc.page.borderInsets=['top','right','bottom','left'].map(side=>lengthMm(attr(page,'margin-'+side)||attr(page,'margin'),0));for(const side of ['top','right','bottom','left'] as const)doc.page[side]+=lengthMm(attr(page,'padding-'+side)||attr(page,'padding'),0)+width*25.4/72;}}

  const header=elements(styles,'header')[0];const footer=elements(styles,'footer')[0];doc.page.header=header?.textContent??'';if(header&&(elements(header,'span').length||elements(header,'p').some(p=>attr(p,'style-name'))))doc.page.headerContent={type:'doc',content:await blocks(header)};if(footer&&!elements(footer,'page-number').length&&(elements(footer,'span').length||elements(footer,'p').some(p=>attr(p,'style-name'))))doc.page.footerContent={type:'doc',content:await blocks(footer)};doc.page.pageNumbers=!!footer&&elements(footer,'page-number').length>0;
  if(footer){const clone=footer.cloneNode(true) as Element;elements(clone,'page-number').forEach(e=>e.remove());doc.page.footer=clone.textContent?.trim()??'';}
  if(zip.file('meta.xml')){const meta=await zipXml(zip,'meta.xml');doc.title=elements(meta,'title')[0]?.textContent||'Untitled';}
  if(elements(content,'table-of-content').length||elements(content,'text-box').length||elements(styles,'columns').length)warnings.add('Text boxes, columns, and generated indexes are not supported.');
  ensureListDirections(doc.content);return {document:doc,warnings:[...warnings]};
}
