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
          const b=data.catalog.books.find((b:any)=>args.bookId?b.id===args.bookId:b.title===(args.collection==='Mishnah'?'Mishnah Berakhot':'Genesis'));const p=data.readings[`${b.id}:1`].passages[0];
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

test('collection navigation includes Tanakh, Mishnah and Bavli and remembers the reading position',async({page})=>{
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();const library=page.getByRole('dialog',{name:'ספריית קודש'});
  await library.getByLabel('בחירת אוסף').selectOption('Bavli');
  await expect(library.getByRole('heading',{name:'ברכות',exact:true})).toBeVisible();
  await expect(library.getByLabel('בחירת פרק או דף')).toHaveValue('2a');
  await library.getByRole('button',{name:'הבא',exact:true}).click();await expect(library.getByRole('status')).toContainText('ברכות, דף ב׳ ע״ב');
  await library.getByRole('button',{name:'סגירת הספרייה',exact:true}).click();await page.reload();
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();await expect(library.getByLabel('בחירת פרק או דף')).toHaveValue('2b');
  await expect(library.getByLabel('בחירת אוסף').locator('option')).toHaveCount(3);
  await library.getByLabel('בחירת אוסף').selectOption('Tanakh');
  await expect(library.getByRole('heading',{name:'בראשית',exact:true})).toBeVisible();
  await library.getByLabel('חיפוש בספרייה').fill('איןתוצאות');await library.getByRole('button',{name:'חיפוש',exact:true}).click();await expect(library.getByRole('status')).toContainText('לא נמצאו קטעים מתאימים');
  await library.getByRole('button',{name:'סגירת הספרייה',exact:true}).click();
});

test('Mishnah browses all six orders, selects a mishnah, aligns Bartenura and inserts Hebrew text only',async({page})=>{
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();
  const library=page.getByRole('dialog',{name:'ספריית קודש'});
  await expect(library.getByLabel('בחירת משנה')).toBeHidden();
  await library.getByLabel('בחירת אוסף').selectOption('Mishnah');
  await expect(library.getByRole('heading',{name:'משנה ברכות',exact:true})).toBeVisible();
  await expect(library.locator('.library-books button')).toHaveCount(63);
  for(const order of ['זרעים','מועד','נשים','נזיקין','קדשים','טהרות'])await expect(library.locator('summary').filter({hasText:order})).toBeVisible();
  await expect(library.locator('.library-column-headings')).toContainText('פירוש ברטנורא');
  await expect(library.locator('.library-parallel-row').first().locator('.library-comment')).toHaveCount(10);
  await expect(library.getByLabel('בחירת משנה').locator('option')).toHaveCount(6);
  await library.getByLabel('בחירת משנה').selectOption('1:2');
  const selected=library.locator('.library-passage[aria-current="true"]');
  await expect(selected).toContainText('פרק א׳, משנה ב׳');
  await library.getByLabel('תצוגת ניקוד').selectOption('hide');
  await expect(selected).toContainText('פרק א׳, משנה ב׳');
  expect(await selected.locator('.library-hebrew').innerText()).not.toMatch(/[\u05b0-\u05bc]/);
  await library.getByLabel('תצוגת ניקוד').selectOption('source');
  await expect(selected).toContainText('פרק א׳, משנה ב׳');
  expect(await library.innerText()).not.toMatch(/[a-z]/i);
  expect(await library.innerText()).not.toContain('רש״י');
  await library.getByRole('button',{name:'סגירת הספרייה',exact:true}).click();await page.reload();
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();
  await expect(library.getByLabel('בחירת אוסף')).toHaveValue('Mishnah');
  await expect(library.getByLabel('בחירת משנה')).toHaveValue('1:2');
  await library.getByLabel('חיפוש בספרייה').fill('מאימתי קורין');await library.getByRole('button',{name:'חיפוש',exact:true}).click();
  await expect(library.locator('.library-results button').first()).toContainText('משנה ברכות, פרק א׳, משנה א׳');
  await library.locator('.library-results button').first().click();
  const passage=library.locator('.library-passage').first();const expected=await passage.locator('.library-hebrew').innerText();
  await passage.getByRole('button',{name:'הוספה למסמך'}).click();
  const editor=page.getByRole('textbox',{name:'Document text'});await expect(editor).toContainText(expected);
  expect(await editor.innerText()).not.toContain('ברטנורא');
});

test('Mishnah includes late Tohorot tractates and Pirkei Avot chapters',async({page})=>{
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();const library=page.getByRole('dialog',{name:'ספריית קודש'});
  await library.getByLabel('בחירת אוסף').selectOption('Mishnah');
  const oktzin=fixture.catalog.books.find((b:any)=>b.title==='Mishnah Oktzin');
  await library.getByRole('button',{name:oktzin.he_title,exact:true}).click();
  await library.getByLabel('בחירת פרק או דף').selectOption('3');
  await expect(library.getByLabel('בחירת משנה').locator('option')).toHaveCount(13);
  expect((await library.locator('.library-passage').last().innerText()).normalize('NFD').replace(/[\u0591-\u05c7]/g,'')).toContain('שלום');
  const avot=fixture.catalog.books.find((b:any)=>b.title==='Pirkei Avot');
  await library.getByRole('button',{name:avot.he_title,exact:true}).click();
  await expect(library.getByLabel('בחירת פרק או דף').locator('option')).toHaveCount(6);
  await expect(library.locator('.library-column-headings')).toContainText('ברטנורא');
  await library.getByLabel('בחירת אוסף').selectOption('Bavli');
  await expect(library.getByLabel('בחירת משנה')).toBeHidden();
  await expect(library.locator('.library-column-headings')).toContainText('רש״י');
});

test('reading can hide vowels and restore the untouched source edition',async({page})=>{
  await page.getByRole('button',{name:'ספריית קודש',exact:true}).click();const library=page.getByRole('dialog',{name:'ספריית קודש'});
  const text=library.locator('.library-passage .library-hebrew').first();const original=await text.textContent();expect(original).toMatch(/[\u05b0-\u05bc]/);
  await library.getByLabel('תצוגת ניקוד').selectOption('hide');await expect(text).toHaveText(original!.replace(/[\u05b0-\u05bd\u05bf\u05c1\u05c2\u05c7]/g,''));
  await library.getByLabel('תצוגת ניקוד').selectOption('source');await expect(text).toHaveText(original!);
  await library.getByLabel('תצוגת ניקוד').selectOption('hide');await library.locator('.library-passage').first().getByRole('button',{name:'הוספה למסמך'}).click();
  await expect(page.getByRole('textbox',{name:'Document text'})).toContainText(original!);
});
