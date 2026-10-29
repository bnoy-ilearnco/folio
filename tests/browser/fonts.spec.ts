import {test,expect} from '@playwright/test';
import {FONT_COLLECTION} from '../../src/font-catalog';
import {readFileSync} from 'node:fs';
test('all 13 open families load offline and grouped picker preserves Hebrew fonts',async({page})=>{
 const external:string[]=[];const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{const url=new URL(route.request().url());if(['localhost','127.0.0.1'].includes(url.hostname))return route.continue();external.push(url.href);return route.abort();});
 await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});const menu=page.getByLabel('Font family',{exact:true});
 await expect(menu.locator('optgroup')).toHaveCount(7);
 for(const f of FONT_COLLECTION){
  await editor.fill(f.group.includes('English')&&!f.group.includes('Hebrew')?'The written word — Publishing 123':'שָׁלוֹם עוֹלָם — Publishing 123');await editor.press('Control+a');await menu.selectOption(f.family);
  await expect(editor.locator('span').first()).toHaveCSS('font-family',new RegExp(f.family));
  const loaded=await page.evaluate(async family=>{const faces=await document.fonts.load(`20px "${family}"`);return faces.length>0&&faces.every(face=>face.status==='loaded');},f.family);expect(loaded,f.family).toBe(true);
 }
 await editor.fill('כֶּתֶר אֲרַם צוֹבָא — Hebrew manuscript');await editor.press('Control+a');await menu.selectOption('Keter Aram Tsova');
 const save=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();const odt=await save;
 await page.locator('#file-input').setInputFiles({name:'fonts.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:readFileSync((await odt.path())!)});
 await expect(menu).toHaveValue('Keter Aram Tsova');await expect(editor).toContainText('כֶּתֶר');
 await page.screenshot({path:'test-results/font-collection.png'});
 await page.pdf({path:'test-results/font-collection.pdf',printBackground:true});
 expect(external).toEqual([]);expect(errors).toEqual([]);
});
