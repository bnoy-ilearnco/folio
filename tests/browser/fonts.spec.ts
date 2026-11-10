import JSZip from 'jszip';
import {test,expect} from '@playwright/test';
import {FONT_COLLECTION} from '../../src/font-catalog';
import {readFileSync} from 'node:fs';
test('all bundled open families load offline and grouped picker preserves Hebrew fonts',async({page})=>{
 const external:string[]=[];const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{const url=new URL(route.request().url());if(['localhost','127.0.0.1'].includes(url.hostname))return route.continue();external.push(url.href);return route.abort();});
 await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});const menu=page.getByLabel('Font family',{exact:true});
 await expect(menu.locator('optgroup')).toHaveCount(7);
 for(const f of FONT_COLLECTION){
  await editor.fill(f.group.includes('English')&&!f.group.includes('Hebrew')?'The written word — Publishing 123':'שָׁלוֹם עוֹלָם — Publishing 123');await editor.press('Control+a');await menu.selectOption(f.family);
  await expect(editor.locator('span').first()).toHaveCSS('font-family',new RegExp(f.family));
  const loaded=await page.evaluate(async family=>{const faces=await document.fonts.load(`20px "${family}"`);return faces.length>0&&faces.every(face=>face.status==='loaded');},f.family);expect(loaded,f.family).toBe(true);
 }
 await editor.fill('אֱ בֱ חֲ מֳ בְּֽ שָֽׁ בֹֿ ךָ רוּחַ');await editor.press('Control+a');await menu.selectOption('Mekorot-Rashi Folio');
 const save=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();const odt=await save;
 await page.locator('#file-input').setInputFiles({name:'fonts.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:readFileSync((await odt.path())!)});
 await expect(menu).toHaveValue('Mekorot-Rashi Folio');await expect(editor).toContainText('רוּחַ');
 const legacy=await JSZip.loadAsync(readFileSync((await odt.path())!));
 for(const name of ['content.xml','styles.xml']){const file=legacy.file(name);if(file)legacy.file(name,(await file.async('string')).replaceAll('Mekorot-Rashi Folio','Mekorot-Rashi'));}
 await page.locator('#file-input').setInputFiles({name:'legacy-mekorot.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:Buffer.from(await legacy.generateAsync({type:'uint8array'}))});
 await expect(menu).toHaveValue('Mekorot-Rashi Folio');await expect(editor).toContainText('שָֽׁ');
 await page.locator('#file-menu summary').click();const docxEvent=page.waitForEvent('download');await page.locator('[data-action="export-docx"]').click();const docx=await docxEvent;
 await page.locator('#file-input').setInputFiles({name:'fixed-mekorot.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:readFileSync((await docx.path())!)});
 await expect(menu).toHaveValue('Mekorot-Rashi Folio');await expect(editor).toContainText('שָֽׁ');
 await page.screenshot({path:'test-results/font-collection.png'});
 const pdf=await page.pdf({path:'test-results/font-collection.pdf',printBackground:true});expect(pdf.toString('latin1')).toContain('Mekorot');
 expect(external).toEqual([]);expect(errors).toEqual([]);
});
