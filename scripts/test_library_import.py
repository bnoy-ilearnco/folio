import unittest
from build_library import parse_book, normalize


class LibraryImportTests(unittest.TestCase):
    def test_hebrew_leadin_does_not_import_english_translation(self):
        raw = '''# Rashi on Genesis

רש"י על בראשית

Version (He): Test edition (Segments: 1, License: Public Domain)

## Chapter 1

###### Rashi on Genesis 1:1:1

[https://torahapp.org/share/book/Rashi/r/1:1:1](https://torahapp.org/share/book/Rashi/r/1:1:1)


**בראשית.** אמר רבי יצחק.

פסקה שנייה בעברית.


בראשית IN THE BEGINNING — English translation starting in Hebrew.
'''.encode()
        title, version, license_name, passages = parse_book(raw, 'Rashi on Genesis')
        self.assertEqual(passages, [('1:1:1', 'בראשית. אמר רבי יצחק.\n\nפסקה שנייה בעברית.')])
        self.assertEqual(license_name, 'Public Domain')

    def test_missing_source_passages_fail_import(self):
        raw = b'# Test\nVersion (He): Test (Segments: 1, License: unknown)\n\n## Chapter 1\n'
        with self.assertRaisesRegex(ValueError, 'differs from declared'):
            parse_book(raw, 'Test')

    def test_search_normalizes_niqqud_and_final_forms(self):
        self.assertEqual(normalize('מֶלֶךְ'), normalize('מלכ'))


if __name__ == '__main__': unittest.main()
