"""Spec-driven reader for DavkaWriter .dwd files (MFC CArchive serialization).

Reads the whole file sequentially from byte 0 to EOF, following the load code of davwrite.exe as
documented in /home/claude/re/spec/{document,text,objects,structure}.md:

  CWrdDoc header (version, TOC settings, summary, page-size flags) -> printer block (margins, DEVNAMES,
  DEVMODE) -> CDocSpec: style list, label sheets, ruler list, page-object array, text-box array,
  page-border array, PowerStyle arrays, page numbering, default CHeader/CFooter, footnote defaults,
  main CParagList, second CParagList, master pages -> EOF.

The MFC object map is kept exactly (class and object indices share one counter, index 1 = the document
object), so back-references (styles, rulers, table rows, text boxes shared between arrays) resolve to the
same Python object.  Every version branch from the spec is implemented (files 390..550; 0x7AB7 =
"protected" 550).

read(d) returns a Doc with the raw object model; to_D(doc) maps it onto the dict the converter uses
(see dwdparse.parse); parse(d) does both.
"""
import struct

__all__ = ['parse', 'read', 'to_D', 'DwdError']


class DwdError(ValueError):
    pass


FIELD_CLASS = {3: 'CFieldGraphic', 7: 'CFieldPageNo', 9: 'CFieldNoteMarker', 10: 'CFieldFootnote',
               11: 'CFieldDateTime', 14: 'CFieldAutoShape', 15: 'CFieldCurvyText', 21: 'CFieldTextBox',
               22: 'CFieldFileName', 23: 'CFieldHusk', 24: 'CFieldMergeField', 25: 'CFieldTextLink',
               26: 'CFieldChapterTitle'}

_S16 = struct.Struct('<H')
_I32 = struct.Struct('<i')
_U32 = struct.Struct('<I')


class Obj(dict):
    """A loaded MFC object: a dict with its class name in 'cls' and its map index in 'idx'."""
    __slots__ = ()

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


class Reader:
    def __init__(self, d):
        self.d = bytes(d)
        self.n = len(self.d)
        self.p = 0
        self.v = 0
        self.map = [None, None]          # map index -> class name (str) or object (Obj); [1] = the document
        self.styles = {}                 # map index -> style Obj (every CDocStyle/CMyStyle loaded anywhere)
        self.rulers = {}                 # map index (or synthetic key for v<9 inline rulers) -> ruler Obj
        self.tables = []                 # every CTable, in load order
        self.inline_ruler_key = 1 << 30

    # ------------------------------------------------------------------ primitives
    def need(self, k):
        if self.p + k > self.n:
            raise DwdError('unexpected end of file at %#x (need %d bytes)' % (self.p, k))

    def u8(self):
        self.need(1)
        x = self.d[self.p]; self.p += 1
        return x

    def i8(self):
        x = self.u8()
        return x - 256 if x > 127 else x

    def u16(self):
        self.need(2)
        x = _S16.unpack_from(self.d, self.p)[0]; self.p += 2
        return x

    def i32(self):
        self.need(4)
        x = _I32.unpack_from(self.d, self.p)[0]; self.p += 4
        return x

    def u32(self):
        self.need(4)
        x = _U32.unpack_from(self.d, self.p)[0]; self.p += 4
        return x

    def dws(self, k):
        self.need(4 * k)
        x = list(struct.unpack_from('<%di' % k, self.d, self.p)); self.p += 4 * k
        return x

    def f64(self):
        self.need(8)
        x = struct.unpack_from('<d', self.d, self.p)[0]; self.p += 8
        return x

    def raw(self, k):
        if k < 0:
            raise DwdError('negative length %d at %#x' % (k, self.p))
        self.need(k)
        x = self.d[self.p:self.p + k]; self.p += k
        return x

    def count(self):
        """MFC ReadCount (CObList/CObArray element count)."""
        k = self.u16()
        if k == 0xffff:
            k = self.u32()
        if k > self.n:
            raise DwdError('implausible element count %d at %#x' % (k, self.p))
        return k

    def strlen(self):
        """AfxReadStringLength -> (length in characters, unicode?)"""
        k = self.u8()
        if k < 0xff:
            return k, False
        k = self.u16()
        if k == 0xfffe:
            k, _ = self.strlen()
            return k, True
        if k < 0xffff:
            return k, False
        k = self.u32()
        if k == 0xffffffff:
            raise DwdError('64-bit string length at %#x' % self.p)
        return k, False

    def cstr(self):
        """CString as bytes (single-byte code page as stored; Unicode strings are converted to cp1252)."""
        k, uni = self.strlen()
        if uni:
            return self.raw(2 * k).decode('utf-16-le', 'replace').encode('cp1252', 'replace')
        return self.raw(k)

    # ------------------------------------------------------------------ MFC object map
    def obj(self, expect=None):
        """CArchive::ReadObject: returns None (NULL), an existing Obj (back-reference) or a new Obj."""
        at = self.p
        tag = self.u16()
        if tag == 0x7fff:
            obtag = self.u32()
        else:
            obtag = ((tag & 0x8000) << 16) | (tag & 0x7fff)
        if not obtag & 0x80000000:
            if obtag == 0:
                return None
            if obtag >= len(self.map) or self.map[obtag] is None or isinstance(self.map[obtag], str):
                raise DwdError('bad back-reference %d at %#x' % (obtag, at))
            o = self.map[obtag]
            return o
        if tag == 0xffff:
            self.u16()                                   # schema
            ln = self.u16()
            name = self.raw(ln).decode('latin-1')
            self.map.append(name)                        # the class gets a map index too
        else:
            ci = obtag & 0x7fffffff
            if ci >= len(self.map) or not isinstance(self.map[ci], str):
                raise DwdError('bad class index %d at %#x' % (ci, at))
            name = self.map[ci]
        fn = getattr(self, 'r_' + name, None)
        if fn is None:
            raise DwdError('unknown class %s at %#x' % (name, at))
        o = Obj(cls=name, idx=len(self.map), at=at)
        self.map.append(o)                               # registered before its data (self references)
        fn(o)
        o['end'] = self.p
        return o

    def oblist(self, expect=None):
        return [self.obj(expect) for _ in range(self.count())]

    # ------------------------------------------------------------------ CLogStyle (CDocStyle, CMyStyle)
    def logstyle(self, o=None):
        v = self.v
        o = Obj() if o is None else o
        h = self.raw(7 if v >= 0x204 else 6)
        f0, f1, o['ul_pattern'], o['ul_thick'], o['position'], nlen = h[:6]
        o['f0'], o['f1'] = f0, f1
        o['f6'] = h[6] if len(h) == 7 else 0
        if f1 & 0x04 and v >= 0xba:
            o['outline_type'] = self.u8()
            if v >= 0xc4:
                o['shadow_orient'] = self.u8(); o['shadow_depth'] = self.i32()
            o['outline_thick'] = self.i32(); o['white_thick'] = self.i32()
        o['bg'] = self.u32(); o['fg'] = self.u32()
        o['spacing'] = self.i32(); size = self.i32()
        if v < 0x88:
            size *= 100
        o['size100'] = size
        if v >= 0x196 and f1 & 1:
            o['nikud_color'] = self.u32(); o['trop_color'] = self.u32()
        o['font'] = self.raw(nlen).decode('latin-1')
        if v >= 0x15a:
            o['pwr_name'] = self.raw(self.u8()).decode('latin-1')
        if v >= 0x1fa and f1 & 1:
            self.i32()
        return o

    def r_CDocStyle(self, o):
        self.logstyle(o)
        self.styles[o['idx']] = o
    r_CMyStyle = r_CDocStyle

    # ------------------------------------------------------------------ CLogRuler (CDocRuler)
    def logruler(self, o=None):
        v = self.v
        o = Obj() if o is None else o
        b = self.raw(5)
        o['align'], o['prop'], o['x10'], o['rtl'] = b[0], b[1], b[2], b[3]
        nt = b[4]
        o['tab_types'] = list(self.raw(nt))
        sp = self.i32(); before = self.i32()
        if v < 0x88:
            sp *= 50 if b[1] else 100
            before *= 100
        o['spacing'] = sp; o['space_before'] = before
        o['first'], o['start'], o['end_margin'] = self.dws(3)
        o['exact'] = self.u8() if v >= 0x1b4 else 0
        o['space_after'] = self.i32() if v >= 0x128 else 0
        o['tab_pos'] = self.dws(nt) if nt else []
        if v >= 0x1a0:
            o['widow'], o['orphan'], o['keep_together'] = self.raw(3)
        if v >= 0x1aa:
            o['x13b'], o['x13c'] = self.raw(2)
        nc = 1
        o['col_gap'] = 0; o['col_widths'] = []
        if v > 2:
            nc = self.i8()
            nc = 1 if nc <= 0 else min(nc, 5) if nc > 5 else nc
            if nc > 1:
                o['col_line'] = self.u8()
                o['col_x14c'] = list(self.raw(2)) if v >= 4 else [0, 1]
                o['col_x14e'] = self.u8() if v >= 12 else 0
                o['col_gap'] = self.u16()
                o['col_widths'] = [self.u16() for _ in range(nc)]
        o['ncols'] = nc
        if v >= 7:
            o['shade_color'] = self.u32(); o['border_color'] = self.u32()
            o['borders'] = list(self.raw(4))             # top, left, bottom, right
            o['border_space'] = list(self.raw(4))
        else:
            o['shade_color'] = 0xffffff; o['border_color'] = 0; o['borders'] = [0, 0, 0, 0]; o['border_space'] = [1, 4, 1, 4]
        o['shade_pct'] = self.i32() if v >= 9 else 100
        if v >= 0x15a:
            o['pwr_name'] = self.raw(self.u8()).decode('latin-1')
        if v >= 0x1f0:
            o['x164'] = self.u8()
        return o

    def r_CDocRuler(self, o):
        self.logruler(o)
        self.rulers[o['idx']] = o
    r_CLogRuler = r_CDocRuler

    # ------------------------------------------------------------------ text: CDocPiece, CParagList, CParagraph, CStyleRun
    def docpiece(self):
        owner = self.obj()
        if owner is not self.map[1]:
            raise DwdError('CDocPiece owner is not the document at %#x' % self.p)
        x = self.i32()
        return owner, x

    def r_CParagList(self, o):
        self.docpiece()
        o['paras'] = [self.obj('CParagraph') for _ in range(self.count())]

    def paraglist_inline(self):
        """CParagList::Serialize called directly (main text and second flow): no tag."""
        o = Obj(cls='CParagList', idx=None, at=self.p)
        self.r_CParagList(o)
        o['end'] = self.p
        return o

    def logpagenum(self):
        return dict(start=self.i32(), b0=self.i8(), b1=self.i8())

    def r_CParagraph(self, o):
        v = self.v
        self.docpiece()
        o['pobjs'] = [self.obj('CParagObject') for _ in range(self.count())] if v >= 10 else []
        o['b90'] = self.u8() if v >= 4 else 0
        pg = hdr = ftr = fn = tr = 0
        if v > 4:
            pg = self.u8(); hdr = self.u8(); ftr = self.u8()
            if v > 5:
                fn = self.u8()
            if v > 55:
                tr = self.u8()
        o['pgflag'] = pg
        o['header'] = self.obj('CHeader') if hdr else None
        o['footer'] = self.obj('CFooter') if ftr else None
        o['fnset'] = self.obj('CFootnoteSet') if (v > 5 and fn) else None
        o['row'] = self.obj('CTableRow') if (v > 55 and tr) else None
        o['pagenum'] = self.logpagenum() if pg else None
        if v >= 526:
            mask = self.u32()
            o['chap_titles'] = [(i, self.cstr(), self.cstr()) for i in range(8) if mask >> i & 1]
        if v >= 536:
            o['x1c0'] = self.i32()
        if v < 9:
            r = self.logruler(Obj(cls='CLogRuler', idx=None, at=self.p))
            k = self.inline_ruler_key; self.inline_ruler_key += 1
            r['key'] = k
            self.rulers[k] = r
            o['ruler'] = r
        else:
            o['ruler'] = self.obj('CLogRuler')
        o['dropcap'] = None
        if v >= 126 and self.u8():
            b = self.raw(6)
            o['dropcap'] = dict(flags=list(b), style=self.obj('CMyStyle') if b[0] else None)
        o['num'] = None
        if v >= 146:
            if self.obj() is not o:                      # owner paragraph (self back-reference)
                raise DwdError('paragraph numbering owner is not the paragraph at %#x' % self.p)
            mode = self.u8()
            if mode:
                b = self.raw(5)
                num = dict(mode=mode, x14=b[0], char=b[1], fmt=b[2], prefix=b[3], suffix=b[4])
                num['style'] = self.obj('CMyStyle')
                num['x30'] = self.i32(); num['x38'] = self.u8()
                num['start'] = self.i32(); num['number'] = self.i32()
                if v >= 166:
                    num['level'] = self.i32()
                if v >= 176:
                    num['x44'] = self.i32(); num['x19'] = self.u8(); num['x1c'] = self.i32()
                o['num'] = num
        o['runs'] = [self.obj('CStyleRun') for _ in range(self.count())]

    def field(self):
        t = self.u8()
        f = self.obj(FIELD_CLASS[t]) if t in FIELD_CLASS else None
        return t, f

    def r_CStyleRun(self, o):
        self.docpiece()
        o['ftype'], o['field'] = self.field() if self.v >= 2 else (2, None)
        o['style'] = self.obj('CMyStyle')
        o['text'] = self.cstr()

    # ------------------------------------------------------------------ objects
    def drawobj(self, o):
        o['x'], o['y'] = self.dws(2)
        o['mode'] = self.i32()
        o['wrap'] = self.dws(4) if o['mode'] else None
        o['oid'] = self.i32() if self.v >= 14 else None
        o['ftype'], o['field'] = self.field()

    def r_CParagObject(self, o):
        self.drawobj(o)

    def r_CPageObject(self, o):
        self.drawobj(o)
        o['pages'] = self.dws(3)                         # CPageRange: first, last, ??

    def textlink(self):
        t = dict(target=self.cstr())
        if self.v < 256:
            self.raw(56)
        else:
            self.raw(60)                                 # 2 x CPartPosn
        if self.v >= 456:
            t['type'] = self.u8(); self.u8(); self.u32()
        return t

    def r_CFieldGraphic(self, o):
        v = self.v
        if v >= 556:
            o['xml'] = self.cstr()
        k = self.u32()
        if v >= 13:
            self.u32()
        o['data'] = self.raw(k)
        o['crop'] = self.dws(8) if self.i32() else None
        o['link'] = None
        if v >= 206 and self.i32():
            o['link'] = self.textlink()
        if v >= 216:
            a, b, has = self.dws(3)
            o['x2b8'] = (a, b)
            o['objborder'] = self.dws(5 if v >= 276 else 4) if has else None

    def r_CFieldAutoShape(self, o):
        f = self.dws(14)
        o['vals'] = f
        o['w'], o['h'], o['shape'] = f[0], f[1], f[2]
        o['subtype'] = f[6]
        o['line_color'] = f[8]; o['fill_color'] = f[10]; o['color2'] = f[11]; o['flags'] = f[13]

    def r_CFieldCurvyText(self, o):
        o['vals'] = self.dws(14)
        o['text'] = self.cstr()
        o['font'] = self.cstr().decode('latin-1')
        o['size'] = self.f64()
        o['xb8'], o['flags'] = self.dws(2)
        if self.v >= 76:
            o['x98'] = self.dws(3)
        if self.v >= 96:
            o['x64'] = self.i32()

    def r_CFieldTextBox(self, o):
        v = self.v
        o['row'] = self.obj('CTableRow')
        o['x10'] = self.i32()
        o['next'] = self.obj('CFieldTextBox')
        o['prev'] = self.obj('CFieldTextBox')
        o['x60'] = self.i32()
        o['x14'] = self.dws(2) if v >= 286 else [0, 5]
        if v >= 316:
            k = self.i32()
            if not 0 <= k <= 64:
                raise DwdError('implausible text-box count %d at %#x' % (k, self.p))
            o['x20'] = [self.dws(3) for _ in range(k)]
            o['x3c'] = self.i32()
            if v >= 326:
                o['x40'] = list(self.raw(2))

    def r_CFieldPageNo(self, o):
        pass
    r_CFieldFileName = r_CFieldPageNo
    r_CFieldHusk = r_CFieldPageNo

    def r_CFieldChapterTitle(self, o):
        o['level'] = self.i32()

    def r_CFieldFootnote(self, o):
        o['vals'] = self.dws(4)

    def r_CFieldDateTime(self, o):
        o['vals'] = self.dws(2); o['fmt1'] = self.cstr(); o['fmt2'] = self.cstr()

    def r_CFieldMergeField(self, o):
        o['name'] = self.cstr(); o['vals'] = self.dws(2); o['x28'] = self.cstr()

    def r_CFieldTextLink(self, o):
        o['display'] = self.cstr()
        o['link'] = self.textlink() if self.i32() else None

    def notedivider(self):
        dv = dict(vals=self.dws(4))
        if self.v >= 156 and self.u8():
            dv['title'] = (self.u8(), self.i32(), self.cstr(), self.logstyle())
        if self.v >= 386:
            dv['x3c'] = (self.u8(), self.i32(), self.i32())
        return dv

    def r_CFieldNoteMarker(self, o):
        o['fmt'] = self.dws(2)
        o['divider'] = self.notedivider()
        o['opts'] = self.dws(3)
        o['vals'] = self.dws(3)
        o['chars'] = list(self.raw(4))

    # ------------------------------------------------------------------ structure: tables, header/footer, footnotes, borders
    def cell(self):
        c = dict(shade=self.u32(), shade_pct=self.u8(), pad=list(self.raw(4)))
        c['at'] = self.p
        c['list'] = self.obj('CParagList')
        c['hmerge'] = self.i8(); c['valign'] = self.u8()
        c['top'] = (self.u32(), self.i8(), self.u8(), self.u8())
        c['left'] = (self.u32(), self.i8(), self.u8(), self.u8())
        c['style'] = None
        if self.v >= 246 and self.u8():
            c['style'] = (self.u8(), self.u8(), self.cstr(), self.logstyle())
        return c

    def r_CTableRow(self, o):
        o['height'] = self.i32()
        o['cells'] = [self.cell() for _ in range(self.count())]
        o['table'] = self.obj('CTable')

    def r_CTable(self, o):
        o['nrows'], o['ncols'], o['x10'] = self.dws(3)
        o['x14'] = self.u8()
        if not 0 <= o['ncols'] < 4096:
            raise DwdError('implausible table column count %d at %#x' % (o['ncols'], self.p))
        o['colpos'] = [self.u16() for _ in range(o['ncols'] + 1)]
        o['rows'] = self.oblist('CTableRow')
        self.tables.append(o)

    def hdrftr(self, o):
        o['distance'] = self.i32()
        o['use_in_middle'] = self.u8(); o['even_odd'] = self.u8()
        o['list'] = self.obj('CParagList')
        o['list2'] = self.obj('CParagList') if o['even_odd'] else None
        return o

    def r_CHeader(self, o):
        self.hdrftr(o)
    r_CFooter = r_CHeader

    def footnoteset(self, o):
        o['numbering'] = self.dws(2)
        o['divider'] = self.notedivider()
        o['options'] = self.dws(3)
        o['style'] = self.logstyle()
        o['outdent'] = self.dws(2)
        o['chars'] = list(self.raw(6))
        return o

    def r_CFootnoteSet(self, o):
        self.footnoteset(o)

    def r_CPageBorder(self, o):
        o['type'] = self.i32()
        o['name'] = self.cstr()
        o['vals'] = self.dws(10)
        o['kind'] = 0; o['border'] = None
        if o['type'] != 1 and self.v >= 476:
            o['kind'] = self.u8()
            if o['kind']:
                o['border'] = self.obj()

    def r_CBorderSimple(self, o):
        o['x8'], o['xc'] = self.dws(2)
        o['sides'] = list(self.raw(4))
        o['style'] = self.i32()
        o['width'] = self.f64()
        o['color'] = self.u32()
        o['x24'] = self.i32()

    def r_CBorderShapes(self, o):
        o['vals'] = self.dws(23)
        o['sides'] = list(self.raw(4))
        o['dist'] = self.i32()

    def r_CMasterPage(self, o):
        o['name'] = self.cstr()
        o['x30'], o['x34'] = self.dws(2)
        o['range'] = self.dws(3)
        o['data'] = self.raw(self.u32())

    # ------------------------------------------------------------------ PowerStyles (CPwrStyleText / CPwrStyleParag)
    def hotkey(self):
        return (self.u8(), self.u16())

    def r_CPwrStyleText(self, o):
        """CPwrStyleText::Serialize (140243b00): name, 2 x CLogStyle, 4 DWORDs, 2 hotkeys (BYTE + WORD)."""
        o['name'] = self.cstr()
        o['style1'] = self.logstyle(); o['style2'] = self.logstyle()
        o['vals'] = self.dws(4)
        o['hotkeys'] = (self.hotkey(), self.hotkey())

    def r_CPwrStyleParag(self, o):
        """From CPwrStyleParag::Serialize (140243e40): name, CLogRuler, 6 DWORDs, optional text-PowerStyle
        name / CLogStyle / numbering options, hotkey.  The optional parts never occur in the samples (111
        paragraph PowerStyles, all with the three flags 0), so their layout is from the code only."""
        v = self.v
        o['name'] = self.cstr()
        o['ruler'] = self.logruler()
        a440, a444, a448, has_style, has_num, has_str = self.dws(6)
        o['vals'] = (a440, a444, a448)
        if has_str:
            o['text_pwr'] = self.cstr()
        if has_style:
            o['style'] = self.logstyle()
        if has_num:
            if v < 0x196:
                o['num_blob'] = self.raw(self.u32())
            else:
                o['num'] = self.parnumopts()
        o['hotkey'] = self.hotkey()

    def parnumopts(self):
        """CParNumbering options serialized for a paragraph PowerStyle (v >= 406): the same record as a
        paragraph's numbering (mode byte, 5 bytes, style, 26 bytes) but with the style inline (CLogStyle)."""
        mode = self.u8()
        if not mode:
            return dict(mode=0)
        b = self.raw(5)
        num = dict(mode=mode, x14=b[0], char=b[1], fmt=b[2], prefix=b[3], suffix=b[4])
        num['style'] = self.logstyle()
        num['x30'] = self.i32(); num['x38'] = self.u8()
        num['start'] = self.i32(); num['number'] = self.i32()
        num['level'] = self.i32()
        num['x44'] = self.i32(); num['x19'] = self.u8(); num['x1c'] = self.i32()
        return num

    # ------------------------------------------------------------------ small embedded records
    def tocsettings(self):
        k = self.i32(); self.i32()
        if not 0 <= k <= 64:
            raise DwdError('implausible TOC level count %d' % k)
        for _ in range(k):
            self.logstyle(); self.logstyle(); self.dws(2); self.logruler(); self.dws(3)

    def label(self):
        a, b = self.dws(2)
        dims = struct.unpack('<10d', self.raw(80))
        k = self.i32(); self.i32(); self.u16(); self.i32()
        if not 0 <= k <= 16:
            raise DwdError('implausible label record count %d' % k)
        self.raw(24 * k)
        return dict(cols=a, rows=b, dims=dims)

    # ------------------------------------------------------------------ top level
    def read(self):
        doc = Obj(cls='CWrdDoc', idx=1, at=0)
        self.map[1] = doc
        ver = self.u32()
        doc['version_raw'] = ver
        doc['protected'] = ver == 0x7ab7
        v = 0x226 if ver == 0x7ab7 else ver
        if v > 0x230 or v < 1:
            raise DwdError('unsupported DavkaWriter file version %d' % ver)
        self.v = doc['version'] = v
        if v >= 0x218:
            for _ in range(self.count()):
                self.tocsettings()
        if v >= 0x164:
            self.dws(2)
        if v >= 0x16e:
            self.i32()
        if v >= 0x178:
            self.cstr(); self.cstr()
        self.i8()
        if v >= 9:
            self.u8()
        if v >= 0x19:
            doc['wrapped_in_front'] = self.i32()
        if v >= 0x1be:
            doc['summary'] = [self.cstr() for _ in range(4)]
        doc['custom_size'] = None
        if v >= 0x1d2 and self.i32():
            doc['custom_size'] = tuple(self.dws(2))
        if v >= 0x222:
            doc['match_underlines'] = self.i32()
        # printer / page-setup block
        if v >= 8:
            doc['mirror'] = self.i8(); doc['oversize_hf'] = self.i8()
        doc['margins_tlbr'] = tuple(self.dws(4)) if v > 0 else (1440, 1440, 1440, 1440)
        n1 = self.u32()
        doc['devnames'] = doc['devmode'] = b''
        if n1:
            n2 = self.u32()
            doc['devnames'] = self.raw(n1); doc['devmode'] = self.raw(n2)
        doc['half_page'] = tuple(self.dws(2)) if v >= 0x18c else (0, 0)
        # ------------------------------------------------------------- CDocSpec
        doc['style_list'] = self.oblist('CDocStyle')
        doc['labels'] = []
        if v >= 0x13c:
            k = self.i32(); self.i32()
            if not 0 <= k <= 16:
                raise DwdError('implausible label count %d at %#x' % (k, self.p))
            doc['labels'] = [self.label() for _ in range(k)]
        doc['page_objects'] = []
        doc['ruler_list'] = []
        if v >= 0x10a:
            doc['ruler_list'] = self.oblist('CDocRuler')
            doc['page_objects'] = self.oblist('CPageObject')
        else:
            if v >= 10:
                doc['page_objects'] = self.oblist('CPageObject')
            if v >= 9:
                doc['ruler_list'] = self.oblist('CDocRuler')
        doc['text_boxes'] = self.oblist('CFieldTextBox') if v >= 0xf6 else []
        doc['page_borders'] = self.oblist('CPageBorder') if v >= 0x150 else []
        doc['pwr_text'] = doc['pwr_parag'] = []
        if v >= 0x15a:
            doc['pwr_text'] = self.oblist('CPwrStyleText')
            doc['pwr_parag'] = self.oblist('CPwrStyleParag')
        doc['x8b4'] = self.i32()
        doc['header'] = doc['footer'] = doc['fnset'] = None
        if v >= 5:
            doc['pagenum'] = self.logpagenum()
            doc['header'] = self.hdrftr(Obj(cls='CHeader', idx=None, at=self.p))
            doc['footer'] = self.hdrftr(Obj(cls='CFooter', idx=None, at=self.p))
        if v >= 6:
            doc['fnset'] = self.footnoteset(Obj(cls='CFootnoteSet', idx=None, at=self.p))
        doc['main'] = self.paraglist_inline()
        doc['second'] = self.paraglist_inline() if v >= 6 else None
        doc['master_pages'] = []
        if v >= 0x1fa:
            flags = self.i32()
            if v >= 0x222 and flags & 1:
                doc['master_pages'] = [self.oblist('CMasterPage') for _ in range(4)]
        if self.p != self.n:
            raise DwdError('document ends at %#x but the file is %#x bytes' % (self.p, self.n))
        doc['map_size'] = len(self.map)
        return doc


def read(d):
    r = Reader(d)
    doc = r.read()
    doc['reader'] = r
    return doc


# ====================================================================== mapping onto the converter's dict
PAPER_SIZES = {1: 'Letter', 2: 'Letter', 5: 'Legal', 9: 'A4', 10: 'A4'}
# Windows DMPAPER_* -> (name, (width, height) twips, portrait)
DM_PAPER = {1: ('Letter', (12240, 15840)), 2: ('Letter', (12240, 15840)), 3: ('Tabloid', (15840, 24480)),
            4: ('Ledger', (24480, 15840)), 5: ('Legal', (12240, 20160)), 6: ('Statement', (7920, 12240)),
            7: ('Executive', (10440, 15120)), 8: ('A3', (16838, 23811)), 9: ('A4', (11906, 16838)),
            10: ('A4', (11906, 16838)), 11: ('A5', (8391, 11906)), 12: ('B4', (14570, 20636)), 13: ('B5', (10319, 14570)),
            14: ('Folio', (12240, 18720)), 15: ('Quarto', (12189, 15591)), 17: ('11x17', (15840, 24480)), 18: ('Note', (12240, 15840))}


def _style(o):
    f0, f1 = o['f0'], o['f1']
    return dict(flags=f0, size=o['size100'] / 100.0, font=o['font'], color=o['fg'] & 0xffffff,
                bold=bool(f0 & 0x80), italic=bool(f0 & 0x10), underline=bool(f1 & 0x40),
                # extra keys
                hebrew=bool(f0 & 0x02), boxed=bool(f0 & 0x40), inverse=bool(f0 & 0x20), overline=bool(f0 & 0x08),
                strike=bool(f0 & 0x04), caps=bool(f0 & 0x01), small_caps=bool(f1 & 0x80),
                word_underline=bool(f1 & 0x20), low_underline=bool(f1 & 0x10), outlined=bool(f1 & 0x04),
                dot_under=bool(o['f6'] & 0x80), position=o['position'], bg=o['bg'] & 0xffffff,
                letter_spacing=o['spacing'], ul_thick=o['ul_thick'], ul_pattern=o['ul_pattern'],
                nikud_color=o.get('nikud_color'), trop_color=o.get('trop_color'), pwr_name=o.get('pwr_name', ''))


def _ruler(o):
    prop = bool(o['prop'])
    mode = 1 if prop else (2 if o['exact'] else 0)
    nc = o['ncols']
    return dict(align=o['align'], rtl=o['rtl'], border_bottom=o['borders'][2] == 1, ncols=nc,
                col_widths=list(o['col_widths']) if nc > 1 else [],
                pct=o['spacing'] if prop else 100, ls_mode=mode,
                ls_pt=o['spacing'] / 100.0 if not prop else 0,
                ind1=o['first'], ind2=o['start'], rind=o['end_margin'],
                tabs=list(zip(o['tab_types'], o['tab_pos'])),
                # extra keys
                space_before=o['space_before'] / 100.0, space_after=o['space_after'] / 100.0,
                exact=o['exact'], keep_together=o.get('keep_together', 0), widow=o.get('widow', 0),
                orphan=o.get('orphan', 0), col_gap=o['col_gap'], borders=list(o['borders']),
                border_color=o['border_color'], border_space=list(o['border_space']),
                shade_color=o['shade_color'], shade_pct=o['shade_pct'], pwr_name=o.get('pwr_name', ''),
                # +0x14C: a line between the columns (the only column flag that matches DavkaWriter's prints)
                col_sep=bool(nc > 1 and (o.get('col_x14c') or [0])[0]))


def _image_info(blob):
    """(format, pixel width, pixel height, dpi x, dpi y) of a picture blob, as far as it can be told."""
    try:
        if blob[:2] == b'BM' and len(blob) >= 54:
            w, h = struct.unpack_from('<ii', blob, 18)
            xp, yp = struct.unpack_from('<ii', blob, 38)
            return 'bmp', w, abs(h), (xp or 3780) * 0.0254, (yp or 3780) * 0.0254
        if blob[:4] == b'\x89PNG' and len(blob) >= 24:
            w, h = struct.unpack_from('>II', blob, 16)
            return 'png', w, h, 96, 96
        if blob[:3] == b'GIF' and len(blob) >= 10:
            w, h = struct.unpack_from('<HH', blob, 6)
            return 'gif', w, h, 96, 96
        if blob[:2] == b'\xff\xd8':
            dx = dy = 96
            i = 2
            while i + 9 < len(blob):
                if blob[i] != 0xff:
                    break
                m = blob[i + 1]
                ln = struct.unpack_from('>H', blob, i + 2)[0]
                if m == 0xe0 and blob[i + 4:i + 9] == b'JFIF\x00':
                    unit = blob[i + 11]
                    x, y = struct.unpack_from('>HH', blob, i + 12)
                    if unit == 1 and x and y:
                        dx, dy = x, y
                    elif unit == 2 and x and y:
                        dx, dy = x * 2.54, y * 2.54
                if m in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                    h, w = struct.unpack_from('>HH', blob, i + 5)
                    return 'jpeg', w, h, dx, dy
                i += 2 + ln
            return 'jpeg', 0, 0, dx, dy
        if blob[:4] == b'LEAD' and len(blob) >= 20:
            dx, dy = struct.unpack_from('<HH', blob, 7)
            w, h = struct.unpack_from('<HH', blob, 16)
            return 'lead', w, h, dx or 96, dy or 96
        if blob[:4] == b'\xd7\xcd\xc6\x9a':
            return 'wmf', 0, 0, 96, 96
    except struct.error:
        pass
    return 'unknown', 0, 0, 96, 96


class Mapper:
    def __init__(self, doc):
        self.doc = doc
        self.R = doc['reader']
        self.tables = {}                 # id(CTable Obj) -> converter table dict
        self.paras = {}                  # id(CParagraph Obj) -> converter paragraph dict

    # ---------------------------------------------------------------- paragraphs
    def para_list(self, lst):
        """CParagList Obj (or None) -> list of converter paragraphs."""
        if lst is None:
            return []
        return [self.para(p) for p in lst['paras']]

    def para(self, po):
        k = id(po)
        if k in self.paras:
            return self.paras[k]
        ru = po['ruler']
        rkey = ru['idx'] if ru is not None and ru.get('idx') is not None else (ru.get('key') if ru else None)
        num = po['num']
        p = dict(pos=po['at'], ruler=rkey, flag=num['mode'] if num else 0, runs=[], list=None, objects=[], end=po['end'])
        self.paras[k] = p
        if num and num['mode'] in (1, 2):
            suffix = '.'
            for c in (num['prefix'], num['suffix']):
                if c in (0x28, 0x29, 0x2e):
                    suffix = chr(c)
                    break
            p['list'] = dict(hebrew=num['fmt'] == 5, suffix=suffix, number=num['number'],
                             mode=num['mode'], fmt=num['fmt'], char=num['char'], prefix=num['prefix'],
                             suffix_char=num['suffix'], start=num['start'], level=num.get('level'),
                             style=num['style']['idx'] if num['style'] else None)
        brk = po['b90'] | (po['pgflag'] << 8)
        if brk:
            p['brk'] = brk
        if po['pagenum']:
            p['pagenum'] = po['pagenum']
        if po['dropcap']:
            p['dropcap'] = dict(po['dropcap'], style=po['dropcap']['style']['idx'] if po['dropcap']['style'] else None)
        extras = []
        if po['header'] is not None:
            p['section_header'] = self.hf(po['header'])
            extras.append(p['section_header'][0])
        if po['footer'] is not None:
            p['section_footer'] = self.hf(po['footer'])
            extras.append(p['section_footer'][0])
        if extras:
            p['extras'] = extras
        if po['fnset'] is not None:
            p['footnote_settings'] = True
        for ob in po['pobjs']:
            o = self.drawn(ob)
            if o is not None:
                o['anchor'] = 'paragraph'
                p['objects'].append(o)
        inline = []
        for r in po['runs']:
            st = r['style']
            run = dict(style=st['idx'] if st is not None else None, text=r['text'])
            f = r['field']
            if f is not None:
                fc = f['cls']
                run['field_class'] = fc
                if fc == 'CFieldPageNo':
                    run['field'] = 'CFieldPageNo'
                elif fc == 'CFieldTextLink':
                    run['link'] = (f['link'] or {}).get('target', b'').decode('latin-1').strip()
                    if not run['text']:
                        run['text'] = f['display']
                elif fc in ('CFieldFootnote', 'CFieldNoteMarker'):
                    run['note'] = fc
                elif fc in ('CFieldGraphic', 'CFieldAutoShape', 'CFieldCurvyText', 'CFieldTextBox'):
                    o = self.field_obj(dict(x=0, y=0, kind=r['ftype'], page=None), f)
                    run['object'] = o
                    inline.append(o)
            p['runs'].append(run)
        if inline:
            p['inline_objects'] = inline
        if po['row'] is not None:
            t = self.table(po['row']['table'])
            if t is not None:
                p['table'] = t
                p['row'] = t['_rowobjs'].index(po['row']) if po['row'] in t['_rowobjs'] else None
        return p

    def hf(self, h):
        return (self.para_list(h['list']), self.para_list(h['list2']) if h['list2'] is not None else None)

    # ---------------------------------------------------------------- tables
    def table(self, to):
        if to is None:
            return None
        k = id(to)
        if k in self.tables:
            return self.tables[k]
        rows_o = [r for r in to['rows'] if r is not None]
        real = rows_o[:to['nrows']] if to['nrows'] > 0 else rows_o
        t = dict(rows=[], row_heights=[], pos=real[0]['at'] if real else to['at'], end=to['end'],
                 _rowobjs=real, nrows=to['nrows'], ncols=to['ncols'], colpos=list(to['colpos']),
                 bounds=list(to['colpos'][1:]), width=to['colpos'][-1] if len(to['colpos']) > 1 else None)
        self.tables[k] = t
        cells_info = []
        for ro in real:
            cells = [self.para_list(c['list']) if c['list'] is not None else None for c in ro['cells']]
            if cells and cells[-1] is None:
                cells.pop()
            t['rows'].append([c or [] for c in cells])
            t['row_heights'].append(ro['height'])
            cells_info.append([dict(shade='%06X' % _rgb(c['shade']), shade_pct=c['shade_pct'], pad=c['pad'],
                                    hmerge=c['hmerge'], valign=c['valign'],
                                    top=_bdr(c['top']), left=_bdr(c['left'])) for c in ro['cells']])
        # bottom borders of the last real row live in the dummy row
        if len(rows_o) > len(real):
            cells_info.append([dict(top=_bdr(c['top'])) for c in rows_o[len(real)]['cells']])
        t['cells'] = cells_info
        c0 = real[0]['cells'][0] if real and real[0]['cells'] else None
        if c0 is not None:
            t['fill'] = '%06X' % _rgb(c0['shade'])
            t['borders'] = [c0['shade_pct']] + c0['pad'][:3]
        else:
            t['fill'] = 'FFFFFF'; t['borders'] = [100, 0, 0, 0]
        return t

    # ---------------------------------------------------------------- drawn objects and fields
    def drawn(self, ob):
        o = dict(x=ob['x'], y=ob['y'], kind=ob['ftype'], start=ob['at'], end=ob['end'],
                 wrap_mode=ob['mode'], wrap=ob['wrap'], oid=ob['oid'])
        if 'pages' in ob:
            o['page'] = ob['pages'][0]
            o['pages'] = list(ob['pages'])
        else:
            o['page'] = None
        if ob['field'] is None:
            return o
        return self.field_obj(o, ob['field'])

    def field_obj(self, o, f):
        fc = f['cls']
        o['field_class'] = fc
        if fc == 'CFieldAutoShape':
            o.update(w=f['w'], h=f['h'], shape=f['shape'], line=f['subtype'] == 0x15, subtype=f['subtype'],
                     line_color=f['line_color'], fill_color=f['fill_color'], shape_flags=f['flags'])
        elif fc == 'CFieldCurvyText':
            v = f['vals']
            # vals[5] = the shape the text is set on (0 straight, 9 arch up ...), vals[6] = the arc's angle in
            # degrees, vals[7] = rotation (degrees), vals[10] (+0x50) = text colour, vals[11] (+0x60) = shadow colour
            o.update(text=f['text'], font=f['font'], size=f['size'] if 4 <= f['size'] <= 400 else 24.0,
                     curve=v[5], arc=v[6], rot=v[7], text_color=v[10], shadow_color=v[11])
            o['flexi'] = flexi_fields(f)
        elif fc == 'CFieldGraphic':
            self.picture(o, f)
        elif fc == 'CFieldTextBox':
            self.textbox(o, f)
        return o

    def picture(self, o, f):
        blob = f['data']
        fmt, pw, ph, dx, dy = _image_info(blob)
        o['picture'] = True
        o['image'] = blob
        o['image_format'] = fmt
        o['crop'] = f['crop']
        o['px'] = (pw, ph)
        o['dpi'] = (dx, dy)
        # displayed size = native size (pixels / the picture's own resolution) x the per-mille scale of the
        # crop/scale record (+0x224, +0x228), times the cropped fraction (+0x214..+0x220, per mille)
        if pw and ph:
            sx = sy = 1000
            fx = fy = 1.0
            c = f['crop']
            if c is not None:
                if 1 <= c[4] <= 100000 and 1 <= c[5] <= 100000:
                    sx, sy = c[4], c[5]
                if 0 <= c[1] < c[3] <= 1000 and 0 <= c[0] < c[2] <= 1000:
                    fx, fy = (c[3] - c[1]) / 1000.0, (c[2] - c[0]) / 1000.0
            o['w'] = int(pw * 1440 / dx * sx / 1000 * fx)
            o['h'] = int(ph * 1440 / dy * sy / 1000 * fy)
        if fmt == 'bmp':
            o['bmp'] = blob

    def textbox(self, o, f):
        row = f['row']
        o['box'] = f
        o['paras'] = []
        o['width'] = 2000; o['width_known'] = False; o['height'] = None; o['border'] = False
        if row is None:
            return
        to = row['table']
        if to is not None and len(to['colpos']) > 1:
            o['width'] = to['colpos'][-1]
            o['width_known'] = True
        o['height'] = abs(row['height']) if row['height'] else None
        o['height_raw'] = row['height']
        c0 = row['cells'][0] if row['cells'] else None
        if c0 is not None:
            o['paras'] = self.para_list(c0['list'])
            # the box is a 1-column table: its frame is the cell's top/left border, the right border is the
            # left border of the (dummy) edge cell and the bottom border the top border of the dummy row
            right = row['cells'][1]['left'] if len(row['cells']) > 1 else c0['left']
            bottom = c0['top']
            if to is not None and len(to['rows']) > 1 and to['rows'][1] is not None and to['rows'][1]['cells']:
                bottom = to['rows'][1]['cells'][0]['top']
            o['box_border'] = dict(top=_bdr(c0['top']), left=_bdr(c0['left']), right=_bdr(right), bottom=_bdr(bottom))
            o['border'] = any(b[1] > 0 for b in (c0['top'], c0['left'], right, bottom))
            o['fill'] = '%06X' % _rgb(c0['shade'])
            o['shade_pct'] = c0['shade_pct']
            o['pad'] = c0['pad']
        o['linked_next'] = f['next'] is not None
        o['linked_prev'] = f['prev'] is not None
        # a table placed inside the box: its placeholder paragraphs carry p['table'] (handled by the converter)

    # ---------------------------------------------------------------- document
    def build(self):
        doc = self.doc
        R = self.R
        styles = {k: _style(o) for k, o in R.styles.items()}
        rulers = {}
        for k, o in R.rulers.items():
            rulers[k] = _ruler(o)
        page = self.page()
        main = self.para_list(doc['main'])
        # a header/footer with any text keeps all its paragraphs (blank lines set its height and so its place
        # on the page); one made only of blank lines is no header at all
        has_text = lambda ps: any(r['text'].strip(b' \t\xa0') or r.get('field') or r.get('object') for p in ps for r in p['runs'])
        nonblank = lambda ps: list(ps) if has_text(ps) else []
        header = footer = []
        hdr2 = ftr2 = None
        if doc['header'] is not None:
            h1, hdr2 = self.hf(doc['header'])
            header = nonblank(h1)
        if doc['footer'] is not None:
            f1, ftr2 = self.hf(doc['footer'])
            footer = nonblank(f1)
        # a header/footer that starts at the first paragraph of the text is the document's header/footer
        if main and not header and main[0].get('section_header'):
            header = nonblank(main[0]['section_header'][0])
        if main and not footer and main[0].get('section_footer'):
            footer = nonblank(main[0]['section_footer'][0])
        objects = [self.drawn(ob) for ob in doc['page_objects'] if ob is not None]
        tables = [self.table(t) for t in R.tables]
        tables = [t for t in tables if t is not None]
        notes = self.para_list(doc['second']) if doc['second'] is not None else []
        footnotes = number_footnotes(main, tables, notes)
        D = dict(styles=styles, rulers=rulers, page=page, main=main, objects=objects, header=header,
                 footer=footer, tables=tables, reader='spec', version=doc['version'],
                 protected=doc['protected'], notes=notes, footnotes=footnotes, wrapped_in_front=bool(doc.get('wrapped_in_front')),
                 header_even=nonblank(hdr2) if hdr2 else None, footer_even=nonblank(ftr2) if ftr2 else None,
                 summary=[s.decode('latin-1') for s in doc.get('summary', [])] if not doc['protected'] else [],
                 master_pages=[dict(name=m['name'].decode('latin-1'), range=m['range'], data=m['data'])
                               for arr in doc['master_pages'] for m in arr if m is not None],
                 powerstyles=dict(text=[o['name'].decode('latin-1') for o in doc['pwr_text'] if o is not None],
                                  parag=[o['name'].decode('latin-1') for o in doc['pwr_parag'] if o is not None]))
        return D

    def page(self):
        doc = self.doc
        t, l, b, r = doc['margins_tlbr']
        border_margins = None
        has_border = False
        borders = []
        for pb in doc['page_borders']:
            if pb is None:
                continue
            # the border's distances from the page edge are stored like the page margins, top, left, bottom,
            # right (a RECT at +0x0C read as +0x10, +0x0C, +0x18, +0x14): -> left, top, right, bottom
            v = pb['vals']
            bm4 = (v[1], v[0], v[3], v[2])
            if border_margins is None:
                border_margins = bm4
            bo = pb['border']
            if bo is not None and bo['cls'] in ('CBorderSimple', 'CBorderShapes'):
                has_border = True
            borders.append(dict(type=pb['type'], kind=pb['kind'], margins=bm4, name=pb.get('name') or '',
                                border_class=bo['cls'] if bo is not None else None,
                                width=bo.get('width') if bo is not None else None,
                                style=bo.get('style') if bo is not None else None,
                                # CBorderShapes: a band of small shapes; its line colour is the 6th value
                                color=(bo.get('color') if bo['cls'] == 'CBorderSimple' else bo['vals'][5]) if bo is not None else None,
                                sides=list(bo['sides']) if bo is not None else [1, 1, 1, 1],
                                band=bo.get('dist') if bo is not None else None))
        if all(200 <= x <= 4000 for x in (t, l, b, r)):
            margins = (l, t, r, b)
        else:
            margins = border_margins or (1080, 1080, 1080, 1080)
        dm = doc['devmode']
        paper = 'Letter'
        orient = 1
        paper_code = None
        form = ''
        dims = None
        size_twips = None
        if len(dm) >= 0x34:
            fields = struct.unpack_from('<I', dm, 0x28)[0] if len(dm) >= 0x2c else 0
            orient, paper_code, plen, pwid = struct.unpack_from('<hhhh', dm, 0x2c)
            dims = (pwid, plen)
            if len(dm) >= 102:
                form = dm[70:102].split(b'\0')[0].decode('latin-1')
            # Which paper DavkaWriter prints on (checked against its own prints): dmPaperSize when the DEVMODE says
            # it is set (DM_PAPERSIZE) - it wins over a stale form name (a "Letter" form with paper 9 printed on
            # A4, an "A4" form with paper 1 on Letter); then dmPaperLength/Width (DM_PAPERLENGTH|DM_PAPERWIDTH);
            # then the form name.
            if fields & 0x2 and paper_code in DM_PAPER:
                paper, size_twips = DM_PAPER[paper_code]
            elif fields & 0xc == 0xc and 500 <= pwid <= 6000 and 500 <= plen <= 6000:
                paper = form or 'Custom'
                size_twips = (int(round(pwid * 1440 / 254.0)), int(round(plen * 1440 / 254.0)))
            else:
                fl = form.lower()
                if fl == 'a4' or fl.startswith('a4 '):
                    paper, size_twips = DM_PAPER[9]
                elif fl.startswith('legal'):
                    paper, size_twips = DM_PAPER[5]
                elif paper_code in DM_PAPER:
                    paper, size_twips = DM_PAPER[paper_code]
            if paper in ('Letter', 'A4', 'Legal'):
                size_twips = None          # (the converter's own table)
        if doc.get('custom_size') and all(500 <= v <= 50000 for v in doc['custom_size']):
            size_twips = tuple(doc['custom_size'])       # CDocSpec custom page size (twips) wins
            paper = 'Custom'
        # a picture border from DavkaWriter's border library ("Bereishis", "Apple and honey"...): only its name is
        # in the file
        art = next(((b['name'].decode('latin-1') if isinstance(b['name'], bytes) else b['name']) for b in borders if b['type'] == 1 and b['name']), None)
        return dict(margins=margins, border=has_border, border_margins=border_margins, paper=paper, border_art=art,
                    end=0, margins_file=(l, t, r, b), orientation=orient, paper_code=paper_code, paper_form=form,
                    paper_dims_mm10=dims, paper_twips=size_twips, landscape=orient == 2,
                    custom_size=doc['custom_size'], page_borders=borders, mirror=doc.get('mirror', 0),
                    half_page=doc['half_page'],
                    header_distance=doc['header']['distance'] if doc['header'] else None,
                    footer_distance=doc['footer']['distance'] if doc['footer'] else None)


def number_footnotes(main, tables, notes):
    """The second text flow holds the footnotes: each starts with a paragraph carrying a CFieldNoteMarker run.
    The k-th footnote reference (a CFieldFootnote run) in reading order - main text, with each table's cells
    where the table starts - belongs to the k-th footnote.  Sets run['footnote_id'] = k (1-based) on both the
    reference and the note's marker and returns [[paragraphs of footnote 1], ...]."""
    fns = []
    for p in notes:
        if any(r.get('note') == 'CFieldNoteMarker' for r in p['runs']):
            fns.append([p])
        elif fns:
            fns[-1].append(p)
    if not fns:
        return []
    refs = []
    seen = set()
    def walk(ps):
        for p in ps:
            t = p.get('table')
            if t is not None:
                if id(t) not in seen:
                    seen.add(id(t))
                    for row in t['rows']:
                        for cell in row:
                            walk(cell)
                continue
            for r in p['runs']:
                if r.get('note') == 'CFieldFootnote':
                    refs.append(r)
    walk(main)
    for k, r in enumerate(refs[:len(fns)]):
        r['footnote_id'] = k + 1
        for q in fns[k]:
            for m in q['runs']:
                if m.get('note') == 'CFieldNoteMarker':
                    m['footnote_id'] = k + 1
    return fns[:len(refs)]


FLEXI_EFFECTS = ('normal', 'outline', 'filled')
FLEXI_3D = ('gradient', 'block', 'shadow')


def flexi_fields(f):
    """Every setting of a FlexiText (CFieldCurvyText), named as DavkaWriter's "FlexiText Settings" dialog names them.
    The mapping of the record's fields (by their place in the object, +0x..) to the dialog comes from DavkaWriter's
    own code that fills the dialog from the object and back (CCurvyTextDlg, CAdvancedCurvyDlg):
      14 DW  +0x38 spacing, +0x3C stretch (%), +0x4C outline thickness, +0x68 3D angle (degrees), +0x6C 3D depth,
             +0x80 path shape (0 straight; 1-3 growth, 4-6 shrinking, 7 rise, 8 drop, 9-10 arc, 11-12 upper arc,
             13-15 arc; the dialog's "Angle of ..." per shape), +0x84 the path's angle, +0x88 rotate (degrees,
             counter-clockwise), +0x8C slant ??, +0x90 skew ?? (the two are in the dialog's order, unconfirmed),
             +0x50 colour, +0x60 3D colour, +0x74 outline colour, +0x7C "gradient to" colour   (COLORREF)
      text (DavkaWriter's encoding for a Hebrew font), font, size (points, double), +0xB8 (always 0)
      flags  bit 0 +0x14 Hebrew, 1 +0x20 bold, 2 +0x24 italic, 3 +0x48 outline drawn, 4 +0x70 filled,
             5 +0x78 gradient, 6 +0x54 3D, 7 +0x58 3D shadow, 8 +0x9C, 9 +0xA0, 10 +0xA4 (Advanced options ??),
             11 +0xA8 3D on the path, 12 +0xAC 3D angle relative to each letter's rotation, 13 +0xB0, 14 +0xB4 (??)
      v76    +0x98 multi-line justification (a list index), flags2 (bit 0 +0x28 underline, 1 +0x2C (Advanced ??),
             2 +0x5C 3D gradient), +0x94 "Fix" (stored twice the dialog's value)
      v96    +0x64 3D gradient's second colour
    Effects: Normal (no outline), Outline (+0x48), Filled (+0x48 and +0x70).  3D: Block unless +0x58 (Shadow) or
    +0x5C (Gradient).  Placement and Fixed are the drawn object's own (CDrawObject wrap mode)."""
    v = f['vals']
    fl = f.get('flags') or 0
    x98 = f.get('x98') or [0, 0, 0]
    f2 = x98[1]
    bit = lambda n: bool(fl >> n & 1)
    outline, filled = bit(3), bit(4)
    return dict(
        text=f['text'], font=f['font'], size=f['size'] if 4 <= f['size'] <= 400 else 24.0,
        heb=bit(0), bold=bit(1), italic=bit(2), underline=bool(f2 & 1), adv2c=bool(f2 & 2),
        spacing=v[0], stretch=v[1] if 10 <= v[1] <= 1000 else 100,
        effect=FLEXI_EFFECTS[2 if outline and filled else 1 if outline else 0],
        color=v[10], outline_color=v[12], outline_w=v[2], gradient=bit(5), gradient_to=v[13],
        d3=bit(6), d3_type=FLEXI_3D[2 if bit(7) else 0 if f2 & 4 else 1], d3_color=v[11],
        d3_color2=f.get('x64', 0xFFFFFF), d3_depth=v[4], d3_angle=v[3], d3_relative=bit(12),
        path=v[5], angle=v[6], rotate=v[7], slant=v[8], skew=v[9], justify=x98[0], fix=x98[2] // 2 if x98[2] else 0,
        path3d=bit(11), adv=[bit(8), bit(9), bit(10), bit(13), bit(14)], xb8=f.get('xb8', 0))


def _rgb(c):
    """COLORREF (0x00BBGGRR) -> 0xRRGGBB"""
    return ((c & 0xff) << 16) | (c & 0xff00) | ((c >> 16) & 0xff)


def _bdr(b):
    color, width, l1, l2 = b
    # Negative widths are still printed (verified against DavkaWriter 7 PDF
    # output); treating the sign as hidden drops most worksheet grid lines.
    return dict(color='%06X' % _rgb(color), width=width, hidden=width == 0, line1=l1, line2=l2)


def to_D(doc):
    return Mapper(doc).build()


def parse(d):
    return to_D(read(d))
