"""Regression checks derived from DavkaWriter 7's own PDF output.
No proprietary font files or user documents are copied into the repository.
"""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor/folio-dwd'))
import dwd2docx as converter
from dwdread import _bdr

class FidelityTests(unittest.TestCase):
    def tearDown(self):
        converter.OPTIONS.pop('installed_fonts', None)

    def test_unicode_face_keeps_original_point_size_without_substitute_calibration(self):
        st = dict(font='Davka David', size=18, bold=False)
        converter.OPTIONS['installed_fonts'] = {'Davka David':'UniDavka David'}
        self.assertEqual(converter.word_font(st['font']), 'UniDavka David')
        self.assertEqual(converter.word_size(st), 36)
        self.assertEqual(converter.width_fix(st), (100, {}))
        self.assertEqual(converter.word_font('Davka Rashi'), 'Noto Rashi Hebrew')

    def test_signed_border_width_still_prints(self):
        self.assertIn('w:val="single"', converter._cell_border(_bdr((0,-4,4,0)), 'left'))
        self.assertIn('w:sz="8"', converter._cell_border(_bdr((0,-4,4,0)), 'left'))
        self.assertIn('w:val="nil"', converter._cell_border(_bdr((0,0,0,0)), 'left'))

    def test_printed_gray_percentage(self):
        info = [[dict(shade='C0C0C0',shade_pct=91,top=_bdr((0,4,4,0)),left=_bdr((0,-4,4,0))), {}], [{}]]
        xml = converter.table_xml_cells({}, {'row_heights':[0]}, [[[]]], [1000], info, False)
        self.assertIn('w:fill="E8E8E8"',xml)
        self.assertIn('<w:start w:val="single"',xml)

if __name__ == '__main__':
    unittest.main()
