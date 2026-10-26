import { Extension, Node, mergeAttributes } from '@tiptap/core';
export const ParagraphLayout=Extension.create({name:'paragraphLayout',addGlobalAttributes(){return [{types:['paragraph','heading'],attributes:{
  language:{default:'auto',parseHTML:e=>e.lang?.startsWith('he')?'he':e.lang?.startsWith('en')?'en':'auto',renderHTML:a=>a.language==='he'?{lang:'he',style:"font-family:'Noto Sans Hebrew','Noto Sans',sans-serif"}:a.language==='en'?{lang:'en'}:{}},
  lineHeight:{default:1.5,parseHTML:e=>parseFloat(e.style.lineHeight)||1.5,renderHTML:a=>({style:`line-height:${a.lineHeight}`})},
  spaceBefore:{default:0,parseHTML:e=>parseFloat(e.style.marginTop)||0,renderHTML:a=>({style:`margin-top:${a.spaceBefore}pt`})},
  spaceAfter:{default:8,parseHTML:e=>parseFloat(e.style.marginBottom)||8,renderHTML:a=>({style:`margin-bottom:${a.spaceAfter}pt`})},
  indent:{default:0,parseHTML:e=>parseFloat(e.style.marginInlineStart||e.style.marginLeft)||0,renderHTML:a=>({style:`margin-inline-start:${a.indent}mm`})},
  firstLine:{default:0,parseHTML:e=>parseFloat(e.style.textIndent)||0,renderHTML:a=>({style:`text-indent:${a.firstLine}mm`})},
  keepWithNext:{default:false,renderHTML:a=>a.keepWithNext?{style:'break-after:avoid'}:{}}
}}];}});
export const PageBreak=Node.create({name:'pageBreak',group:'block',atom:true,selectable:true,parseHTML(){return [{tag:'div[data-page-break]'}];},renderHTML({HTMLAttributes}){return ['div',mergeAttributes(HTMLAttributes,{'data-page-break':'true',class:'page-break',contenteditable:'false','aria-label':'Page break'}),['span',{},'Page break']];}});
