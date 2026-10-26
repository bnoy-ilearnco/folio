"""Parser for DavkaWriter .dwd files (MFC CArchive serialization).

parse(d) uses the spec-driven reader (dwdread.py), which reads the file sequentially from byte 0 to EOF
following DavkaWriter's own load code (all file versions 390..550).  Only if that reader raises does it
fall back to the older heuristic parser below (_parse_heuristic); D['reader'] records which one was used
('spec' or 'heuristic', with the spec reader's error in D['reader_error']).

The heuristic parser was reverse-engineered from sample files. Layout of the parts we use:
  CDocStyle   : character styles (font, size, flags)   referenced by object index
  CDocRuler   : paragraph formats (alignment, RTL, line spacing %, indent)
  CPageObject : floating objects (text boxes / tables / autoshapes) with x, y (twips) and page
  CPageBorder : page margins + border
  main flow   : one long list of CParagraph objects, each with CStyleRun runs
"""
import struct, re

def read_cstring(d, p):
    n = d[p]; p += 1
    if n == 0xff:
        n = struct.unpack_from('<H', d, p)[0]; p += 2
        if n == 0xfffe:
            raise ValueError('unicode cstring at %x' % p)
        if n == 0xffff:
            n = struct.unpack_from('<I', d, p)[0]; p += 4
    return d[p:p+n], p + n

def find_class(d, name):
    m = re.search(rb'\xff\xff..' + struct.pack('<H', len(name)) + re.escape(name), d, re.S)
    return m

# ---------------------------------------------------------------- styles
def parse_styles(d):
    m = find_class(d, b'CDocStyle')
    p = m.end()
    # object-map index of the first style = class index + 1. The class index is
    # whatever tag later style objects use (0x80nn).
    styles = []
    first = True
    cls = None
    while True:
        if not first:
            if d[p+1] != 0x80:
                break
            tag = d[p] | 0x00
            if cls is None:
                cls = tag
            elif tag != cls:
                break
            p += 2
        first = False
        flags = d[p]
        f2 = d[p+1]
        nlen = struct.unpack_from('<H', d, p+5)[0]
        color = struct.unpack_from('<I', d, p+11)[0]
        size = struct.unpack_from('<I', d, p+19)[0]
        name = d[p+23:p+23+nlen].decode('latin-1')
        styles.append(dict(flags=flags, size=size/100.0, font=name, color=color & 0xffffff,
                           bold=bool(flags & 0x80), italic=bool(flags & 0x10), underline=bool(f2 & 0x40)))
        p = p + 23 + nlen + 1
    base = (cls or 2) + 1
    return {base + i: s for i, s in enumerate(styles)}

# ---------------------------------------------------------------- rulers
def parse_rulers(d):
    """Paragraph formats. Each record: align, ?, ?, rtl, ntabs, ntabs tab-type bytes, pct, ?, ind1, ind2,
    ..., ntabs tab positions (int32), 4 bytes, then a fixed 24-byte tail starting 05 01 ff ff ff 00."""
    m = find_class(d, b'CDocRuler')
    if not m:
        return {}
    p = m.end()
    rulers = {}
    idx = None
    first = True
    while p < len(d) - 40:
        if not first:
            if d[p+1] != 0x80:
                break
            tag = struct.unpack_from('<H', d, p)[0] & 0x7fff
            if idx is None:
                idx = tag            # class index
            elif tag != idx:
                break
            p += 2
        # the record ends with a column block: 05, ncols, [6 bytes + ncols WORD widths if ncols > 1],
        # then ff ff ff 00 and 18 more bytes
        mk = -1
        for cand in re.finditer(rb'\x05([\x01-\x08])', d[p:p + 400]):
            n = cand.group(1)[0]
            q = p + cand.end() + (6 + 2 * n if n > 1 else 0)
            if d[q:q + 4] == b'\xff\xff\xff\x00':
                mk = p + cand.start(); ncols = n; tail_start = q
                break
        if mk < 0:
            break
        b = d[p:mk]
        widths = [struct.unpack_from('<H', d, mk + 8 + 2 * k)[0] for k in range(ncols)] if ncols > 1 else []
        nt = b[4] if b[4] < 20 else 0
        o = 5 + nt
        tabs = []
        for k in range(nt):
            pos = struct.unpack_from('<i', b, len(b) - 4 - 4 * (nt - k))[0]
            tabs.append((b[5 + k], pos))
        tail = d[tail_start:tail_start + 22]
        rulers.setdefault('_list', []).append(dict(
            align=b[0], rtl=b[3], border_bottom=tail[10] == 1, ncols=ncols, col_widths=widths,
            pct=struct.unpack_from('<I', b, o)[0] if b[1] == 1 else 100,
            ls_mode=b[1],                                   # 1 = multiple (pct), 0 = at least, 2 = exactly
            ls_pt=struct.unpack_from('<I', b, o)[0] / 100.0 if b[1] != 1 else 0,
            ind1=struct.unpack_from('<i', b, o + 8)[0],      # first-line start (absolute)
            ind2=struct.unpack_from('<i', b, o + 12)[0],     # margin at start of line
            rind=struct.unpack_from('<i', b, o + 16)[0],     # margin at end of line
            tabs=tabs))
        p = tail_start + 22
        first = False
    lst = rulers.pop('_list', [])
    base = (idx or 0) + 1
    return {base + i: r for i, r in enumerate(lst)}

# ---------------------------------------------------------------- paragraphs
PARA_RE = re.compile(rb'(?:\xff\xff..\x0a\x00CParagraph|.[\x80-\xff])\x01\x00\x01\x00\x00\x00(?:(.{12})\xff\xff\xff\xff|([\x01-\x09])\x00(?=\xff\xff..\x0c\x00CParagObject|.[\x80-\xff](?!\x01\x00\x01\x00\x00\x00)))', re.S)
PARA_END_RE = re.compile(rb'\x00{10}\xff\xff\xff\xff')

def parse_field(d, s, e, kind):
    """Parse a field object body (after the x,y,0,id,kind header) between s and e."""
    body = d[s:e]
    o = {}
    if kind == 0x0e:
        mm = re.match(rb'(?:\xff\xff..\x0f\x00CFieldAutoShape|.[\x80-\xff])(.{4})(.{4})(.{4})(.{8})(.{4})(.{4})', body, re.S)
        if mm:
            o['w'], o['h'], o['shape'] = [struct.unpack('<i', g)[0] for g in mm.groups()[:3]]
            o['line'] = struct.unpack('<i', mm.group(6))[0] == 0x15    # drawn as a single line
    elif kind == 0x0f:
        o.update(parse_curvy(body))
    elif kind == 0x03:                  # CFieldGraphic: a picture (a Windows bitmap, or LEAD-compressed which can't be decoded)
        o['picture'] = True
        q = _skip_tag(d, s)
        if q is not None and d[q+8:q+10] == b'BM':
            n = struct.unpack_from('<I', d, q)[0]
            bmp = d[q+8:q+8+n]
            if len(bmp) >= 54:
                bw, bh = struct.unpack_from('<ii', bmp, 18)
                xppm, yppm = struct.unpack_from('<ii', bmp, 38)
                xppm = xppm or 3780; yppm = yppm or 3780
                o['bmp'] = bmp
                o['w'], o['h'] = int(bw * 1440 * 39.3701 / xppm), int(abs(bh) * 1440 * 39.3701 / yppm)
                # after the data: 3 int32, then scale x/y (1000 = 100%) and the pixels-per-inch the picture is placed at
                t = q + 8 + n
                if t + 28 <= len(d):
                    sx, sy, rx, ry = struct.unpack_from('<iiii', d, t + 12)
                    if 50 <= rx <= 5000 and 50 <= ry <= 5000 and 10 <= sx <= 100000 and 10 <= sy <= 100000:
                        o['w'] = int(bw * 1440 / rx * sx / 1000)
                        o['h'] = int(abs(bh) * 1440 / ry * sy / 1000)
                return o
        mm = re.search(rb'LEAD\x00\x00\x00(..)(..)\x00{5}(..)(..)', body, re.S)
        if mm:
            dx, dy, pw, ph = [struct.unpack('<H', g)[0] for g in mm.groups()]
            dx, dy = dx or 96, dy or 96
            o['w'], o['h'] = pw * 1440 // dx, ph * 1440 // dy
    return o

def parse_curvy(body):
    """CFieldCurvyText: decorative (arched) title text: <text cstring><font cstring><double size>."""
    for fm in re.finditer(rb'([\x03-\x40])([A-Z][ -~]{2,62})', body):
        n = fm.group(1)[0]
        name = fm.group(2)[:n]
        if len(name) != n or not re.match(rb'^[A-Za-z][A-Za-z0-9 \-]+$', name):
            continue
        f = fm.start()
        for t in range(f - 1, max(f - 260, -1), -1):
            if body[t] == f - t - 1 and f - t - 1 > 0:
                size = struct.unpack_from('<d', body, f + 1 + n)[0] if f + 9 + n <= len(body) else 24.0
                if not (4 <= size <= 400):
                    size = 24.0
                return dict(text=body[t+1:f], font=name.decode('latin-1'), size=size)
    return {}


def skip_tag(d, p, name):
    if d[p:p+2] == b'\xff\xff':
        n = struct.unpack_from('<H', d, p+4)[0]
        assert d[p+6:p+6+n] == name, (hex(p), d[p+6:p+6+n])
        return p + 6 + n
    assert d[p+1] & 0x80, hex(p)
    return p + 2

def parse_paragraph(d, m):
    p = m.end()
    pobjs = []
    if m.group(2) is not None:          # paragraph with embedded objects
        seg_s = p
        # embedded object (first one): [class def or tag] x y flag [16 extra if flag==1] id kind field...
        om = re.match(rb'\xff\xff..\x0c\x00CParagObject', d[seg_s:seg_s+20])
        start = seg_s + (om.end() if om else 2)
        x, y, z = struct.unpack_from('<iii', d, start)
        hdr = 16 if z == 0 else 32
        kind = d[start + hdr]
        search_from = p
        if kind == 0x03:                # a picture carries its data length: skip the data before looking for the end
            q = _skip_tag(d, start + hdr + 1)
            if q is not None:
                n = struct.unpack_from('<I', d, q)[0]
                if 0 < n < len(d):
                    search_from = q + 8 + n
        em = PARA_END_RE.search(d, search_from, search_from + 4000)
        if not em:
            raise ValueError('no paragraph end')
        seg_e = em.start()
        o = dict(x=x, y=y, kind=kind, anchor='paragraph')
        o.update(parse_field(d, start + hdr + 1, seg_e, kind))
        pobjs.append(o)
        p = em.end()
    return parse_tail(d, p, m.start(), pobjs)

def parse_tail(d, p, pos, pobjs=()):
    """The part of a paragraph after its object/table header: ruler, id, list flag, runs."""
    ruler, b1, pid, flag = struct.unpack_from('<HBHB', d, p); p += 6
    para = dict(pos=pos, ruler=ruler, flag=flag, runs=[], list=None, objects=list(pobjs))
    if flag in (1, 2):
        para['list'] = parse_list(d[p:p+33]); p += 33
    elif flag != 0:
        raise ValueError('para flag %d at %x' % (flag, p))
    nruns = struct.unpack_from('<H', d, p)[0]; p += 2
    if nruns > 2000:
        raise ValueError('bad run count')
    for _ in range(nruns):
        p = skip_tag(d, p, b'CStyleRun')
        hdr = d[p:p+6]
        if hdr != b'\x01\x00\x01\x00\x00\x00':
            raise ValueError('run header %s at %x' % (hdr.hex(), p))
        kind = d[p+6]
        if kind == 0x07:                      # field run: class tag, style, 1 byte
            p += 7
            fm = re.match(rb'\xff\xff..(..)|.[\x80-\xff]', d[p:p+40], re.S)
            if fm and fm.group(1):
                n = struct.unpack('<H', fm.group(1))[0]
                fname = d[p+6:p+6+n]; p += 6 + n
            else:
                fname = b'?'; p += 2
            style = struct.unpack_from('<H', d, p)[0]; p += 3
            para['runs'].append(dict(style=style, text=b'', field=fname.decode('latin-1')))
            continue
        if kind != 0x02:
            raise ValueError('run kind %d at %x' % (kind, p))
        style = struct.unpack_from('<H', d, p+7)[0]; p += 9
        txt, p = read_cstring(d, p)
        para['runs'].append(dict(style=style, text=txt))
    para['end'] = p
    return para

def parse_list(b):
    hebrew = b[2] == 0x05
    suffix = '.'
    for c in b[3:5]:
        if c in (0x28, 0x29, 0x2e):
            suffix = chr(c)
            break
    number = struct.unpack_from('<I', b, 16)[0]
    return dict(hebrew=hebrew, suffix=suffix, number=number)

def parse_paragraphs(d, start=0, end=None):
    out = []; p = start
    end = end or len(d)
    while True:
        m = PARA_RE.search(d, p, end)
        if not m:
            break
        try:
            para = parse_paragraph(d, m)
        except Exception:
            p = m.start() + 1
            continue
        out.append(para); p = para['end']
    return out

# ---------------------------------------------------------------- page setup
def parse_page(d):
    m = find_class(d, b'CPageBorder')
    border_margins = None
    has_border = False
    if m:
        p = m.end()
        bt, bl, bb, br = struct.unpack_from('<4i', d, p+5)     # stored top, left, bottom, right (as the margins)
        border_margins = (bl, bt, br, bb)
        has_border = find_class(d, b'CBorderSimple') is not None
    # text margins (left, top, right, bottom) live in the file header
    hm = struct.unpack_from('<4i', d, 0x28)      # stored as top, left, bottom, right
    if all(200 <= v <= 4000 for v in hm):
        margins = (hm[1], hm[0], hm[3], hm[2])     # -> left, top, right, bottom
    else:
        margins = border_margins or (1080, 1080, 1080, 1080)
    # paper size: look for the DEVMODE-ish "Letter"/"A4" name
    paper = 'Letter'
    if b'\x00A4\x00' in d[:0x1000]:
        paper = 'A4'
    return dict(margins=margins, border=has_border, border_margins=border_margins, paper=paper,
                end=(m.end() if m else 0))

# ---------------------------------------------------------------- floating objects
def parse_objects(d, paras, limit=None):
    m = find_class(d, b'CPageObject')
    if not m:
        return []
    pb = find_class(d, b'CPageBorder')
    end = pb.start() if pb else (limit or len(d))
    cls_idx = None
    # tag for later objects: find "XX 80" followed by plausible coords
    starts = [m.end()]
    # the class index of CPageObject: count is not tracked, so infer from the
    # 2-byte tag that occurs right before the 2nd object.  Objects begin with
    # x, y (int32), 0, id (int32), kind byte.
    tag_counts = {}
    for mm in re.finditer(rb'(.)\x80(.{4})(.{4})(?:\x00\x00\x00\x00|[\x01-\x0f]\x00\x00\x00.{16})(.{4})([\x03\x0e\x0f\x15])', d[m.end():end], re.S):
        tag_counts[mm.group(1)] = tag_counts.get(mm.group(1), 0) + 1
    if tag_counts:
        tag = max(tag_counts, key=tag_counts.get) + b'\x80'
        for mm in re.finditer(re.escape(tag) + rb'(.{4})(.{4})(?:\x00\x00\x00\x00|[\x01-\x0f]\x00\x00\x00.{16})(.{4})([\x03\x0e\x0f\x15])', d[m.end():end], re.S):
            starts.append(m.end() + mm.start() + 2)
    objs = []
    bounds = starts + [end]
    for i, s in enumerate(starts):
        e = bounds[i+1] - (2 if i + 1 < len(starts) else 0)
        x, y, z = struct.unpack_from('<iii', d, s)
        hdr = 16 if z == 0 else 32
        kind = d[s+hdr]
        body = d[s+hdr+1:e]
        # page index: last "(n) 00 00 00 (n) 00 00 00 03 00 00 00" in the object
        page = None
        for pm in re.finditer(rb'([\x00-\xff])\x00\x00\x00\1\x00\x00\x00\x03\x00\x00\x00', body):
            page = pm.group(1)[0]
        o = dict(x=x, y=y, kind=kind, page=page, start=s, end=e)
        if kind == 0x15:
            w = None
            mm = re.search(rb'(?:CTableRow|.\x80)(.{4})\x02\x00\xff\xff\xff\x00', body, re.S)
            if mm:
                w = struct.unpack_from('<i', mm.group(1))[0]
            o['height'] = w
            wm = re.search(rb'(..)\x02\x00..\x42\x80', body, re.S)
            o['width'] = struct.unpack('<H', wm.group(1))[0] if wm else 2000
            o['width_known'] = bool(wm)
            o['paras'] = [p for p in paras if s <= p['pos'] < e]
            o['border'] = b'\x08\x08' in body
            o['table'] = b'CTable' in body or len(re.findall(rb'\x64\x03\x03\x03\x03', body)) > 1
        else:
            o.update(parse_field(d, s + hdr + 1, e, kind))
        objs.append(o)
    return objs

def parse_tables(d, paras):
    """Inline tables.  Stream layout: row, CTable record (row count, column boundaries), remaining rows.
    Row: tag, int32, WORD ncells, then per cell: fill(3) 00 shade borders(4), a CParagList (or 00 00 = none),
    17 bytes.  Returns tables as dicts with rows (lists of cells, each a list of paragraphs)."""
    tables = []
    cell_lists = set()           # byte positions of the '01 00 01 00 00 00' of every cell's paragraph list
    parse_tables.cell_lists = cell_lists
    by_pos = sorted(paras, key=lambda p: p['pos'])
    pos_index = {p['pos']: i for i, p in enumerate(by_pos)}

    def read_row(p):
        """p points at the row tag.  Returns (cells, end) or None."""
        if d[p:p+2] == b'\xff\xff':
            n = struct.unpack_from('<H', d, p + 4)[0]
            if d[p+6:p+6+n] != b'CTableRow':
                return None
            p += 6 + n
        elif d[p+1] & 0x80:
            p += 2
        else:
            return None
        rh = struct.unpack_from('<i', d, p)[0]; p += 4      # row height in twips (negative: fixed height)
        ncells = struct.unpack_from('<H', d, p)[0]; p += 2
        if not 1 <= ncells <= 64:
            return None
        cells = []
        for _ in range(ncells):
            p += 9
            if d[p:p+2] == b'\x00\x00':          # no paragraph list
                p += 2; cells.append(None)
            else:
                if d[p:p+2] == b'\xff\xff':
                    n = struct.unpack_from('<H', d, p + 4)[0]; p += 6 + n
                else:
                    p += 2
                if d[p:p+6] != b'\x01\x00\x01\x00\x00\x00':
                    return None
                cell_lists.add(p)
                cnt = struct.unpack_from('<H', d, p + 6)[0]; p += 8
                cps = []
                for _ in range(cnt):
                    i = pos_index.get(p)
                    if i is None:
                        # paragraph regex may have matched a few bytes earlier/later: find the next one
                        nxt = [q for q in by_pos if q['pos'] >= p - 2][:1]
                        if not nxt:
                            return None
                        q = nxt[0]
                    else:
                        q = by_pos[i]
                    cps.append(q); p = q['end']
                cells.append(cps)
            p += 17
        if cells and cells[-1] is None:
            cells.pop()                 # the trailing cell with no paragraph list is an end marker
        cells = [c or [] for c in cells]
        return cells, p, rh

    # candidate first rows: a tag, 4 bytes, WORD ncells, then a cell header (fill, 00, shade, 4 border widths)
    cand = set(m.start() for m in re.finditer(rb'\xff\xff..\x09\x00CTableRow', d, re.S))
    for m in re.finditer(rb'[\x00-\xff][\x80-\xff].{4}[\x01-\x40]\x00...\x00.[\x00-\x08]{4}(?:\xff\xff..\x0a\x00CParagList|[\x00-\xff][\x80-\xff]\x01\x00\x01\x00\x00\x00|\x00\x00)', d, re.S):
        cand.add(m.start())
    done_end = 0
    for start in sorted(cand):
        if start < done_end:
            continue
        p = start
        r = read_row(p)
        if not r:
            continue
        rows = [r[0]]; p = r[1]; heights = [r[2]]
        # CTable record
        if d[p:p+2] == b'\xff\xff':
            n = struct.unpack_from('<H', d, p + 4)[0]
            if d[p+6:p+6+n] != b'CTable':
                continue
            p += 6 + n
        elif d[p+1] & 0x80:
            p += 2
        else:
            continue
        nrows, nb = struct.unpack_from('<ii', d, p)
        if not (1 <= nrows <= 500 and 1 <= nb <= 64 and 0 <= struct.unpack_from('<i', d, p + 8)[0] <= 16):
            continue
        tm_start = start
        p += 15
        bounds = [struct.unpack_from('<H', d, p + 2 * k)[0] for k in range(max(0, min(nb, 64)))]
        p += 2 * len(bounds) + 2
        for _ in range(nrows - 1):
            # each following row is preceded by a 2-byte value; skip to the next object tag
            for _k in range(3):
                if d[p:p+2] == b'\xff\xff' or (d[p+1] & 0x80):
                    break
                p += 2
            r = read_row(p)
            if not r:
                break
            rows.append(r[0]); p = r[1]; heights.append(r[2])
        # some tables end with an extra row whose cells are all empty (a terminator); swallow it
        q = p
        for _k in range(3):
            if d[q:q+2] == b'\xff\xff' or (d[q+1] & 0x80):
                break
            q += 2
        r = read_row(q)
        if r and not any(r[0]):
            p = r[1]
        done_end = p
        first = tm_start + (6 + 9 if d[tm_start:tm_start+2] == b'\xff\xff' else 2)
        shade = d[first + 6:first + 9]
        bw = d[first + 10:first + 14]
        tables.append(dict(rows=rows, row_heights=heights, width=bounds[-1] if bounds else None, bounds=bounds, pos=tm_start, end=p,
                           fill='%02X%02X%02X' % tuple(shade) if len(shade) == 3 else 'FFFFFF',
                           borders=list(bw)))
        # later tables in the same file reuse the row class by tag; find them from the CTable records instead
    # tables whose first row uses a short ref tag: locate via CTable class refs
    return tables

SUPPORTED_VERSION = 550      # DavkaWriter 7

MAIN_MARKER = re.compile(rb'\x2e\x00\x2e\x01\x00\x01\x00\x00\x00(..)', re.S)

def walk_main(d, start, count, paras, tables):
    return walk_list(d, start, count, paras, tables)[0]

def _skip_tag(d, p):
    """Skip an MFC object tag (class definition or short tag); None if there is none."""
    if d[p:p+2] == b'\xff\xff':
        n = struct.unpack_from('<H', d, p + 4)[0]
        return p + 6 + n
    if d[p+1] & 0x80:
        return p + 2
    return None

def walk_list(d, start, count, paras, tables, depth=0):
    """Read a paragraph list record by record.  A table occupies one paragraph per row: the first
    carries the serialized rows (and the CTable record), the others only refer back to their row.
    A paragraph may also carry section headers/footers (CHeader/CFooter) or a footnote set."""
    by_pos = {p['pos']: p for p in paras}
    tbl_by_pos = {t['pos']: t for t in tables}
    out = []
    p = start
    cur = None          # (table, rows still to come)
    for _ in range(count):
        if p + 8 > len(d):
            raise ValueError('paragraph list runs past the end of the file')
        if d[p:p+2] == b'\xff\xff':
            n = struct.unpack_from('<H', d, p + 4)[0]
            if d[p+6:p+6+n] != b'CParagraph':
                raise ValueError('expected a paragraph at %x' % p)
            hp = p + 6 + n
        elif d[p+1] & 0x80:
            hp = p + 2
        else:
            raise ValueError('expected a paragraph tag at %x' % p)
        if d[hp:hp+6] != b'\x01\x00\x01\x00\x00\x00':
            raise ValueError('bad paragraph header at %x' % hp)
        body = d[hp+6:hp+14]
        nobj = struct.unpack_from('<H', body, 0)[0]
        brk = struct.unpack_from('<H', body, 2)[0]
        nhead, nfoot, nfootnote, has_table = body[4], body[5], body[6], body[7]
        if nobj:
            # embedded page objects: the regex parser knows this shape
            para = by_pos.get(p)
            if para is None:
                m = PARA_RE.match(d, p)
                if not m:
                    raise ValueError('unreadable paragraph at %x' % p)
                para = parse_paragraph(d, m)
            out.append(para); p = para['end']
            continue
        q = hp + 14
        extras = []
        for _h in range(nhead + nfoot):           # CHeader / CFooter: tag, int32, WORD, paragraph list
            q2 = _skip_tag(d, q)
            if q2 is None:
                raise ValueError('bad section header at %x' % q)
            q = q2 + 6
            q2 = _skip_tag(d, q)
            if q2 is None or d[q2:q2+6] != b'\x01\x00\x01\x00\x00\x00':
                raise ValueError('bad header list at %x' % q)
            n = struct.unpack_from('<H', d, q2 + 6)[0]
            ps, q = walk_list(d, q2 + 8, n, paras, tables, depth + 1)
            extras.append(ps)
        if nfootnote:
            q2 = _skip_tag(d, q)
            if q2 is None:
                raise ValueError('bad footnote set at %x' % q)
            fm = re.compile(rb'\x2e\x00\x2e').search(d, q2, q2 + 400)      # the set's settings record
            if not fm:
                raise ValueError('bad footnote set at %x' % q)
            q = fm.end()
        t = None
        if has_table:
            t = tbl_by_pos.get(q)
            if t is not None:
                q = t['end'] + 2          # the rows, then a reference to this paragraph's row
                cur = (t, len(t['rows']) - 1)
            else:
                if d[q+1] & 0x80 or d[q:q+2] == b'\xff\xff':
                    raise ValueError('unparsed table at %x' % q)
                q += 2
                if cur is not None and cur[1] > 0:
                    t = cur[0]; cur = (t, cur[1] - 1)
        q += 4
        if d[q:q+4] != b'\xff\xff\xff\xff':
            raise ValueError('bad paragraph body at %x' % q)
        para = parse_tail(d, q + 4, p)
        if brk:
            para['brk'] = brk
        if t is not None:
            para['table'] = t
        if extras:
            para['extras'] = extras
        out.append(para)
        p = para['end']
    return out, p

PAGE_DEFAULTS = dict(paper='Letter', orientation=1, landscape=False, paper_code=None, paper_form='', paper_dims_mm10=None,
                     paper_twips=None, custom_size=None, page_borders=[], border=False, border_margins=None, border_art=None,
                     mirror=0, half_page=(0, 0), header_distance=720, footer_distance=720, margins=(1440, 1440, 1440, 1440))

def parse(d):
    """.dwd bytes -> D (styles, rulers, page, main, objects, header, footer, tables, reader, ...).
    D['page'] always has every key of PAGE_DEFAULTS."""
    import dwdread
    try:
        D = dwdread.parse(d)
    except Exception as e:
        err = '%s: %s' % (type(e).__name__, e)
        try:
            D = _parse_heuristic(d)
        except ValueError:
            raise                  # (not a DavkaWriter 7 file, an older format: said in its own words)
        except Exception:
            # (1.3.25) cut off within its first few hundred bytes, before the heuristic reader can find its way:
            # "cut off", not the heuristic reader's own error ('NoneType' object has no attribute 'end')
            if _looks_truncated(err):
                raise ValueError('this file is cut off (it ends at %d bytes, before any of its text); get a complete copy and try again' % len(d))
            raise
        D['reader'] = 'heuristic'
        D['reader_error'] = err
        got, want = len(D['main']), D.get('declared_paragraphs')
        if _looks_truncated(err):
            # the spec reader ran out of bytes: the file was cut off (an interrupted download/copy).  The heuristic
            # reader still salvages what is there, but the caller must say that the result is incomplete.
            if not got:
                raise ValueError('this file is cut off (it ends at %d bytes, before any of its text); get a complete copy and try again' % len(d))
            D['truncated'] = dict(paragraphs=got, declared=want, size=len(d))
            D.setdefault('warnings', []).append(
                'file appears cut off (it ends early, at %d bytes): only %d%s paragraphs could be read'
                % (len(d), got, ' of its %d' % want if want and want > got else ''))
        elif want and got < want:
            # damaged (not short): the heuristic reader skipped what it could not follow
            D.setdefault('warnings', []).append(
                'file looks damaged: only %d of its %d paragraphs could be read' % (got, want))
    for k, v in PAGE_DEFAULTS.items():
        D['page'].setdefault(k, v)
    return D

def _looks_truncated(err):
    """does a reader error say the bytes ran out (rather than that they were wrong)?"""
    e = (err or '').lower()
    return 'unexpected end of file' in e or 'past the end of the file' in e

def _parse_heuristic(d):
    ver = struct.unpack_from('<I', d, 0)[0] if len(d) >= 4 else 0
    if ver != SUPPORTED_VERSION:
        if 100 <= ver < 2000:
            raise ValueError('this file was saved by an older DavkaWriter (format %d); open it in DavkaWriter 7, save it again, then convert' % ver)
        raise ValueError('not a DavkaWriter 7 document')
    styles = parse_styles(d)
    rulers = parse_rulers(d)
    page = parse_page(d)
    paras = parse_paragraphs(d)
    # paragraph lists: header, footer, then the main flow (the largest list).
    best = (0, page['end'], 0)
    for lm in re.finditer(rb'\x01\x00\x01\x00\x00\x00(..)(?=.[\x80-\xff]\x01\x00\x01\x00\x00\x00|\xff\xff..\x0a\x00CParagraph)', d[page['end']:], re.S):
        n = struct.unpack('<H', lm.group(1))[0]
        if n > best[0]:
            best = (n, page['end'] + lm.end(), page['end'] + lm.start())
    mm = MAIN_MARKER.search(d)
    # page objects live before the main flow; its position bounds the object area
    objs = parse_objects(d, paras, limit=(mm.start() - 120 if mm else best[2]) or None)
    inobj = set()
    for o in objs:
        for p in o.get('paras', []):
            inobj.add(p['pos'])
    main = [p for p in paras if p['pos'] >= best[1] and p['pos'] not in inobj]
    extra = []
    # header and footer: the two tagged CParagList objects just before the main flow
    hf_lists = []
    for lm in re.finditer(rb'(?:\xff\xff..\x0a\x00CParagList|.[\x80-\xff])\x01\x00\x01\x00\x00\x00(..)(?=.[\x80-\xff]\x01\x00\x01\x00\x00\x00|\xff\xff..\x0a\x00CParagraph)', d[:best[2] or len(d)], re.S):
        n = struct.unpack('<H', lm.group(1))[0]
        ps = [p for p in paras if p['pos'] >= lm.start() and p['pos'] not in inobj][:n]
        if any(p['pos'] < page['end'] for p in ps):
            continue
        hf_lists.append(ps)
    hf_lists = hf_lists[-2:]
    nonblank = lambda ps: [p for p in ps if any(r['text'].strip(b' \t\xa0') or r.get('field') for r in p['runs'])]
    header = nonblank(hf_lists[0]) if len(hf_lists) == 2 else []
    footer = nonblank(hf_lists[-1]) if hf_lists else []
    footer = footer or nonblank(extra)
    tables = parse_tables(d, paras)
    walked = None
    declared = struct.unpack('<H', mm.group(1))[0] if mm else None
    if mm:
        try:
            walked = walk_main(d, mm.end(), struct.unpack('<H', mm.group(1))[0], paras, tables)
        except Exception as e:
            walked = None
    if walked is not None:
        incell = set()
        for t in tables:
            for row in t['rows']:
                for cell in row:
                    for q in cell:
                        q['table'] = t
        return dict(styles=styles, rulers=rulers, page=page, main=walked, objects=objs, header=header, footer=footer, tables=tables,
                    declared_paragraphs=declared)
    # the main flow ends where the next paragraph list (not a table cell's) begins
    for lm in re.finditer(rb'\x01\x00\x01\x00\x00\x00(..)(?=.[\x80-\xff]\x01\x00\x01\x00\x00\x00|\xff\xff..\x0a\x00CParagraph)', d[best[1]:], re.S):
        at = best[1] + lm.start()
        if at in parse_tables.cell_lists:
            continue
        main = [p for p in main if p['pos'] < at]
        break
    incell = set()
    for t in tables:
        for row in t['rows']:
            for cell in row:
                for p in cell:
                    p['table'] = t
                    incell.add(id(p))
    # a table takes the place of its cell paragraphs in the flow: keep the first cell paragraph as the anchor
    seen_tables = set()
    flow = []
    for p in main:
        t = p.get('table')
        if t is None:
            flow.append(p)
        elif id(t) not in seen_tables:
            seen_tables.add(id(t)); flow.append(p)
    main = flow
    return dict(styles=styles, rulers=rulers, page=page, main=main, objects=objs, header=header, footer=footer, tables=tables,
                declared_paragraphs=declared)
