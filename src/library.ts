import {invoke} from '@tauri-apps/api/core';
import type {Editor} from '@tiptap/core';
import {desktop} from './platform';
import {stripNiqqud} from './niqqud-core';
import {bookHe,categoryHe,sectionHe,referenceHe,libraryTextHe,numberHe,commentaryHe} from './library-he';

export interface LibraryBook {id:number;title:string;he_title:string;collection:string;category:string;base_title:string|null;version:string;license:string;source_url:string;segments:number}
export interface LibraryPassage {id:number;ref_:string;text:string;base_ref:string|null}
export interface LibraryCatalog {books:LibraryBook[];metadata:Record<string,string>}
export interface LibraryReading {passages:LibraryPassage[];commentary:LibraryPassage[];commentary_book:LibraryBook|null}
interface Hit {id:number;book_id:number;title:string;section:string;ref_:string;text:string}

const el=<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string,className?:string)=>{const node=document.createElement(tag);if(text)node.textContent=text;if(className)node.className=className;return node;};
const option=(value:string,label:string)=>{const node=el('option',label);node.value=value;return node;};
const label=(text:string,input:HTMLElement)=>{const node=el('label',text);node.append(input);return node;};
const button=(text:string,handler:()=>void|Promise<void>)=>{const node=el('button',text);node.type='button';node.addEventListener('click',()=>void handler());return node;};

export function createLibrary(editor:Editor){
    const dialog=el('dialog',undefined,'library-dialog');dialog.setAttribute('aria-labelledby','library-title');dialog.lang='he';dialog.dir='rtl';
    const heading=el('h1','ספריית קודש');heading.id='library-title';
    const close=button('סגירה',()=>dialog.close());close.setAttribute('aria-label','סגירת הספרייה');
    const head=el('header',undefined,'library-heading');head.append(heading,el('span','שמורה במחשב · זמינה ללא חיבור לרשת','library-offline'),close);
    const status=el('p',undefined,'library-status');status.setAttribute('role','status');
    const collection=el('select');collection.setAttribute('aria-label','בחירת אוסף');
    collection.append(option('Tanakh','תנ״ך'),option('Mishnah','משניות'),option('Bavli','תלמוד בבלי'));
    const filter=el('input');filter.type='search';filter.placeholder='איתור ספר…';filter.setAttribute('aria-label','איתור ספר בספרייה');
    const books=el('nav',undefined,'library-books');books.setAttribute('aria-label','ספרי הספרייה');
    const sidebar=el('aside',undefined,'library-sidebar');sidebar.append(label('אוסף',collection),filter,books);
    const query=el('input');query.type='search';query.placeholder='חיפוש בעברית, עם ניקוד או בלעדיו';query.setAttribute('aria-label','חיפוש בספרייה');query.maxLength=250;
    const scope=el('select');scope.setAttribute('aria-label','תחום החיפוש');scope.append(option('collection','באוסף זה'),option('book','בספר זה'),option('all','בכל הספרייה'));
    const search=button('חיפוש',()=>searchTexts(0));
    const searchbar=el('form',undefined,'library-search');searchbar.append(query,scope,search);searchbar.addEventListener('submit',e=>{e.preventDefault();void searchTexts(0);});
    const title=el('h2','בחירת ספר');const section=el('select');section.setAttribute('aria-label','בחירת פרק או דף');
    const mishnah=el('select');mishnah.setAttribute('aria-label','בחירת משנה');
    const mishnahLabel=label('משנה',mishnah);mishnahLabel.hidden=true;
    const prev=button('הקודם',()=>move(-1)),next=button('הבא',()=>move(1));
    const vowelMode=el('select');vowelMode.setAttribute('aria-label','תצוגת ניקוד');vowelMode.append(option('source','ניקוד המקור'),option('hide','הסתרת ניקוד'));
    const nav=el('div',undefined,'library-navigation');nav.append(title,prev,label('פרק או דף',section),next,mishnahLabel,label('ניקוד',vowelMode));
    const body=el('div',undefined,'library-reading');body.setAttribute('aria-label','טקסט הספרייה');
    const results=el('div',undefined,'library-results');results.hidden=true;
    const right=el('section',undefined,'library-main');right.append(searchbar,nav,status,results,body);
    const layout=el('div',undefined,'library-layout');layout.append(sidebar,right);dialog.append(head,layout);document.body.append(dialog);
    let catalog:LibraryCatalog|null=null,current:LibraryBook|null=null,sections:string[]=[],reading:LibraryReading|null=null,generation=0,selection=editor.state.selection.to;
    let searchGeneration=0;
    function saveLocation(ref?:string){if(current)try{localStorage.setItem('folio-library-location',JSON.stringify({title:current.title,section:section.value,ref}));}catch{/* Preferences are optional. */}}
    function jumpToMishnah(){
        if(!current||!reading)return;
        const selected=reading.passages.find(p=>p.ref_===mishnah.value);
        for(const article of body.querySelectorAll<HTMLElement>('.library-passage')){
            const active=article.id===`library-passage-${selected?.id}`;article.classList.toggle('library-selected',active);
            if(active)article.setAttribute('aria-current','true');else article.removeAttribute('aria-current');
        }
        saveLocation(selected?.ref_);
        if(selected)document.getElementById(`library-passage-${selected.id}`)?.scrollIntoView({block:'start'});
    }
    mishnah.addEventListener('change',jumpToMishnah);
    function error(_e:unknown){status.textContent='לא ניתן לקרוא מהספרייה שבמחשב. נסו לפתוח את הספר מחדש. אם הבעיה נמשכת, התקינו מחדש את קובצי הספרייה.';status.classList.add('error');}
    function message(text:string){status.textContent=text;status.classList.remove('error');}
    function renderBooks(){
        books.replaceChildren();if(!catalog)return;
        const term=filter.value.toLocaleLowerCase();
        const list=catalog.books.filter(b=>!b.base_title&&b.collection===collection.value&&`${b.title} ${b.he_title}`.toLocaleLowerCase().includes(term));
        for(const group of [...new Set(list.map(b=>b.category))]){
            const details=el('details');details.open=true;details.append(el('summary',categoryHe(group)));
            for(const book of list.filter(b=>b.category===group)){
                const choose=button(bookHe(book),()=>selectBook(book.id));
                choose.setAttribute('aria-current',String(current?.id===book.id));details.append(choose);
            }books.append(details);
        }
        if(!list.length)books.append(el('p','לא נמצאו ספרים מתאימים.'));
    }
    function insert(passage:LibraryPassage){
        const content=libraryTextHe(passage.text).split(/\n\n/).map(text=>({type:'paragraph',attrs:{dir:'rtl',language:'he',textAlign:'start'},content:[{type:'text',text}]}));
        dialog.close();editor.chain().focus().setTextSelection(Math.min(selection,editor.state.doc.content.size)).insertContent(content).run();
    }
    function passageNode(passage:LibraryPassage,book:LibraryBook,commentary=false){
        const article=el('article',undefined,commentary?'library-comment':'library-passage');article.id=`library-passage-${passage.id}`;
        const toolbar=el('div',undefined,'library-passage-tools');toolbar.append(el('span',`${bookHe(book)}, ${referenceHe(passage.ref_,book)}`),button('הוספה למסמך',()=>insert(passage)));
        const text=el('p',vowelMode.value==='hide'?stripNiqqud(libraryTextHe(passage.text)):libraryTextHe(passage.text),'library-hebrew');text.dir='rtl';text.lang='he';article.append(toolbar,text);return article;
    }
    function renderReading(){
        body.replaceChildren();if(!current||!reading)return;
        const commentBook=reading.commentary_book;
        body.classList.toggle('library-single',!commentBook);
        const commentator=commentaryHe(current);
        const headers=el('div',undefined,'library-column-headings');headers.append(el('strong',current.base_title?commentator:'הטקסט'),el('strong',commentBook?`פירוש ${commentator}`:'אין פירוש נלווה במקור זה'));body.append(headers);
        const grouped=new Map<string,LibraryPassage[]>();for(const c of reading.commentary){const key=c.base_ref??'';grouped.set(key,[...(grouped.get(key)??[]),c]);}
        const displayed=new Set<number>();
        for(const passage of reading.passages){
            const row=el('div',undefined,'library-parallel-row');row.append(passageNode(passage,current));
            const comments=el('div',undefined,'library-comments');const linked=grouped.get(passage.ref_)??[];
            for(const c of linked){displayed.add(c.id);comments.append(passageNode(c,commentBook!,true));}
            if(commentBook&&!linked.length)comments.append(el('p',`אין פירוש ${commentator} לקטע זה.`,'library-muted'));
            row.append(comments);body.append(row);
        }
        const unlinked=reading.commentary.filter(c=>!displayed.has(c.id));
        if(unlinked.length&&commentBook){body.append(el('h3',`פירושי ${commentator} נוספים בפרק או בדף זה`));for(const c of unlinked)body.append(passageNode(c,commentBook,true));}
        if(!reading.passages.length)body.append(el('p','אין טקסט בפרק או בדף זה.'));
    }
    async function loadSection(target?:number){
        if(!current||!section.value)return;
        const request=++generation;message('הטקסט נטען מהספרייה שבמחשב…');body.setAttribute('aria-busy','true');
        results.hidden=true;body.hidden=false;
        prev.disabled=section.selectedIndex<=0;next.disabled=section.selectedIndex>=sections.length-1;
        try{
            const result=await invoke<LibraryReading>('library_read',{bookId:current.id,section:section.value});if(request!==generation)return;
            reading=result;renderReading();
            message(`${bookHe(current)}, ${sectionHe(section.value,current.collection)} · ${result.passages.length} ${current.collection==='Mishnah'?'משניות':'קטעים'} · ${result.commentary.length} פירושי ${commentaryHe(current)}`);
            mishnahLabel.hidden=current.collection!=='Mishnah'||!!current.base_title;
            mishnah.replaceChildren(option('','כל הפרק'),...result.passages.map(p=>option(p.ref_,`משנה ${numberHe(Number(p.ref_.split(':')[1]))}`)));
            saveLocation();
            if(target)document.getElementById(`library-passage-${target}`)?.scrollIntoView({block:'center'});else body.scrollTop=0;
        }catch(e){if(request===generation)error(e)}finally{if(request===generation)body.removeAttribute('aria-busy')}
    }
    async function selectBook(id:number,desiredSection?:string,target?:number,desiredRef?:string){
        const book=catalog?.books.find(b=>b.id===id);if(!book)return;
        const request=++generation;searchGeneration++;current=book;reading=null;mishnahLabel.hidden=true;title.textContent=bookHe(book);collection.value=book.collection;renderBooks();message('רשימת הפרקים והדפים נטענת…');section.replaceChildren();body.replaceChildren();
        try{const list=await invoke<string[]>('library_sections',{bookId:id});if(request!==generation)return;sections=list;section.append(...list.map(s=>option(s,sectionHe(s,book.collection))));if(desiredSection&&list.includes(desiredSection))section.value=desiredSection;await loadSection(target);if(desiredRef&&current?.id===id&&Array.from(mishnah.options).some(o=>o.value===desiredRef)){mishnah.value=desiredRef;jumpToMishnah();}}catch(e){if(request===generation)error(e)}
    }
    async function move(delta:number){const index=section.selectedIndex+delta;if(index>=0&&index<sections.length){section.selectedIndex=index;await loadSection();}}
    async function searchTexts(offset:number){
        if(!query.value.trim()){message('יש להזין מילים בעברית לחיפוש.');return;}
        const request=++searchGeneration;++generation;body.hidden=true;results.hidden=false;results.replaceChildren();message('החיפוש מתבצע בספרייה שבמחשב…');
        try{
            const hits=await invoke<Hit[]>('library_search',{query:query.value,collection:scope.value==='all'?'':collection.value,bookId:scope.value==='book'?current?.id??null:null,offset});if(request!==searchGeneration)return;
            const more=hits.length>50;for(const hit of hits.slice(0,50)){
                const book=catalog!.books.find(b=>b.id===hit.book_id);if(!book)continue;
                const b=button(`${bookHe(book)}, ${referenceHe(hit.ref_,book)}`,()=>selectBook(hit.book_id,hit.section,hit.id));
                const snippet=el('span',Array.from(libraryTextHe(hit.text)).slice(0,220).join('')+(hit.text.length>220?'…':''),'library-hebrew');snippet.dir='rtl';snippet.lang='he';b.append(snippet);results.append(b);
            }
            if(offset>0)results.append(button('התוצאות הקודמות',()=>searchTexts(Math.max(0,offset-50))));if(more)results.append(button('תוצאות נוספות',()=>searchTexts(offset+50)));
            message(hits.length?`תוצאות ${offset+1}–${offset+Math.min(hits.length,50)}${more?' · יש תוצאות נוספות':''} · החיפוש מתעלם מניקוד ומטעמים`:'לא נמצאו קטעים מתאימים. נסו פחות מילים או הרחיבו את תחום החיפוש.');
        }catch(e){if(request===searchGeneration)error(e)}
    }
    filter.addEventListener('input',renderBooks);collection.addEventListener('change',()=>{searchGeneration++;renderBooks();const first=catalog?.books.find(b=>!b.base_title&&b.collection===collection.value);if(first)void selectBook(first.id);});section.addEventListener('change',()=>void loadSection());
    vowelMode.addEventListener('change',()=>{renderReading();if(current?.collection==='Mishnah'&&mishnah.value)jumpToMishnah();message(vowelMode.value==='hide'?'הניקוד מוסתר בקריאה. בהוספת קטע למסמך יישמר ניקוד המקור.':'מוצג ניקוד מהדורת המקור.');});
    dialog.addEventListener('close',()=>{generation++;searchGeneration++;});
    return {async open(){
        selection=editor.state.selection.to;dialog.showModal();
        if(!desktop){message('הספרייה ללא חיבור לרשת זמינה ביישום המותקן במחשב.');return;}
        try{if(!catalog){message('הספרייה שבמחשב נפתחת…');catalog=await invoke<LibraryCatalog>('library_catalog');renderBooks();let last:{title?:string;section?:string;ref?:string}={};try{last=JSON.parse(localStorage.getItem('folio-library-location')??'{}')??{};}catch{}const book=catalog.books.find(b=>b.title===last.title)??catalog.books.find(b=>!b.base_title);await selectBook(book?.id??0,last.section,undefined,last.ref);}else if(current){const ref=mishnah.value;await loadSection();if(ref){mishnah.value=ref;jumpToMishnah();}}}catch(e){error(e)}
    }};
}
