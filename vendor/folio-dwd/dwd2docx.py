#!/usr/bin/env python3
"""Convert DavkaWriter .dwd files to Word .docx.

usage: python3 dwd2docx.py input.dwd [more.dwd ...] [-o OUTDIR]
"""
import sys, os, re, json, unicodedata, math, zipfile, argparse, struct, time
from xml.sax.saxutils import escape
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dwdparse import parse
from davkamap import decode, NIKUD, UPPER_DOT, is_symbol_font, symbol_decode, symbol_encode, mark_rank, NEW_1326
import pageborders

HERE = os.path.dirname(os.path.abspath(__file__))
# per Davka/GuttmanD font: [ (ascent+descent) per 1000 em, widths of chars 0x20..0x7f in 1/200 em ]
METRICS = json.load(open(os.path.join(HERE, 'metrics_all.json')))

# Hebrew fonts: Folio never uses DavkaWriter's fonts.  A Davka/GuttmanD font name is written to Word as the
# free, openly licensed font that is similar to it (freefonts.FREE_FOR), drawn at SIZE_ADJ of the size so a
# line takes about the room it took in DavkaWriter; the free fonts' own widths are in freefonts_metrics.json.
import freefonts
_FREE = json.load(open(os.path.join(HERE, 'freefonts_metrics.json')))
METRICS.update(_FREE['w'])
FREE_FAMILIES = set(_FREE['files'])
FREE_FILES = _FREE['files']
FONT_MAP = {}                      # other (non-Davka) Hebrew font -> font used; edit to taste
DEFAULT_HEB_FONT = freefonts.DEFAULT_FREE
# own_davka_fonts: write "Davka X Unicode" (fonts the user installed themselves) instead of the free fonts
OPTIONS = {'own_davka_fonts': False}
# written into every .docx (docProps/app.xml); the web page sets it to its build version ("1.<n>")
APP_VERSION = '0.5.1'

def word_font(name):
    if name in OPTIONS.get('installed_fonts', {}):
        return OPTIONS['installed_fonts'][name]
    if freefonts.is_davka(name):
        return name + ' Unicode' if OPTIONS.get('own_davka_fonts') else freefonts.free_font(name)
    if name in FREE_FAMILIES:
        return name
    return FONT_MAP.get(name, DEFAULT_HEB_FONT)

def calibrated(st, rtl=True):
    """whether a run is drawn in the free font that stands in for a Davka font (and so is calibrated to its widths)"""
    return bool(rtl) and freefonts.is_davka(st['font']) and not OPTIONS.get('own_davka_fonts') and st['font'] not in OPTIONS.get('installed_fonts', {})

def word_size(st, rtl=True):
    """half-points written to Word: a Davka font shown in its free counterpart is drawn at its calibrated size
    (freefonts.size_adj, per weight)."""
    if not calibrated(st, rtl):
        return max(int(round(st['size'] * 2)), 1)
    # rounded down to Word's half points, so the letters are never taller than the calibrated size (the
    # character scale, width_fix, makes up the width)
    return max(int(math.floor(st['size'] * 2 * freefonts.size_adj(st['font'], st.get('bold')) + 1e-6)), 1)

def width_fix(st, rtl=True):
    """(character scale %, {' ': %, '_': %}) that make a Davka font's free stand-in as wide as DavkaWriter's font:
    the scale of its letters (making up for the size's limits and rounding), and of a blank (a row of spaces or
    underscores, which gets a run of its own)"""
    if not calibrated(st, rtl) or not st.get('size'):
        return 100, {}
    drawn = word_size(st, rtl) / 2.0
    sc = freefonts.char_scale(st['font'], st.get('bold'), st['size'], drawn)
    return sc, freefonts.fix_scales(st['font'], st.get('bold'), st['size'], drawn)

def text_scale(st, rtl, text):
    """the character scale (%) of a piece of a Davka font's text: its letters at their calibrated width and the
    single spaces and underscores between them at DavkaWriter's, together (one scale for the piece, so the words
    stay in one run and the line holds what DavkaWriter's line holds)"""
    c = freefonts.calib(st['font'], st.get('bold'))
    drawn = word_size(st, rtl) / 2.0
    n_sp = sum(1 for ch in text if ch in ' \u00a0')
    n_us = text.count('_')
    n_let = sum(1 for ch in text if ch not in ' \u00a0_\u200e\u200f' and not unicodedata.combining(ch))
    let_dw = n_let * c.get('lw', 0.5) * c['k']                 # DavkaWriter's width of the letters (em)
    dw = let_dw + n_sp * c['sp'][0] + n_us * c['us'][0]
    fr = let_dw / c['k'] + n_sp * c['sp'][1] + n_us * c['us'][1]
    if not fr:
        return 100
    return int(round(min(max(100.0 * dw / fr * st['size'] / drawn, freefonts.SCALE_RANGE[0]), freefonts.SCALE_RANGE[1])))

BLANK_RE = re.compile('([ \u00a0]{2,}|_{2,})')     # a blank: a row of spaces or underscores (an answer line)

LATIN_RATIO = {'Times New Roman': 1.149, 'Comic Sans MS': 1.394, 'Arial': 1.149}
RULE_EXTRA = 60        # twips DavkaWriter adds under a paragraph that has a rule beneath it (fitted)
LAST_LINE_HANG = 0     # twips a last line may reach past the bottom margin (0: none; see notes)
CAPACITY_SLACK = -200  # a page border makes the text area slightly taller than the margins say (fitted on a 12-page bordered file)
PAPER = {'Letter': (12240, 15840), 'A4': (11906, 16838), 'Legal': (12240, 20160)}
def paper(D):
    pt_ = D['page'].get('paper_twips')
    w, h = pt_ if pt_ else PAPER.get(D['page'].get('paper'), PAPER['Letter'])
    return (h, w) if D['page'].get('landscape') else (w, h)   # twips lost to page-border padding (top+bottom)

def is_hebrew_style(st):
    return bool(st['flags'] & 0x02) or st['font'].startswith(('Davka', 'GuttmanD'))

# empirical corrections fitted to DavkaWriter's own page breaks
FIT = {'KsavYad': 0.95, 'Gonen': 1.1, 'David': 0.9}
FIT_LATIN = 1.1
# measured on DavkaWriter screenshots: Comic Sans 14pt is 21pt at single, 24.7pt at 1.25 lines
LATIN_FIT_SINGLE = {'Comic Sans MS': 1.076}
LATIN_FIT_MULTI = {'Times New Roman': 1.1}

HEB_W_FACTOR = 1.0
CP1252_W = {0x95: 0.35, 0x96: 0.5, 0x97: 1.0, 0x91: 0.33, 0x92: 0.33, 0x93: 0.44, 0x94: 0.44, 0x85: 1.0, 0xa0: 0.25, 0xb7: 0.25}
# the widths of the cp1252 punctuation above 0x7f in fonts that differ from CP1252_W (em; from DavkaWriter's prints)
CP1252_FONT_W = {'Comic Sans MS': {0x85: 0.675, 0x91: 0.18, 0x92: 0.18, 0x93: 0.394, 0x94: 0.394, 0x95: 0.387, 0x96: 0.441,
                                   0x97: 0.883, 0xa0: 0.299, 0xb7: 0.249},
                 'Arial': {0x91: 0.222, 0x92: 0.222, 0x93: 0.333, 0x94: 0.333}}
LATIN_W = json.load(open(os.path.join(HERE, 'latin_widths.json')))     # Latin fonts: widths 0x20..0x7f in 1/200 em
VMETRICS = json.load(open(os.path.join(HERE, 'vmetrics.json')))   # font -> [ascent, descent, line gap] in em
for _k, _v in _FREE['v'].items():
    VMETRICS.setdefault(_k, _v)
for _k, _v in freefonts.CALIB.items():        # line heights DavkaWriter uses for fonts vmetrics.json lacks (font_calib.json)
    if _v.get('lh'):
        VMETRICS.setdefault(_k, _v['lh'])
DEFAULT_VM = [0.95, 0.25, 0.03]

def inline_picture(r):
    """The picture a run carries in line with its text (a CFieldGraphic in the run, or one inserted in the
    Folio editor), if it is in a format Word can show; else None."""
    o = r.get('newpic')
    if o is not None:
        return o if o.get('newpic') == 'inline' else None
    o = r.get('object')
    if o is not None and o.get('picture') and o.get('w') and o.get('h'):
        return o                      # (a picture in a format Word can't show keeps its room: a marked spot)
    return None

def pic_renderable(o):
    return bool(o.get('bmp')) or o.get('image_format') in RAW_IMAGE_EXT

def vmetric(st):
    """(ascent, descent, gap) in points for a style.  Measured on DavkaWriter: a line is as tall as the
    tallest ascent plus the deepest descent of the fonts on it (plus the dominant font's line gap)."""
    if 'pic_h' in st:                    # a picture in the line: as tall as the picture
        return st['pic_h'], 0, 0
    f = st['font']
    m = VMETRICS.get(f + '/Bold') if st.get('bold') else None
    m = m or VMETRICS.get(f) or DEFAULT_VM
    sz = st['size']
    return m[0] * sz, m[1] * sz, m[2] * sz

def line_height_pt(styles, pct, ru=None):
    """height in points of one line holding runs of the given styles, at pct line spacing.
    ru may carry DavkaWriter's other spacing modes: ls_mode 0 = 'at least ls_pt points', 2 = 'exactly'."""
    if not styles:
        return 0
    asc = max(vmetric(st)[0] for st in styles)
    desc = max(vmetric(st)[1] for st in styles)
    gap = max(vmetric(st)[2] for st in styles)
    nat = asc + desc + gap
    mode = ru.get('ls_mode', 1) if ru else 1
    if mode == 1 or not ru:
        # the single line times the percentage, for wider and narrower spacing alike and for a line holding a
        # picture too (measured on DavkaWriter prints: Comic Sans 10/12/14 pt at 125% = 1.25 x the font's height)
        return nat * pct / 100.0
    if mode == 0:
        return max(nat, ru.get('ls_pt', 0))
    return ru.get('ls_pt', 0) or nat

def indents(ru):
    """(start margin, first-line offset, end margin) in twips, the way DavkaWriter's dialog shows them."""
    left = max(ru.get('ind2', 0), 0)
    first = ru.get('ind1', 0) - left
    right = max(ru.get('rind', 0), 0)
    if ru.get('ncols', 1) > 1:
        right = 0
    return left, first, right

BULLET_HANG = 187        # twips between a DavkaWriter bullet and the text after it (its prints: 9.4-9.8 pt)

def bullet_char(lst, st=None):
    """the character of a bulleted list (CParNumbering mode 1): its code in the number style's font"""
    c = lst.get('char') or 149
    try:
        if st and is_symbol_font(st.get('font') or ''):
            ch = symbol_decode(st['font'], bytes([c & 0xff]))
        else:
            ch = bytes([c & 0xff]).decode('cp1252')
    except Exception:
        ch = ''
    return ch if ch and ch.isprintable() and ch.strip() else '•'

def line_ratio(st, pct=100):
    return line_height_pt([st], pct) / st['size']

def usable_tabs(ru, avail):
    """The ruler's tab stops that DavkaWriter uses: a stop past the right margin is ignored (a tab or a rule
    character there goes on along the default half-inch stops instead, e.g. answer lines of 13 rules each)."""
    return [(typ, pos) for typ, pos in (ru or {}).get('tabs') or [] if 0 < pos <= avail]

def next_tab(x, tabs, tab=720):
    for pos in sorted(tabs or []):
        if pos > x + 1:
            return pos
    return (int(x // tab) + 1) * tab

def text_width(st, b, x0, tabs=None):
    """width in twips of the bytes b starting at x position x0 (twips)."""
    m = METRICS.get(st['font'])
    size = st['size'] * 20
    x = x0
    for c in b:
        if c == 9:
            x = next_tab(x, tabs)
            continue
        if m and is_hebrew_style(st):
            if c in NIKUD or c in UPPER_DOT:
                continue                  # marks take no room (1.3.27: the 1.3.26 trop / vowel codes too, so lines
                                          # with trop fit as DavkaWriter's do)
            w = (m[1 + c - 0x20] / 200.0 if 0x20 <= c < 0x80 else 0.3) * HEB_W_FACTOR
        else:
            lw = LATIN_W.get(st['font'] + '/Bold') if st.get('bold') else None
            lw = lw or LATIN_W.get(st['font']) or LATIN_W['Arial']
            w = lw[c - 0x20] / 200.0 if 0x20 <= c < 0x80 else (CP1252_FONT_W.get(st['font'], {}).get(c) or CP1252_W.get(c, 0.5))
        x += w * size
    return x - x0

# ------------------------------------------------------------- layout
WORD_RE = re.compile(rb'[^ \t\r]+ *| +|\t|\r')

def line_span(obstacles, y, lh, avail, hits=None):
    """(start, end) in twips of the room a line at y (top, twips from the text area's top) of height lh has
    between the objects text wraps around: DavkaWriter puts the text on the wider side of an object (never
    on both sides).  obstacles: [(top, bottom, x0, x1, dist)] in text-area twips."""
    lo, hi = 0, avail
    for ob in obstacles or ():
        top, bottom, x0, x1, dist = ob[:5]
        if bottom <= y or top >= y + lh:
            continue
        if hits is not None and len(ob) > 5:
            hits.add(id(ob[5]))
        left_room = x0 - dist                     # text left of the object
        right_room = avail - (x1 + dist)          # text right of it
        if left_room >= right_room:
            hi = min(hi, max(x0 - dist, 0))
        else:
            lo = max(lo, min(x1 + dist, avail))
    if hi - lo < 600:                             # too narrow for words: the line goes below the object
        return None
    return lo, hi

def para_lines(D, p, avail, obstacles=None, y=0, hits=None):
    """Lay the paragraph out the way DavkaWriter does: words wrap greedily, a bare CR forces a new line.
    Positions are measured from the margin, like the tab stops.  Returns the height of each line in twips.
    obstacles (see line_span) are the page's objects the text wraps around; y is where the paragraph starts
    on the page (twips from the top of the text area)."""
    S, R = D['styles'], D['rulers']
    ru = R.get(p['ruler'], dict(pct=100, ind1=0, ind2=0))
    runs = [r for r in p['runs'] if r['style'] in S] or []
    left, first, right = indents(ru)
    lim = max(avail - right, left + 1000)          # the right edge of every line
    # the first line starts at its own indent (a hanging first line further out than the rest); only a list
    # paragraph's text starts at the indent, its number hanging in front of it
    x0_first = min(max(0, left + first) if not p.get('list') else left + max(first, 0), lim - 1000)
    tabs = [pos for typ, pos in usable_tabs(ru, avail)]
    last = max((i for i, r in enumerate(runs) if r['text'].strip(b' \xa0') or inline_picture(r)), default=-1)
    lines = []           # list of style lists
    heights = []         # the height of each finished line (twips)
    skips = set()        # entries of heights that are not lines but a jump below an object
    cur = []
    st0 = S[runs[0]['style']] if runs else dict(font='Times New Roman', size=12)
    lh_est = line_height_pt([st0], ru.get('pct', 100), ru) * 20
    yy = [y]
    box = [None]         # (start, end) of the current line when an obstacle narrows it
    def place(first_line):
        """start x and right edge of a new line at yy[0], around the page's objects"""
        if obstacles:
            sp = line_span(obstacles, yy[0], lh_est, avail, hits)
            while sp is None and yy[0] < 40000:          # no room beside the object: skip below it
                nxt = min((ob[1] for ob in obstacles if ob[1] > yy[0]), default=None)
                if nxt is None:
                    break
                skips.add(len(heights))
                heights.append(nxt - yy[0]); lines.append(None)
                yy[0] = nxt
                sp = line_span(obstacles, yy[0], lh_est, avail, hits)
            if sp and (sp[0] > 0 or sp[1] < avail):
                box[0] = sp
                lo, hi = sp
                return max(left + (max(first, 0) if first_line else 0), lo), min(lim, hi)
        box[0] = None
        return (x0_first if first_line else left), lim
    x0, width = place(True)
    x = x0

    def newline(sts):
        nonlocal cur, x0, x, width
        lines.append(cur or sts)
        h = line_height_pt(cur or sts, ru['pct'], ru) * 20
        heights.append(h)
        yy[0] += h
        cur = []
        x0, width = place(False)
        x = x0

    def tw(st, tok, at):
        return text_width(st, tok, at, tabs)
    # a list number ("1.", "א.") hangs in the paragraph's indent: the text starts at the indent
    for i, r in enumerate(runs):
        pic = inline_picture(r)
        if pic is not None and i <= last:
            w = int(pic.get('w') or 1440)
            if x > x0 and x + w > width:
                newline([S[r['style']]])
            x += w
            cur.append({'pic_h': int(pic.get('h') or 1440) / 20.0, 'size': 1})
            continue
        t = r['text']
        if i == last:
            t = t.rstrip(b' \xa0')          # trailing spaces never force a line break
        elif i > last:
            continue
        st = S[r['style']]
        for tok in WORD_RE.findall(t.replace(b'\x03', b'\t')):
            if tok == b'\r':
                newline([st])
                continue
            if tok == b'\t':
                nx = x + tw(st, tok, x)
                if nx > width and x > x0:
                    # no stop left on this line: the tab ends the line and is used up (measured on a DavkaWriter
                    # print: the text after "...?\t\t\t   \t\t" starts at the 5th stop of the next line)
                    newline([st])
                    continue
                x = nx; cur.append(st)
                continue
            w = tw(st, tok, x)
            wt = tw(st, tok.rstrip(b' '), x) if tok.endswith(b' ') else w
            if wt > width - (box[0][0] if box[0] else left):
                # a word longer than a whole line (a row of underscores): it starts where the line is and
                # breaks at the right margin, as many times as needed
                rest = tok.rstrip(b' ')
                while rest:
                    k = len(rest)
                    while k > 1 and x + tw(st, rest[:k], x) > width:
                        k -= 1
                    if k == 1 and x > x0 and x + tw(st, rest[:1], x) > width:
                        newline([st])
                        continue
                    x += tw(st, rest[:k], x); cur.append(st)
                    rest = rest[k:]
                    if rest:
                        newline([st])
                if tok.endswith(b' '):
                    x += tw(st, b' ', x)
                continue
            if x > x0 and x + wt > width + LINE_TOL:
                newline([st])
                w = tw(st, tok, x)
            x += w
            cur.append(st)
    lines.append(cur or [S[r['style']] for r in runs] or [dict(font='Times New Roman', size=12)])
    heights.append(line_height_pt(lines[-1], ru['pct'], ru) * 20)
    out = Lines(heights)
    out.skips = skips
    if ru.get('border_bottom'):
        out[-1] += RULE_EXTRA
    return out

class Lines(list):
    """line heights of a paragraph; .skips = the entries that are a jump below an object, not a line"""
    skips = frozenset()

def para_spacing(D, p):
    """(space before, space after) of a paragraph in twips (the ruler keeps them in points).  Measured on a
    DavkaWriter print: the gap between paragraphs is the line plus exactly this."""
    ru = D['rulers'].get(p.get('ruler'), {}) if not p.get('blank_page') else {}
    return int(round((ru.get('space_before') or 0) * 20)), int(round((ru.get('space_after') or 0) * 20))

def para_height(D, p, avail):
    """(total height with the space before/after, average line height) in twips"""
    ls = para_lines(D, p, avail)
    sb, sa = para_spacing(D, p)
    total = sum(ls)
    return total + sb + sa, total / len(ls)

WRAP_THROUGH = 5         # DavkaWriter wrap mode 5 (written as 1 for old versions): on its prints the text keeps clear of
                         # these objects too, unless the object is a background that covers most of the page
DEFAULT_WRAP_DIST = 144
BACKGROUND_AREA = 0.45 * 9360 * 12960     # twips²: a picture this large (about half a Letter text area) is a background

def wraps_text(o):
    """True when the text flows around this object in DavkaWriter (every mode and kind; a mode-5 background that
    covers most of the page lies behind the text)."""
    if o.get('newpic') or o.get('is_frame'):
        return False
    if o.get('folio_shape') and o.get('folio_wrap') in ('fixed', 'behind'):
        return False                       # (1.3.15: a shape or line in front of the text or behind it)
    if o.get('wrap_mode', 0) == WRAP_THROUGH:
        wh = object_box(o)
        return not (wh and wh[0] * wh[1] >= BACKGROUND_AREA)
    return True

def object_box(o):
    """(w, h) in twips of a page object, or None when its size is not known."""
    if o.get('kind') == 0x15:
        w, h = o.get('width'), o.get('height')
    elif o.get('kind') == 0x0f:
        return None
    else:
        w, h = o.get('w'), o.get('h')
        if o.get('disp_w') and o.get('disp_h'):
            w, h = o['disp_w'], o['disp_h']
    return (int(w), int(h)) if w and h else None

def mark_frames(D):
    """A curvy-text title drawn inside an autoshape on the same page: the shape is its frame (o['is_frame']),
    the title is laid out in it (t['frame']).  Done before pagination so every path sees the same objects."""
    by = {}
    for o in D.get('objects') or []:
        by.setdefault(o.get('page'), []).append(o)
    for objs in by.values():
        for t in objs:
            if t.get('kind') != 0x0f:
                continue
            for r in objs:
                if r.get('kind') == 0x0e and not r.get('folio') and r.get('w') and r.get('h') and r['x'] - 300 <= t['x'] <= r['x'] + r['w'] and r['y'] - 300 <= t['y'] <= r['y'] + r['h']:
                    t['frame'] = (r['x'], r['y'], r['w'], r['h'])
                    r['is_frame'] = True
                    break

def page_obstacles(D, mar, avail):
    """page index -> [(top, bottom, x0, x1, dist)] of the page objects text wraps around (text-area twips)."""
    out = {}
    for o in D.get('objects') or []:
        if o.get('page') is None or o.get('anchor') == 'paragraph' or not wraps_text(o):
            continue
        wh = object_box(o)
        if not wh:
            continue
        w, h = wh
        x0, y0 = o['x'] - mar[0], o['y'] - mar[1]
        wr = o.get('wrap') or [DEFAULT_WRAP_DIST, 0, DEFAULT_WRAP_DIST, 0]
        dist = max(0, int((wr[0] + wr[2]) / 2)) if wr else DEFAULT_WRAP_DIST
        if x0 + w <= 0 or x0 >= avail or y0 + h <= 0:
            continue
        out.setdefault(o['page'], []).append((y0 - (wr[1] if wr else 0), y0 + h + (wr[3] if wr else 0), x0, x0 + w, dist, o))
    for v in out.values():
        v.sort(key=lambda ob: ob[:5])        # (never by the object itself)
    return out

def is_empty_box(o):
    """a text box with no text in it (a frame to draw or write in)"""
    if o.get('kind') != 0x15:
        return False
    return not any((r.get('utext') or r['text']).strip(b' \t\r\xa0' if isinstance(r.get('utext') or r['text'], bytes) else ' \t\r\xa0') or r.get('object') or r.get('field')
                   for q in o.get('paras') or [] for r in q['runs']) and not any(q.get('table') for q in o.get('paras') or [])

def anchored_obstacle(o, top, avail):
    """(top, bottom, x0, x1, dist) of an object anchored to a paragraph that starts at top (text-area twips),
    or None when the text does not wrap around it"""
    if not wraps_text(o):
        return None
    wh = object_box(o)
    if not wh:
        return None
    w, h = wh
    x0, y0 = o.get('x') or 0, top + (o.get('y') or 0)
    if x0 + w <= 0 or x0 >= avail:
        return None
    wr = o.get('wrap') or [DEFAULT_WRAP_DIST, 0, DEFAULT_WRAP_DIST, 0]
    return (y0 - wr[1], y0 + h + wr[3], x0, x0 + w, max(0, int((wr[0] + wr[2]) / 2)), o)

def column_geometry(D, ru, text_w):
    """(column widths, gap) in twips of a multi-column paragraph format.  DavkaWriter stores the widths and
    the gap as shares of the text width (they add up to 10000), so they are stretched to the text column."""
    nc = ru.get('ncols', 1) or 1
    ws = [w for w in (ru.get('col_widths') or []) if isinstance(w, (int, float))]
    gap = ru.get('col_gap') or 0
    if len(ws) != nc or min(ws, default=0) <= 0:
        gap = int(gap) if 0 < gap < text_w / nc else 360
        w = max(300, (text_w - gap * (nc - 1)) // nc)
        return [w] * nc, gap
    tot = sum(ws) + gap * (nc - 1)
    f = text_w / float(tot) if tot > 0 else 1.0
    ws = [max(300, int(round(w * f))) for w in ws]
    return ws, int(round(gap * f))

def para_ncols(D, p):
    if p.get('table') is not None or p.get('blank_page') or p.get('flat'):
        return 1
    return D['rulers'].get(p['ruler'], {}).get('ncols', 1) or 1

def paginate(D, capacity):
    """Page breaks the way DavkaWriter makes them: line by line.  Returns the paragraph indices that start
    pages (pages[0] == 0) and the height of every paragraph.  A page may begin inside a paragraph: then
    that paragraph is listed with D['main'][i]['soft'] = True and no explicit break is written for it (Word
    splits the paragraph itself); D['soft_pages'] holds those page numbers.

    Columns are a paragraph property in DavkaWriter: a run of paragraphs with the same column format is a
    block whose text fills column 1 of the page, then column 2 ...; a block that ends before the page does
    is balanced (DavkaWriter and Word both do that); a column break (brk 2) ends the column, a page break
    (brk 1) the page.  D['_cols'] records, per page, the column boxes and the paragraphs in them."""
    pages = [0]
    pw = paper(D)[0]
    mar = D['page']['margins']
    avail = pw - mar[0] - mar[2]
    main = D['main']
    mark_frames(D)
    for o in D.get('objects') or []:
        o.pop('_text_wraps', None)
    for p in main:
        for o in p.get('objects') or []:
            o.pop('_text_wraps', None)
    lines = []           # per paragraph: list of line (or table row) heights, at the width it is laid out at
    seen_tables = set()
    pinned = bool(D.get('pinned'))      # page breaks from a printout (dwdfix): no breaks of the model's own
    ncol = [para_ncols(D, p) for p in main]
    colgeo = {}
    for i, p in enumerate(main):
        if ncol[i] > 1:
            ru = D['rulers'].get(p['ruler'], {})
            colgeo[i] = column_geometry(D, ru, avail)
    def para_line_list(i, width, obstacles=None, y=0, hits=None):
        p = main[i]
        t = p.get('table')
        if t is not None:
            if id(t) in seen_tables:
                return [0]
            seen_tables.add(id(t))
            return [row_height(D, t, ri, width) for ri in range(len(t['rows']))] + [20]
        sb, sa = para_spacing(D, p)
        pl = para_lines(D, p, width, obstacles, y + sb, hits)
        ls = Lines(pl)
        ls.skips = getattr(pl, 'skips', frozenset())
        ls[0] += sb; ls[-1] += sa
        return ls
    obstacles = page_obstacles(D, mar, avail)
    at_width = {}
    def lines_at(k, w):
        """the line heights of paragraph k laid out at width w (cached; tables keep their own rows)"""
        if main[k].get('table') is not None:
            return lines[k]
        key = (k, int(w))
        if key not in at_width:
            at_width[key] = para_line_list(k, w)
        return at_width[key]
    D['_lines_at'] = at_width
    for i, p in enumerate(main):
        w = avail if ncol[i] == 1 else colgeo[i][0][0]
        lines.append(para_line_list(i, w))
    # footnotes: a paragraph's notes are printed at the foot of its page, so they take room on that page; the
    # first ones on a page also bring the divider line
    note_h = [0] * len(main)
    fns = D.get('footnotes') or []
    if fns:
        for i, p in enumerate(main):
            ids = [r['footnote_id'] for r in p['runs'] if r.get('note') == 'CFieldFootnote' and r.get('footnote_id')]
            note_h[i] = sum(para_height(D, q, avail)[0] for k in ids if 0 < k <= len(fns) for q in fns[k - 1])
    page_has_notes = [False]
    carry_for = {}           # page index -> footnote height carried over to its foot
    note_ids = [[r['footnote_id'] for r in p['runs'] if r.get('note') == 'CFieldFootnote' and r.get('footnote_id') and r['footnote_id'] <= len(fns)] for p in main]
    def with_notes(i, ls):
        if not note_h[i]:
            return ls
        extra = note_h[i] + (0 if page_has_notes[0] else FOOTNOTE_DIVIDER)
        return ls[:-1] + [ls[-1] + extra]
    hs = [sum(ls) for ls in lines]
    total_after = [0] * (len(hs) + 1)
    for i in range(len(hs) - 1, -1, -1):
        total_after[i] = total_after[i + 1] + hs[i]
    # empty paragraphs at the very end of the document never earn a page of their own
    last_text = max((i for i, p in enumerate(main) if p.get('table') or any(r['text'].strip(b' \t\xa0') or r.get('field') for r in p['runs'])), default=-1)
    # ...unless pictures and boxes still sit on later pages (a document of text boxes laid on blank lines)
    last_obj_page = max((o['page'] for o in D.get('objects') or [] if o.get('page') is not None and 0 <= o['page'] < 5000), default=-1)
    has_text = lambda p: any(r['text'].strip(b' \t\xa0') for r in p['runs']) or p.get('table') is not None
    used = 0
    soft = set()
    cols = {}            # page index -> list of column dicts (x, w, top, paras: [(i, first line, last line)])
    for p in main:
        for k in ('soft', 'soft_lines', 'band_push', 'drop', 'col_start', 'col_break', 'col_sect'):
            p.pop(k, None)
    i = 0
    n = len(main)
    notes_page = [-1]
    retry_i = -1
    base = [list(ls) for ls in lines]     # each paragraph's lines without page-dependent additions
    added = {}                            # paragraph -> the obstacles its anchored objects added (page, obstacle)
    while i < n:
        p = main[i]
        page_has_notes[0] = notes_page[0] == len(pages) - 1
        if note_h[i]:
            notes_page[0] = len(pages) - 1
        retry = retry_i == i                 # the paragraph was moved to a new page: lay it out again there
        retry_i = -1
        if i > 0 and (main[i - 1].get('brk') and ncol[i - 1] == 1 or p.get('pbb') and used > 0) and not retry:   # DavkaWriter's page break sits after a paragraph
            pages.append(i); used = 0
        if ncol[i] > 1:
            # ---- a column block: paragraphs i..j-1 with the same column format
            j = i
            while j < n and ncol[j] == ncol[i] and colgeo[j] == colgeo[i]:
                j += 1
            ws0, gap = colgeo[i]
            nc = len(ws0)
            xs0 = [sum(ws0[:k]) + gap * k for k in range(nc)]
            is_rtl = lambda k: bool(D['rulers'].get(main[k]['ruler'], {}).get('rtl'))
            def order(k):
                """column widths and x positions in fill order for a block that paragraph k starts: a
                right-to-left block fills the rightmost column first (like a bidi section in Word)"""
                if is_rtl(k):
                    return ws0[::-1], xs0[::-1]
                return list(ws0), list(xs0)
            if used > 0 and (used + min(hs[i], lines[i][0]) > capacity and not pinned or p.get('pbb')):
                pages.append(i); used = 0
            top = used
            col = 0
            cused = 0
            ws, xs = order(i)
            main[i]['col_sect'] = is_rtl(i)
            boxes = [dict(x=xs[k], w=ws[k], top=top, paras=[]) for k in range(nc)]
            page_blocks = [(len(pages) - 1, boxes)]     # (page index, column boxes) of every page the block touches
            def new_page(at):
                nonlocal top, col, cused, boxes, ws, xs
                pages.append(at)
                top = 0; col = 0; cused = 0
                boxes = [dict(x=xs[k], w=ws[k], top=0, paras=[]) for k in range(nc)]
                page_blocks.append((len(pages) - 1, boxes))
            k = i
            while k < j:
                q = main[k]
                # lines at this column's width (a block with unequal columns re-wraps per column)
                ls = lines_at(k, ws[col])
                cap = capacity - top + FIT_TOL
                room = cap - cused
                if sum(ls) <= room or cused == 0 and len(ls) == 1 or pinned and col == nc - 1:
                    boxes[col]['paras'].append((k, 0, len(ls)))
                    cused += sum(ls)
                    if cused > cap:
                        cused = cap
                    k += 1
                else:
                    # fill the rest of the column line by line, the rest of the paragraph starts the next column
                    m = 0
                    while m < len(ls) and cused + ls[m] <= cap:
                        cused += ls[m]; m += 1
                    if m == 0 and cused > 0:
                        # nothing fits here: the paragraph starts in the next column
                        if col + 1 < nc:
                            col += 1; cused = 0
                        else:
                            new_page(k)
                        continue
                    boxes[col]['paras'].append((k, 0, m))
                    rest = ls[m:]
                    if col + 1 < nc:
                        col += 1; cused = 0
                    else:
                        new_page(k); soft.add(len(pages) - 1)
                        q['soft'] = True; q['soft_lines'] = m
                    # the remaining lines
                    while rest:
                        cap = capacity - top + FIT_TOL
                        mm = 0
                        while mm < len(rest) and cused + rest[mm] <= cap:
                            cused += rest[mm]; mm += 1
                        if mm == 0:
                            mm = 1; cused = cap
                        boxes[col]['paras'].append((k, m, m + mm))
                        m += mm
                        rest = rest[mm:]
                        if rest:
                            if col + 1 < nc:
                                col += 1; cused = 0
                            else:
                                new_page(k); soft.add(len(pages) - 1)
                                q['soft'] = True; q['soft_lines'] = m
                    k += 1
                if q.get('brk') == 2 and k < j:            # column break after this paragraph
                    if col + 1 < nc:
                        col += 1; cused = 0
                        q['col_break'] = 'col'
                    else:
                        new_page(k)
                        q['col_break'] = 'page'            # (the next paragraph gets the page break)
                elif q.get('brk') and k < j:               # page break after this paragraph
                    new_page(k)
            # the block's last page: DavkaWriter balances the columns there (so does Word at a continuous
            # section end), so the block takes about 1/n of its text height on that page
            heights = [sum(sum(lines_at(q, bx['w'])[a:b]) for q, a, b in bx['paras']) for bx in boxes]
            if sum(heights) and not any(main[q].get('col_break') or main[q].get('brk') for bx in boxes for q, a, b in bx['paras']):
                bal = int(math.ceil(sum(heights) / float(nc))) + 10
                # re-distribute the lines over the columns at that height
                # (paragraphs that move to another column keep their line count: close enough for the balance)
                flat = [(q, li, lines_at(q, bx['w'])) for bx in boxes for q, a, b in bx['paras'] for li in range(a, b)]
                boxes_b = [dict(x=xs[c], w=ws[c], top=top, paras=[]) for c in range(nc)]
                c = 0; acc = 0
                for q, li, lq in flat:
                    h = lq[li] if li < len(lq) else 0
                    if acc + h > bal and acc > 0 and c + 1 < nc:
                        c += 1; acc = 0
                    bp = boxes_b[c]['paras']
                    if bp and bp[-1][0] == q and bp[-1][2] == li:
                        bp[-1] = (q, bp[-1][1], li + 1)
                    else:
                        bp.append((q, li, li + 1))
                    acc += h
                boxes[:] = boxes_b
                page_blocks[-1] = (page_blocks[-1][0], boxes_b)
                heights = [sum(sum(lines_at(q, bx['w'])[a:b]) for q, a, b in bx['paras']) for bx in boxes]
            used = top + min(max(heights) if heights else 0, capacity - top)
            for bi, (pi, bxs) in enumerate(page_blocks):
                bh = (used - top) if bi == len(page_blocks) - 1 else capacity - bxs[0]['top']
                for bx in bxs:
                    bx['bh'] = bh
                cols.setdefault(pi, []).append(bxs)
            main[i]['col_start'] = True
            if j < n and main[j - 1].get('brk'):
                pages.append(j); used = 0
            i = j
            continue
        # less the footnotes carried over from the page before; plus FIT_TOL: the model's rounding (a page that
        # DavkaWriter fills to the last line comes out a hair too tall here)
        cap = capacity - carry_for.get(len(pages) - 1, 0) + FIT_TOL
        lines[i] = list(base[i])
        body_ls = lines[i]
        if note_h[i]:
            lines[i] = with_notes(i, lines[i])
        hs[i] = sum(lines[i])
        if p.get('objects'):
            # pictures and boxes anchored to this paragraph: the text after them (on this page) wraps around them
            for pg_, ob in added.pop(i, []):
                if ob in obstacles.get(pg_, []):
                    obstacles[pg_].remove(ob)
            for o in p['objects']:
                ob = anchored_obstacle(o, used, avail)
                if ob is not None:
                    obstacles.setdefault(len(pages) - 1, []).append(ob)
                    added.setdefault(i, []).append((len(pages) - 1, ob))
                    o['_obstacle'] = True
        obs = obstacles.get(len(pages) - 1)
        hits = set()
        if obs and p.get('table') is None:
            # the text wraps around this page's pictures and boxes: lay the paragraph out where it starts.
            # Empty lines too (a document of boxes laid on blank lines fills exactly the pages its boxes are on),
            # except under an empty box (a frame to draw in, laid over the blank lines that make its room) or one
            # that runs off the foot of the page.
            # An object that some line meets is marked, so Word wraps around it as well
            if not has_text(p):
                # (also under an object that reaches into the bottom margin: blank lines at the foot of the page)
                obs = [ob for ob in obs if not (len(ob) > 5 and (is_empty_box(ob[5]) or ob[1] > capacity - 400))]
            ls = para_line_list(i, avail, obs, used, hits) if obs else list(base[i])
            body_ls = ls
            lines[i] = with_notes(i, ls) if note_h[i] else ls
            hs[i] = sum(lines[i])
            total_after[i] = total_after[i + 1] + hs[i]
        ls = lines[i]
        def commit():
            """the paragraph stays on this page: the objects its text met are wrapped around in Word too"""
            for ob in obs or ():
                if len(ob) > 5 and id(ob[5]) in hits:
                    ob[5]['_text_wraps'] = True
        if note_h[i] and used + hs[i] > cap and used > 0:
            # the notes don't all fit: the reference line and the first line of each note stay, the rest of the
            # notes go on at the foot of the next page (DavkaWriter and Word continue a long footnote)
            first = sum(sum(para_lines(D, q, avail)[:1]) for k in note_ids[i] for q in fns[k - 1][:1])
            need = sum(body_ls) + first + (0 if page_has_notes[0] else FOOTNOTE_DIVIDER)
            if used + need <= cap:
                over = used + hs[i] - cap
                carry_for[len(pages)] = carry_for.get(len(pages), 0) + min(over, capacity * 0.5)
                used = cap
                commit()
                i += 1
                continue
        if pinned:
            # the page breaks are the printout's: the model only follows them (Word breaks a page that overflows)
            commit()
            used += hs[i]
            i += 1
            continue
        if used > cap and used > 0 and i > 0:
            pages.append(i); used = 0
            retry_i = i                       # (laid out again at the top of the new page)
            continue
        elif used + hs[i] > cap and used > 0:
            if i > last_text and len(pages) > last_obj_page:
                hs[i] = 0; p['drop'] = True; i += 1; continue
            # the estimate is ~1% uncertain: don't start a new page just for the
            # document's last few lines when they nearly fit
            if used + total_after[i] <= cap * 1.012:
                commit()
                used += hs[i]; i += 1; continue
            k_fit = 0
            acc = used
            while k_fit < len(ls) and acc + ls[k_fit] <= cap:
                acc += ls[k_fit]; k_fit += 1
            only_skips = all(k in getattr(ls, 'skips', ()) for k in range(k_fit))
            if len(ls) == 1 or used + ls[0] > cap or only_skips or (p.get('table') is not None and hs[i] <= capacity and TABLE_WHOLE):
                pages.append(i); used = 0
                if obs or obstacles.get(len(pages) - 1) or p.get('objects'):
                    retry_i = i                   # lay it out again among the new page's objects
                    continue
            else:
                # the paragraph straddles the page end: its first lines stay, the rest start the next page
                k = 0
                while k < len(ls) and used + ls[k] <= cap:
                    used += ls[k]; k += 1
                rest = sum(ls[k:])
                while rest > capacity:          # a very long paragraph can span several pages
                    pages.append(i); soft.add(len(pages) - 1)
                    rest -= capacity
                pages.append(i); soft.add(len(pages) - 1)
                p['soft'] = True
                p['soft_lines'] = k            # lines that stay on the previous page
                used = rest
                commit()
                i += 1
                continue
        commit()
        used += hs[i]
        i += 1
    # where a model column ends at the end of a paragraph (and no page or column break follows anyway), Word gets
    # an explicit column break there, so it fills the columns the way the model (and DavkaWriter) did
    starts = set(pages)
    for pi, blocks in cols.items():
        for bxs in blocks:
            for c, bx in enumerate(bxs[:-1]):
                if not bx['paras'] or not bxs[c + 1]['paras']:
                    continue
                q, a, b = bx['paras'][-1]
                if bxs[c + 1]['paras'][0][0] == q:
                    continue                      # the paragraph goes on in the next column
                if b < len(lines_at(q, bx['w'])) or main[q].get('col_break') or (q + 1) in starts:
                    continue
                main[q]['col_break'] = 'col'
    D['soft_pages'] = soft
    D['_obstacles'] = obstacles
    D['_cols'] = cols
    D['_lines'] = lines
    return pages, hs

# ------------------------------------------------------------- docx xml
HEB_LETTERS = 'אבגדהוזחטיכלמנסעפצקרשת'
def hebrew_number(n):
    vals = [(400,'ת'),(300,'ש'),(200,'ר'),(100,'ק'),(90,'צ'),(80,'פ'),(70,'ע'),(60,'ס'),(50,'נ'),(40,'מ'),(30,'ל'),(20,'כ'),(10,'י'),(9,'ט'),(8,'ח'),(7,'ז'),(6,'ו'),(5,'ה'),(4,'ד'),(3,'ג'),(2,'ב'),(1,'א')]
    out = ''
    if n >= 15 and n % 100 in (15, 16):
        pass
    for v, ch in vals:
        while n >= v:
            if v == 10 and n in (15, 16):
                break
            out += ch; n -= v
        if n in (15, 16) and v == 10:
            out += 'טו' if n == 15 else 'טז'; n = 0
    return out

PAREN_SWAP = str.maketrans('()[]{}<>', ')(][}{><')
NEUTRAL_RE = re.compile(r'[-\u2013\u2014:;,.?!/\\"\'*+=#%&@~^_|]+')
DIGITS_RE = re.compile(r'[0-9]+')
def hebrew_text(b):
    """Davka Hebrew run -> Unicode. DavkaWriter shows a Hebrew run simply reversed, so punctuation
    keeps its place in the Hebrew order (surround it with RLM) and digits come out reversed."""
    t = decode(b).translate(PAREN_SWAP)
    t = DIGITS_RE.sub(lambda m: m.group()[::-1], t)
    return NEUTRAL_RE.sub(lambda m: '\u200f' + m.group() + '\u200f', t)

LETTER_MARKS_RE = re.compile('([\u05d0-\u05ea])([\u0591-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]+)')
CTRL_RE = re.compile('[\x00-\x02\x04-\x08\x0b\x0c\x0e-\x1f]')
RULE = '\x03'          # DavkaWriter's line character: advances to the next tab stop drawing a rule

def run_xml(st, text, rtl, extra='', bidi=None):
    size = word_size(st, rtl)
    if rtl:
        font = word_font(st['font'])
    else:
        font = st['font']
    props = ['<w:rFonts w:ascii="%s" w:hAnsi="%s" w:cs="%s"%s/>' % (font, font, font, ' w:hint="cs"' if rtl else '')]
    if st.get('outline'):
        props.append('<w:color w:val="%s"/>' % outline_spec(st)[0])
    elif st.get('color'):
        c = st['color']
        props.append('<w:color w:val="%02X%02X%02X"/>' % (c & 0xff, (c >> 8) & 0xff, (c >> 16) & 0xff))
    if st.get('bold'):
        props.append('<w:b/><w:bCs/>')
    if st.get('italic'):
        props.append('<w:i/><w:iCs/>')
    if st.get('underline'):
        props.append('<w:u w:val="single"/>')
    scale, fix = width_fix(st, rtl)
    if scale != 100:
        props.append('<w:w w:val="%d"/>' % scale)
    props.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size))
    if rtl:
        props.append('<w:rtl/>')
    props.append(extra)
    ol = outline_xml(st)
    if ol:
        # hollow letters where w14 effects aren't read (LibreOffice)
        props.insert(-2 if rtl else -1, '<w:outline/>' )
        props.append(ol)
    out = []
    if extra == 'FIELD:PAGE':
        rp = '<w:rPr>%s</w:rPr>' % ''.join(props[:-1])
        return ('<w:r>%s<w:fldChar w:fldCharType="begin"/></w:r><w:r>%s<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
                '<w:r>%s<w:fldChar w:fldCharType="separate"/></w:r><w:r>%s<w:t>1</w:t></w:r><w:r>%s<w:fldChar w:fldCharType="end"/></w:r>') % ((rp,) * 5)
    # split on tabs; a bare CR is a line break; other control characters (DavkaWriter markers) become spaces
    text = CTRL_RE.sub(' ', text)
    if is_symbol_font(st['font']) and not rtl:
        # Wingdings & co.: the pictures as Unicode in a font every Word has (Segoe UI Symbol on Windows; Word for Mac
        # and LibreOffice fall back for the glyph).  w:sym would be exact in Word but LibreOffice loses it next to
        # Hebrew.  Codes without a Unicode twin stay w:sym in the original font.
        uf = 'Times New Roman' if st['font'] == 'Symbol' else 'Segoe UI Symbol'
        up = [('<w:rFonts w:ascii="%s" w:hAnsi="%s" w:cs="%s"/>' % (uf, uf, uf)) if x.startswith('<w:rFonts') else x for x in props]
        rp, urp = '<w:rPr>%s</w:rPr>' % ''.join(props), '<w:rPr>%s</w:rPr>' % ''.join(up)
        for part in re.split(r'(\t|\r|\x03| +)', text):
            if not part:
                continue
            if part in ('\t', RULE):
                out.append('<w:r>%s<w:tab/></w:r>' % rp)
            elif part == '\r':
                out.append('<w:r>%s<w:br/></w:r>' % rp)
            elif not part.strip(' '):
                out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rp, part))
            else:
                for ch in part:
                    if 0xF020 <= ord(ch) <= 0xF0FF:
                        out.append('<w:r>%s<w:sym w:font="%s" w:char="%04X"/></w:r>' % (rp, st['font'], ord(ch)))
                    else:
                        out.append('<w:r>%s<w:t>%s</w:t></w:r>' % (symbol_rpr(st, ch, urp, uf), escape(ch)))
        return ''.join(out)
    # (1.3.25) the marks on a letter in Folio's one order (shin / sin dot, dagesh, vowel, then meteg and trop:
    # davkamap.mark_rank), whatever order they came in (the editor, a Word file, a PDF): ךָּ is ך, dagesh, kamatz
    # (only a Hebrew letter's marks: a mark after anything else, e.g. a DavkaWriter byte Folio can't read yet, stays put)
    if any('\u0591' <= c <= '\u05c7' for c in text):
        text = LETTER_MARKS_RE.sub(lambda m: m.group(1) + ''.join(sorted(m.group(2), key=mark_rank)), text)
    parts = re.split(r'(\t|\r|\x03)', text)
    texts = [i for i, part in enumerate(parts) if part and part not in ('\t', '\r', RULE)]
    for i, part in enumerate(parts):
        if part == '\t':
            out.append('<w:r><w:rPr>%s</w:rPr><w:tab/></w:r>' % ''.join(props))
        elif part == RULE:
            rp = [x for x in props if not x.startswith('<w:u ')] + ['<w:u w:val="%s"/>' % ('thick' if st['size'] >= 20 else 'single')]
            out.append('<w:r><w:rPr>%s</w:rPr><w:tab/></w:r>' % ''.join(rp))
        elif part == '\r':
            out.append('<w:r><w:rPr>%s</w:rPr><w:br/></w:r>' % ''.join(props))
        elif part:
            txt = bidi_edges(part, rtl, bidi, i == texts[0], i == texts[-1], i + 1 < len(parts) or (bidi is not None and bidi[3]))
            if not fix:
                out.append('<w:r><w:rPr>%s</w:rPr><w:t xml:space="preserve">%s</w:t></w:r>' % (''.join(props), escape(txt)))
                continue
            # the words with their single spaces at one scale; a blank (a row of spaces or underscores) in a run of
            # its own, scaled to DavkaWriter's width of those characters
            at = next(k for k, x in enumerate(props) if x.startswith(('<w:w ', '<w:sz ')))
            skip = 1 if props[at].startswith('<w:w ') else 0
            for seg in BLANK_RE.split(txt):
                if not seg:
                    continue
                sc = fix.get(seg[0] if seg[0] != '\u00a0' else ' ') if BLANK_RE.fullmatch(seg) else text_scale(st, rtl, seg)
                pr = props[:at] + ['<w:w w:val="%d"/>' % sc] + props[at + skip:] if sc != 100 else props[:at] + props[at + skip:]
                out.append('<w:r><w:rPr>%s</w:rPr><w:t xml:space="preserve">%s</w:t></w:r>' % (''.join(pr), escape(seg)))
    return ''.join(out)

def symbol_rpr(st, ch, urp, uf):
    """the run properties of a Wingdings / Webdings picture written as Unicode: drawn smaller where the font that
    shows it (a fallback such as DejaVu Sans; font_calib.json 'sym') is wider than the layout model makes the
    Wingdings code, so a line of checkboxes holds what DavkaWriter's line holds"""
    adv = freefonts.SYMBOLS.get(ch) if uf == 'Segoe UI Symbol' else None
    if not adv or not st.get('size'):
        return urp
    mw = text_width(dict(st, size=1), symbol_encode(st['font'], ch), 0) / 20.0
    if not mw or adv <= mw * 1.02:
        return urp
    sz = max(int(math.floor(st['size'] * 2 * mw / adv + 1e-6)), 2)
    return re.sub(r'<w:sz w:val="\d+"/><w:szCs w:val="\d+"/>', '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (sz, sz), urp)

LRM, RLM = '\u200e', '\u200f'

def bidi_edges(text, rtl, bidi, first=True, last=True, sep_after=False):
    """Pin a run's edge characters to the run's own direction.  bidi = (paragraph rtl, the nearest text run
    before is in the other direction, the nearest text run after is): a Hebrew run in an English paragraph (or
    an English run in a Hebrew one) that starts or ends with a space, a digit or punctuation gets an RLM (LRM)
    there, and so does a run of the paragraph's own direction where it meets a run of the other direction.
    Every neutral character then belongs to the run it was typed in, the way the Folio editor (and
    DavkaWriter) show it, so Word, LibreOffice and Google Docs lay a mixed line out in the same order.  The
    editor adds the very same marks where it draws the text (web/editor/src/bidi.js: runMarks)."""
    if not text or bidi is None:
        return text
    para_rtl, prev_opp, next_opp = bidi[:3]
    foreign = bool(rtl) != bool(para_rtl)
    own = ('R', 'AL') if rtl else ('L',)
    if (foreign or (first and prev_opp)) and unicodedata.bidirectional(text[0]) not in own:
        text = (RLM if rtl else LRM) + text
    if (foreign or (last and next_opp)) and unicodedata.bidirectional(text[-1]) not in own:
        core = text.rstrip(' ')
        if sep_after and core != text:
            # spaces before a tab or at the end of the paragraph take the paragraph's direction anyway: the
            # mark goes before them, so they can still hang at the end of a full line
            if core and unicodedata.bidirectional(core[-1]) not in own:
                text = core + (RLM if rtl else LRM) + text[len(core):]
        else:
            text = text + (RLM if rtl else LRM)
    return text

def run_neighbours(runs, rtl):
    """bidi info (see bidi_edges) of each (st, txt, heb) run of a paragraph"""
    texty = [k for k, (st, txt, heb) in enumerate(runs)
             if not isinstance(txt, dict) and txt != '\ufffc' and re.sub(r'[\t\r\x03]', '', txt)]
    out = []
    for k, (st, txt, heb) in enumerate(runs):
        prev = [j for j in texty if j < k]
        nxt = [j for j in texty if j > k]
        # what follows the run: nothing, or a tab / line break (then its trailing spaces are at a segment end)
        after = next((r[1] for r in runs[k + 1:] if isinstance(r[1], dict) or r[1]), None)
        sep = after is None or (not isinstance(after, dict) and after[0] in '\t\r\x03')
        out.append((rtl, bool(prev) and runs[prev[-1]][2] != heb, bool(nxt) and runs[nxt[0]][2] != heb, sep))
    return out
    own = ('R', 'AL') if rtl else ('L',)
    if unicodedata.bidirectional(text[0]) not in own:
        text = (RLM if rtl else LRM) + text
    if unicodedata.bidirectional(text[-1]) not in own:
        text = text + (RLM if rtl else LRM)
    return text

def outline_spec(st):
    """(fill RRGGBB, outline RRGGBB, width in EMU) of outlined text, or None.  Styles made in the Folio editor
    carry st['outline'] = {'f': '#RRGGBB', 'c': '#RRGGBB', 'w': EMU}; DavkaWriter's own outlined styles are
    hollow letters (white fill, outline in the text colour)."""
    o = st.get('outline')
    if o:
        return (o.get('f') or '#FFFFFF').lstrip('#').upper(), (o.get('c') or '#000000').lstrip('#').upper(), int(o.get('w') or 12700)
    if st.get('outlined'):
        c = st.get('color') or 0
        # the stroke grows with the size, as in a DavkaWriter print (a 28 pt title: about 2.2 pt, nearly filling the thin letters)
        return 'FFFFFF', '%02X%02X%02X' % (c & 0xff, (c >> 8) & 0xff, (c >> 16) & 0xff), int(max(9525, (st.get('size') or 12) * 0.08 * 12700))
    return None

def outline_xml(st):
    """Word 2010+ text outline (w14:textOutline) and fill (w14:textFill)."""
    sp = outline_spec(st)
    if not sp:
        return ''
    fill, line, w = sp
    return ('<w14:textOutline w14:w="%d" w14:cap="flat" w14:cmpd="sng" w14:algn="ctr"><w14:solidFill><w14:srgbClr w14:val="%s"/></w14:solidFill>'
            '<w14:prstDash w14:val="solid"/><w14:round/></w14:textOutline>'
            '<w14:textFill><w14:solidFill><w14:srgbClr w14:val="%s"/></w14:solidFill></w14:textFill>' % (w, line, fill))

def boxed_runs(st, text, rtl, bidi=None):
    """A boxed run is one box around all its words, as DavkaWriter prints it (Word joins the borders of the runs
    the text is split into); spaces before and after it stay outside the box."""
    import re
    out = []
    lead, core, trail = re.match(r'^(\s*)(.*?)(\s*)$', text, re.S).groups()
    toks = [t for t in (lead, core, trail) if t]
    for i, tok in enumerate(toks):
        b = None if bidi is None else (bidi[0], bidi[1] and i == 0, bidi[2] and i == len(toks) - 1, bidi[3] if i == len(toks) - 1 else False)
        if tok.isspace():
            out.append(run_xml(st, tok, rtl, bidi=b))
        else:
            # (a space inside each end: DavkaWriter's box stands about 2.5 pt clear of its letters at the sides; the
            # border's own w:space would pad the top and bottom too, in LibreOffice)
            # (a right-to-left run's spaces between right-to-left marks: else, at a line's end in a left-to-right
            # paragraph, the space is drawn as a box of its own beside the word's, in LibreOffice.  Not for a
            # left-to-right run: a Latin font without the mark changes the line's height there)
            m = '\u200f' if rtl else ''
            out.append(run_xml(st, m + ' ' + tok + ' ' + m, rtl, '<w:bdr w:val="single" w:sz="6" w:space="0" w:color="000000"/>', bidi=b))
    return ''.join(out)

def para_xml(D, p, page_break=False, anchors='', in_box=False, sect='', box_w=None):
    S, R = D['styles'], D['rulers']
    ru = R.get(p['ruler'], dict(align=2, rtl=1, pct=100, ind1=0, ind2=0))
    runs = []
    first_heb = None
    for r in p['runs']:
        st = S.get(r['style'])
        if st is None:
            continue
        heb = is_hebrew_style(st)
        if 'utext' in r:                 # edited in the browser: already Unicode
            txt = r['utext']
        elif heb:
            txt = hebrew_text(r['text'])
        elif is_symbol_font(st['font']):
            txt = symbol_decode(st['font'], r['text'])
        else:
            txt = r['text'].decode('cp1252', 'replace')
        if r.get('field'):
            txt = '\ufffc'
        if r.get('footnote_id') and D.get('footnotes'):
            # a footnote reference in the text, or the number at the start of the note itself
            runs.append((st, dict(footnote=r['footnote_id'], ref=r.get('note') == 'CFieldFootnote'), heb))
            continue
        pic = inline_picture(r)
        if pic is not None:
            runs.append((st, dict(pic, newpic='inline'), heb))
            continue
        if r.get('newpic') is not None:
            continue
        if first_heb is None and txt.strip():
            first_heb = heb
        runs.append((st, txt, heb))
    rtl = bool(ru['rtl'])        # DavkaWriter lays runs out from the ruler's side; each Hebrew run is one block
    # alignment: Davka 0=left 1=center 2=right 3=justify (absolute sides)
    a = ru['align']
    if a == 3 and LO_SAFE and (ru.get('ncols', 1) or 1) > 1:
        # (test renders only) LibreOffice never finishes laying out a justified hanging-indent paragraph with
        # Hebrew runs in unequal columns; ragged lines break at the same places
        a = 0 if not rtl else 2
    if a == 1:
        jc = 'center'
    elif a == 3:
        jc = 'both'
    elif a == 4:                # justified with a centered last line: closest Word match is centered
        jc = 'center'
    elif a == 2:
        jc = 'left' if rtl else 'right'     # in bidi paragraphs Word's left/right mean start/end
    else:
        jc = 'right' if rtl else 'left'
    # Word needs one exact spacing per paragraph: use the average line height from the layout model
    # so the paragraph's total height matches DavkaWriter's
    avail_h = paper(D)[0] - D['page']['margins'][0] - D['page']['margins'][2]
    if box_w:
        avail_h = box_w
    elif not in_box and (ru.get('ncols', 1) or 1) > 1 and p.get('table') is None:
        avail_h = column_geometry(D, ru, avail_h)[0][0]       # laid out at its column's width
    total_h, lh = para_height(D, p, avail_h)
    lh = int(lh)
    # a picture wider than its column is shown at the column's width (Word would push it out of the column;
    # LibreOffice never finishes laying it out)
    max_w = max(600, avail_h - max(indents(ru)[0], 0) - max(indents(ru)[2], 0))
    if p.get('fs_scale'):           # a page fitted to a printout's page break: the text a little smaller
        runs = [(dict(st_, size=round(st_['size'] * p['fs_scale'] * 2) / 2.0), txt_, heb_) for st_, txt_, heb_ in runs]
    for k, (st_, txt_, heb_) in enumerate(runs):
        if isinstance(txt_, dict) and (txt_.get('w') or 0) > max_w:
            f = max_w / float(txt_['w'])
            runs[k] = (st_, dict(txt_, w=int(txt_['w'] * f), h=max(20, int((txt_.get('h') or 1440) * f))), heb_)
    if p.get('ls_scale'):        # a page fitted to a printout's page break (pinned_fit)
        lh = int(lh * p['ls_scale'])
    if p.get('tail'):            # empty lines at the very end: keep them from spilling onto a blank page
        lh = 20
    ppr = []
    if page_break:
        ppr.append('<w:pageBreakBefore/>')
    ppr.append('<w:widowControl w:val="0"/>')
    ml = p.get('mlist')
    if ml and ml.get('num'):       # a numbered list made in the Folio editor: real Word numbering
        ppr.append('<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%d"/></w:numPr>' % (ml.get('lvl', 0), ml.get('num', 1)))
    bsz = 0
    if ru.get('border_bottom'):
        bsz = 8 - 2 * (p.get('seq', 0) & 1)     # alternate so Word doesn't merge neighbours into one box
    inline_pic = any(inline_picture(r) is not None for r in p['runs'] if r['style'] in S)
    pic_exact = False
    if inline_pic:
        # 'at least' the height of a line of text: the lines with a picture grow by themselves
        pls = para_lines(D, p, avail_h)
        lh = int(min(pls))
        if len(pls) == 1:
            # one line holding the picture: 'at least' its height (with 'exactly', Word clips the picture and
            # LibreOffice draws it up over the line above)
            lh = int(pls[0])
    if ru.get('folio'):
        # a paragraph format made in the Folio editor: its own spacing before/after and line spacing
        before = p.get('push', 0) + p.get('band_push', 0) + int(round((ru.get('space_before') or 0) * 20 * p.get('sp_scale', 1.0)))
        after = int(round((ru.get('space_after') or 0) * 20 * p.get('sp_scale', 1.0)))
        mode = ru.get('ls_mode', 1)
        if inline_pic:
            line, rule = max(lh, 40), 'atLeast'
        elif mode == 1:
            line, rule = max(lh - (bsz * 20 // 8), 40), 'exact'
        else:
            line, rule = max(int(round((ru.get('ls_pt') or 12) * 20)), 40), ('exact' if mode == 2 else 'atLeast')
        ppr.append('<w:spacing w:before="%d" w:after="%d" w:line="%d" w:lineRule="%s"/>' % (before, after, line, rule))
    else:
        sb, sa = para_spacing(D, p)
        if p.get('sp_scale'):
            sb, sa = int(sb * p['sp_scale']), int(sa * p['sp_scale'])
        ppr.append('<w:spacing w:before="%d" w:after="%d" w:line="%d" w:lineRule="%s"/>' % (p.get('push', 0) + p.get('band_push', 0) + sb, sa, max(lh - (bsz * 20 // 8), 40), 'atLeast' if inline_pic and not pic_exact else 'exact'))
    bd = ru.get('borders') or [0, 0, 0, 0]
    if any(bd[k] for k in (0, 1, 3)):
        # DavkaWriter sides: top, left, bottom, right. Border 3 is double
        # (verified against native PDF), not a thick single stroke.
        col = colorref(ru.get('border_color') or 0)
        sp = ru.get('border_space') or [1, 4, 1, 4]
        kind = {1: ('single', 6), 2: ('single', 18), 3: ('double', 8)}
        sides = []
        for name, k in (('top', 0), ('left', 1), ('bottom', 2), ('right', 3)):
            if bd[k] in kind:
                v, sz = kind[bd[k]]
                side = name if name in ('top', 'bottom') else (('right' if name == 'left' else 'left') if rtl else name)
                sides.append((side, '<w:%s w:val="%s" w:sz="%d" w:space="%d" w:color="%s"/>' % (side, v, sz, min(31, sp[k] if k < len(sp) else 1), col)))
        order = {'top': 0, 'left': 1, 'bottom': 2, 'right': 3}
        ppr.append('<w:pBdr>%s</w:pBdr>' % ''.join(x for _, x in sorted(sides, key=lambda t: order[t[0]])))
    elif bsz:
        ppr.append('<w:pBdr><w:bottom w:val="single" w:sz="%d" w:space="0" w:color="000000"/></w:pBdr>' % bsz)
    left, first, right = indents(ru)
    lst = p.get('list')
    if lst and lst.get('mode') == 1:
        # bullets: DavkaWriter starts the text at the indent and hangs the bullet BULLET_HANG in front of it
        # (into the margin or the gutter when the indent is smaller), whatever the first-line indent
        left, first = left + max(first, 0), -BULLET_HANG
    elif lst and first >= 0:
        # the number hangs in the indent and the text starts at the indent (a tab after the number goes to the
        # hanging position); with too small an indent the number gets the usual 1/4"
        if left < 200:
            left, first = 360, -360
        else:
            first = -left
    if ml:
        left, first = 360 * (ml.get('lvl', 0) + 1) + max(0, left), -360
    if left or first or right:
        attrs = ' w:start="%d"' % left
        if right:
            attrs += ' w:end="%d"' % right
        if first < 0:
            attrs += ' w:hanging="%d"' % (-first)
        elif first > 0:
            attrs += ' w:firstLine="%d"' % first
        ppr.append('<w:ind%s/>' % attrs)
    text_w = avail_h
    tabs_ok = usable_tabs(ru, box_w if box_w else (text_w if not in_box else 20000))
    if tabs_ok:
        ppr.append('<w:tabs>%s</w:tabs>' % ''.join('<w:tab w:val="left" w:pos="%d"/>' % pos for typ, pos in tabs_ok))
    if rtl:
        ppr.append('<w:bidi/>')
    ppr.append('<w:jc w:val="%s"/>' % jc)
    # empty paragraph: give the mark the run size so its height is right
    mark = ''
    if runs:
        st = runs[0][0]
        mark = '<w:rPr><w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>' % (st['size'] * 2, st['size'] * 2)
    body = []
    # DavkaWriter wraps a line made only of spaces/tabs; Word lets them hang. Reproduce the wrap.
    lead_w, k = 0, 0
    tabs_pos = [pos for typ, pos in tabs_ok]
    avail_w = paper(D)[0] - D['page']['margins'][0] - D['page']['margins'][2] + 400
    raw = [r for r in p['runs'] if r['style'] in S]
    cross = None
    while k < len(runs) and not isinstance(runs[k][1], dict) and not runs[k][1].strip():
        lead_w += text_width(runs[k][0], raw[k]['text'], lead_w, tabs_pos)
        if cross is None and lead_w >= avail_w:
            cross = k
        k += 1
    if cross is not None and k < len(runs):
        # the wrapped line drops its leading spaces but keeps the tabs that follow the break
        ntab = sum(runs[j][1].count('\t') for j in range(cross + 1, k) if not isinstance(runs[j][1], dict))
        st0, _, heb0 = runs[k]
        runs = ([(st0, '\t' * ntab, heb0)] if ntab else []) + runs[k:]
        body.append('<w:r><w:br/></w:r>')
    if lst and runs:
        st = S.get(lst.get('style')) or runs[0][0]          # the number has its own style in DavkaWriter
        if lst.get('mode') == 1:
            body.append(run_xml(st, bullet_char(lst, st) + '\t', rtl, bidi=(rtl, False, False, False)))
        else:
            num = hebrew_number(lst['number']) if lst['hebrew'] else str(lst['number'])
            suf = lst['suffix']
            if rtl:
                suf = suf.translate(PAREN_SWAP)
            body.append(run_xml(st, num + suf + '\t', rtl, bidi=(rtl, False, False, False)))
    nb = run_neighbours(runs, rtl)
    for k, (st, txt, heb) in enumerate(runs):
        if isinstance(txt, dict) and 'footnote' in txt:
            rp = run_xml(st, 'x', heb).split('<w:rPr>', 1)[1].split('</w:rPr>', 1)[0]      # the run's own look
            rp = '<w:rPr>%s<w:vertAlign w:val="superscript"/></w:rPr>' % rp.replace('<w:rtl/>', '')
            body.append('<w:r>%s%s</w:r>' % (rp, '<w:footnoteReference w:id="%d"/>' % txt['footnote'] if txt['ref'] else '<w:footnoteRef/>'))
            continue
        if isinstance(txt, dict):            # a picture inserted in the editor, in line with the text
            body.append(inline_picture_xml(txt))
            continue
        if st['flags'] & 0x40 and txt.strip():
            body.append(boxed_runs(st, txt, heb, nb[k]))
        else:
            body.append(run_xml(st, txt, heb, 'FIELD:PAGE') if txt == '\ufffc' else run_xml(st, txt, heb, bidi=nb[k]))
    return '<w:p><w:pPr>%s%s%s</w:pPr>%s%s</w:p>' % (''.join(ppr), mark, sect, anchors, ''.join(body))

_id = [100]
class _Media:
    def __init__(self):
        self.items = []          # (name, png bytes)
    def reset(self):
        self.items = []
    def add(self, bmp):
        from bmpng import bmp_to_png
        try:
            png = bmp_to_png(bmp)
        except Exception:
            png = None
        if png is None:
            return None
        n = len(self.items) + 1
        self.items.append(('image%d.png' % n, png))
        return 'rIdImg%d' % n
    def add_raw(self, data, ext):
        """A picture Word can read as it is (JPEG, PNG, GIF), embedded byte for byte."""
        n = len(self.items) + 1
        self.items.append(('image%d.%s' % (n, ext), data))
        return 'rIdImg%d' % n
# picture formats stored in .dwd files that Word reads directly (CFieldGraphic data, by its length prefix)
RAW_IMAGE_EXT = {'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif'}
IMAGE_CT = {'png': 'image/png', 'jpeg': 'image/jpeg', 'gif': 'image/gif'}
MEDIA = _Media()

def _pic_rid(o):
    if o.get('bmp'):
        return MEDIA.add(o['bmp'])
    return MEDIA.add_raw(o['image'], RAW_IMAGE_EXT[o['image_format']])

def _pic_graphic(nid, rid, w, h, xfrm=''):
    emu = 635
    return ('<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="%d" name="picture %d"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm%s><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            '</a:graphicData></a:graphic>' % (nid, nid, rid, xfrm, w * emu, h * emu))

def placeholder_geom(o, w, h):
    """A marked spot (dashed rounded box with a note) the size of a picture Word can't show."""
    emu = 635
    fmt = 'LEAD (DavkaWriter\u2019s own) format' if o.get('image_format') == 'lead' else 'a format Word can\u2019t read'
    small = min(w, h) < 1500
    lines = ['Picture', 'not converted'] if small else ['Picture not converted', 'It is in ' + fmt + '.', 'Insert it again in Word.']
    rp = '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:color w:val="7A8494"/><w:sz w:val="%d"/></w:rPr>'
    note = ''.join('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="%d" w:lineRule="exact"/><w:jc w:val="center"/></w:pPr>'
                   '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (200 if small else 220, rp % (14 if k or small else 16), escape(t))
                   for k, t in enumerate(lines))
    return ('<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="F3F5F8"/></a:solidFill>'
            '<a:ln w="9525"><a:solidFill><a:srgbClr val="C3CAD5"/></a:solidFill><a:prstDash val="dash"/></a:ln></wps:spPr>'
            '<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>'
            '<wps:bodyPr rot="0" vert="horz" wrap="square" lIns="36000" tIns="36000" rIns="36000" bIns="36000" anchor="ctr"><a:noAutofit/></wps:bodyPr></wps:wsp>'
            % (w * emu, h * emu, note))

def inline_picture_xml(o):
    """A picture in line with the text: one inserted in the Folio editor (o['newpic'] == 'inline') or a
    DavkaWriter run picture.  One Word can't show keeps its room as a marked spot."""
    _id[0] += 1
    nid = _id[0]
    w, h = int(o.get('w') or 1440), int(o.get('h') or 1440)
    if not pic_renderable(o):
        return ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
                '<wp:docPr id="%d" name="Picture %d"/><wp:cNvGraphicFramePr/>'
                '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">%s</a:graphicData></a:graphic>'
                '</wp:inline></w:drawing></w:r>') % (w * 635, h * 635, nid, nid, placeholder_geom(o, w, h))
    rid = _pic_rid(o)
    return ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>'
            '<wp:docPr id="%d" name="Picture %d"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>%s'
            '</wp:inline></w:drawing></w:r>') % (w * 635, h * 635, nid, nid, _pic_graphic(nid, rid, w, h, arr_xfrm(o)))

# ------------------------------------------------------------- 1.3.14 Arrange (the editor's arrange.js) in Word
# Word's own wrap distances (twips: top, bottom, left, right) for the modes the text goes around
ARR_DIST0 = {'wrap': [0, 0, 187, 187], 'tight': [0, 0, 187, 187], 'topbottom': [0, 0, 0, 0]}
TIGHT_POLY = ('<wp:wrapPolygon edited="0"><wp:start x="0" y="0"/><wp:lineTo x="0" y="21600"/><wp:lineTo x="21600" y="21600"/>'
              '<wp:lineTo x="21600" y="0"/><wp:lineTo x="0" y="0"/></wp:wrapPolygon>')

def doc_rtl(D):
    """is the document mostly right to left (Hebrew)? (the side a wrap's "start" is on)"""
    if D is None:
        return True
    if '_rtl' not in D:
        rs = [bool((D['rulers'].get(p.get('ruler')) or {}).get('rtl')) for p in (D.get('main') or [])[:200] if p.get('ruler') is not None]
        D['_rtl'] = (sum(rs) * 2 >= len(rs)) if rs else True
    return D['_rtl']

def arr_wrap(D, o, mode):
    """(distance attributes, wrap element, behindDoc) for a wrap set in the editor: wrap (Square), tight, topbottom,
    behind, fixed (In front of the text)"""
    emu = 635
    if mode in ('fixed', 'behind'):
        return 'distT="0" distB="0" distL="0" distR="0"', '<wp:wrapNone/>', 1 if mode == 'behind' else 0
    d = o.get('wrap_dist') or ARR_DIST0.get(mode) or [0, 0, 187, 187]
    dist = 'distT="%d" distB="%d" distL="%d" distR="%d"' % tuple(int(v) * emu for v in d)
    if mode == 'topbottom':
        return dist, '<wp:wrapTopAndBottom/>', 0
    side = o.get('wrap_side') or 'both'
    rtl = doc_rtl(D)
    wt = {'both': 'bothSides', 'largest': 'largest', 'start': 'right' if rtl else 'left', 'end': 'left' if rtl else 'right'}[side]
    if mode == 'tight':
        return dist, '<wp:wrapTight wrapText="%s">%s</wp:wrapTight>' % (wt, TIGHT_POLY), 0
    return dist, '<wp:wrapSquare wrapText="%s"/>' % wt, 0

def arr_xfrm(o):
    """the a:xfrm attributes of a turned or flipped object (Word turns clockwise, in 60000ths of a degree)"""
    a = ''
    r = o.get('folio_rot') or 0
    if r:
        a += ' rot="%d"' % (int(r) % 360 * 60000)
    if o.get('flip_h'):
        a += ' flipH="1"'
    if o.get('flip_v'):
        a += ' flipV="1"'
    return a

def arr_height(o, nid):
    """relativeHeight: the stacking order the teacher set (from_editor: z_order), else the document's order"""
    z = o.get('z_order')
    return z if isinstance(z, int) and z > 0 else nid

def new_anchor_xml(o, D=None):
    """A picture inserted in the Folio editor that isn't in line with the text: wrapped by it (Square, Tight, Top and
    bottom; 1.3.13's Wrap text not yet placed: at the column's right edge), behind it or in front of it, at x (from the
    margin), y (from the paragraph, or from the page when it is fixed on the page)."""
    _id[0] += 1
    nid = _id[0]
    w, h = int(o.get('w') or 1440), int(o.get('h') or 1440)
    rid = _pic_rid(o)
    mode = o['newpic']
    if mode == 'wrap' and not o.get('placed'):
        pos = ('<wp:positionH relativeFrom="column"><wp:align>right</wp:align></wp:positionH>'
               '<wp:positionV relativeFrom="paragraph"><wp:posOffset>0</wp:posOffset></wp:positionV>'
               '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>' % (w * 635, h * 635))
        if o.get('wrap_dist') or o.get('wrap_side'):
            dist, wrap, behind = arr_wrap(D, o, 'wrap')
            dist = ' ' + dist
        else:
            wrap, behind, dist = '<wp:wrapSquare wrapText="bothSides"/>', 0, ' distT="0" distB="91440" distL="182880" distR="0"'
        pos += wrap
    else:
        rel_v = 'page' if o.get('pin') == 'page' else 'paragraph'
        dist, wrap, behind = arr_wrap(D, o, mode)
        dist = ' ' + dist
        pos = ('<wp:positionH relativeFrom="margin"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
               '<wp:positionV relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
               '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>%s'
               % (int(o.get('x') or 0) * 635, rel_v, int(o.get('y') or 0) * 635, w * 635, h * 635, wrap))
    return ('<w:r><w:drawing><wp:anchor%s simplePos="0" relativeHeight="%d" behindDoc="%d" locked="%d" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/>%s<wp:docPr id="%d" name="Picture %d"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>%s'
            '</wp:anchor></w:drawing></w:r>') % (dist, arr_height(o, nid), behind, 1 if o.get('locked') else 0, pos, nid, nid,
                                                _pic_graphic(nid, rid, w, h, arr_xfrm(o)))

def colorref(c):
    """Windows COLORREF (0x00BBGGRR) -> 'RRGGBB'"""
    c = int(c or 0)
    return '%02X%02X%02X' % (c & 0xff, (c >> 8) & 0xff, (c >> 16) & 0xff)

def shape_style(o):
    """An autoshape's look: (preset geometry, line colour or None, fill colour or None).  The shape type is
    the subtype (3 = ellipse, as in a DavkaWriter print; 4 = rounded rectangle); older files only set the shape
    field (3 = ellipse).  flags bit 0 = outline drawn, bit 1 = filled; colours are Windows COLORREFs."""
    sub, shape = o.get('subtype'), o.get('shape')
    if sub == 3:
        prst = 'ellipse'
    elif sub == 4:
        prst = 'roundRect'
    else:
        prst = {1: 'rect', 3: 'ellipse'}.get(shape, 'rect')
    flags = o.get('shape_flags')
    line = colorref(o.get('line_color')) if flags is None or flags & 1 else None
    fill = colorref(o.get('fill_color')) if flags is not None and flags & 2 and o.get('fill_color') is not None else None
    return prst, line, fill

def box_line(o):
    """A text box's outline: the colour and width DavkaWriter keeps for it (a white border is invisible on
    the page, as DavkaWriter shows it), or none."""
    if not o.get('border'):
        return '<a:ln><a:noFill/></a:ln>'
    bb = (o.get('box_border') or {}).get('top') or {}
    col = (bb.get('color') or '000000').upper()
    wd = bb.get('width')
    emuw = int(max(6350, min(76200, (wd or 4) * 6350))) if wd is not None else 25400     # width in 1/4 pt
    cmpd = ' cmpd="dbl"' if o.get('box_double') else ''
    return '<a:ln w="%d"%s><a:solidFill><a:srgbClr val="%s"/></a:solidFill></a:ln>' % (emuw, cmpd, col)

def box_fill(o):
    """a text box's fill: the colour set in the editor, else none"""
    f = o.get('folio_fill')
    return '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % f if f else '<a:noFill/>'

def box_pad(o):
    """inner margins (left, top, right, bottom) in points: DavkaWriter's box padding, 3.6 pt if unknown"""
    p = o.get('pad')
    if p and len(p) == 4 and all(isinstance(v, (int, float)) and 0 <= v <= 40 for v in p):
        return [p[0], p[1], p[2], p[3]]
    return [3.6, 3.6, 3.6, 3.6]

def anchor_xml(D, o, hint_heights):
    if o.get('newpic'):
        return new_anchor_xml(o, D)
    _id[0] += 1
    nid = _id[0]
    emu = 635
    x, y = o['x'], o['y']
    rel_h, rel_v = 'page', 'page'
    if o.get('anchor') == 'paragraph':
        rel_h, rel_v = ('page', 'page') if o.get('pin_page') else ('margin', 'paragraph')
    elif o.get('rel_y') is not None:
        rel_v = 'paragraph'
        y = o['rel_y']
    as_pic = bool(o.get('replaced_image')) and o.get('image_format') in RAW_IMAGE_EXT
    if o.get('folio_shape') and not as_pic:
        return shape_anchor_xml(D, o, nid, rel_h, rel_v, x, y)
    if o['kind'] == 0x0f and not as_pic and not o.get('frame') and (o.get('flexi') is not None or o.get('flexi_ed') is not None):
        return flexi_anchor_xml(D, o, nid, rel_h, rel_v, x, y)
    if o['kind'] == 0x0f and not as_pic:             # DavkaWriter "curvy text" (decorative title)
        txt_b = o.get('text', b'')
        font = o.get('font', 'Times New Roman')
        heb = font.startswith(('Davka', 'GuttmanD'))
        size = o.get('size', 24)
        st = dict(font=font, size=size, flags=0x02 if heb else 0, color=0, bold=True)
        txt = hebrew_text(txt_b) if heb else txt_b.decode('cp1252', 'replace')
        w = int(max(len(txt.replace('\u05b0', '')) * size * 0.55 * 20, 1200)) if not heb else int(sum(1 for c in txt if '\u05d0' <= c <= '\u05ea' or c == ' ') * size * 0.62 * 20 + 600)
        w = max(w, int(text_width(st, txt_b, 0) * 1.15) + 600)      # never narrower than the text (it would be cut off)
        h = int(size * 1.6 * 20)
        warp = ''
        geo = curvy_geometry(o, st, txt_b)
        if geo is not None and not o.get('frame'):
            # text on an arc (DavkaWriter's curved titles): a Word text warp on a shape whose ellipse is the arc's
            # circle; the arc's top is where DavkaWriter's box starts
            prst, adj, w, h, dx, dy = geo
            x, y = x + dx, y + dy
            warp = '<a:prstTxWarp prst="%s"><a:avLst><a:gd name="adj" fmla="val %d"/></a:avLst></a:prstTxWarp>' % (prst, adj)
        if o.get('frame'):                     # sits inside a box: fill the box, centered
            x, y, w, h = o['frame']
            if rel_v == 'paragraph' and o.get('host_top') is not None:
                y = y - o['host_top']
        rx = run_xml(st, txt, heb)
        if warp:
            # WordArt text takes its colour from the run's text fill (LibreOffice draws it white without one)
            col = colorref(o.get('text_color') or 0)
            rx = rx.replace('</w:rPr>', '<w:color w:val="%s"/><w14:textFill><w14:solidFill><w14:srgbClr w14:val="%s"/></w14:solidFill></w14:textFill></w:rPr>' % (col, col))
        para = ('<w:p><w:pPr><w:spacing w:before="0" w:after="0"/>%s<w:jc w:val="center"/></w:pPr>%s</w:p>'
                % ('<w:bidi/>' if heb else '', rx))
        rot = o.get('rot') or 0
        rot_xml = ' rot="%d"' % int((360 - rot) % 360 * 60000) if not warp and 0 < rot < 360 else ''   # (DavkaWriter turns counter-clockwise)
        geom = ('<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm%s><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></wps:spPr>'
                '<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>'
                '<wps:bodyPr rot="0" vert="horz" wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"%s>%s<a:noAutofit/></wps:bodyPr></wps:wsp>'
                % (rot_xml, w * emu, h * emu, para, ' fromWordArt="1"' if warp else '', warp))
    elif o['kind'] == 0x15 and not as_pic:
        w = o.get('width') or 2000
        o.setdefault('paras', [])
        tw = [p['table'].get('width') or 0 for p in o['paras'] if p.get('table')]
        if tw and not o.get('width_known'):
            w = max(w, max(tw) + 160)        # the box is at least as wide as the table it holds
        mar = D['page']['margins']
        est = 200
        inner = ''
        done = set()
        for p in o['paras']:
            t = p.get('table')
            if t is not None:
                if id(t) not in done:
                    done.add(id(t))
                    inner += table_xml(D, t, mar, max_width=w - 100)
                    est += table_height(D, t, w - 100)
                continue
            inner += para_xml(D, p, in_box=True, box_w=max(w - 140, 300))
            est += para_height(D, p, max(w - 140, 600))[0]      # at the box's own width
        inner = inner or '<w:p/>'
        h = max(o.get('height') or 0, est)
        pad = [int(v * 20 * emu) for v in box_pad(o)]
        geom = ('<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>%s%s</wps:spPr>'
                '<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>'
                '<wps:bodyPr rot="0" vert="horz" wrap="square" lIns="%d" tIns="%d" rIns="%d" bIns="%d" anchor="t"><a:noAutofit/></wps:bodyPr></wps:wsp>'
                % (w * emu, h * emu, box_fill(o), box_line(o), inner, pad[0], pad[1], pad[2], pad[3]))
    elif o.get('bmp') or o.get('image_format') in RAW_IMAGE_EXT:   # a Windows bitmap (embedded as a PNG) or JPEG/PNG/GIF
        w, h = o.get('w') or 1440, o.get('h') or 1440
        if o.get('disp_w') and o.get('disp_h'):
            w, h = o['disp_w'], o['disp_h']
        rid = MEDIA.add(o['bmp']) if o.get('bmp') else MEDIA.add_raw(o['image'], RAW_IMAGE_EXT[o['image_format']])
        pic = ('<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="%d" name="picture %d"/><pic:cNvPicPr/></pic:nvPicPr>'
               '<pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
               '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
               % (nid, nid, rid, w * emu, h * emu))
        dist, wrap, behind = wrap_xml(D, o)
        if arr_xfrm(o):
            pic = pic.replace('<pic:spPr><a:xfrm>', '<pic:spPr><a:xfrm%s>' % arr_xfrm(o), 1)
        return ('<w:r><w:drawing><wp:anchor %s simplePos="0" relativeHeight="%d" behindDoc="%d" locked="%d" layoutInCell="1" allowOverlap="1">'
                '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
                '<wp:positionV relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
                '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>%s'
                '<wp:docPr id="%d" name="Davka picture %d"/><wp:cNvGraphicFramePr/>'
                '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">%s</a:graphicData></a:graphic>'
                '</wp:anchor></w:drawing></w:r>') % (dist, arr_height(o, nid), behind, 1 if o.get('locked') else 0, rel_h, int(x * emu), rel_v, int(y * emu), int(w * emu), int(h * emu), wrap, nid, nid, pic)
    elif o.get('picture'):         # DavkaWriter picture: stored in a format Word can't read, so leave a marked spot
        w, h = o.get('w') or 1440, o.get('h') or 1440
        geom = placeholder_geom(o, w, h)
    else:
        w, h = o.get('w') or 800, o.get('h') or 800
        shape = o.get('shape')
        if o.get('line'):          # a straight line through the middle of its box
            if w >= 2 * h:
                y = y + h // 2; h = 0
            else:
                x = x + w // 2; w = 0
            prst = 'line'
        else:
            prst = None
        sp, line, fill = shape_style(o)
        prst = prst or sp
        if prst == 'line':
            line, fill = line or '000000', None
        fill_xml = '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % fill if fill else '<a:noFill/>'
        ln_xml = '<a:ln w="19050"><a:solidFill><a:srgbClr val="%s"/></a:solidFill></a:ln>' % line if line else '<a:ln><a:noFill/></a:ln>'
        geom = ('<wps:wsp><wps:cNvSpPr/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
                '<a:prstGeom prst="%s"><a:avLst/></a:prstGeom>%s%s</wps:spPr>'
                '<wps:bodyPr/></wps:wsp>' % (w * emu, h * emu, prst, fill_xml, ln_xml))
        o['_behind'] = bool(fill)       # a filled shape goes behind the text so it never hides it
    dist, wrap, behind = wrap_xml(D, o)
    if o.pop('_behind', False) and not wraps_text(o) and not o.get('folio_wrap'):
        behind = 1
    if arr_xfrm(o) and '<wps:spPr><a:xfrm>' in geom:
        geom = geom.replace('<wps:spPr><a:xfrm>', '<wps:spPr><a:xfrm%s>' % arr_xfrm(o), 1)
    return ('<w:r><w:drawing><wp:anchor %s simplePos="0" relativeHeight="%d" behindDoc="%d" locked="%d" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>%s'
            '<wp:docPr id="%d" name="Davka object %d"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">%s</a:graphicData></a:graphic>'
            '</wp:anchor></w:drawing></w:r>') % (dist, arr_height(o, nid), behind, 1 if o.get('locked') else 0, rel_h, int(x * emu), rel_v, int(y * emu), int(w * emu), int(h * emu),
               wrap, nid, nid, geom)

# ------------------------------------------------------------- shapes and lines drawn in Folio (1.3.15)
# o['folio_shape'] (dwdedit.shape_clean): shape, ln {c, w (pt), d, a0, a1}, fill, shadow, lh / lv (a line's flips);
# o['paras']: a closed shape's text.  Word's preset shapes with their default adjustments (the editor, shapes.js, draws
# the same geometry); a line with arrows is a straight connector with Word's triangle arrowheads.
SHAPE_PRST = {'rect': 'rect', 'roundRect': 'roundRect', 'ellipse': 'ellipse', 'triangle': 'triangle', 'star5': 'star5',
              'speech': 'wedgeRoundRectCallout', 'callout': 'wedgeRectCallout'}
SHAPE_DASH = {'dash': 'dash', 'dot': 'sysDot'}
# (a shape's text in the document's text colour: without a style LibreOffice draws it in the background colour)
SHAPE_STYLE = ('<wps:style><a:lnRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:lnRef><a:fillRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:fillRef>'
               '<a:effectRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:effectRef><a:fontRef idx="minor"><a:schemeClr val="tx1"/></a:fontRef></wps:style>')

def shape_anchor_xml(D, o, nid, rel_h, rel_v, x, y):
    emu = 635
    S = o['folio_shape']
    line = S.get('shape') == 'line'
    w, h = max(0, int(o.get('w') or 0)), max(0, int(o.get('h') or 0))
    if not line:
        w, h = max(w, 60), max(h, 60)
    ln = S.get('ln') or {}
    lw = int(round(max(0.25, min(20.0, float(ln.get('w') or 1.5))) * 12700))
    col = (ln.get('c') or '').lstrip('#').upper()
    if line and not col:
        col = '000000'
    dash = SHAPE_DASH.get(ln.get('d'))
    ends = ''
    if line:
        if ln.get('a0'):
            ends += '<a:headEnd type="triangle" w="lg" len="lg"/>'
        if ln.get('a1'):
            ends += '<a:tailEnd type="triangle" w="lg" len="lg"/>'
    ln_xml = ('<a:ln w="%d"><a:solidFill><a:srgbClr val="%s"/></a:solidFill>%s<a:round/>%s</a:ln>' % (lw, col, '<a:prstDash val="%s"/>' % dash if dash else '', ends)
              if col else '<a:ln><a:noFill/></a:ln>')
    fill = (S.get('fill') or '').lstrip('#').upper()
    fill_xml = '<a:noFill/>' if line or not fill else '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % fill
    eff = ('<a:effectLst><a:outerShdw blurRad="38100" dist="25400" dir="2700000" algn="tl" rotWithShape="0"><a:srgbClr val="000000"><a:alpha val="40000"/></a:srgbClr></a:outerShdw></a:effectLst>'
           if S.get('shadow') else '')
    if line:
        prst = 'straightConnector1' if (ln.get('a0') or ln.get('a1')) else 'line'
        flips = (' flipH="1"' if S.get('lh') else '') + (' flipV="1"' if S.get('lv') else '')
    else:
        prst = SHAPE_PRST.get(S.get('shape'), 'rect')
        flips = arr_xfrm(o)
    txt = ''
    paras = o.get('paras') or []
    if not line and any((r.get('utext') or r['text']) for p in paras for r in p.get('runs') or []):
        inner = ''.join(para_xml(D, p, in_box=True, box_w=max(w - 300, 300)) for p in paras if not p.get('table')) or '<w:p/>'
        txt = '<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>' % inner
    body = '<wps:bodyPr rot="0" vert="horz" wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720" anchor="ctr" anchorCtr="0"><a:noAutofit/></wps:bodyPr>'
    geom = ('<wps:wsp><wps:cNvSpPr/><wps:spPr><a:xfrm%s><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="%s"><a:avLst/></a:prstGeom>%s%s%s</wps:spPr>%s%s%s</wps:wsp>'
            % (flips, w * emu, h * emu, prst, fill_xml, ln_xml, eff, SHAPE_STYLE if txt else '', txt, body))
    dist, wrap, behind = wrap_xml(D, o)
    if not o.get('folio_wrap') and fill and not wraps_text(o):
        behind = 1                         # (a filled DavkaWriter shape lies behind the text, as before)
    return ('<w:r><w:drawing><wp:anchor %s simplePos="0" relativeHeight="%d" behindDoc="%d" locked="%d" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>%s'
            '<wp:docPr id="%d" name="Folio %s %d"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">%s</a:graphicData></a:graphic>'
            '</wp:anchor></w:drawing></w:r>') % (dist, arr_height(o, nid), behind, 1 if o.get('locked') else 0, rel_h, int(x * emu), rel_v, int(y * emu),
                                                 int(w * emu), int(h * emu), wrap, nid, 'line' if line else 'shape', nid, geom)

# DavkaWriter's curve presets that were checked against its prints (9: arch over, as on a cover; 7: a shallow
# arch); the others stay straight text until their shapes are known
CURVE_WARP = {9: 'textArchUp', 7: 'textArchUp'}

def curvy_geometry(o, st, txt_b):
    """(warp preset, adj, w, h, dx, dy) in twips for curved text, or None for straight text.  The text runs
    along an arc of o['arc'] degrees of a circle; the shape is that circle's square (Word lays a warped text on
    the ellipse inscribed in its shape), placed so the arc starts at DavkaWriter's x, y (the arc's box)."""
    prst = CURVE_WARP.get(o.get('curve'))
    arc = o.get('arc') or 0
    if not prst or not 10 <= arc <= 350:
        return None
    L = max(text_width(st, txt_b, 0), 600)                  # the text's length along the arc
    th = math.radians(arc)
    r = L / th + st['size'] * 10                            # (the baseline runs half a line inside the circle)
    chord = 2 * r * math.sin(min(th, math.pi) / 2) if arc <= 180 else 2 * r
    d = int(2 * r)
    start = (90 + arc / 2.0) % 360 if prst == 'textArchUp' else (270 - arc / 2.0) % 360
    adj = int(round(start * 60000))
    # DavkaWriter's x, y is the top left of the arc's box: the circle's left is half the difference further out
    dx = -int(r - chord / 2)
    dy = 0 if prst == 'textArchUp' else -int(d - (r * (1 - math.cos(min(th, math.pi) / 2)) + st['size'] * 20))
    return prst, adj, d, d, dx, dy

# ------------------------------------------------------------- FlexiText (DavkaWriter's curved / decorated titles)
# Every setting of DavkaWriter's FlexiText Settings dialog (dwdread.flexi_fields), in the form the editor uses
# (text in Unicode, colours #RRGGBB).  Edited in Folio: o['flexi_ed'] (the editor's own record, from_editor).
FLEXI_DEFAULT = dict(text='', font='Times New Roman', size=24.0, heb=False, bold=False, italic=False, underline=False,
                     spacing=0, stretch=100, effect='normal', color='#000000', outline_color='#000000', outline_w=1,
                     gradient=False, gradient_to='#80FF00', d3=False, d3_type='block', d3_color='#808080',
                     d3_color2='#FFFFFF', d3_depth=9, d3_angle=45, d3_relative=False, path=0, angle=135, rotate=0,
                     slant=0, skew=0, justify=0)
FLEXI_JUSTIFY = ('center', 'left', 'right', 'full', 'spread', 'stretch', 'stretchfinal')
# path shapes (dwdread.flexi_fields) Word draws with a WordArt warp of its own the way DavkaWriter does: the arch over
# (9, checked against DavkaWriter's prints).  Word's own cup and peak warps (textArchDown, textTriangle) don't follow
# DavkaWriter's shapes closely enough (and LibreOffice draws them upside down or not at all): from the editor those go
# in as its picture of the title; converted without the editor, a peak (7) is a shallow arch (as since 1.3.7) and the
# others straight text.
FLEXI_WARP = {9: 'textArchUp'}
FLEXI_WARP_NOPIC = {9: 'textArchUp', 7: 'textArchUp'}
_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


def _num(v, lo, hi, d):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return d
    return d if v != v else max(lo, min(hi, v))


def flexi_clean(f):
    """a FlexiText record (from the file or the editor) with every key, in range"""
    out = dict(FLEXI_DEFAULT)
    for k, d in FLEXI_DEFAULT.items():
        v = f.get(k, d) if isinstance(f, dict) else d
        if isinstance(d, bool):
            out[k] = bool(v)
        elif k in ('color', 'outline_color', 'gradient_to', 'd3_color', 'd3_color2'):
            out[k] = v.upper() if isinstance(v, str) and _HEX_RE.match(v) else d
        elif isinstance(d, str):
            out[k] = v if isinstance(v, str) else d
        else:
            out[k] = v
    out['text'] = out['text'][:2000]
    out['font'] = out['font'][:64] or 'Times New Roman'
    out['size'] = _num(out['size'], 4, 400, 24.0)
    out['spacing'] = int(_num(out['spacing'], -50, 200, 0))
    out['stretch'] = int(_num(out['stretch'], 10, 600, 100))
    out['outline_w'] = int(_num(out['outline_w'], 1, 20, 1))
    out['d3_depth'] = int(_num(out['d3_depth'], 1, 100, 9))
    out['d3_angle'] = int(_num(out['d3_angle'], -360, 360, 45))
    out['path'] = int(_num(out['path'], 0, 15, 0))
    out['angle'] = int(_num(out['angle'], 1, 360, 135))
    out['rotate'] = int(_num(out['rotate'], -360, 360, 0)) % 360
    out['slant'] = int(_num(out['slant'], -80, 80, 0))
    out['skew'] = int(_num(out['skew'], -80, 80, 0))
    out['justify'] = int(_num(out['justify'], 0, 6, 0))
    if out['effect'] not in ('normal', 'outline', 'filled'):
        out['effect'] = 'normal'
    if out['d3_type'] not in ('gradient', 'block', 'shadow'):
        out['d3_type'] = 'block'
    return out


def flexi_of(o):
    """A FlexiText object's settings for the editor and for Word (see FLEXI_DEFAULT), or None"""
    if o.get('flexi_ed') is not None:
        return flexi_clean(o['flexi_ed'])
    f = o.get('flexi')
    if f is None:                                        # (the heuristic reader: what it knows)
        if o.get('kind') != 0x0f:
            return None
        font = o.get('font', 'Times New Roman')
        f = dict(text=o.get('text', b''), font=font, size=o.get('size', 24.0), heb=font.startswith(('Davka', 'GuttmanD')),
                 bold=True, path=o.get('curve') or 0, angle=o.get('arc') or 135, rotate=o.get('rot') or 0,
                 color=o.get('text_color') or 0, d3_color=o.get('shadow_color', 0x808080))
    f = dict(f)
    font = f.get('font') or 'Times New Roman'
    tb = f.get('text', b'')
    if isinstance(tb, bytes):
        text = hebrew_text(tb) if font.startswith(('Davka', 'GuttmanD')) else tb.decode('cp1252', 'replace')
    else:
        text = tb
    f['text'] = text.replace('\r\n', '\n').replace('\r', '\n').replace('‏', '').replace('‎', '')
    for k in ('color', 'outline_color', 'gradient_to', 'd3_color', 'd3_color2'):
        if isinstance(f.get(k), int):
            f[k] = '#' + colorref(f[k])
    return flexi_clean(f)


# fonts DavkaWriter draws titles in bigger than their size (as flexi.js FIT): font (+ '/Bold') -> (letter scale,
# extra width of a space in em); measured on DavkaWriter's prints and screen
FLEXI_FIT = {'GuttmanD Adii': (1.18, 0.0), 'GuttmanD Adii/Bold': (1.18, 0.44)}


def flexi_fit(F):
    return FLEXI_FIT.get(F['font'] + ('/Bold' if F['bold'] else '')) or FLEXI_FIT.get(F['font']) or (1.0, 0.0)


def flexi_hebrew(F):
    """is the FlexiText Hebrew (its Hebrew flag, or a Davka font with Hebrew letters in it)"""
    return bool(F['heb'] or re.search('[֐-׿]', F['text']))


def flexi_native(F):
    """can Word draw it itself (a WordArt text warp and Word's text effects), so that it looks like DavkaWriter's?"""
    if F['path'] not in (0,) + tuple(FLEXI_WARP):
        return False
    if F['d3'] and F['d3_type'] == 'gradient':
        return False
    if F['slant'] or F['skew']:
        return False
    return True


def flexi_bytes(F, line):
    """a line of the FlexiText in the bytes the width model measures"""
    if F['font'].startswith(('Davka', 'GuttmanD')):
        from davkamap import encode
        return encode(line)
    return line.encode('cp1252', 'replace')


def flexi_rpr(F, heb):
    """the run properties of a FlexiText line in Word: font, size, bold, italic, underline, spacing, stretch, and
    the text effects (w14): fill (colour or gradient, none for Outline), outline, shadow (3D Block or Shadow)"""
    fs, ft = flexi_fit(F)
    st = dict(font=F['font'], size=F['size'] * fs, flags=0x02 if heb else 0, bold=F['bold'])
    size = word_size(st, heb)
    font = word_font(F['font']) if heb else F['font']
    col = F['color'].lstrip('#')
    p = ['<w:rFonts w:ascii="%s" w:hAnsi="%s" w:cs="%s"%s/>' % (escape(font), escape(font), escape(font), ' w:hint="cs"' if heb else '')]
    if F['bold']:
        p.append('<w:b/><w:bCs/>')
    if F['italic']:
        p.append('<w:i/><w:iCs/>')
    p.append('<w:color w:val="%s"/>' % (F['outline_color'].lstrip('#') if F['effect'] == 'outline' else col))
    # (the wider spaces of a FLEXI_FIT font, shared out over the letters: a run's spacing is the same for each letter)
    n = len(F['text'].replace('\n', ''))
    extra = ft * F['size'] * fs * 20 * F['text'].count(' ') / n if n else 0
    if F['spacing'] or extra:
        p.append('<w:spacing w:val="%d"/>' % int(round(F['spacing'] * F['size'] * fs * 20 / 100.0 + extra)))
    scale = int(round(width_fix(st, heb)[0] * F['stretch'] / 100.0))
    if scale != 100:
        p.append('<w:w w:val="%d"/>' % max(1, min(600, scale)))
    p.append('<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size, size))
    if F['underline']:
        p.append('<w:u w:val="single"/>')
    if heb:
        p.append('<w:rtl/>')
    if F['d3']:
        a = math.radians(F['d3_angle'])
        dist = F['size'] * fs * F['d3_depth'] / 150.0 * 12700               # points -> EMU
        ang = math.degrees(math.atan2(math.cos(a), math.sin(a))) % 360      # DrawingML: clockwise from the x axis
        p.append('<w14:shadow w14:blurRad="0" w14:dist="%d" w14:dir="%d" w14:sx="100000" w14:sy="100000" w14:kx="0" w14:ky="0" w14:algn="none">'
                 '<w14:srgbClr w14:val="%s"/></w14:shadow>' % (int(dist), int(round(ang * 60000)), F['d3_color'].lstrip('#')))
    if F['effect'] != 'normal':
        p.append('<w14:textOutline w14:w="%d" w14:cap="flat" w14:cmpd="sng" w14:algn="ctr"><w14:solidFill><w14:srgbClr w14:val="%s"/></w14:solidFill>'
                 '<w14:prstDash w14:val="solid"/><w14:round/></w14:textOutline>' % (int(F['outline_w'] * 9525), F['outline_color'].lstrip('#')))
    if F['effect'] == 'outline':
        p.append('<w14:textFill><w14:noFill/></w14:textFill>')
    elif F['gradient']:
        p.append('<w14:textFill><w14:gradFill><w14:gsLst><w14:gs w14:pos="0"><w14:srgbClr w14:val="%s"/></w14:gs><w14:gs w14:pos="100000"><w14:srgbClr w14:val="%s"/></w14:gs></w14:gsLst>'
                 '<w14:lin w14:ang="5400000" w14:scaled="0"/></w14:gradFill></w14:textFill>' % (col, F['gradient_to'].lstrip('#')))
    else:
        p.append('<w14:textFill><w14:solidFill><w14:srgbClr w14:val="%s"/></w14:solidFill></w14:textFill>' % col)
    return '<w:rPr>%s</w:rPr>' % ''.join(p)


def flexi_geometry(F, heb, x, y):
    """(warp XML, x, y, w, h) in twips of a FlexiText's shape in Word.  An arch (Word's textArchUp) is set on the
    circle whose arc of F['angle'] degrees is as long as the text, placed so the arc's box starts at DavkaWriter's
    x, y (as curvy_geometry); anything else is straight text."""
    fs, ft = flexi_fit(F)
    st = dict(font=F['font'], size=F['size'] * fs, flags=0x02 if heb else 0, bold=F['bold'])
    lines = F['text'].split('\n') or ['']
    per = F['size'] * fs * 20 * F['spacing'] / 100.0
    L = max([text_width(st, flexi_bytes(F, ln), 0) * F['stretch'] / 100.0 + ft * F['size'] * fs * 20 * ln.count(' ') + per * len(ln) for ln in lines] + [600])
    lh = F['size'] * fs * 20 * 1.3
    prst = FLEXI_WARP_NOPIC.get(F['path'])
    if prst in ('textArchUp', 'textArchDown') and 10 <= F['angle'] <= 350:
        th = math.radians(F['angle'])
        r = L / th + F['size'] * fs * 10
        chord = 2 * r * math.sin(min(th, math.pi) / 2) if F['angle'] <= 180 else 2 * r
        d = int(2 * r)
        if prst == 'textArchUp':
            start = (90 + F['angle'] / 2.0) % 360
            dy = 0
        else:
            start = (270 - F['angle'] / 2.0) % 360
            dy = -int(d - (r * (1 - math.cos(min(th, math.pi) / 2)) + F['size'] * fs * 20))
        warp = '<a:prstTxWarp prst="%s"><a:avLst><a:gd name="adj" fmla="val %d"/></a:avLst></a:prstTxWarp>' % (prst, int(round(start * 60000)))
        return warp, x - int(r - chord / 2), y + dy, d, d
    # (straight: the box 1.3.7-1.3.13 gave a title, a line and a half high per line, its text in the middle)
    return '', x, y, int(L * 1.15) + 600, int(F['size'] * fs * 1.6 * 20) + int(lh * (len(lines) - 1))


def flexi_anchor_xml(D, o, nid, rel_h, rel_v, x, y):
    """A FlexiText in Word: Word's own WordArt (text warp + text effects) when Word can draw it like DavkaWriter
    does (flexi_native), else the picture of it the editor drew (o['flexi_png']: png bytes, width, height in
    twips), so it always looks right.  Without that picture (a conversion outside the editor) the WordArt is
    written anyway, as close as Word allows."""
    emu = 635
    F = flexi_of(o)
    heb = flexi_hebrew(F)
    dist, wrap, behind = wrap_xml(D, o)
    zi = o.get('z_order')
    rh = zi if isinstance(zi, int) and zi > 0 else nid
    png = o.get('flexi_png')
    locked = '1' if o.get('locked') else '0'
    if png and not flexi_native(F):
        data, w, h = png
        rid = MEDIA.add_raw(data, 'png')
        return ('<w:r><w:drawing><wp:anchor %s simplePos="0" relativeHeight="%d" behindDoc="%d" locked="%s" layoutInCell="1" allowOverlap="1">'
                '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
                '<wp:positionV relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
                '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>%s'
                '<wp:docPr id="%d" name="FlexiText %d" descr="%s"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>%s'
                '</wp:anchor></w:drawing></w:r>') % (dist, rh, behind, locked, rel_h, int(x * emu), rel_v, int(y * emu), int(w * emu), int(h * emu),
                                                    wrap, nid, nid, escape(F['text'].replace('\n', ' '), {'"': '&quot;'}), _pic_graphic(nid, rid, int(w), int(h)))
    warp, x, y, w, h = flexi_geometry(F, heb, x, y)
    rpr = flexi_rpr(F, heb)
    jc = {'left': 'left', 'right': 'right', 'full': 'both', 'spread': 'distribute'}.get(FLEXI_JUSTIFY[F['justify']], 'center')
    paras = ''
    for ln in F['text'].split('\n'):
        if heb:     # (punctuation keeps its place in the Hebrew order, as hebrew_text marks it)
            ln = NEUTRAL_RE.sub(lambda m: '\u200f' + m.group() + '\u200f', ln)
        paras += ('<w:p><w:pPr><w:spacing w:before="0" w:after="0"/>%s<w:jc w:val="%s"/></w:pPr><w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
                  % ('<w:bidi/>' if heb else '', jc, rpr, escape(CTRL_RE.sub(' ', ln))))
    rot = F['rotate']
    rot_xml = ' rot="%d"' % int((360 - rot) % 360 * 60000) if 0 < rot < 360 else ''      # (DavkaWriter turns counter-clockwise)
    geom = ('<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm%s><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></wps:spPr>'
            '<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>'
            '<wps:bodyPr rot="0" vert="horz" wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"%s>%s<a:noAutofit/></wps:bodyPr></wps:wsp>'
            % (rot_xml, w * emu, h * emu, paras, ' fromWordArt="1"' if warp else '', warp))
    return ('<w:r><w:drawing><wp:anchor %s simplePos="0" relativeHeight="%d" behindDoc="%d" locked="%s" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>%s'
            '<wp:docPr id="%d" name="FlexiText %d"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">%s</a:graphicData></a:graphic>'
            '</wp:anchor></w:drawing></w:r>') % (dist, rh, behind, locked, rel_h, int(x * emu), rel_v, int(y * emu), int(w * emu), int(h * emu),
                                                wrap, nid, nid, geom)


# ------------------------------------------------------------- groups (1.3.16)
# Objects grouped in Folio (o['grp']: the editor's group id, arrange.js) are written as one Word group: a wpg:wgp
# in one wp:anchor, its members as the group's children (their own turn, flip and look kept), in their stacking order.
# The group is anchored where its first member is (in the document's order): fixed on the page or moving with that
# member's paragraph; a member anchored another way is re-anchored to it, keeping its place on the page (the editor
# sends where each member is on its page: data['grpos'], key -> {page, x, y} in twips, dwdedit.from_editor).
GRP_URI = 'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup'
_ANCH_RE = re.compile(r'^<w:r><w:drawing><wp:anchor ?([^>]*)>(.*)</wp:anchor></w:drawing></w:r>$', re.S)

def track_obj(D, o, x):
    """remember which editor object a Word object is (its docPr name -> the editor's key: dwdedit.objmap), so a group
    made in Word from Folio's objects is read back as a group"""
    ref = o.get('_ref')
    if ref:
        m = re.search(r'<wp:docPr id="\d+" name="([^"]*)"', x or '')
        if m:
            D.setdefault('_objmap', {})[m.group(1)] = ref
    return x

def plan_groups(D, host):
    """{id(lead): [members]}, {id(other member)}: the groups of two or more objects, in the order they are written"""
    order = []
    for i, p in enumerate(D['main']):
        if p.get('drop'):
            continue
        for o in host.get(i, []) + list(p.get('objects') or []):
            order.append(o)
    by = {}
    for o in order:
        g = o.get('grp')
        if isinstance(g, str) and g and not (o.get('newpic') == 'inline'):
            by.setdefault(g, []).append(o)
    at = {}
    for i, p in enumerate(D['main']):
        for o in host.get(i, []) + list(p.get('objects') or []):
            at[id(o)] = i
    D['_grp_at'] = at
    lead, skip = {}, set()
    for g, ms in by.items():
        if len(ms) < 2:
            continue
        lead[id(ms[0])] = ms
        for o in ms[1:]:
            skip.add(id(o))
    return lead, skip

def _parse_anchor(x):
    """the parts of one wp:anchor run as anchor_xml writes it, or None"""
    m = _ANCH_RE.match(x or '')
    if not m:
        return None
    attrs, inner = m.group(1), m.group(2)
    a = dict(re.findall(r'(\w+)="([^"]*)"', attrs))
    ph = re.search(r'<wp:positionH relativeFrom="(\w+)"><wp:posOffset>(-?\d+)</wp:posOffset></wp:positionH>', inner)
    pv = re.search(r'<wp:positionV relativeFrom="(\w+)"><wp:posOffset>(-?\d+)</wp:posOffset></wp:positionV>', inner)
    ext = re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', inner)
    wrap = re.search(r'<wp:effectExtent[^>]*/>(.*?)<wp:docPr', inner, re.S)
    dp = re.search(r'<wp:docPr id="(\d+)" name="([^"]*)"', inner)
    gd = re.search(r'<a:graphicData uri="([^"]+)">(.*)</a:graphicData>', inner, re.S)
    if not (ph and pv and ext and wrap and dp and gd):
        return None
    return dict(a=a, rh=ph.group(1), x=int(ph.group(2)), rv=pv.group(1), y=int(pv.group(2)), cx=int(ext.group(1)), cy=int(ext.group(2)),
                wrap=wrap.group(1), id=dp.group(1), name=dp.group(2), uri=gd.group(1), body=gd.group(2))

def _child_xml(m, dx, dy):
    """a member as a child of the group, at (dx, dy) EMU from the group's corner"""
    body = m['body']
    nm = m['name']                       # (already escaped in the anchor)
    if m['uri'].endswith('wordprocessingShape'):
        k = body.find('<wps:wsp>')
        if k != 0:
            return None
        body = '<wps:wsp><wps:cNvPr id="%s" name="%s"/>' % (m['id'], nm) + body[len('<wps:wsp>'):]
    elif not m['uri'].endswith('/picture'):
        return None
    k = body.find('<a:off x="0" y="0"/>')
    if k < 0:
        return None
    return body[:k] + '<a:off x="%d" y="%d"/>' % (dx, dy) + body[k + len('<a:off x="0" y="0"/>'):]

def group_anchor_xml(D, members, hint):
    """one Word group of the members (see plan_groups); the members one by one when they can't be one group"""
    xs = [track_obj(D, o, anchor_xml(D, o, hint)) for o in members]
    ps = [_parse_anchor(x) for x in xs]
    if any(p is None for p in ps):
        return ''.join(xs)
    emu = 635
    L = ps[0]
    gp = D.get('_grpos') or {}
    lead_pos = gp.get(members[0].get('_ref'))
    mar_l = D['page']['margins'][0] * emu
    pts = []
    for o, m in zip(members, ps):
        x, y = m['x'], m['y']
        # horizontal: the page and the margin differ by the left margin
        if m['rh'] != L['rh']:
            conv = {('margin', 'page'): mar_l, ('column', 'page'): mar_l, ('page', 'margin'): -mar_l, ('page', 'column'): -mar_l,
                    ('margin', 'column'): 0, ('column', 'margin'): 0}.get((m['rh'], L['rh']))
            if conv is None:
                return ''.join(xs)
            x += conv
        other_para = m['rv'] == 'paragraph' and (D.get('_grp_at') or {}).get(id(o)) != (D.get('_grp_at') or {}).get(id(members[0]))
        if m['rv'] != L['rv'] or other_para:
            # vertical, another way: from where the editor shows both on their pages
            mp = gp.get(o.get('_ref'))
            if not (isinstance(mp, dict) and isinstance(lead_pos, dict)):
                return ''.join(xs)
            y = L['y'] + int(round((float(mp.get('y', 0)) - float(lead_pos.get('y', 0))) * emu))
        pts.append((x, y))
    gx = min(p[0] for p in pts)
    gy = min(p[1] for p in pts)
    gw = max(p[0] + m['cx'] for p, m in zip(pts, ps)) - gx
    gh = max(p[1] + m['cy'] for p, m in zip(pts, ps)) - gy
    kids = []
    for (x, y), m in sorted(zip(pts, ps), key=lambda t: int(t[1]['a'].get('relativeHeight') or 0)):
        c = _child_xml(m, x - gx, y - gy)
        if c is None:
            return ''.join(xs)
        kids.append(c)
    a = L['a']
    rh = max(int(m['a'].get('relativeHeight') or 0) for m in ps)
    locked = 1 if any(m['a'].get('locked') == '1' for m in ps) else 0
    dist = 'distT="%s" distB="%s" distL="%s" distR="%s"' % (a.get('distT', '0'), a.get('distB', '0'), a.get('distL', '0'), a.get('distR', '0'))
    _id[0] += 1
    nid = _id[0]
    return ('<w:r><w:drawing><wp:anchor %s simplePos="0" relativeHeight="%d" behindDoc="%s" locked="%d" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="%s"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/>%s'
            '<wp:docPr id="%d" name="Folio group %d"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="%s"><wpg:wgp><wpg:cNvGrpSpPr/><wpg:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="%d" cy="%d"/></a:xfrm></wpg:grpSpPr>%s</wpg:wgp></a:graphicData></a:graphic>'
            '</wp:anchor></w:drawing></w:r>') % (dist, rh, a.get('behindDoc', '0'), locked, L['rh'], gx, L['rv'], gy, gw, gh, L['wrap'],
                                                 nid, nid, GRP_URI, gw, gh, gw, gh, ''.join(kids))

def wrap_xml(D, o):
    """(distance attributes, wrap element, behindDoc) of an anchored object: DavkaWriter wraps the text around
    every object except a background (see wraps_text), which the text passes over (behind the text, or in front of
    it when the document says so).  The distances are DavkaWriter's wrap distances (0.15" at the sides by default)."""
    emu = 635
    mw = o.get('folio_wrap')                            # the wrap set in the editor (1.3.13 boxes; 1.3.14 Arrange)
    if mw in ('fixed', 'behind', 'wrap', 'tight', 'topbottom'):
        return arr_wrap(D, o, mw)
    if o.get('kind') == 0x0f and not o.get('frame'):     # curvy text: no reliable size, never pushes text
        return 'distT="0" distB="0" distL="0" distR="0"', '<wp:wrapNone/>', 1
    if wraps_text(o) and o.get('_text_wraps') and (o.get('page') is not None or o.get('_obstacle')):
        wr = o.get('wrap') or [DEFAULT_WRAP_DIST, 0, DEFAULT_WRAP_DIST, 0]
        d = 'distT="%d" distB="%d" distL="%d" distR="%d"' % (max(0, wr[1]) * emu, max(0, wr[3]) * emu, max(0, wr[0]) * emu, max(0, wr[2]) * emu)
        return d, '<wp:wrapSquare wrapText="largest"/>', 0
    if wraps_text(o):
        # (an object the text would wrap around but only empty lines meet: in front of them, like DavkaWriter shows it)
        return 'distT="0" distB="0" distL="0" distR="0"', '<wp:wrapNone/>', 0
    behind = 0 if D.get('wrapped_in_front') else 1
    return 'distT="0" distB="0" distL="0" distR="0"', '<wp:wrapNone/>', behind

def page_border_style(D):
    """(Word border style, size in 1/8 pt, RRGGBB) for the document's page border: a plain line in the
    border's own colour and width; DavkaWriter's art borders (a band of small shapes) become a dotted band in
    their colour (Folio never reproduces DavkaWriter's border art)."""
    bl = D['page'].get('border_line')
    if bl:                                               # the border the teacher set in Folio (Page setup)
        st = bl.get('style') or 'single'
        w = max(0.25, min(6.0, float(bl.get('width') or 1.5)))
        col = re.sub(r'[^0-9A-Fa-f]', '', str(bl.get('color') or '000000'))[:6].upper().rjust(6, '0')
        val = {'single': 'single', 'double': 'double', 'thick': 'thickThinSmallGap', 'dotted': 'dotted', 'dashed': 'dashed'}.get(st, 'single')
        per = w / 3.0 if val in ('double', 'thickThinSmallGap') else w      # (Word's size is one line's width)
        return val, int(max(2, min(96, round(per * 8)))), col
    bs = [b for b in D['page'].get('page_borders') or [] if b.get('border_class') in ('CBorderSimple', 'CBorderShapes')]
    if not bs:
        return 'thickThinSmallGap', 24, '000000'
    b = bs[0]
    col = colorref(b.get('color') or 0) if b.get('color') is not None else '000000'
    if col == 'FFFFFF':
        col = '000000'
    if b['border_class'] == 'CBorderShapes':
        return 'dotted', 24, col
    w = b.get('width') or 3.0
    sz = int(max(4, min(48, round(w * 8 / 3.0))))     # a DavkaWriter frame of n points draws about n/3 pt of ink per line
    # style 10 is a double line (measured on a DavkaWriter print: two lines of a third of the width each)
    if b.get('style') == 10:
        return 'double', int(max(2, min(48, round(w / 3.0 * 8)))), col
    # style 23 is DavkaWriter's shadowed frame (a thin line with a grey shadow, as printed)
    return ('thickThinSmallGap' if w >= 6 and b.get('style') != 23 else 'single'), sz, col + ('__SHADOW__' if b.get('style') == 23 else '')

def border_box(D):
    """The page border as drawn: {'l','t','r','b'} distances of its outer edge from the page edges and 'w' its ink
    width, in twips; None without a border.  DavkaWriter measures from the page edge; a border the teacher set "from
    the text" in Folio sits that far outside the margins."""
    pg = D['page']
    bl = pg.get('border_line')
    if bl is not None and bl.get('on') is False:
        return None
    if not pg.get('border') and not bl:
        return None
    val, sz, _ = page_border_style(D)
    w = sz / 8.0 * (3 if val in ('double', 'thickThinSmallGap') else 1) * 20
    if bl and bl.get('from') == 'text':
        mar = pg['margins']
        d = [int(x) for x in (bl.get('dist') or [360] * 4)]
        out = [max(0, mar[i] - d[i] - w) for i in range(4)]
    else:
        out = list((bl.get('dist') if bl and bl.get('dist') else None) or pg.get('border_margins') or (720, 720, 720, 720))
    return dict(l=out[0], t=out[1], r=out[2], b=out[3], w=w)

HF_BORDER_PAD = 80     # twips between a page border's inside and a header / footer kept inside it

def row_height(D, t, ri, avail):
    """Height of one table row in twips: the row's stored height (DavkaWriter keeps it as a negative
    twip value) or the tallest cell's content plus the cell margins, whichever is larger."""
    rows = t['rows']
    ncol = max(len(r) for r in rows) or 1
    b = t.get('bounds') or []
    if len(b) >= ncol and all(b[i] < b[i+1] for i in range(ncol - 1)):
        widths = [b[0]] + [b[i] - b[i-1] for i in range(1, ncol)]
    else:
        widths = [(t.get('width') or avail) // ncol] * ncol
    content = 0
    for ci, cell in enumerate(rows[ri]):
        cw = widths[ci] if ci < len(widths) else widths[-1]
        h = sum(para_height(D, p, max(cw - 120, 300))[0] for p in cell) if cell else 0
        content = max(content, h)
    stored = (t.get('row_heights') or [0] * len(rows))[ri] or 0
    if stored < 0 and t.get('cells') is not None and not t.get('folio'):
        return -stored                  # an exact row height (written as such, see table_xml_cells)
    return max(abs(stored), content + 80)

def table_height(D, t, avail):
    return sum(row_height(D, t, ri, avail) for ri in range(len(t['rows']))) + 20

def table_rtl(D, t, rows, ncol, width, avail_w):
    """A table whose cells are mostly right-to-left paragraphs, as wide as the text column and with every row
    complete, is written as a right-to-left table (first column on the right).  Its look does not change."""
    if ncol < 2 or any(len(r) != ncol for r in rows) or width < avail_w - 200:
        return False
    R = D['rulers']
    n = sum(1 for r in rows for cell in r for p in cell)
    k = sum(1 for r in rows for cell in r for p in cell if R.get(p['ruler'], {'rtl': 1}).get('rtl'))
    return n > 0 and k * 2 > n

def table_xml(D, t, mar, max_width=None):
    width = t.get('width') or (paper(D)[0] - mar[0] - mar[2])
    rows = t['rows']
    ncol = max(len(r) for r in rows) or 1
    b = t.get('bounds') or []
    if len(b) >= ncol and all(b[i] < b[i+1] for i in range(ncol - 1)):
        widths = [b[0]] + [b[i] - b[i-1] for i in range(1, ncol)]
    else:
        widths = [width // ncol] * ncol
    if max_width and width > max_width:          # a table inside a text box is scaled to the box
        f = max_width / width
        widths = [int(x * f) for x in widths]; width = sum(widths)
    cw = widths[0]
    bw = (t.get('borders') or [0, 2, 2, 2])[1:]
    sz = max(4, min(24, (max(bw) or 2) * 4))
    b = '<w:%s w:val="single" w:sz="' + str(sz) + '" w:space="0" w:color="000000"/>' if max(bw) else '<w:%s w:val="nil"/>'
    borders = ''.join(b % side for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    fill = t.get('fill') or 'FFFFFF'
    shd = '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill if fill.upper() != 'FFFFFF' else ''
    if t.get('folio'):            # made in the Folio editor: cells are in reading order
        rtl = bool(t.get('rtl'))
    else:
        rtl = table_rtl(D, t, rows, ncol, sum(widths), avail_w=paper(D)[0] - mar[0] - mar[2])
    cinfo = t.get('cells') if not t.get('folio') else None
    if cinfo is not None and (len(cinfo) < len(rows) or any(len(cinfo[ri]) < len(r) for ri, r in enumerate(rows))):
        cinfo = None
    if cinfo is not None:
        return table_xml_cells(D, t, rows, widths, cinfo, rtl)
    if rtl and not t.get('folio'):     # a right-to-left table: the first column is on the right (same look, Hebrew reading order)
        rows = [list(reversed(r)) for r in rows]
        widths = list(reversed(widths))
        cw = widths[0]
    out = ['<w:tbl><w:tblPr>' + ('<w:bidiVisual/>' if rtl else '') + '<w:tblW w:w="%d" w:type="dxa"/><w:tblBorders>%s</w:tblBorders>'
           '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="60" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/><w:right w:w="60" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           '<w:tblGrid>%s</w:tblGrid>' % (width, borders, ''.join('<w:gridCol w:w="%d"/>' % w for w in widths))]
    avail = paper(D)[0] - mar[0] - mar[2]
    for ri, r in enumerate(rows):
        rh = abs((t.get('row_heights') or [0] * len(rows))[ri] or 0)
        out.append('<w:tr><w:trPr><w:trHeight w:val="%d" w:hRule="atLeast"/></w:trPr>' % rh if rh else '<w:tr>')
        for ci, cell in enumerate(r):
            inner = ''.join(para_xml(D, p, in_box=True, box_w=max((widths[ci] if ci < len(widths) else cw) - 120, 300)) for p in cell) or '<w:p/>'
            sh = '<w:shd w:val="clear" w:color="auto" w:fill="E8ECF3"/>' if t.get('hdr') and ri == 0 else shd
            out.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s</w:tcPr>%s</w:tc>' % (widths[ci] if ci < len(widths) else cw, sh, inner))
        out.append('</w:tr>')
    out.append('</w:tbl>')
    return ''.join(out)

def _cell_border(b, side):
    """One side of a cell border (signed width in 1/4 pt; a second line = double)."""
    if not b or b.get('hidden') or not b.get('width'):
        return '<w:%s w:val="nil"/>' % side
    w = abs(b['width'])
    double = bool(b.get('line2'))
    sz = max(2, min(96, (b.get('line1') or w) * 2 if double else w * 2))
    return '<w:%s w:val="%s" w:sz="%d" w:space="0" w:color="%s"/>' % (side, 'double' if double else 'single', sz, (b.get('color') or '000000').upper())

def table_xml_cells(D, t, rows, widths, cinfo, rtl):
    """A DavkaWriter table from its cell records: each cell's own top and left border (its right border is the
    next cell's left one, its bottom the top of the cell below: the extra edge cell and the dummy last row hold
    the table's right and bottom edges), horizontal merges, shading, vertical alignment and the row heights
    (negative = exactly, positive = at least)."""
    ncol = len(widths)
    width = sum(widths)
    def info(ri, ci):
        r = cinfo[ri] if ri < len(cinfo) else []
        return r[ci] if ci < len(r) else {}
    out = ['<w:tbl><w:tblPr>' + ('<w:bidiVisual/>' if rtl else '') + '<w:tblW w:w="%d" w:type="dxa"/>'
           '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="60" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="60" w:type="dxa"/></w:tblCellMar></w:tblPr>'
           '<w:tblGrid>%s</w:tblGrid>' % (width, ''.join('<w:gridCol w:w="%d"/>' % w for w in (widths[::-1] if rtl else widths)))]
    heights = t.get('row_heights') or [0] * len(rows)
    for ri, r in enumerate(rows):
        rh = heights[ri] if ri < len(heights) else 0
        out.append('<w:tr><w:trPr><w:cantSplit/>%s</w:trPr>' % ('<w:trHeight w:val="%d" w:hRule="%s"/>' % (abs(rh), 'exact' if rh < 0 else 'atLeast') if rh else ''))
        cells = []
        ci = 0
        while ci < ncol:
            c = info(ri, ci)
            hm = c.get('hmerge') or 0
            if hm < 0:                  # covered by a merge to its left (left over at a broken record)
                ci += 1
                continue
            span = max(1, min(1 + hm, ncol - ci))
            w = sum(widths[ci:ci + span])
            last = ci + span                  # the cell whose left border is this cell's right one
            right = info(ri, last).get('left')
            bottom = info(ri + 1, ci).get('top')
            bd = (_cell_border(c.get('top'), 'top') + _cell_border(c.get('left'), 'start' if not rtl else 'end')
                  + _cell_border(bottom, 'bottom') + _cell_border(right, 'end' if not rtl else 'start'))
            # shade_pct is the printed gray percentage, not opacity of the
            # separate COLORREF. 91 -> #E8E8E8 in DavkaWriter's own PDF.
            pct = c.get('shade_pct')
            shade = ('%02X' % round(pct * 255 / 100)) * 3 if pct is not None and 0 <= pct <= 100 else (c.get('shade') or 'FFFFFF').upper()
            shd = '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shade if shade != 'FFFFFF' else ''
            va = {1: 'center', 2: 'bottom'}.get(c.get('valign'), '')
            cell = r[ci] if ci < len(r) else []
            inner = ''.join(para_xml(D, p, in_box=True, box_w=max(w - 120, 300)) for p in cell) or '<w:p/>'
            cells.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s<w:tcBorders>%s</w:tcBorders>%s%s</w:tcPr>%s</w:tc>' % (
                w, '<w:gridSpan w:val="%d"/>' % span if span > 1 else '', bd, shd, '<w:vAlign w:val="%s"/>' % va if va else '', inner))
            ci += span
        out.append(''.join(cells[::-1] if rtl else cells))     # a bidi table lists its cells right to left
        out.append('</w:tr>')
    out.append('</w:tbl>')
    return ''.join(out)

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
      'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
      'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
      'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"')

def hf_sections(D):
    """The document's header/footer sections: [{'start': paragraph index, 'header': paras, 'footer': paras}].
    Section 0 is the document's own header/footer; a later paragraph that carries a new CHeader/CFooter starts
    a section whose header (footer) is the new one, the other one carrying on."""
    has_text = lambda ps: any(r['text'].strip(b' \t\xa0') or r.get('field') or r.get('object') for p in ps for r in p['runs'])
    norm = lambda ps: list(ps) if ps and has_text(ps) else []
    key = lambda ps: [(r['text'], r.get('field'), r['style']) for p in ps for r in p['runs']]
    secs = [dict(start=0, header=list(D.get('header') or []), footer=list(D.get('footer') or []))]
    for i, p in enumerate(D['main']):
        if i == 0 or not (p.get('section_header') or p.get('section_footer')):
            continue
        cur = secs[-1]
        h = norm(p['section_header'][0]) if p.get('section_header') else cur['header']
        f = norm(p['section_footer'][0]) if p.get('section_footer') else cur['footer']
        if key(h) == key(cur['header']) and key(f) == key(cur['footer']):
            continue
        secs.append(dict(start=i, header=h, footer=f))
    return secs

def _insert_sect_para(body, body_para, i, inner):
    """Put a section-closing empty paragraph after the output of paragraph i (used when that paragraph
    produced no paragraph of its own, e.g. a table row).  body_para[j] = paragraph index of body[j]."""
    k = max((j for j, q in enumerate(body_para) if q <= i), default=None)
    para = '<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/>%s</w:pPr></w:p>' % inner
    if k is None:
        body_para.insert(0, i)
        return [para] + body
    body_para.insert(k + 1, i)
    return body[:k + 1] + [para] + body[k + 1:]

def hf_heights(D):
    """(header height, footer height) in twips, laid out at the text width."""
    mar = D['page']['margins']
    avail = paper(D)[0] - mar[0] - mar[2]
    return (sum(para_height(D, p, avail)[0] for p in D.get('header') or []),
            sum(para_height(D, p, avail)[0] for p in D.get('footer') or []))

def hf_distances(D):
    """(header, footer) distance from the page edge in twips: DavkaWriter's own (default 0.5")."""
    pg = D['page']
    h = pg.get('header_distance'); f = pg.get('footer_distance')
    h = int(h) if isinstance(h, (int, float)) and 0 <= h < 5000 else 720
    f = int(f) if isinstance(f, (int, float)) and 0 <= f < 5000 else 720
    return h, f

BOTTOM_SLACK = 250     # twips the Word bottom margin is smaller than DavkaWriter's (room for rounding; page breaks are explicit)

def hf_layout(D):
    """Where DavkaWriter puts the header and footer (measured on prints): the header starts at its distance
    from the top edge but is moved up so that it ends at the top margin when it would reach past it; the
    footer ends at its distance from the bottom edge but is moved down so that it starts at the bottom margin
    when it would reach above it.  Only a header/footer taller than its margin pushes the body.
    Returns (header top, footer bottom distance, body top extra, body bottom extra), twips."""
    mar = D['page']['margins']
    hh, fh = hf_heights(D)
    hd, fd = hf_distances(D)
    hdr_top = min(hd, max(0, mar[1] - hh)) if hh else hd
    ftr_d = min(fd, max(0, mar[3] - fh)) if fh else fd
    if D['page'].get('header_top') is not None:        # where the teacher's printout has it (Fix it from a printout)
        hdr_top = max(0, min(int(D['page']['header_top']), mar[1]))
    if D['page'].get('footer_bottom') is not None:
        ftr_d = max(0, min(int(D['page']['footer_bottom']), mar[3]))
    # a page border: the header and footer stay inside it, as far as the margin leaves room (the body never moves)
    bb = border_box(D)
    if bb:
        if hh:
            hdr_top = max(hdr_top, min(bb['t'] + bb['w'] + HF_BORDER_PAD, max(hdr_top, mar[1] - hh)))
        if fh:
            ftr_d = max(ftr_d, min(bb['b'] + bb['w'] + HF_BORDER_PAD, max(ftr_d, mar[3] - fh)))
    top = max(0, hh - mar[1]) if hh else 0
    bottom = max(0, fh - mar[3]) if fh else 0
    # a distance the teacher set in Folio is kept as it is (as in Word): a header that then reaches past the top
    # margin pushes the body down, and a footer the body up
    if D['page'].get('hdr_fixed') and hh:
        hdr_top = hd
        top = max(top, hd + hh + 60 - mar[1])
    if D['page'].get('ftr_fixed') and fh:
        ftr_d = fd
        bottom = max(bottom, fd + fh + 60 - mar[3])
    return hdr_top, ftr_d, top, bottom

def hf_overflow(D):
    """(top, bottom) twips the body loses to a header or footer taller than its margin."""
    return hf_layout(D)[2:]

def page_capacity(D):
    """height in twips the text may fill on a page (the model's page length)."""
    mar = D['page']['margins']
    t, b = hf_overflow(D)
    return paper(D)[1] - mar[1] - mar[3] - 8 - t - b + LAST_LINE_HANG - (CAPACITY_SLACK if D['page']['border'] else 0)

PINNED_ROOM = 720      # at most this much (and half) of the bottom margin a page may use when its breaks are a printout's
PINNED_LS_MIN = 0.97   # a page that runs longer than the printout's: line spacing down to 97% ...
PINNED_SP_MIN = 0.5    # ... and the space before/after paragraphs down to half ...
PINNED_FS_MIN = 0.97   # ... and the text size down to 97%
PINNED_AIM = 0.97      # (aiming at 97% of the page: Word's lines are not exactly the model's)

def pinned_room(D):
    """twips of the bottom margin the text may run into when the page breaks are a printout's: the explicit
    breaks end every page, so a page whose lines come out a little taller than DavkaWriter's still holds them
    (never into the footer)"""
    mar = D['page']['margins']
    room = min(PINNED_ROOM, mar[3] // 2)
    fh = hf_heights(D)[1]
    if fh:
        ftr_d = hf_layout(D)[1]
        room = max(0, min(room, mar[3] - BOTTOM_SLACK - (ftr_d + fh + 120)))
    return room

def pinned_fit(D, pages, hs, capacity):
    """Page breaks from a printout (Fix it from a printout): a page whose text the model finds taller than the
    page gets small, bounded adjustments so that it still ends where the printout's does: empty lines at its
    foot shrink to nothing, line spacing tightens by up to 3%, space before/after paragraphs by up to half.
    (A page that is still too long runs over in Word: the printout's next break still follows.)"""
    main = D['main']
    cap = capacity + pinned_room(D)
    D['_fit'] = fit = {}
    for k, s in enumerate(pages):
        e = pages[k + 1] if k + 1 < len(pages) else len(main)
        if any(para_ncols(D, main[i]) > 1 for i in range(s, e)):
            continue                              # (a column block's height is not the sum of its paragraphs)
        tot = sum(hs[s:e])
        if tot <= cap * PINNED_AIM:
            continue
        has_text = lambda p: p.get('table') is not None or p.get('objects') or any(r['text'].strip(b' \t\xa0') or r.get('field') or r.get('object') is not None for r in p['runs'])
        aim = cap * PINNED_AIM
        j = e - 1
        while j > s and not has_text(main[j]) and tot > aim:
            main[j]['tail'] = True
            tot -= max(0, hs[j] - 20)
            j -= 1
        if tot <= aim:
            fit[k] = dict(tail=True)
            continue
        f = max(PINNED_LS_MIN, aim / float(tot))
        sp, fs = 1.0, 1.0
        if f <= PINNED_LS_MIN + 1e-9:
            spacing = sum(sum(para_spacing(D, main[i])) for i in range(s, e) if main[i].get('table') is None)
            need = tot * PINNED_LS_MIN - aim
            sp = max(PINNED_SP_MIN, 1.0 - need / float(spacing)) if spacing > 0 and need > 0 else 1.0
            left = tot * PINNED_LS_MIN - (1.0 - sp) * spacing
            if left > aim:
                fs = max(PINNED_FS_MIN, aim / float(left))
        for i in range(s, e):
            if main[i].get('table') is None:
                main[i]['ls_scale'] = f * fs
                if sp < 1.0:
                    main[i]['sp_scale'] = sp
                if fs < 1.0:
                    main[i]['fs_scale'] = fs
        fit[k] = dict(ls=round(f, 3), sp=round(sp, 3), fs=round(fs, 3))

def is_blank_para(D, p):
    """an empty line: no text, field, picture, table or object"""
    if p.get('table') is not None or p.get('objects') or p.get('blank_page'):
        return False
    S = D['styles']
    for r in p['runs']:
        if r.get('field') or r.get('footnote_id') or r.get('newpic') is not None:
            return False
        if r['text'].strip(b' \t\xa0'):
            return False
        if r['style'] in S and inline_picture(r) is not None:
            return False
    return True

def shrink_trailing_blanks(D, pages):
    """Empty lines at the foot of a page that the next page starts with a break of its own, and at the foot of a
    column that a column break ends, take (almost) no room in Word: they show nothing, and in Word they would
    otherwise be pushed onto a new page or column of their own (an empty page when a page break follows) the
    moment Word's lines come out a little taller than DavkaWriter's.  The first line of a page or column keeps
    its height."""
    main = D['main']
    n = len(main)
    starts = set(pages)
    ends = []                         # paragraph indices that end a page or a column
    for k, s in enumerate(pages):
        if k > 0 and s > 0 and not main[s].get('soft'):
            ends.append(s - 1)
    for i, p in enumerate(main):
        if p.get('col_break') in ('col', 'page') or (p.get('brk') == 2 and para_ncols(D, p) > 1):
            ends.append(i)
    cstarts = set(starts)
    for i, p in enumerate(main):
        if i > 0 and (main[i - 1].get('col_break') in ('col', 'page') or main[i - 1].get('brk')):
            cstarts.add(i)
    for e in ends:
        j = e
        while 0 <= j < n and j not in cstarts and is_blank_para(D, main[j]):
            main[j]['tail'] = True
            j -= 1

def flatten_blank_column_blocks(D, pages):
    """A column block of nothing but empty lines (a spacer between two parts of the page) is written as that many
    empty lines in one column as it takes in its columns: Word would make a section of it, and a section that small
    can send what follows to a new page."""
    main = D['main']
    starts = set(pages)
    i = 0
    while i < len(main):
        nc = para_ncols(D, main[i])
        if nc <= 1:
            i += 1
            continue
        geo = lambda q: (lambda ru: (ru.get('ncols'), tuple(ru.get('col_widths') or ()), ru.get('col_gap')))(D['rulers'].get(q['ruler'], {}))
        j = i
        while j < len(main) and para_ncols(D, main[j]) == nc and geo(main[j]) == geo(main[i]):
            j += 1
        blk = main[i:j]
        if all(is_blank_para(D, q) and not q.get('pbb') and not (q.get('brk') and q.get('brk') != 2) for q in blk) \
                and not any(k in starts for k in range(i + 1, j)):
            keep = max(1, -(-len(blk) // nc))
            for k, q in enumerate(blk):
                q['flat'] = True
                q.pop('col_break', None)
                if k >= keep:
                    q['drop'] = True
        i = j

def build_document(D, capacity):
    _id[0] = 100
    mar = D['page']['margins']
    if capacity is None:
        capacity = page_capacity(D)
    pages, hs = paginate(D, capacity)
    # pages that hold only pictures or boxes (a back cover, a full-page diagram after the last text): DavkaWriter
    # keeps them, so add an empty page for each instead of piling their objects onto the last page of text
    need = max((o['page'] for o in D['objects'] if o.get('page') is not None and o.get('anchor') != 'paragraph'), default=0)
    if need >= len(pages) and need < len(pages) + 50:
        ruler = D['main'][-1]['ruler'] if D['main'] else 0
        extra = []
        while len(pages) + len(extra) <= need:
            extra.append(dict(pos=-1, end=-1, ruler=ruler, flag=0, runs=[], list=None, objects=[], blank_page=True))
        D['main'] = D['main'] + extra
        for k in range(len(extra)):
            pages.append(len(D['main']) - len(extra) + k)
            hs.append(0)
    page_of = {}
    for pi, start in enumerate(pages):
        page_of[start] = pi
    # objects grouped by page
    by_page = {}
    for o in D['objects']:
        pg = o['page'] if o['page'] is not None else 0
        by_page.setdefault(min(pg, len(pages) - 1), []).append(o)
    for objs in by_page.values():
        for t in objs:
            if t['kind'] != 0x0f:
                continue
            for r in objs:
                if r['kind'] == 0x0e and r.get('w') and r.get('h') and r['x'] - 300 <= t['x'] <= r['x'] + r['w'] and r['y'] - 300 <= t['y'] <= r['y'] + r['h']:
                    t['frame'] = (r['x'], r['y'], r['w'], r['h'])
                    r['is_frame'] = True
                    break
    avail = paper(D)[0] - mar[0] - mar[2] - 300
    hint = lambda p: para_height(D, p, (2000))[0]
    # where each paragraph starts on its page (twips from the top of the page), per our layout model
    tops = [0] * len(D['main'])
    body_top = mar[1] + hf_overflow(D)[0]
    for pi, start in enumerate(pages):
        end = pages[pi + 1] if pi + 1 < len(pages) else len(D['main'])
        y = body_top
        blocks = list(D.get('_cols', {}).get(pi, []))
        i = start
        while i < end:
            if para_ncols(D, D['main'][i]) > 1:
                # a column block: its paragraphs share the block's top; it is as tall as its tallest column
                j = i
                while j < end and para_ncols(D, D['main'][j]) > 1:
                    j += 1
                bh = blocks.pop(0)[0]['bh'] if blocks else sum(hs[i:j]) / para_ncols(D, D['main'][i])
                for k in range(i, j):
                    tops[k] = y
                y += bh
                i = j
                continue
            tops[i] = y
            y += hs[i]
            i += 1
    # DavkaWriter pushes text that would run into a title box down below the box
    for pi, objs in by_page.items():
        start = pages[pi]
        end = pages[pi + 1] if pi + 1 < len(pages) else len(D['main'])
        wide = lambda o: (o['kind'] == 0x0e and not o.get('line') and not o.get('folio') and (o.get('w') or 0) > 0.5 * avail
                          and (o.get('h') or 0) > 600)
        for r in sorted((o for o in objs if o.get('is_frame') or wide(o)), key=lambda o: o['y']):
            bottom = r['y'] + r['h'] + 40
            for i in range(start, end):
                p = D['main'][i]
                if tops[i] < bottom and tops[i] + hs[i] > r['y'] + 20 and any(ru['text'].strip(b' \t\xa0') for ru in p['runs']):
                    push = bottom - tops[i]
                    # the push must not make the page overflow: it can only use the page's spare room
                    # plus blank lines further down the page (which give their height back)
                    spare = capacity - sum(hs[start:end]) - sum(D['main'][j].get('push', 0) for j in range(start, end))
                    blanks = [j for j in range(end - 1, i, -1)
                              if not D['main'][j].get('objects') and not D['main'][j].get('tail')
                              and not any(ru['text'].strip(b' \t\xa0') for ru in D['main'][j]['runs'])]
                    allowed = max(0, spare) + sum(hs[j] for j in blanks)
                    push = min(push, allowed)
                    if push <= 0:
                        break
                    p['push'] = p.get('push', 0) + push
                    room = push - max(0, spare)
                    for j in blanks:
                        if room <= 0:
                            break
                        D['main'][j]['tail'] = True
                        room -= hs[j]
                    for j in range(i, end):
                        tops[j] += push
                    break
    for p in reversed(D['main']):
        if p.get('objects') or any(ru['text'].strip(b' \t\xa0') for ru in p['runs']):
            break
        p['tail'] = True
    shrink_trailing_blanks(D, pages)
    flatten_blank_column_blocks(D, pages)
    if D.get('pinned') and D.get('pinned_fit', True):
        pinned_fit(D, pages, hs, capacity)
    D['_layout'] = dict(pages=list(pages), hs=list(hs), tops=list(tops), capacity=capacity)   # for the fidelity audit
    host = {}                      # paragraph index -> objects anchored to it
    for pi, objs in by_page.items():
        start = pages[pi]
        end = pages[pi + 1] if pi + 1 < len(pages) else len(D['main'])
        for o in objs:
            # DavkaWriter places page objects at absolute page positions; every page starts with an
            # explicit page break, so the objects hang from the page's first paragraph, page-relative
            k = start
            if pi in D.get('soft_pages', ()) and start + 1 < end:
                k = start + 1                   # the page begins inside a paragraph; use the next one
            host.setdefault(k, []).append(o)
    # column blocks: runs of paragraphs whose ruler has more than one column
    text_w = paper(D)[0] - mar[0] - mar[2]
    def cols_xml(geo, rtl, sep=False):
        """w:cols for a column block: DavkaWriter's widths stretched to the text width (column_geometry); the
        last column takes whatever rounding leaves.  A right-to-left page fills the rightmost column first: a
        bidi section, whose first w:col is the rightmost one."""
        if geo is None:
            return ''
        ws, gap = geo
        nc = len(ws)
        ws = list(ws)
        ws[-1] = max(300, text_w - sum(ws[:-1]) - gap * (nc - 1))
        if rtl:
            ws = ws[::-1]
        return ('<w:cols w:num="%d" w:space="%d" w:equalWidth="0"%s>' % (nc, gap, ' w:sep="1"' if sep else '')
                + ''.join('<w:col w:w="%d"%s/>' % (w, (' w:space="%d"' % gap) if k < nc - 1 else '') for k, w in enumerate(ws))
                + '</w:cols>' + ('__TITLEPG__<w:bidi/>' if rtl else ''))
    geos = [column_geometry(D, D['rulers'].get(p['ruler'], {}), text_w) if para_ncols(D, p) > 1 else None for p in D['main']]
    seps = [bool(D['rulers'].get(p['ruler'], {}).get('col_sep')) for p in D['main']]
    # column sections: a block of multi-column paragraphs is a section (continuous: the block is balanced
    # where it ends); inside it a page whose first paragraph runs the other way starts a new section (a page
    # break anyway, so the break is a page one)
    sect_at = {}                   # paragraph index -> (cols xml, section type) closing there
    state = (None, False, False)
    state_at = []                  # the column state (geometry, rtl) each paragraph is in
    for i, p in enumerate(D['main']):
        if geos[i] is not None and (p.get('col_sect') is not None or geos[i] != state[0]):
            if i > 0:
                hard = i in page_of and not p.get('soft')
                sect_at[i - 1] = (cols_xml(*state), 'nextPage' if hard else 'continuous')
            state = (geos[i], bool(p.get('col_sect')) if p.get('col_sect') is not None else state[1], seps[i])
        elif geos[i] is None and state[0] is not None:
            sect_at[i - 1] = (cols_xml(*state), 'continuous')
            state = (None, False, False)
        state_at.append(state)
    last_cols = cols_xml(*state)
    # header/footer changes in the middle of the document (a DavkaWriter paragraph carrying a new CHeader/CFooter
    # takes effect from its page on): each is a Word section with its own header/footer parts (write_docx
    # writes them from D['_hf_sections'])
    sections = hf_sections(D)



    def page_start_of(i):
        # DavkaWriter's prints (measured with their cover page left out): on a page begun by a page break the new
        # header/footer is that page's own, from its top (kiddushin); on a page the text ran onto, it starts on the
        # page after (seder hilchos pesach; 1.3.10 took the page after for every page)
        on = [q for q in pages if q <= i and not D['main'][q].get('soft')]
        s = on[-1] if on else 0
        if s > 0:
            pv = D['main'][s - 1]
            if (pv.get('brk') and pv.get('brk') != 2) or pv.get('col_break') == 'page' or D['main'][s].get('pbb'):
                return s
        nxt = [q for q in pages if q > i and not D['main'][q].get('soft')]
        return nxt[0] if nxt else None
    merged = [sections[0]]
    for sec in sections[1:]:
        k = page_start_of(sec['start'])
        if k is None:
            continue
        sec = dict(sec, start=k)
        if k <= merged[-1]['start']:
            merged[-1] = dict(sec, start=merged[-1]['start'])
        else:
            merged.append(sec)
    sections = merged
    # (1.3.25) no header or footer on the first N pages (Page setup; a PDF's covers: page.hfskip).  One page: Word's
    # "different first page" on the first section only.  More: the covers are a section of their own (it ends with a
    # next-page break where page N+1 starts) whose header and footer are empty.
    skip = int(D['page'].get('hfskip') or 0)
    D['_cover_sec'] = None
    if skip >= 2 and skip < len(pages):
        k = pages[skip] if not D['main'][pages[skip]].get('soft') else page_start_of(pages[skip])
        if k is not None and k > 0:
            cur = [sec for sec in sections if sec['start'] <= k][-1]
            sections = ([dict(sec, header=[], footer=[]) for sec in sections if sec['start'] < k]
                        + ([] if any(sec['start'] == k for sec in sections) else [dict(cur, start=k)])
                        + [sec for sec in sections if sec['start'] >= k])
            D['_cover_sec'] = k
    D['_hf_sections'] = sections
    art = page_art(D)
    any_h = any(sec['header'] for sec in sections) or bool(art)
    any_f = any(sec['footer'] for sec in sections)
    def refs(k):
        # every section names its parts (an empty one too), or Word would carry the previous section's over
        r = ''
        if any_h:
            r += '<w:headerReference w:type="default" r:id="rIdHeader%d"/>' % (k + 1)
        if any_f:
            r += '<w:footerReference w:type="default" r:id="rIdFooter%d"/>' % (k + 1)
        return r
    # (1.3.16) groups made in Folio: one Word group (wpg:wgp) in the anchor of the group's first member
    grp_lead, grp_skip = plan_groups(D, host)
    body = []
    body_para = []             # paragraph index of each body item
    done_tables = set()
    hf_close = set(sec['start'] - 1 for sec in D['_hf_sections'][1:])
    sect_breaks = set(sec['start'] for sec in D['_hf_sections'][1:] if sec['start'] in page_of and not D['main'][sec['start']].get('soft'))
    # a column section that starts a page starts with a next-page section break (no page break of its own: the two
    # together would make Word leave a page empty)
    sect_breaks |= set(i + 1 for i, (cols, typ) in sect_at.items() if typ == 'nextPage')
    pending_col = False
    for i, p in enumerate(D['main']):
        p['seq'] = i
        if p.get('drop'):
            continue
        pb = (i in page_of or p.get('pbb')) and i != 0 and not p.get('soft') and i not in sect_breaks
        anchors = ''
        for o in host.get(i, []) + list(p.get('objects') or []):
            if id(o) in grp_skip:
                continue
            if id(o) in grp_lead:
                anchors += group_anchor_xml(D, grp_lead[id(o)], hint)
                continue
            anchors += track_obj(D, o, anchor_xml(D, o, hint))
        t = p.get('table')
        if t is not None:
            if id(t) in done_tables:
                if anchors:
                    body.append('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/></w:pPr>%s</w:p>' % anchors); body_para.append(i)
                continue
            done_tables.add(id(t))
            if anchors or pb or p.get('band_push'):
                body.append(para_xml(D, dict(runs=[], ruler=p['ruler'], tail=True, band_push=p.get('band_push', 0)), page_break=pb, anchors=anchors)); body_para.append(i)
            body.append(table_xml(D, t, mar)); body_para.append(i)
            continue
        px = para_xml(D, p, page_break=pb, anchors=anchors, sect='__SECT_%d__' % i if (i in sect_at or i in hf_close) else '')
        if pending_col and not pb:
            # the column break goes at the start of the paragraph that begins the next column (at the end of the
            # previous one it would carry that paragraph's mark over as an empty first line)
            k = px.find('</w:pPr>')
            k = k + len('</w:pPr>') if k >= 0 else px.find('>') + 1
            px = px[:k] + '<w:r><w:br w:type="column"/></w:r>' + px[k:]
        pending_col = False
        if p.get('col_break') == 'col':          # DavkaWriter's column break: the next paragraph starts the next column
            nxt = D['main'][i + 1] if i + 1 < len(D['main']) else None
            if nxt is not None and nxt.get('table') is None and not nxt.get('drop') and i not in sect_at and i not in hf_close:
                pending_col = True
            else:
                px = px[:-len('</w:p>')] + '<w:r><w:br w:type="column"/></w:r></w:p>'
        body.append(px); body_para.append(i)
    # page border
    pg_border = ''
    if D['page']['border'] and (D['page'].get('border_line') or {}).get('on') is not False:
        bl = D['page'].get('border_line') or {}
        val, sz, color = page_border_style(D)
        sides = (('top', 1), ('left', 0), ('bottom', 3), ('right', 2))
        shadow = color.endswith('__SHADOW__')
        color = color.replace('__SHADOW__', '')
        if bl.get('from') == 'text':
            # the teacher's distance from the text (Word allows up to 31 pt)
            dt = [int(x) for x in (bl.get('dist') or [360] * 4)]
            off, dist = 'text', (lambda i: max(0, min(31, int(dt[i] / 20))))
        else:
            # measured from the page edge, at DavkaWriter's distance (Word allows up to 31 pt)
            bm = bl.get('dist') or D['page']['border_margins'] or (720, 720, 720, 720)
            off, dist = 'page', (lambda i: max(0, min(31, int(bm[i] / 20))))
        pg_border = ('<w:pgBorders w:offsetFrom="%s">' % off
                     + ''.join('<w:%s w:val="%s" w:sz="%d" w:space="%d" w:color="%s"%s/>' % (sd, val, sz, dist(i), color, ' w:shadow="1"' if shadow else '')
                               for sd, i in sides) + '</w:pgBorders>')
    # header and footer where DavkaWriter puts them (hf_layout); one taller than its margin pushes the body,
    # in Word as in DavkaWriter (page_capacity knows).  The footer keeps clear of the slack in the bottom margin.
    hdr_dist, ftr_dist, _, _ = hf_layout(D)
    fh = hf_heights(D)[1]
    if fh and ftr_dist + fh > mar[3] - BOTTOM_SLACK:
        ftr_dist0 = ftr_dist
        ftr_dist = max(0, mar[3] - BOTTOM_SLACK - fh)
        # (never down into a page border: it stays inside it, as in DavkaWriter)
        bb = border_box(D)
        if bb:
            ftr_dist = max(ftr_dist, min(ftr_dist0, bb['b'] + bb['w'] + HF_BORDER_PAD))
    sect = ('<w:sectPr>__HF__<w:type w:val="__TYPE__"/><w:pgSz w:w="%d" w:h="%d"%s/>' % (paper(D) + (' w:orient="landscape"' if D['page'].get('landscape') else '',)) +
            '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" w:header="%d" w:footer="%d" w:gutter="0"/>'
            '%s__COLS____TITLEPG__</w:sectPr>') % (max(mar[1], 0), max(mar[2] - 5, 0), max(mar[3] - BOTTOM_SLACK - (pinned_room(D) if D.get('pinned') else 0), 0), max(mar[0], 0),
               hdr_dist, ftr_dist,
               pg_border + '__PGNUM__')
    # (1.3.25) the page numbers: Folio's format (Hebrew letters) in every section; the number the first page gets
    # (page.pnoff: Page setup's "Number pages starting at", a PDF's own numbering) on the first section, and on the
    # section after the covers (they may be numbered below 1 in the editor: Word starts at 0 at the lowest)
    pnoff = int(D['page'].get('pnoff') or 0)
    def pgnum(first_page):
        a = ' w:fmt="%s"' % D['page']['pn_fmt'] if D['page'].get('pn_fmt') else ''
        if first_page is not None and pnoff:
            a += ' w:start="%d"' % max(0, first_page + 1 + pnoff)
        return '<w:pgNumType%s/>' % a if a else ''
    cover_k = D.get('_cover_sec')
    first_tpg = (int(D['page'].get('hfskip') or 0) == 1) and not D['page'].get('title_pg')
    # the section properties that close at paragraph i: column block ends and header/footer changes
    closes = {}
    for i, (cols, typ) in sect_at.items():
        closes[i] = [cols, typ, None]
    for k, sec in enumerate(sections[1:], 1):
        i = sec['start'] - 1
        c = closes.setdefault(i, [None, 'continuous', None])
        c[2] = k
    sec_of = 0
    # (a section's w:type says how that section starts: the break that closes section n gives section n+1's type)
    own_type = 'nextPage'
    n_sect = 0                 # sections written so far; own_start: the paragraph the section being closed starts at
    own_start = 0
    for i in sorted(closes):
        cols, typ, k = closes[i]
        if cols is None:
            cols = cols_xml(*state_at[i])    # a header change inside a column block keeps the block's columns
        if k is not None:
            # the new header starts on the page of its paragraph: a page break there is a real section break
            if (i + 1) in page_of and not D['main'][i + 1].get('soft'):
                typ = 'nextPage'
        inner = sect.replace('__HF__', refs(sec_of)).replace('__TYPE__', own_type).replace('__COLS__', cols)
        own_type = typ
        inner = inner.replace('__TITLEPG__', '<w:titlePg/>' if D['page'].get('title_pg') or (first_tpg and n_sect == 0) else '', 1).replace('__TITLEPG__', '')
        inner = inner.replace('__PGNUM__', pgnum(0 if n_sect == 0 else (int(D['page'].get('hfskip') or 0) if cover_k is not None and own_start == cover_k else None)))
        n_sect += 1
        own_start = i + 1
        if k is not None:
            sec_of = k
        tok = '__SECT_%d__' % i
        if not any(tok in b for b in body):
            body = _insert_sect_para(body, body_para, i, inner)
        else:
            body = [b.replace(tok, inner) for b in body]
    sect = sect.replace('__HF__', refs(sec_of)).replace('__TYPE__', own_type)
    sect = sect.replace('__COLS__', last_cols).replace('__TITLEPG__', '<w:titlePg/>' if D['page'].get('title_pg') or (first_tpg and n_sect == 0) else '', 1).replace('__TITLEPG__', '')
    sect = sect.replace('__PGNUM__', pgnum(0 if n_sect == 0 else (int(D['page'].get('hfskip') or 0) if cover_k is not None and own_start == cover_k else None)))
    # (the left/right margins are DavkaWriter's, so lines break where they do; the right one gives a hair (¼ pt) so that a
    #  tab or rule ending exactly at the margin stays on its line, as in DavkaWriter.  The bottom margin is a
    #  little smaller so that small font-metric differences never push a line onto an extra page; page breaks
    #  are explicit)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document %s mc:Ignorable="w14"><w:body>%s%s</w:body></w:document>'
            % (NS, ''.join(body), sect)), pages

CT = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/></Types>'''
RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
DOCRELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/></Relationships>'''
STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US" w:bidi="he-IL"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>'''
CT_FOOTER = CT.replace('</Types>', '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>')
DOCRELS_FOOTER = DOCRELS.replace('</Relationships>', '<Relationship Id="rIdFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>')
SETTINGS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:defaultTabStop w:val="720"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>'''

TABLE_WHOLE = os.environ.get('TABLE_SPLIT') != '1'   # (experiment switch)
LINE_TOL = 20           # twips a word may reach past the line's end and still fit (the width tables' rounding)
FIT_TOL = 60            # twips a page's text may exceed the model's page length and still fit (see paginate)
FOOTNOTE_DIVIDER = 240   # twips above a page's footnotes (the divider line and its spacing)
LO_SAFE = os.environ.get('FOLIO_LO_SAFE') == '1'     # test renders with LibreOffice (see para_xml)
DEFAULT_CAPACITY = None   # computed from the page margins

def footnotes_xml(D):
    """word/footnotes.xml: the separators Word requires, then every footnote's paragraphs"""
    out = ['<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>',
           '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>']
    for k, paras in enumerate(D.get('footnotes') or []):
        out.append('<w:footnote w:id="%d">%s</w:footnote>' % (k + 1, ''.join(para_xml(D, p, in_box=True) for p in paras) or '<w:p/>'))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:footnotes %s>%s</w:footnotes>' % (NS, ''.join(out)))

def footer_xml(D, paras=None):
    paras = D['footer'] if paras is None else paras
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr %s>%s</w:ftr>'
            % (NS, ''.join(para_xml(D, p) for p in paras) or '<w:p/>'))

def page_design(D):
    """(design id, tab text) of the page border Folio draws, or None.  The Folio editor's choice wins
    (D['page']['border_design'] = {'id': ..., 'tab': ...}, id 'none' for no border); otherwise a DavkaWriter
    picture border (only its name is in the file) gets the closest of Folio's own designs."""
    ch = D['page'].get('border_design')
    if isinstance(ch, dict) and ch.get('id'):
        if ch['id'] == 'none' or ch['id'] not in dict(pageborders.DESIGNS):
            return None
        return ch['id'], (ch.get('tab') or '') if ch['id'] == 'chumash' else ''
    return pageborders.design_for(D['page'].get('border_art'))

def page_art(D):
    """the picture of the page border (PNG bytes of one of Folio's own designs), or None"""
    d = page_design(D)
    if not d:
        return None
    pw, ph = paper(D)
    return pageborders.png(d[0], pw, ph, bool(d[1]))

def main_hebrew_font(D):
    """the Hebrew font most of the document is written in (for the border's name tab)"""
    count = {}
    for p in D['main']:
        for r in p['runs']:
            st = D['styles'].get(r['style'])
            if st and is_hebrew_style(st):
                count[st['font']] = count.get(st['font'], 0) + len(r['text'])
    return word_font(max(count, key=count.get)) if count else word_font('Davka David')

def page_tab_run(D, text):
    """the parsha name in the border's tab: real text in a text box over the tab"""
    pw, ph = paper(D)
    x, y, w, h = [int(v * 20) for v in pageborders.tab_rect(pw / 20.0, ph / 20.0)]
    emu = 635
    font = main_hebrew_font(D)
    para = ('<w:p><w:pPr><w:spacing w:before="0" w:after="0"/><w:bidi/><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:rFonts w:ascii="%s" w:hAnsi="%s" w:cs="%s" w:hint="cs"/><w:b/><w:bCs/><w:color w:val="1D3F7A"/>'
            '<w:sz w:val="32"/><w:szCs w:val="32"/><w:rtl/></w:rPr><w:t>%s</w:t></w:r></w:p>' % (font, font, font, escape(text)))
    return ('<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="2" behindDoc="1" locked="1" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>%d</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="page"><wp:posOffset>%d</wp:posOffset></wp:positionV>'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
            '<wp:docPr id="98" name="Page border name"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
            '<wps:wsp><wps:cNvSpPr txBox="1"/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></wps:spPr>'
            '<wps:txbx><w:txbxContent>%s</w:txbxContent></wps:txbx>'
            '<wps:bodyPr rot="0" vert="horz" wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="ctr"><a:noAutofit/></wps:bodyPr></wps:wsp>'
            '</a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>') % (x * emu, y * emu, w * emu, h * emu, w * emu, h * emu, para)

def page_art_run(D):
    """the border picture over the whole page, behind the text; in the header so every page has it"""
    pw, ph = paper(D)
    emu = 635
    return ('<w:r><w:drawing><wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="1" behindDoc="1" locked="1" layoutInCell="1" allowOverlap="1">'
            '<wp:simplePos x="0" y="0"/><wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>'
            '<wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>'
            '<wp:extent cx="%d" cy="%d"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:wrapNone/>'
            '<wp:docPr id="99" name="Page border (Folio design)"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="99" name="Page border"/><pic:cNvPicPr/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="rIdPageArt"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            '</a:graphicData></a:graphic></wp:anchor></w:drawing></w:r>') % (pw * emu, ph * emu, pw * emu, ph * emu)

def header_xml(D, paras=None):
    paras = [para_xml(D, p) for p in (D.get('header') or [] if paras is None else paras)]
    if page_art(D):
        run = page_art_run(D)
        tab = page_design(D)[1]
        if tab:
            run += page_tab_run(D, tab)
        if paras:
            k = paras[0].find('</w:pPr>')
            k = k + len('</w:pPr>') if k >= 0 else paras[0].find('>') + 1
            paras[0] = paras[0][:k] + run + paras[0][k:]
        else:
            paras = ['<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="exact"/></w:pPr>%s</w:p>' % run]
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr %s>%s</w:hdr>'
            % (NS, ''.join(paras)))

CT_APP_OVR = '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
RELS_APP = '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'

def app_xml(pages=None):
    """docProps/app.xml: names the converter and its version (Word shows it under File > Properties)."""
    v = str(APP_VERSION)
    m = re.match(r'^(\d+)\.(\d+)$', v)
    appver = '<AppVersion>%02d.%04d</AppVersion>' % (int(m.group(1)), int(m.group(2))) if m and int(m.group(2)) < 10000 else ''
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
            '<Application>%s</Application>%s%s</Properties>'
            % (escape('Folio ' + ('v' + v if v[:1].isdigit() else v)), '<Pages>%d</Pages>' % pages if pages else '', appver))

CT_HEADER_OVR = '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
DOCRELS_HEADER_REL = '<Relationship Id="rIdHeader1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>'

def all_paragraphs(D):
    """Every paragraph that is rendered: main flow, header, footer, table cells, text boxes."""
    seen = set()
    def walk(ps):
        for p in ps:
            if id(p) in seen:
                continue
            seen.add(id(p))
            yield p
            for o in p.get('objects') or []:          # text boxes anchored to the paragraph
                yield from walk(o.get('paras') or [])
            t = p.get('table')
            if t is not None:
                for row in t['rows']:
                    for cell in row:
                        yield from walk(cell)
    yield from walk(D['main'])
    yield from walk(D.get('header') or [])
    yield from walk(D.get('footer') or [])
    for o in D['objects']:
        yield from walk(o.get('paras') or [])

def apply_edits(D, edits):
    """edits: {'<paragraph pos>:<run index>': unicode text} from the browser editor."""
    from davkamap import encode
    if not edits:
        return
    for p in all_paragraphs(D):
        for ri, r in enumerate(p['runs']):
            key = '%d:%d' % (p['pos'], ri)
            if key in edits:
                u = edits[key]
                if r.get('field'):
                    continue
                r['utext'] = u
                r['text'] = encode(u) if is_hebrew_style(D['styles'].get(r['style'], {'flags': 0})) else u.encode('cp1252', 'replace')

def file_version(d):
    """The DavkaWriter file version: the first DWORD of the file (0 if the file is shorter)."""
    return struct.unpack_from('<I', d, 0)[0] if len(d) >= 4 else 0

HANDLED_FIELDS = ('CFieldAutoShape', 'CFieldCurvyText', 'CFieldGraphic', 'CFieldTextBox')

def make_diagnostics(D, d):
    """What was in the file and what could not be converted (counts and short warnings; never any text)."""
    paras = list(all_paragraphs(D))
    objs, seen = [], set()
    for o in list(D['objects']) + [o for p in paras for o in (p.get('objects') or [])]:
        if id(o) not in seen:
            seen.add(id(o)); objs.append(o)
    tables = set(id(t) for t in D.get('tables') or []) | set(id(p['table']) for p in paras if p.get('table') is not None)
    pics, not_shown, unknown = {}, 0, {}
    for o in objs:
        fc = o.get('field_class')
        if o.get('picture'):
            fmt = o.get('image_format') or ('bmp' if o.get('bmp') else 'unknown')
            pics[fmt] = pics.get(fmt, 0) + 1
            if not (o.get('bmp') or fmt in RAW_IMAGE_EXT):
                not_shown += 1
        elif fc and fc not in HANDLED_FIELDS:
            unknown[fc] = unknown.get(fc, 0) + 1
        elif not fc and not any(k in o for k in ('shape', 'text', 'paras', 'w', 'box')):
            k = 'object kind %s' % o.get('kind')
            unknown[k] = unknown.get(k, 0) + 1
    fields = {}
    for p in paras:
        for r in p['runs']:
            f = r.get('field')
            if f:
                k = f if isinstance(f, str) else type(f).__name__
                fields[k] = fields.get(k, 0) + 1
    warnings = list(D.get('warnings') or [])      # from the parser (e.g. a cut-off file), most important first
    used_fonts = sorted({D['styles'][r['style']]['font'] for p in all_paragraphs(D) for r in p['runs'] if r.get('style') in D['styles']})
    substitutions = [name + ' → ' + word_font(name) for name in used_fonts if freefonts.is_davka(name) and name not in OPTIONS.get('installed_fonts', {})]
    if substitutions:
        warnings.append('Font substitutes: ' + '; '.join(substitutions) + '. Original Unicode counterparts are used when installed.')
    if D.get('reader') != 'spec':
        warnings.append(('heuristic reader used: %s' % (D.get('reader_error') or 'spec reader failed'))[:300])
    if pics.get('lead'):
        warnings.append('%d LEAD picture(s) cannot be shown' % pics['lead'])
    other = not_shown - pics.get('lead', 0)
    if other > 0:
        warnings.append('%d picture(s) in an unreadable format (%s)' % (other, ', '.join(sorted(k for k in pics if k not in RAW_IMAGE_EXT and k not in ('bmp', 'lead')))))
    for k, n in sorted(unknown.items()):
        warnings.append('%d unsupported object(s): %s' % (n, k))
    if D.get('protected'):
        warnings.append('protected file')
    if any(r['text'].strip() for p in (D.get('notes') or []) for r in p['runs']) and not D.get('footnotes'):
        warnings.append('notes text not converted (%d paragraphs)' % len(D['notes']))
    if D.get('header_even') or D.get('footer_even'):
        warnings.append('separate even-page header/footer not converted')
    if D.get('master_pages'):
        warnings.append('%d master page(s) not converted' % len(D['master_pages']))
    return dict(reader=D.get('reader', 'spec'), reader_error=D.get('reader_error'), file_version=file_version(d),
                format_version=D.get('version'), size=len(d),
                counts=dict(paragraphs=len(paras), main_paragraphs=len(D['main']), objects=len(objs),
                            page_objects=len(D['objects']), tables=len(tables), pictures=pics,
                            pictures_not_shown=not_shown, lead_pictures=pics.get('lead', 0),
                            unsupported=unknown, fields=fields,
                            header=len(D.get('header') or []), footer=len(D.get('footer') or [])),
                warnings=warnings, truncated=bool(D.get('truncated')), timings={})

LAST_DIAGNOSTICS = None

def _ms(t0):
    return round((time.perf_counter() - t0) * 1000, 1)

def convert_bytes(d, capacity=DEFAULT_CAPACITY, edits=None, diagnostics=False, extra_parts=None):
    """In-memory conversion (used by the web page): .dwd bytes -> (.docx bytes, pages, paragraphs, objects),
    plus a diagnostics dict as a fifth item when diagnostics=True (also kept in LAST_DIAGNOSTICS).
    extra_parts: as write_docx's (1.3.28: dwdedit.convert_bytes_folio puts Folio's own parts in, so the Word file
    opens again in the editor); the Word content (word/*) is the same with or without them."""
    import io
    global LAST_DIAGNOSTICS
    buf = io.BytesIO()
    if edits is not None and hasattr(edits, 'to_py'):
        edits = edits.to_py()
    d = bytes(d)
    tm = {}
    D, pages = convert(None, buf, capacity, data=d, edits=edits, timings=tm, extra_parts=extra_parts)
    t0 = time.perf_counter()
    diag = make_diagnostics(D, d)
    diag['counts']['pages'] = len(pages)
    diag['counts']['media_embedded'] = len(MEDIA.items)
    if edits:
        diag['edited'] = len(edits)
    tm['diagnostics_ms'] = _ms(t0)
    diag['timings'] = tm
    LAST_DIAGNOSTICS = diag
    out = (buf.getvalue(), len(pages), len(D['main']), len(D['objects']))
    return out + (diag,) if diagnostics else out

def preview_bytes(d, font_base='fonts/free/', edits=None, diagnostics=False):
    """In-memory preview (used by the web page): .dwd bytes -> (html, pages), plus a diagnostics dict as a
    third item when diagnostics=True."""
    from dwdhtml import render_html
    global LAST_DIAGNOSTICS
    if edits is not None and hasattr(edits, 'to_py'):
        edits = edits.to_py()
    d = bytes(d)
    t0 = time.perf_counter()
    D = parse(d)
    apply_edits(D, edits)
    tm = {'parse_ms': _ms(t0)}
    t1 = time.perf_counter()
    out = render_html(D, font_base=font_base)
    tm['render_ms'] = _ms(t1)
    diag = make_diagnostics(D, d)
    diag['counts']['pages'] = out[1]
    tm['total_ms'] = _ms(t0)
    diag['timings'] = tm
    LAST_DIAGNOSTICS = diag
    return tuple(out) + (diag,) if diagnostics else out

def convert(path, out, capacity=DEFAULT_CAPACITY, data=None, edits=None, timings=None, extra_parts=None):
    tm = timings if timings is not None else {}
    t0 = time.perf_counter()
    d = data if data is not None else open(path, 'rb').read()
    D = parse(d)
    apply_edits(D, edits)
    tm['parse_ms'] = _ms(t0)
    return write_docx(D, out, capacity, tm, t0, extra_parts=extra_parts)

NUM_FMT = {'he': ('hebrew1', '%{0}.'), 'num': ('decimal', '%{0}.'), 'alpha': ('lowerLetter', '%{0}.'), 'bullet': ('bullet', '\u2022')}

def assign_numbering(D):
    """Numbered lists made in the Folio editor (p['mlist'] = {'t': he|num|alpha|bullet, 'lvl'}): each run of
    list paragraphs of one kind is one Word list (its own w:num, so it starts at 1); returns numbering.xml
    or None."""
    blocks = []
    prev = None
    def flat():
        seen = set()
        for p in D['main']:
            t = p.get('table')
            if t is None:
                yield p
            elif id(t) not in seen:
                seen.add(id(t))
                for r in t['rows']:
                    for cell in r:
                        for q in cell:
                            yield q
                        yield None
    for p in flat():
        ml = p.get('mlist') if p is not None else None
        if not ml:
            prev = None
            continue
        if prev is None or prev != ml.get('t'):
            blocks.append(ml.get('t') if ml.get('t') in NUM_FMT else 'num')
        prev = ml.get('t')
        ml['num'] = len(blocks)
    if not blocks:
        return None
    kinds = sorted(set(blocks))
    absn = []
    for ai, k in enumerate(kinds):
        fmt, text = NUM_FMT[k]
        lvls = ''.join('<w:lvl w:ilvl="%d"><w:start w:val="1"/><w:numFmt w:val="%s"/><w:lvlText w:val="%s"/><w:lvlJc w:val="left"/>'
                       '<w:pPr><w:ind w:left="%d" w:hanging="360"/></w:pPr>%s</w:lvl>'
                       % (i, fmt, text.replace('{0}', str(i + 1)), 360 * (i + 1),
                          '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>' if False else '')
                       for i in range(9))
        absn.append('<w:abstractNum w:abstractNumId="%d"><w:multiLevelType w:val="hybridMultilevel"/>%s</w:abstractNum>' % (ai, lvls))
    restart = ''.join('<w:lvlOverride w:ilvl="%d"><w:startOverride w:val="1"/></w:lvlOverride>' % i for i in range(9))
    nums = ''.join('<w:num w:numId="%d"><w:abstractNumId w:val="%d"/>%s</w:num>' % (i + 1, kinds.index(k), restart) for i, k in enumerate(blocks))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            + ''.join(absn) + nums + '</w:numbering>')

def write_docx(D, out, capacity=DEFAULT_CAPACITY, tm=None, t0=None, extra_parts=None):
    """Write the .docx for the document D to out (a path or a file object).  extra_parts:
    [(zip name, bytes, content type)] stored in the package as well (the Folio editor keeps the original
    .dwd and its own document there); they are listed in [Content_Types].xml and linked from _rels/.rels."""
    tm = tm if tm is not None else {}
    t0 = t0 if t0 is not None else time.perf_counter()
    t1 = time.perf_counter()
    MEDIA.reset()
    numbering = assign_numbering(D)
    doc, pages = build_document(D, capacity)
    tm['build_ms'] = _ms(t1)
    t2 = time.perf_counter()
    art = page_art(D)
    sections = D.get('_hf_sections') or hf_sections(D)
    ct, rels = CT, DOCRELS
    parts = {}                 # zip name -> xml
    part_rels = {}             # zip name -> its relationships xml
    media_rels = ''.join(
        '<Relationship Id="rIdImg%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/%s"/>' % (i + 1, name)
        for i, (name, _) in enumerate(MEDIA.items))
    any_h = any(sec['header'] for sec in sections) or bool(art)
    any_f = any(sec['footer'] for sec in sections)
    for k, sec in enumerate(sections):
        n = k + 1
        if any_h:
            parts['word/header%d.xml' % n] = header_xml(D, sec['header'])
            ct = ct.replace('</Types>', '<Override PartName="/word/header%d.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>' % n)
            rels = rels.replace('</Relationships>', '<Relationship Id="rIdHeader%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header%d.xml"/></Relationships>' % (n, n))
            part_rels['word/_rels/header%d.xml.rels' % n] = ('<Relationship Id="rIdPageArt" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/pageborder.png"/>' if art else '')
        if any_f:
            parts['word/footer%d.xml' % n] = footer_xml(D, sec['footer'])
            ct = ct.replace('</Types>', '<Override PartName="/word/footer%d.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>' % n)
            rels = rels.replace('</Relationships>', '<Relationship Id="rIdFooter%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer%d.xml"/></Relationships>' % (n, n))
            part_rels['word/_rels/footer%d.xml.rels' % n] = ''
    has_notes = bool(D.get('footnotes'))
    notes_xml = footnotes_xml(D) if has_notes else None
    # (header/footer/footnote parts are made after the body, so the media list is complete only now)
    media_rels = ''.join(
        '<Relationship Id="rIdImg%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/%s"/>' % (i + 1, name)
        for i, (name, _) in enumerate(MEDIA.items))
    if MEDIA.items or art:
        exts = sorted(set([name.rsplit('.', 1)[1] for name, _ in MEDIA.items] + (['png'] if art else [])))
        ct = ct.replace('<Default Extension="xml"', ''.join('<Default Extension="%s" ContentType="%s"/>' % (e, IMAGE_CT[e]) for e in exts) + '<Default Extension="xml"')
        rels = rels.replace('</Relationships>', media_rels + '</Relationships>')
    if has_notes:
        ct = ct.replace('</Types>', '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/></Types>')
        rels = rels.replace('</Relationships>', '<Relationship Id="rIdFootnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/></Relationships>')
    if numbering:
        ct = ct.replace('</Types>', '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>')
        rels = rels.replace('</Relationships>', '<Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>')
    ct = ct.replace('</Types>', CT_APP_OVR + '</Types>')
    prels = RELS.replace('</Relationships>', RELS_APP + '</Relationships>')
    for k, (name, data_, ctype) in enumerate(extra_parts or []):
        ct = ct.replace('</Types>', '<Override PartName="/%s" ContentType="%s"/></Types>' % (name, ctype))
        prels = prels.replace('</Relationships>', '<Relationship Id="rIdFolio%d" Type="urn:folio:relationships:%s" Target="%s"/></Relationships>'
                              % (k + 1, name.rsplit('/', 1)[-1].replace('.', '-'), name))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, png in MEDIA.items:
            z.writestr('word/media/' + name, png)
        z.writestr('[Content_Types].xml', ct)
        z.writestr('_rels/.rels', prels)
        z.writestr('docProps/app.xml', app_xml(len(pages)))
        z.writestr('word/_rels/document.xml.rels', rels)
        for name, xml in parts.items():
            z.writestr(name, xml)
        for name, extra in part_rels.items():
            z.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s%s</Relationships>' % (extra, media_rels))
        if art:
            z.writestr('word/media/pageborder.png', art)
        z.writestr('word/document.xml', doc)
        if has_notes:
            z.writestr('word/footnotes.xml', notes_xml)
            z.writestr('word/_rels/footnotes.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>' % media_rels)
        if numbering:
            z.writestr('word/numbering.xml', numbering)
        z.writestr('word/styles.xml', STYLES)
        z.writestr('word/settings.xml', SETTINGS)
        for name, data_, ctype in extra_parts or []:
            z.writestr(name, data_(D) if callable(data_) else data_)
    tm['zip_ms'] = _ms(t2)
    tm['total_ms'] = _ms(t0)
    return D, pages

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files', nargs='+')
    ap.add_argument('-o', '--outdir')
    ap.add_argument('--capacity', type=int, default=None)
    a = ap.parse_args()
    failed = 0
    for f in a.files:
        outdir = a.outdir or os.path.dirname(os.path.abspath(f))
        out = os.path.join(outdir, os.path.splitext(os.path.basename(f))[0] + '.docx')
        try:
            os.makedirs(outdir, exist_ok=True)
            D, pages = convert(f, out, a.capacity)
            warns = D.get('warnings') or []
            print('%s %s -> %s  (%d paragraphs, %d pages, %d objects)' % ('WARN' if warns else 'OK  ', f, out, len(D['main']), len(pages), len(D['objects'])))
            for w in warns:
                print('     warning: %s' % w)
        except Exception as e:
            failed += 1
            print('ERR %s: %s' % (f, e))
    return 1 if failed else 0

if __name__ == '__main__':
    sys.exit(main())
