import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('Rashi Hebrew is selectable offline and survives ODT and DOCX interchange',async({page})=>{
 const external:string[]=[];
 await page.route('**/*',route=>{const url=new URL(route.request().url());if(['localhost','127.0.0.1'].includes(url.hostname))return route.continue();external.push(url.href);return route.abort();});
 await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});
 await editor.fill('רַשִׁ״י — פירוש התורה');await editor.press('Control+a');
 await page.getByRole('button',{name:'עברית',exact:true}).click();await page.getByLabel('Font family',{exact:true}).selectOption('Noto Rashi Hebrew');
 await page.getByRole('button',{name:'Bold (Ctrl+B)',exact:true}).click();
 await expect(editor.locator('span').first()).toHaveCSS('font-family',/Noto Rashi Hebrew/);
 await page.evaluate(()=>document.fonts.ready);expect(await page.evaluate(()=>document.fonts.check('bold 16px "Noto Rashi Hebrew"','רשי'))).toBe(true);
 const save=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();const odt=await save;
 await page.locator('#file-input').setInputFiles({name:'rashi.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:readFileSync((await odt.path())!)});
 await expect(editor.locator('span').first()).toHaveCSS('font-family',/Noto Rashi Hebrew/);await expect(editor.locator('strong')).toContainText('רַשִׁ״י');
 await page.locator('#file-menu summary').click();const exportEvent=page.waitForEvent('download');await page.locator('[data-action="export-docx"]').click();const docx=await exportEvent;
 await page.locator('#file-input').setInputFiles({name:'rashi.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:readFileSync((await docx.path())!)});
 await expect(editor.locator('span').first()).toHaveCSS('font-family',/Noto Rashi Hebrew/);await expect(editor.locator('strong')).toContainText('רַשִׁ״י');
 await page.screenshot({path:'test-results/rashi-font.png',fullPage:false});expect(external).toEqual([]);
});
