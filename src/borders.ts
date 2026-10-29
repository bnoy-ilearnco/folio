import {pageDimensions,type Page} from './model';
export const BORDER_STYLES=['none','single','double','dashed','dotted','bold'] as const;
export type BorderStyle=typeof BORDER_STYLES[number];
export function borderSettings(page:Page){
  const style=BORDER_STYLES.includes(page.border as BorderStyle)?page.border??'none':'none';
  const color=/^#[0-9a-f]{6}$/i.test(page.borderColor??'')?page.borderColor!:'#364a63';
  const width=Number.isFinite(page.borderWidth)?Math.max(.25,Math.min(18,page.borderWidth!)):style==='double'||style==='bold'?3:1;
  const inset=Math.max(0,Math.min(10,page.top/2,page.right/2,page.bottom/2,page.left/2));
  const insets=Array.isArray(page.borderInsets)&&page.borderInsets.length===4?page.borderInsets.map(v=>Number.isFinite(v)?Math.max(0,Math.min(50,v)):inset):[inset,inset,inset,inset];
  return {style,color,width,inset,insets,css:style==='none'?'none':`${width}pt ${style==='single'||style==='bold'?'solid':style} ${color}`};
}
export function parseBorder(style:string,width:number):BorderStyle{
  if(/^(thickThin|thinThick|triple)/.test(style))return 'double';
  if(style==='double'||style==='dashed'||style==='dotted')return style;
  if(style==='solid'||style==='single')return width>=2?'bold':'single';
  return 'none';
}
export function borderPrintCss(page:Page){
 const frame=borderSettings(page);if(frame.style==='none')return '';
 const [,height]=pageDimensions(page),b=frame.css;
 const [top,right,bottom,left]=frame.insets.map(v=>`${v}mm`);
 // Page margin boxes paint in the margins; fixed DOM overlays are clipped to
 // Chromium's content area. Keep the document's text margins unchanged.
 return `@page{
 @top-left-corner{content:"";border-top:${b};border-left:${b};margin-top:${top};margin-left:${left}}
 @top-center{border-top:${b};margin-top:${top}}
 @top-right-corner{content:"";border-top:${b};border-right:${b};margin-top:${top};margin-right:${right}}
 @left-middle{content:"";border-left:${b};margin-left:${left};height:${height-page.top-page.bottom}mm;box-sizing:border-box}
 @right-middle{content:"";border-right:${b};margin-right:${right};height:${height-page.top-page.bottom}mm;box-sizing:border-box}
 @bottom-left-corner{content:"";border-left:${b};border-bottom:${b};margin-left:${left};margin-bottom:${bottom}}
 @bottom-center{border-bottom:${b};margin-bottom:${bottom}}
 @bottom-right-corner{content:"";border-right:${b};border-bottom:${b};margin-right:${right};margin-bottom:${bottom}}
 }`;
}
