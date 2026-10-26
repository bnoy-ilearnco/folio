import {it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {bookHe,categoryHe,numberHe,referenceHe,sectionHe,libraryTextHe,commentaryHe} from '../src/library-he';
import type {LibraryBook} from '../src/library';
const books:LibraryBook[]=JSON.parse(readFileSync('docs/library-manifest.json','utf8')).books;
it('cleans known markup artifacts and preserves the cross-shaped diagram',()=>{
 expect(libraryTextHe('חפצו (.b)בבבל /b> ויהודה(qb) ועשוי כזה x')).toBe('חפצו בבבל  ויהודה ועשוי כזה ×');
 expect(libraryTextHe('בְּרֵאשִׁ֖ית')).toBe('בְּרֵאשִׁ֖ית');
 expect(libraryTextHe('[כָּזֶה c ]')).toBe('[כָּזֶה ⊂ ]');
});

it('localizes titles and categories for the entire bundled catalog',()=>{
 expect(books).toHaveLength(277);
 for(const book of books){
  for(const value of [bookHe(book),categoryHe(book.category)])expect(value).not.toMatch(/[a-z]/i);
  expect(categoryHe(book.category)).not.toBe('ספרים נוספים');
 }
});
it('formats chapters, daf sides and commentary references without Latin letters',()=>{
 expect(numberHe(15)).toBe('ט״ו');expect(numberHe(16)).toBe('ט״ז');expect(numberHe(115)).toBe('קט״ו');
 expect(sectionHe('2a','Bavli')).toBe('דף ב׳ ע״א');expect(sectionHe('2b','Bavli')).toBe('דף ב׳ ע״ב');
 expect(referenceHe('1:2:3',books[0])).toBe('פרק א׳, פסוק ב׳, פירוש ג׳');
 expect(referenceHe('2b:1:2',books.find(b=>b.title==='Berakhot')!)).toBe('דף ב׳ ע״ב, קטע א׳, פירוש ב׳');
 const mishnah=books.find(b=>b.title==='Mishnah Berakhot')!;
 expect(referenceHe('1:2',mishnah)).toBe('פרק א׳, משנה ב׳');
 expect(referenceHe('1:2:3',mishnah)).toBe('פרק א׳, משנה ב׳, פירוש ג׳');
 expect(commentaryHe(mishnah)).toBe('ברטנורא');
});
