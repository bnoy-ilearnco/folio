"""Folio's own page borders (original designs, drawn here as SVG).

A DavkaWriter file can name a picture border from DavkaWriter's border library ("Bereishis", "Apple and
honey"...).  That artwork belongs to DavkaWriter and is not in the file; Folio never copies it.  Instead each
border name is mapped to one of these original designs, in a similar spirit.  The parsha name that some
DavkaWriter borders show is written as real text in a plain tab (not part of the picture).

design ids: 'chumash' (deep blue and warm gold with small stars, optional name tab), 'apples' (apples and honey
drops, for Rosh Hashana), 'celebrate' (confetti dots and corner flourishes), 'double' (a neutral double line).
The SVG is in points for a page of w x h points; build.py rasterizes it to PNG (PNG_DPI) for Word files.
"""
import math

DESIGNS = [('chumash', 'Chumash frame'), ('apples', 'Apples & honey'), ('celebrate', 'Celebration'), ('double', 'Double line')]
PNG_DPI = 150
NAVY, GOLD, SKY = '#1D3F7A', '#D9A21B', '#E9EEF8'

# DavkaWriter border name -> (design, tab text); unknown names get the neutral double line
_PARSHA = {'bereishis': 'בראשית', 'bereshit': 'בראשית', 'shemos': 'שמות', 'shmos': 'שמות', 'shemot': 'שמות',
           'vayikra': 'ויקרא', 'bamidbar': 'במדבר', 'devarim': 'דברים'}


def design_for(name):
    """(design id, tab text or '') for a DavkaWriter border name; None for no name"""
    if not name:
        return None
    n = name.strip().lower()
    for k, heb in _PARSHA.items():
        if k in n:
            return 'chumash', heb
    if 'bible' in n or 'chumash' in n or 'torah' in n:
        return 'chumash', ''
    if 'apple' in n or 'honey' in n or 'rosh' in n:
        return 'apples', ''
    if 'invite' in n or 'party' in n or 'birthday' in n or 'celebr' in n:
        return 'celebrate', ''
    return 'double', ''


def tab_rect(w, h):
    """where the name tab sits (x, y, width, height in points from the page's top-left)"""
    return (w - 44 - 132, 10, 132, 38)


def _star(cx, cy, r, fill):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append('%.2f,%.2f' % (cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return '<polygon points="%s" fill="%s"/>' % (' '.join(pts), fill)


def _along(w, h, inset, step):
    """points along a rectangle's sides (the band's middle line), evenly spaced, corners excluded"""
    out = []
    for (x0, y0, x1, y1) in ((inset, inset, w - inset, inset), (w - inset, inset, w - inset, h - inset),
                             (w - inset, h - inset, inset, h - inset), (inset, h - inset, inset, inset)):
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L // step))
        for k in range(1, n):
            t = k / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    return out


def svg(design, w, h, tab=False):
    """the border as an SVG document for a page of w x h points"""
    o, b = 22.0, 22.0                      # the band: from 22 pt to 44 pt from the page edge
    mid = o + b / 2
    p = []
    if design == 'chumash':
        # a very light band (low ink) between the navy and gold lines
        p.append('<path fill-rule="evenodd" fill="%s" d="M%g %gH%gV%gH%gZ M%g %gH%gV%gH%gZ"/>' % (SKY, o, o, w - o, h - o, o, o + b, o + b, w - o - b, h - o - b, o + b))
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="2.2" rx="3"/>' % (o, o, w - 2 * o, h - 2 * o, NAVY))
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="1"/>' % (o + b, o + b, w - 2 * (o + b), h - 2 * (o + b), GOLD))
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="0.6"/>' % (o + b + 3, o + b + 3, w - 2 * (o + b + 3), h - 2 * (o + b + 3), NAVY))
        tx, ty, tw, th = tab_rect(w, h)
        for (x, y) in _along(w, h, mid, 34):
            if tab and tx - 8 <= x <= tx + tw + 8 and y < ty + th + 4:
                continue
            p.append(_star(x, y, 3.6, GOLD))
        for (x, y) in ((mid, mid), (w - mid, mid), (w - mid, h - mid), (mid, h - mid)):
            p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>' % (x - b / 2, y - b / 2, b, b, NAVY))
            p.append(_star(x, y, 6.5, GOLD))
        if tab:
            p.append('<rect x="%g" y="%g" width="%g" height="%g" rx="9" fill="#FFFFFF" stroke="%s" stroke-width="1.6"/>' % (tx, ty, tw, th, NAVY))
            p.append('<rect x="%g" y="%g" width="%g" height="%g" rx="7" fill="none" stroke="%s" stroke-width="0.7"/>' % (tx + 3, ty + 3, tw - 6, th - 6, GOLD))
    elif design == 'apples':
        red, green, honey = '#B8392C', '#4F7F3A', '#E0A526'
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="1.6" rx="10"/>' % (o, o, w - 2 * o, h - 2 * o, green))
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="0.8" rx="6"/>' % (o + b, o + b, w - 2 * (o + b), h - 2 * (o + b), honey))
        for k, (x, y) in enumerate(_along(w, h, mid, 40)):
            if k % 2 == 0:            # a small apple: round body, stem and leaf
                p.append('<circle cx="%.1f" cy="%.1f" r="5.2" fill="%s"/>' % (x, y + 0.8, red))
                p.append('<path d="M%.1f %.1f q0.6 -3 2 -4" stroke="#6B4A2B" stroke-width="0.9" fill="none"/>' % (x, y - 3.8))
                p.append('<path d="M%.1f %.1f q3.5 -2.5 6 0 q-3 2.2 -6 0z" fill="%s"/>' % (x + 0.6, y - 5.6, green))
            else:                     # a honey drop
                p.append('<path d="M%.1f %.1f q4.2 5.6 0 8.6 q-4.2 -3 0 -8.6z" fill="%s"/>' % (x, y - 4.6, honey))
        for (x, y) in ((mid, mid), (w - mid, mid), (w - mid, h - mid), (mid, h - mid)):
            p.append('<circle cx="%.1f" cy="%.1f" r="8" fill="none" stroke="%s" stroke-width="1.2"/>' % (x, y, honey))
            p.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (x, y, honey))
    elif design == 'celebrate':
        plum, teal, rose = '#6A3D9A', '#1C8C86', '#D9577A'
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="1.4"/>' % (o, o, w - 2 * o, h - 2 * o, plum))
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="0.7"/>' % (o + 4, o + 4, w - 2 * (o + 4), h - 2 * (o + 4), plum))
        cols = (teal, GOLD, rose, plum)
        for k, (x, y) in enumerate(_along(w, h, o + b - 6, 18)):
            c = cols[k % 4]
            if k % 3 == 0:
                p.append('<circle cx="%.1f" cy="%.1f" r="2.2" fill="%s"/>' % (x, y, c))
            elif k % 3 == 1:
                p.append('<rect x="%.1f" y="%.1f" width="4.4" height="1.8" fill="%s" transform="rotate(%d %.1f %.1f)"/>' % (x - 2.2, y - 0.9, c, (k * 37) % 180, x, y))
            else:
                p.append(_star(x, y, 2.6, c))
        for (x, y, sx, sy) in ((o, o, 1, 1), (w - o, o, -1, 1), (w - o, h - o, -1, -1), (o, h - o, 1, -1)):
            p.append('<path d="M%.1f %.1f q%.1f 0 %.1f %.1f" stroke="%s" stroke-width="1.2" fill="none"/>' % (x + sx * 30, y + sy * 8, -sx * 22, -sx * 22, sy * 22, teal))
            p.append('<circle cx="%.1f" cy="%.1f" r="3" fill="%s"/>' % (x + sx * 10, y + sy * 10, rose))
    else:                             # 'double': a neutral double line
        grey = '#3A4150'
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="1.8"/>' % (o, o, w - 2 * o, h - 2 * o, grey))
        p.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="%s" stroke-width="0.7"/>' % (o + 4, o + 4, w - 2 * (o + 4), h - 2 * (o + 4), grey))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%gpt" height="%gpt" viewBox="0 0 %g %g">%s</svg>'
            % (w, h, w, h, ''.join(p)))


# rasterized designs for Word files: (design, paper key, tab) -> base64 PNG, made by web/make_borders.py
try:
    from pageborders_png import PNG
except Exception:
    PNG = {}


def paper_key(w, h):
    """the nearest pre-drawn page shape for a page of w x h twips"""
    land = w > h
    a4 = abs(min(w, h) - 11906) < 200
    return ('A4' if a4 else 'Letter') + ('-land' if land else '')


def png(design, w, h, tab=False):
    """PNG bytes of a design for a page of w x h twips (the nearest pre-drawn shape, stretched to the page)"""
    import base64
    v = PNG.get((design, paper_key(w, h), bool(tab)))
    return base64.b64decode(v) if v else None
