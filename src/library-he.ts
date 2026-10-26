import type {LibraryBook} from './library';

export const categoryHe=(category:string)=>(({Torah:'תורה',Neviim:'נביאים',Ketuvim:'כתובים',Zeraim:'זרעים',Moed:'מועד',Nashim:'נשים',Nezikin:'נזיקין',Kodashim:'קדשים',Tohorot:'טהרות'} as Record<string,string>)[category]??'ספרים נוספים');
export const bookHe=(book:LibraryBook)=>book.he_title.replace(/"/g,'״');
// Four known source artifacts; preserve the raw edition text in the database.
export const libraryTextHe=(text:string)=>text.replaceAll('(.b)','').replaceAll('/b>','').replaceAll('(qb)','').replace('כזה x','כזה ×');

export function numberHe(value:number):string {
 if(!Number.isFinite(value))return 'לא ידוע';
 if(!Number.isInteger(value)||value<1||value>999)return String(value);
 let n=value,result='';while(n>=400){result+='ת';n-=400;}
 for(const [amount,letter] of [[300,'ש'],[200,'ר'],[100,'ק'],[90,'צ'],[80,'פ'],[70,'ע'],[60,'ס'],[50,'נ'],[40,'מ'],[30,'ל'],[20,'כ']] as const){if(n>=amount){result+=letter;n-=amount;}}
 if(n===15){result+='טו';n=0;}if(n===16){result+='טז';n=0;}
 if(n>=10){result+='י';n-=10;}if(n)result+='אבגדהוזחט'[n-1];
 return result.length===1?result+'׳':result.slice(0,-1)+'״'+result.slice(-1);
}
export function sectionHe(section:string,collection:string){
 const daf=/^(\d+)([ab])$/.exec(section);
 if(daf)return `דף ${numberHe(Number(daf[1]))} ${daf[2]==='a'?'ע״א':'ע״ב'}`;
 return `${collection==='Bavli'?'דף':'פרק'} ${numberHe(Number(section))}`;
}
export function referenceHe(ref:string,book:LibraryBook){
 const [section,...parts]=ref.split(':');
 return [sectionHe(section,book.collection),...parts.map((n,i)=>`${i===0?(book.collection==='Tanakh'?'פסוק':'קטע'):'פירוש'} ${numberHe(Number(n))}`)].join(', ');
}
