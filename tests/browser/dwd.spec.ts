import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import JSZip from 'jszip';

test('imports DavkaWriter offline, retains Hebrew points and styles, and saves as ODT',async({page})=>{
 // Exercise the portable fallback even on a developer machine with Davka installed.
 await page.addInitScript(()=>{const Original=window.FontFace;window.FontFace=class extends Original{constructor(family:string,source:ConstructorParameters<typeof FontFace>[1],descriptors?:FontFaceDescriptors){if(family.startsWith('UniDavka '))throw Error('Local font unavailable in fallback test');super(family,source,descriptors);}};});
 const external:string[]=[];const errors:string[]=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{const url=new URL(route.request().url());if(['127.0.0.1','localhost'].includes(url.hostname))return route.continue();external.push(url.href);return route.abort();});
 await page.goto('/');
 await expect(page.locator('#file-input')).toHaveAttribute('accept',/\.dwd/);
 await page.locator('#file-input').setInputFiles('tests/fixtures/hebrew.dwd');
 const editor=page.getByRole('textbox',{name:'Document text'});
 await expect(editor).toContainText('שָׁלוֹם עוֹלָם',{timeout:45000});
 await expect(editor).toContainText('English 123');
 await expect(editor.locator('p[dir="rtl"] strong')).toContainText('שָׁלוֹם');
 await expect(editor.locator('p[dir="rtl"]')).toHaveCSS('text-align','right');
 await expect(editor.locator('p[dir="rtl"] strong span, p[dir="rtl"] span strong').first()).toHaveCSS('font-family',/Taamey David CLM|UniDavka David/);
 await page.evaluate(()=>document.fonts.ready);
 await expect(editor.locator('p[dir="ltr"] em')).toContainText('English 123');
 await expect(page.locator('#notice')).toContainText('DavkaWriter document imported');
 await expect(page.getByLabel('Document name',{exact:true})).toHaveValue('hebrew');
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();
 const saved=await download;expect(saved.suggestedFilename()).toBe('hebrew.odt');
 await page.locator('#file-input').setInputFiles({name:'roundtrip.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:readFileSync((await saved.path())!)});
 await expect(editor.locator('p[dir="rtl"] strong')).toContainText('שָׁלוֹם');
 expect(external).toEqual([]);expect(errors).toEqual([]);
});

test('uses a locally installed Unicode Davka face at the original size',async({page})=>{
 await page.goto('/');
 const present=await page.evaluate(async()=>{try{await new FontFace('UniDavka David','local("UniDavka David")').load();return true;}catch{return false;}});
 test.skip(!present,'DavkaWriter Unicode fonts are not installed on this test machine.');
 await page.locator('#file-input').setInputFiles('tests/fixtures/hebrew.dwd');
 const editor=page.getByRole('textbox',{name:'Document text'});
 await expect(editor).toContainText('שָׁלוֹם עוֹלָם',{timeout:45000});
 const run=editor.locator('p[dir="rtl"] span').first();
 await expect(run).toHaveCSS('font-family',/UniDavka David/);
 await expect(run).toHaveCSS('font-size','24px'); // Original 18 pt, no substitute calibration.
 await expect(page.locator('#font-family option[value="UniDavka David"]')).toHaveCount(1);
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();const saved=await download;
 const zip=await JSZip.loadAsync(readFileSync((await saved.path())!));expect(await zip.file('content.xml')!.async('string')).toContain('UniDavka David');
});

test('rejects damaged DWD without replacing existing work; a subsequent valid import works',async({page})=>{
 await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});await editor.fill('Keep this work.');
 await page.locator('#file-input').setInputFiles({name:'broken.dwd',mimeType:'application/octet-stream',buffer:Buffer.from([38,2,0,0,0])});
 await expect(page.locator('#notice')).toHaveClass(/error/,{timeout:45000});await expect(editor).toHaveText('Keep this work.');
 await page.locator('#file-input').setInputFiles('tests/fixtures/hebrew.dwd');await expect(editor).toContainText('שָׁלוֹם',{timeout:45000});
});

// The user's worksheet is intentionally outside the source/release. Enable only for local QA.
test('local real-world worksheet imports its tables and text',async({page})=>{
 test.skip(!process.env.FOLIO_DWD_SAMPLE,'Set FOLIO_DWD_SAMPLE to a local DWD document.');
 await page.goto('/');await page.locator('#file-input').setInputFiles(process.env.FOLIO_DWD_SAMPLE!);
 const editor=page.getByRole('textbox',{name:'Document text'});
 await expect(editor.locator('table')).toHaveCount(5,{timeout:45000});
 await expect(page.locator('#notice')).toContainText('DavkaWriter document imported');
 await page.evaluate(()=>document.fonts.ready);
 await expect(page.locator('#page-header')).toContainText('פרשת שמות');
 await expect(page.locator('#page-header p')).toHaveCSS('text-align','center');
 expect(await page.locator('#page-header').evaluate(e=>e.querySelector('span')?.getBoundingClientRect().height)).toBeGreaterThan(20);
 await expect(editor.locator('table').first()).toHaveCSS('width',/65[0-9]/);
 await expect(editor.locator('table').first().locator('td').first()).toHaveCSS('padding-left','4px');
 await expect(editor.locator('table').first().locator('td').first()).toHaveCSS('background-color','rgb(232, 232, 232)');
 await expect(editor.locator('table').first().locator('td').first()).toHaveCSS('border-left-style','solid');
 await expect(editor.locator('table').first().locator('td').first()).toHaveCSS('border-right-style','solid');
 await expect(editor.locator(':scope > p').first()).toHaveCSS('border-top-style','double');
 const installed=await page.evaluate(async()=>{try{await new FontFace('UniDavka Rashi','local("UniDavka Rashi")').load();return true;}catch{return false;}});
 if(installed){
  expect(await editor.locator('span[style*="UniDavka Rashi"]').first().evaluate(e=>parseFloat(getComputedStyle(e).fontSize))).toBeCloseTo(16*96/72,3);
  await expect(editor.locator('span[style*="UniDavka David"]').first()).toHaveCSS('font-size','24px');
 }
 expect((await editor.innerText()).match(/[\u05d0-\u05ea]/g)?.length).toBeGreaterThan(1000);
 expect((await editor.innerText()).match(/[\u05b0-\u05bd\u05c1\u05c2]/g)?.length).toBeGreaterThan(100);
 if(process.env.FOLIO_DWD_REFERENCE){
   const zip=await JSZip.loadAsync(readFileSync(process.env.FOLIO_DWD_REFERENCE));const xml=await zip.file('word/document.xml')!.async('string');
   const expected=await page.evaluate(xml=>Array.from(new DOMParser().parseFromString(xml,'application/xml').getElementsByTagNameNS('*','body')[0].getElementsByTagNameNS('*','p')).map(p=>Array.from(p.getElementsByTagNameNS('*','t')).map(t=>t.textContent).join('')),xml);
   const normalize=(texts:string[])=>texts.map(t=>t.normalize('NFC').replace(/\s/g,'')).filter(Boolean).sort();
   expect(normalize(await editor.locator('p').allTextContents())).toEqual(normalize(expected));
 }
 await page.screenshot({path:'test-results/dwd-worksheet.png',fullPage:false});
 if(process.env.FOLIO_DWD_QA_PDF)await page.pdf({path:process.env.FOLIO_DWD_QA_PDF,printBackground:true,preferCSSPageSize:true});
});
