import {test,expect} from '@playwright/test';
import {writeFileSync} from 'node:fs';

test('manual niqqud keyboard replaces a vowel and preserves shin dots',async({page})=>{
 await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});await editor.fill('ש');await editor.press('Control+End');
 await page.getByRole('button',{name:'Vowel keyboard',exact:true}).click();
 await page.getByRole('button',{name:'Add Shin dot',exact:true}).click();await page.getByRole('button',{name:'Add Qamats',exact:true}).click();
 await expect(editor).toHaveText('שָׁ');await page.getByRole('button',{name:'Add Patah',exact:true}).click();await expect(editor).toHaveText('שַׁ');
 await page.getByRole('button',{name:'Clear letter vowels',exact:true}).click();await expect(editor).toHaveText('ש');
});

test('page borders display on paper and repeat across composed PDF pages',async({page})=>{
 await page.goto('/');await page.getByRole('textbox',{name:'Document text'}).fill('שָׁלוֹם — Page border test.');
 await page.locator('[data-page="border"]').selectOption('double');await page.locator('[data-page="borderColor"]').fill('#2255aa');await page.locator('[data-page="borderColor"]').dispatchEvent('change');
 await expect(page.locator('#paper')).toHaveCSS('--page-border','3pt double #2255aa');
 await page.getByRole('textbox',{name:'Document text'}).press('Control+End');await page.getByRole('tab',{name:'Layout',exact:true}).click();await page.getByRole('button',{name:'Page break',exact:true}).click();await expect(page.locator('[data-page-break]')).toHaveCount(1);await page.getByRole('textbox',{name:'Document text'}).pressSequentially('Second page.');
 await expect(page.locator('[data-page-break]')).toHaveCount(1);await expect(page.getByRole('textbox',{name:'Document text'}).locator('p').last()).toHaveText('Second page.');const pdf=await page.pdf({preferCSSPageSize:true,printBackground:true});expect(pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)).toHaveLength(2);writeFileSync('test-results/page-border.pdf',pdf);
 await page.screenshot({path:'test-results/page-border-editor.png',fullPage:true});
});
