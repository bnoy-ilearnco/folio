import {Extension} from '@tiptap/core';
import {cssQuoted} from './language';

// Measurements retained from imported documents. Normal documents keep the
// existing toolbar defaults; editing their spacing clears the imported override.
export const ImportedLayout=Extension.create({name:'importedLayout',addGlobalAttributes(){return [
 {types:['paragraph','heading'],attributes:{
  lineHeightPt:{default:null,renderHTML:a=>a.lineHeightPt?{style:`line-height:${a.lineHeightPt}pt`}:{}},
  minLineHeightPt:{default:null,renderHTML:a=>a.minLineHeightPt?{style:`min-height:${a.minLineHeightPt}pt`}:{}},
  paragraphFontFamily:{default:null,renderHTML:a=>a.paragraphFontFamily?{style:`font-family:${cssQuoted(a.paragraphFontFamily)}`}:{}},
  paragraphFontSize:{default:null,renderHTML:a=>a.paragraphFontSize?{style:`font-size:${a.paragraphFontSize}pt`}:{}},
  endIndent:{default:null,renderHTML:a=>a.endIndent?{style:`margin-inline-end:${a.endIndent}mm`}:{}},
 }},
 {types:['table'],attributes:{
  layoutWidth:{default:null,renderHTML:a=>a.layoutWidth?{'data-imported-table':'true',style:`width:${a.layoutWidth}pt;margin:0;max-width:none`}:{}},
 }},
 {types:['tableRow'],attributes:{rowHeight:{default:null,renderHTML:a=>a.rowHeight?{style:`height:${a.rowHeight}pt`}:{}}}},
 {types:['tableCell','tableHeader'],attributes:{
  cellPadding:{default:null,renderHTML:a=>Array.isArray(a.cellPadding)?{style:`padding:${a.cellPadding.map((v:number)=>`${v}pt`).join(' ')}`} :{}},
  cellBorders:{default:null,renderHTML:a=>Array.isArray(a.cellBorders)?{style:a.cellBorders.map((v:string,i:number)=>`border-${['top','right','bottom','left'][i]}:${v}`).join(';')}:{}},
  fillColor:{default:null,renderHTML:a=>a.fillColor?{style:`background-color:${a.fillColor}`}:{}},
  verticalAlign:{default:null,renderHTML:a=>a.verticalAlign?{style:`vertical-align:${a.verticalAlign}`}:{}},
 }},
 {types:['textStyle'],attributes:{
  boxed:{default:null,renderHTML:a=>a.boxed?{style:'border:0.75pt solid currentColor;padding:0 2pt'}:{}},
  characterSpacing:{default:null,renderHTML:a=>a.characterSpacing?{style:`letter-spacing:${a.characterSpacing}pt`}:{}},
 }},
 ];}});
