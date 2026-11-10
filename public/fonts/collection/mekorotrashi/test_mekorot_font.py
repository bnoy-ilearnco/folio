"""Shaping regression checks. Requires fonttools and uharfbuzz."""
import unittest, unicodedata
from pathlib import Path
import uharfbuzz as hb
from fontTools.ttLib import TTFont
ROOT=Path(__file__).resolve().parents[1];DIR=ROOT/'public/fonts/collection/mekorotrashi'
if not DIR.exists():DIR=Path(__file__).resolve().parent
ORIGINAL=TTFont(DIR/'Mekorot-Rashi.ttf');FIXED=TTFont(DIR/'Mekorot-Rashi-Folio.ttf')
def shape(text,fixed=True):
    p=DIR/('Mekorot-Rashi-Folio.ttf' if fixed else 'Mekorot-Rashi.ttf');font=hb.Font(hb.Face(p.read_bytes()));font.scale=(1000,1000)
    b=hb.Buffer();b.add_str(text);b.guess_segment_properties();hb.shape(font,b)
    order=FIXED.getGlyphOrder() if fixed else ORIGINAL.getGlyphOrder();x=0;out=[]
    for i,pos in zip(b.glyph_infos,b.glyph_positions):
        out.append((order[i.codepoint],x+pos.x_offset,pos.y_offset,pos.x_advance));x+=pos.x_advance
    return out
class Niqqud(unittest.TestCase):
    def test_original_ink_and_advances_preserved(self):
        for n in ORIGINAL.getGlyphOrder():
            self.assertEqual(ORIGINAL['glyf'][n].compile(ORIGINAL['glyf']),FIXED['glyf'][n].compile(FIXED['glyf']),n)
            self.assertEqual(ORIGINAL['hmtx'][n],FIXED['hmtx'][n],n)
        self.assertEqual(ORIGINAL['GSUB'].compile(ORIGINAL),FIXED['GSUB'].compile(FIXED))
    def test_all_base_letters_have_composite_and_rafe_anchors(self):
        letters={FIXED.getBestCmap()[c] for c in range(0x5d0,0x5eb)}
        for i in [1,4]:self.assertTrue(letters<=set(FIXED['GPOS'].table.LookupList.Lookup[i].SubTable[0].BaseCoverage.glyphs))
    def test_all_niqqud_present_and_zero_advance(self):
        for c in list(range(0x5b0,0x5be))+[0x5bf,0x5c1,0x5c2,0x5c7]:
            n=FIXED.getBestCmap()[c];self.assertEqual(FIXED['hmtx'][n][0],0);self.assertEqual(FIXED['GDEF'].table.GlyphClassDef.classDefs[n],3)
    def test_meteg_attaches_left_of_vowel_on_every_letter(self):
        cmap=FIXED.getBestCmap()
        for base in range(0x5d0,0x5eb):
            for vowel in list(range(0x5b0,0x5b9))+[0x5bb,0x5c7]:
                text=chr(base)+chr(vowel)+'\u05bc\u05bd';glyphs=shape(text)
                meteg=next(g for g in glyphs if g[0]=='uni05BD');v=next(g for g in glyphs if g[0]==cmap[vowel]);ink=FIXED['glyf'][v[0]]
                self.assertLess(meteg[1]+22,v[1]+ink.xMin,text)
                self.assertEqual(sum(g[3] for g in glyphs),ORIGINAL['hmtx'][cmap[base]][0])
    def test_rafe_clears_base_and_holam(self):
        cmap=FIXED.getBestCmap()
        for base in range(0x5d0,0x5eb):
            s=shape(chr(base)+'\u05bf');rafe=next(g for g in s if g[0]=='rafe');self.assertGreater(rafe[2]+715,FIXED['glyf'][cmap[base]].yMax)
        s=shape('בֹֿ');rafe=next(g for g in s if g[0]=='rafe');holam=next(g for g in s if g[0]==cmap[0x5b9]);self.assertGreater(rafe[2]+715,holam[2]+853)
    def test_canonical_order_and_final_kaf(self):
        for text in ['שָּֽׁ','שָּֽׁ','בֳּֽ','בֹֿ','ךָ','ךְ','רוּחַ']:
            self.assertEqual(shape(text),shape(unicodedata.normalize('NFD',text)))
        for text in ['ךָ','ךְ','רוּחַ']:self.assertEqual(shape(text),shape(text,False))
if __name__=='__main__':unittest.main()
