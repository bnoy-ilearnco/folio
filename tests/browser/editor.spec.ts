import {test,expect} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';

test('writes, formats, saves ODT, imports DOCX, and exports PDF',async({page})=>{
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');
  const editor=page.getByRole('textbox',{name:'Document text'});
  await expect(editor).toBeVisible();
  await editor.fill('A quieter place to write');
  await editor.press('Control+a');
  await page.getByRole('button',{name:'Heading 1 Section title'}).click();
  await expect(editor.locator('h1')).toContainText('A quieter place to write');
  await editor.press('End');await editor.press('Enter');
  await page.getByRole('button',{name:'Normal Body text'}).click();
  await editor.pressSequentially('Keep your focus on the words. Format the details when you are ready.');
  await page.getByLabel('Document name',{exact:true}).fill('Writing notes');
  await page.getByRole('tab',{name:'Layout',exact:true}).click();
  await page.locator('#ribbon-layout [data-page="size"]').selectOption('Letter');
  await expect(page.locator('#paper-size')).toContainText('Letter');
  const downloadEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();
  const download=await downloadEvent;expect(download.suggestedFilename()).toBe('Writing notes.odt');
  await expect(page.locator('#saved-state')).toContainText('Saved as ODT');
  await page.getByRole('tab',{name:'Home',exact:true}).click();
  await expect(page.locator('i[data-lucide]')).toHaveCount(0);
  await page.locator('[data-action="dismiss"]').click();
  await page.screenshot({path:'test-results/editor-desktop.png',fullPage:true});
  await page.setViewportSize({width:1000,height:760});
  await page.screenshot({path:'test-results/editor-compact.png',fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('tab',{name:'Insert',exact:true}).click();await page.getByRole('button',{name:'Table',exact:true}).click();await page.getByRole('button',{name:'Insert table',exact:true}).click();await expect(editor.locator('table')).toBeVisible();
  await page.locator('#file-input').setInputFiles({name:'Imported.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:readFileSync('examples/example.docx')});
  await expect(editor).toContainText('Thoughtful writing');
  await page.locator('#file-menu summary').click();const pdfEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Export PDF…',exact:true}).click();const pdf=await pdfEvent;const path=await pdf.path();expect(path).toBeTruthy();const bytes=readFileSync(path!);expect(bytes.subarray(0,4).toString()).toBe('%PDF');writeFileSync('test-results/example.pdf',bytes);
  await expect(page.locator('#notice')).not.toHaveClass(/error/);
  expect(errors).toEqual([]);
});
test('find and replace keeps replacement text literal and recovery can be restored',async({page})=>{await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});await editor.fill('One idea. One page.');await page.keyboard.press('Control+f');await page.locator('#find-input').fill('One');await page.locator('#replace-input').fill('<two>');await page.getByRole('button',{name:'Replace all',exact:true}).click();await expect(editor).toHaveText('<two> idea. <two> page.');await page.waitForTimeout(900);await page.reload();await expect(page.locator('#recovery-banner')).toBeVisible();await page.getByRole('button',{name:'Restore copy',exact:true}).click();await expect(editor).toHaveText('<two> idea. <two> page.');});
test('opening a damaged document preserves the current text',async({page})=>{await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});await editor.fill('Keep this work.');await page.locator('#file-input').setInputFiles({name:'broken.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:Buffer.from('broken')});await expect(page.locator('#notice')).toHaveClass(/error/);await expect(editor).toHaveText('Keep this work.');});
test('ODT formatting survives a save and reopen, and unsaved work can be cancelled',async({page})=>{
  await page.goto('/');const editor=page.getByRole('textbox',{name:'Document text'});await editor.fill('Words with emphasis');await editor.press('Control+a');await page.getByRole('button',{name:'Bold (Ctrl+B)',exact:true}).click();await page.getByRole('button',{name:'Italic (Ctrl+I)',exact:true}).click();await page.getByLabel('Font size in points',{exact:true}).fill('18');await page.getByLabel('Font size in points',{exact:true}).press('Tab');
  await expect(editor.locator('strong em,em strong')).toContainText('Words with emphasis');
  const downloadEvent=page.waitForEvent('download');await page.getByRole('button',{name:'Save',exact:true}).click();const download=await downloadEvent;
  const bytes=readFileSync((await download.path())!);await page.locator('#file-input').setInputFiles({name:'Styled.odt',mimeType:'application/vnd.oasis.opendocument.text',buffer:bytes});await expect(editor.locator('strong em,em strong')).toContainText('Words with emphasis');
  await expect(page.locator('#saved-state')).toHaveText('Imported · save as ODT');await page.keyboard.press('Control+n');await expect(page.getByRole('dialog')).toBeVisible();await page.getByRole('button',{name:'Cancel',exact:true}).click();await expect(editor).toContainText('Words with emphasis');
});

