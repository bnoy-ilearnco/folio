"""Synthetic MFC DavkaWriter 550 fixture; contains no user document content.
Run with Python from the project root. The fixture is independently serialized
from the documented fields consumed by Folio's reader, including back-references.
"""
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'vendor/folio-dwd'))
from davkamap import encode_exact
out = bytearray()
mapping = [None, 'document']
def b(*v): out.extend(bytes(v))
def h(v): out.extend(struct.pack('<H', v))
def i(*v): out.extend(struct.pack('<'+'i'*len(v), *v))
def string(v):
    assert len(v)<255
    b(len(v));out.extend(v)
def obj(cls, writer):
    h(0xffff);h(1);h(len(cls));out.extend(cls.encode())
    mapping.append(cls);idx=len(mapping);mapping.append(idx)
    writer(idx)
    return idx
def style(idx, hebrew=False):
    name=b'Davka David' if hebrew else b'Times New Roman'
    b(0x82 if hebrew else 0x10, 0, 0, 1, 0, len(name), 0)
    i(0xffffff,0x663300,0,1800 if hebrew else 1200)
    out.extend(name);b(0)
def ruler(idx, rtl=False):
    b(2 if rtl else 0,1,0,1 if rtl else 0,0)
    i(100,0,0,0,0);b(0);i(800);b(1,1,0,0,0,1)
    i(0xffffff,0);b(*([0]*4),1,4,1,4);i(100);b(0,0)
def docpiece():h(1);i(0)
def paragraph(idx, text, rtl):
    docpiece();h(0);b(0,0,0,0,0,0);i(0,0)
    h(he_ruler if rtl else en_ruler);b(0);h(idx);b(0);h(1)
    def run(_):
        docpiece();b(2);h(he_style if rtl else en_style)
        string(encode_exact(text)[0] if rtl else text.encode())
    obj('CStyleRun',run)
i(550);h(0);i(0,0,0);string(b'');string(b'');b(0,0);i(0)
for _ in range(4):string(b'')
i(0,0);b(0,0);i(1440,1440,1440,1440,0,0,0)
h(2)
he_style=obj('CDocStyle',lambda idx:style(idx,True))
en_style=obj('CDocStyle',style)
i(0,0);h(2)
he_ruler=obj('CDocRuler',lambda idx:ruler(idx,True))
en_ruler=obj('CDocRuler',ruler)
for _ in range(5):h(0) # page objects, boxes, borders, power text, power paragraphs
i(0);i(1);b(0,0)
for _ in range(2):i(720);b(0,0);h(0)
i(0,0,*([0]*4));b(0,0);i(0,0,*([0]*3));style(None);i(0,0);b(*([0]*6))
docpiece();h(2)
obj('CParagraph',lambda idx:paragraph(idx,'שָׁלוֹם עוֹלָם',True))
obj('CParagraph',lambda idx:paragraph(idx,'English 123',False))
docpiece();h(0);i(0)
path=Path(__file__).with_name('hebrew.dwd');path.write_bytes(out)
from dwdread import parse
parsed=parse(out)
assert len(parsed['main'])==2
print('Wrote',path,len(out),'bytes')
