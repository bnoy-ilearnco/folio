import {test,expect} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
test('English button switches back from Hebrew and carries LTR English into the next paragraph',async({page})=>{
  await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});
  await editor.fill('שלום עולם');await page.getByRole('button',{name:'עברית',exact:true}).click();
  await page.getByRole('button',{name:'English',exact:true}).click();
  await expect(page.getByLabel('Paragraph direction',{exact:true})).toHaveValue('ltr');
  await expect(page.locator('[data-paragraph="language"]')).toHaveValue('en');
  await expect(page.getByLabel('Font family',{exact:true})).toHaveValue('Noto Serif');
  await expect(page.getByRole('button',{name:'English',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(editor).toHaveText('שלום עולם');
  await expect(editor.locator('p')).toHaveCSS('direction','ltr');
  await editor.press('Control+End');await editor.press('Enter');await editor.pressSequentially('Back to English.');
  await expect(editor.locator('p').last()).toHaveAttribute('lang','en');
  await expect(editor.locator('p').last()).toHaveAttribute('dir','ltr');
  await page.getByRole('button',{name:'עברית',exact:true}).click();
  await expect(editor.locator('p').last()).toHaveAttribute('dir','rtl');
});
test('Hebrew typing supports automatic direction, explicit controls, inherited paragraphs, and ODT round-trip',async({page})=>{
  await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});
  await editor.fill('שלום עולם, English 123.');
  await expect(editor.locator('p')).toHaveCSS('direction','rtl');
  await page.getByRole('button',{name:'עברית',exact:true}).click();
  await expect(page.getByLabel('Paragraph direction',{exact:true})).toHaveValue('rtl');
  await expect(page.getByLabel('Font family',{exact:true})).toHaveValue('Noto Sans Hebrew');
  await expect(editor.locator('p')).toHaveAttribute('lang','he');
  await expect(editor.locator('p')).toHaveCSS('font-family',/Noto Sans Hebrew/);
  await editor.press('Control+End');await editor.press('Enter');await editor.pressSequentially('שָׁלוֹם, English 123 (בדיקה).');
  await expect(editor.locator('p').last()).toHaveAttribute('dir','rtl');
  await expect(editor.locator('p').last()).toHaveAttribute('lang','he');
  await editor.press('Control+Alt+l');await expect(editor.locator('p').last()).toHaveAttribute('dir','ltr');
  await editor.press('Control+Alt+r');await expect(editor.locator('p').last()).toHaveAttribute('dir','rtl');
  const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();const file=await downloaded;const bytes=readFileSync((await file.path())!);
  await page.locator('#file-input').setInputFiles({name:'Hebrew.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:bytes});
  await expect(page.locator('#saved-state')).toHaveText('Imported · save as ODT');
  await expect(editor).toContainText('שָׁלוֹם, English 123');await expect(editor.locator('p').last()).toHaveAttribute('dir','rtl');
  await page.screenshot({path:'test-results/hebrew-editor.png',fullPage:true});
});
test('Hebrew examples print with browser bidi shaping and bundled fonts',async({page})=>{
  await page.goto('/');await page.locator('#file-input').setInputFiles('examples/hebrew.odt');
  await expect(page.getByRole('textbox',{name:'Document text'})).toContainText('שָׁלוֹם עוֹלָם');
  await page.evaluate(()=>document.fonts.ready);
  const pdf=await page.pdf({preferCSSPageSize:true,printBackground:true});writeFileSync('test-results/hebrew-print.pdf',pdf);
  expect(pdf.subarray(0,4).toString()).toBe('%PDF');
});

