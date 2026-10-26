export const NIQQUD_MARKS=[
 ['ְ','Sheva'],['ֱ','Hataf segol'],['ֲ','Hataf patah'],['ֳ','Hataf qamats'],['ִ','Hiriq'],['ֵ','Tsere'],['ֶ','Segol'],['ַ','Patah'],['ָ','Qamats'],['ֹ','Holam'],['ֺ','Holam haser'],['ֻ','Qubuts'],['ּ','Dagesh / shuruk'],['ׁ','Shin dot'],['ׂ','Sin dot'],['ׇ','Qamats qatan'],['ֽ','Meteg'],['ֿ','Rafe'],
] as const;
export const isNiqqud=(c:string)=>/[\u05b0-\u05bd\u05bf\u05c1\u05c2\u05c7]/u.test(c);
export const isHebrewMark=(c:string)=>/[\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]/u.test(c);
export const stripNiqqud=(text:string)=>text.replace(/[\u05b0-\u05bd\u05bf\u05c1\u05c2\u05c7]/gu,'');
export function units(text:string){
 const result:{base:string;marks:string;start:number;end:number}[]=[];let offset=0;
 for(const c of text){if(isHebrewMark(c)&&result.length&&/[א-ת]/u.test(result.at(-1)!.base)){const last=result.at(-1)!;last.marks+=c;last.end+=c.length;}else result.push({base:c,marks:'',start:offset,end:offset+c.length});offset+=c.length;}
 return result;
}
function category(mark:string){return /[\u05b0-\u05bb\u05c7]/u.test(mark)?'vowel':/[\u05c1\u05c2]/u.test(mark)?'shin':/[\u05bc\u05bf]/u.test(mark)?'dagesh':mark;}
export function withMark(cluster:string,mark:string){
 const u=units(cluster);if(u.length!==1||!/[א-ת]/u.test(u[0].base))throw Error('Place the cursor after a Hebrew letter, or select one Hebrew letter.');
 if(mark&&!NIQQUD_MARKS.some(([m])=>m===mark))throw Error('Unknown vowel mark.');
 const kept=Array.from(u[0].marks).filter(c=>mark?category(c)!==category(mark):!isNiqqud(c));
 return (u[0].base+kept.join('')+mark).normalize('NFD');
}
