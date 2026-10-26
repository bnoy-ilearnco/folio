# -*- coding: utf-8 -*-
"""Davka / GuttmanD font names -> the free, openly licensed font Folio uses in their place.

Folio never ships DavkaWriter's fonts.  A document that names a Davka font keeps that name (so it can be
saved back unchanged), and is shown and written to Word in the free font listed here.  The free fonts are
"similar to" the Davka ones, not copies of them.  QUALITY: how close the match is, judged by eye on
side-by-side samples:  good / approx (similar style) / none (no real match; a neutral fallback).
"""
FREE_FOR = {
    'Davka Aharony': ('Miriam Libre', 'approx'),
    'Davka Chayim': ('Secular One', 'good'),
    'Davka David': ('Taamey David CLM', 'good'),
    'Davka DavidFix': ('Taamey David CLM', 'approx'),
    'Davka Drogolin': ('Keter YG', 'approx'),
    'Davka FrankRuhl': ('Taamey Frank CLM', 'good'),
    'Davka FrankRuhlLight': ('Frank Ruhl Libre Light', 'good'),
    'Davka Gefen': ('Secular One', 'none'),
    'Davka Gonen': ('Varela Round', 'approx'),
    'Davka Hadasah': ('Hadasim CLM', 'good'),
    'Davka Kastel': ('Heebo', 'approx'),
    'Davka KsavYad': ('Playpen Sans Hebrew', 'approx'),
    'Davka Meir': ('Alef', 'approx'),
    'Davka Miriam': ('Miriam Libre', 'good'),
    'Davka Rashi': ('Noto Rashi Hebrew', 'good'),
    'Davka Siddur': ('Ezra SIL', 'approx'),
    'Davka Stam': ('Shlomo Stam', 'good'),
    'Davka Yerushalmy': ('Shofar', 'approx'),
    'GuttmanD Adii': ('David Libre', 'approx'),
    'GuttmanD Almog': ('Secular One', 'approx'),
    'GuttmanD Ashknaz': ('Noto Serif Hebrew', 'approx'),
    'GuttmanD Calligraphic': ('Bellefair', 'approx'),
    'GuttmanD Hadar': ('Noto Serif Hebrew', 'good'),
    'GuttmanD Hatzvi': ('Frank Ruhl Libre', 'approx'),
    'GuttmanD Keren': ('Heebo', 'approx'),
    'GuttmanD Mantova-Deco': ('Makabi YG', 'none'),
    'GuttmanD Noam': ('Noto Sans Hebrew', 'approx'),
    'GuttmanD Pearl': ('Alef', 'approx'),
    'GuttmanD Rolit': ('Secular One', 'none'),
    'GuttmanD Slavita': ('Frank Ruhl Libre', 'good'),
    'GuttmanD StamAri': ('Shlomo SemiStam', 'approx'),
    'GuttmanD Tzuk': ('Secular One', 'good'),
    'GuttmanD Venice': ('Linux Libertine', 'approx'),
    'GuttmanD Vilna': ('Romm Vilna', 'good'),
    'GuttmanD Yad': ('Playpen Sans Hebrew', 'approx'),
}
# How big the free font is drawn for a Davka font, and how much wider or narrower it is then made, so that a line
# takes the room it took in DavkaWriter: font_calib.json (made by tests/calib/make_font_calib.py from the DavkaWriter
# fonts' widths, the free fonts' widths and the corpus' own text).  Per font and weight:
#   k   DavkaWriter's letter width / the free font's (letters with their nekudos, weighted by how often they occur)
#   sp  [DavkaWriter, free font] width of a space, us: the same for an underscore (em at the nominal size)
#   lh  [ascent, descent, line gap] / size that DavkaWriter uses for the line height
# The free font is drawn at k of the size (kept within size_range: an extreme k would make the letters far taller
# or smaller than DavkaWriter's); what is left over, and the point size's rounding, is made up by the character
# scale in Word (w:w) and the letter spacing in the editor.  Spaces get DavkaWriter's width from the scale of their
# run in Word (dwd2docx.text_scale) and the word spacing in the editor; a blank (a row of spaces or underscores)
# gets a scale of its own in Word, and underscores a face of their own in the editor (build.py).
import json as _json, os as _os
try:
    _CAL = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'font_calib.json')))
except (OSError, ValueError):
    _CAL = {'fonts': {}, 'size_range': [0.75, 1.15], 'scale_range': [80, 125]}
CALIB = _CAL['fonts']
SIZE_RANGE = tuple(_CAL['size_range'])
SCALE_RANGE = tuple(_CAL['scale_range'])
SYMBOLS = _CAL.get('sym', {})          # Wingdings picture (Unicode) -> its fallback font's advance (em)
DEFAULT_FREE = 'Taamey David CLM'      # any other Davka/GuttmanD name


def is_davka(name):
    return bool(name) and name.startswith(('Davka ', 'GuttmanD '))


def free_font(name):
    """the free font shown / written for a font name (non-Davka names are returned unchanged)."""
    if is_davka(name):
        return FREE_FOR.get(name, (DEFAULT_FREE,))[0]
    return name


def like_label(name):
    """'Davka FrankRuhl' -> 'like Davka FrankRuhl' (wording: similar to, never 'is')."""
    return 'like ' + name


def calib(name, bold=False):
    """the calibration entry of a Davka font (its bold weight's when it has one), or None"""
    if not is_davka(name):
        return None
    return (CALIB.get(name + '/Bold') if bold else None) or CALIB.get(name) or CALIB.get(DEFAULT_CALIB)


DEFAULT_CALIB = 'Davka David'


def size_adj(name, bold=False):
    """the free font's size / the document's size for a Davka font"""
    c = calib(name, bold)
    if not c:
        return 1.0
    return round(min(max(c['k'], SIZE_RANGE[0]), SIZE_RANGE[1]), 3)


def char_scale(name, bold, size, drawn):
    """the character scale (percent) that gives a Davka font's free stand-in, drawn at `drawn` points for a size of
    `size` points, DavkaWriter's letter widths; 100 = none"""
    c = calib(name, bold)
    if not c or not size or not drawn:
        return 100
    return int(round(min(max(100.0 * c['k'] * size / drawn, SCALE_RANGE[0]), SCALE_RANGE[1])))


def fix_scales(name, bold, size, drawn):
    """{' ': percent, '_': percent}: the character scale that gives each space and underscore of a Davka font's
    free stand-in, drawn at `drawn` points for a size of `size` points, DavkaWriter's width.  (A scale, not
    character spacing: LibreOffice leaves out most negative spacing on spaces.)"""
    c = calib(name, bold)
    out = {}
    if not c or not size or not drawn:
        return out
    for ch, key in ((' ', 'sp'), ('_', 'us')):
        dw, fr = c[key]
        if fr > 0:
            out[ch] = int(round(min(max(100.0 * dw * size / (fr * drawn), 1), 600)))
    return out


SIZE_ADJ = {d: size_adj(d) for d in FREE_FOR}      # (the regular weight's, for the font lists)
