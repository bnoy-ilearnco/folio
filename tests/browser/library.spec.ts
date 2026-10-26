import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

const fixture=JSON.parse(readFileSync('tests/fixtures/library.json','utf8'));
test.beforeEach(async({page})=>{
  await page.addInitScript((data)=>{
    (window as any).isTauri=true;
    (window as any).__TAURI_INTERNALS__={
      metadata:{currentWindow:{label:'main'},currentWebview:{label:'main'}},
      transformCallback:()=>1,
      invoke:async(cmd:string,args:any)=>{
        if(cmd==='library_catalog')return data.catalog;
        if(cmd==='library_sections')return data.sections[args.bookId]??[];
        if(cmd==='library_read')return data.readings[`${args.bookId}:${args.section}`]??{passages:[],commentary:[],commentary_book:null};
        if(cmd==='library_search'){
          const b=data.catalog.books.find((b:any)=>b.title==='Genesis');const p=data.readings[`${b.id}:1`].passages[0];
          return args.query.includes('איןתוצאות')?[]:[{...p,book_id:b.id,title:b.title,section:'1'}];
        }
        return null;
      }
    };
  },fixture);
  await page.goto('/');
});

test('organized offline reader aligns Rashi, navigates, searches, and inserts only the selected RTL passage',async({page})=>{
  const external:string[]=[];page.on('request',r=>{if(!r.url().startsWith(new URL(page.url()).origin)&&!r.url().startsWith('data:'))external.push(r.url());});
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();
  const library=page.getByRole('dialog',{name:'ספריית קודש'});
  await expect(library.getByRole('heading',{name:'בראשית',exact:true})).toBeVisible();
  await expect(library.locator('.library-passage').first()).toContainText('בְּרֵאשִׁ֖ית');
  await expect(library.locator('.library-parallel-row').first().locator('.library-comment')).toHaveCount(3);
  await expect(library.locator('.library-hebrew').first()).toHaveCSS('direction','rtl');
  await library.getByRole('button',{name:'הבא',exact:true}).click();
  await expect(library.getByLabel('בחירת פרק או דף')).toHaveValue('2');
  await library.getByLabel('חיפוש בספרייה').fill('בראשית ברא');await library.getByRole('button',{name:'חיפוש',exact:true}).click();
  await expect(library.getByRole('status')).toContainText('תוצאות 1–1');
  await library.locator('.library-results button').first().click();
  await expect(library.getByLabel('בחירת פרק או דף')).toHaveValue('1');
  await library.locator('.library-passage').first().getByRole('button',{name:'הוספה למסמך'}).click();
  await expect(library).not.toBeVisible();
  const editor=page.getByRole('textbox',{name:'Document text'});await expect(editor).toContainText('בְּרֵאשִׁ֖ית');
  await expect(editor).toHaveText(fixture.readings['1:1'].passages[0].text);await expect(editor.locator('p[lang="he"]').first()).toHaveAttribute('dir','rtl');
  await expect(editor.locator('p').last()).toHaveAttribute('dir','rtl');
  await expect(editor.locator('p').last()).not.toContainText(/[a-z]/i);
  await expect(editor.locator('a')).toHaveCount(0);
  await expect(editor.locator('p')).toHaveCount(1);
  await expect(editor).not.toContainText('מקור מקוון');
  expect(external).toEqual([]);
});

test('all library text, accessibility labels and search results are Hebrew in RTL',async({page})=>{
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();const library=page.getByRole('dialog',{name:'ספריית קודש'});
  await expect(library).toHaveAttribute('lang','he');await expect(library).toHaveAttribute('dir','rtl');
  await expect(library.locator('.library-credits')).toHaveCount(0);
  await expect(library).not.toContainText(/תורה אל־אם|ספריא|רישיון|מהדורה/);
  expect(await library.innerText()).not.toMatch(/[a-z]/i);
  expect(await library.locator('[aria-label],[placeholder],[title]').evaluateAll(nodes=>nodes.flatMap(n=>['aria-label','placeholder','title'].map(a=>n.getAttribute(a)??'')).join(' '))).not.toMatch(/[a-z]/i);
  const sidebar=await library.locator('.library-sidebar').boundingBox(),main=await library.locator('.library-main').boundingBox();expect(sidebar!.x).toBeGreaterThan(main!.x);
  await library.getByLabel('בחירת אוסף').selectOption('Bavli');await expect(library.getByRole('heading',{name:'ברכות',exact:true})).toBeVisible();
  await expect(library).toContainText('דף ב׳ ע״א');expect(await library.innerText()).not.toMatch(/[a-z]/i);
  await library.getByLabel('חיפוש בספרייה').fill('מאימתי');await library.getByRole('button',{name:'חיפוש',exact:true}).click();
  await expect(library.getByRole('status')).toContainText('תוצאות');expect(await library.innerText()).not.toMatch(/[a-z]/i);
  await library.getByLabel('איתור ספר בספרייה').fill('איןספרכזה');await expect(library).toContainText('לא נמצאו ספרים מתאימים.');
  await library.getByLabel('איתור ספר בספרייה').fill('');
  await page.screenshot({path:'test-results/library-hebrew.png',fullPage:true});
});

test('library failures are explained in Hebrew without leaking backend English',async({page})=>{
  await page.evaluate(()=>{(window as any).__TAURI_INTERNALS__.invoke=async()=>{throw Error('Cannot open offline library: database missing');};});
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();const library=page.getByRole('dialog',{name:'ספריית קודש'});
  await expect(library.getByRole('status')).toContainText('לא ניתן לקרוא מהספרייה');expect(await library.innerText()).not.toMatch(/[a-z]/i);
});

test('collection navigation includes only Tanakh and Bavli and remembers the reading position',async({page})=>{
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();const library=page.getByRole('dialog',{name:'ספריית קודש'});
  await library.getByLabel('בחירת אוסף').selectOption('Bavli');
  await expect(library.getByRole('heading',{name:'ברכות',exact:true})).toBeVisible();
  await expect(library.getByLabel('בחירת פרק או דף')).toHaveValue('2a');
  await library.getByRole('button',{name:'הבא',exact:true}).click();await expect(library.getByRole('status')).toContainText('ברכות, דף ב׳ ע״ב');
  await library.getByRole('button',{name:'סגירת הספרייה',exact:true}).click();await page.reload();
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();await expect(library.getByLabel('בחירת פרק או דף')).toHaveValue('2b');
  await expect(library.getByLabel('בחירת אוסף').locator('option')).toHaveCount(2);
  await library.getByLabel('בחירת אוסף').selectOption('Tanakh');
  await expect(library.getByRole('heading',{name:'בראשית',exact:true})).toBeVisible();
  await library.getByLabel('חיפוש בספרייה').fill('איןתוצאות');await library.getByRole('button',{name:'חיפוש',exact:true}).click();await expect(library.getByRole('status')).toContainText('לא נמצאו קטעים מתאימים');
  await library.getByRole('button',{name:'סגירת הספרייה',exact:true}).click();
});

test('reading can hide vowels and restore the untouched source edition',async({page})=>{
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();const library=page.getByRole('dialog',{name:'ספריית קודש'});
  const text=library.locator('.library-passage .library-hebrew').first();const original=await text.textContent();expect(original).toMatch(/[\u05b0-\u05bc]/);
  await library.getByLabel('תצוגת ניקוד').selectOption('hide');await expect(text).toHaveText(original!.replace(/[\u05b0-\u05bd\u05bf\u05c1\u05c2\u05c7]/g,''));
  await library.getByLabel('תצוגת ניקוד').selectOption('source');await expect(text).toHaveText(original!);
  await library.getByLabel('תצוגת ניקוד').selectOption('hide');await library.locator('.library-passage').first().getByRole('button',{name:'הוספה למסמך'}).click();
  await expect(page.getByRole('textbox',{name:'Document text'})).toContainText(original!);
});
