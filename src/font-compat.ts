import type {DocNode} from './model';
// Use the explicitly named LPPL derivative when reopening older Folio files.
// Preserve text, point sizes and all other marks, including headers/footers.
export function upgradeMekorotFont(root:DocNode):void{
 for(const mark of root.marks??[])if(mark.type==='textStyle'&&mark.attrs?.fontFamily==='Mekorot-Rashi')mark.attrs.fontFamily='Mekorot-Rashi Folio';
 root.content?.forEach(upgradeMekorotFont);
}
