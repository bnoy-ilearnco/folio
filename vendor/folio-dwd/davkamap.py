"""Davka 8-bit Hebrew font encoding -> Unicode. Derived by matching glyph outlines
between 'Davka David' and its Unicode twin 'UniDavka David' shipped with DavkaWriter."""
BASE = {}
# Hebrew letters alef..tav at 0x60..0x7A
for i, cp in enumerate(range(0x05D0, 0x05EB)):
    BASE[0x60 + i] = chr(cp)
DAG = 'ּ'; SHIN = 'ׁ'; SIN = 'ׂ'
BASE.update({
    0x41: 'ב'+DAG, 0x42: 'ג'+DAG, 0x43: 'ד'+DAG, 0x44: 'ה'+DAG,
    0x45: 'ו'+DAG, 0x46: 'וֹ', 0x47: 'ז'+DAG, 0x48: 'ט'+DAG,
    0x49: 'י'+DAG, 0x4A: 'ך'+DAG, 0x4B: 'ךְ', 0x4C: 'ךָ',
    0x82: 'ך'+DAG+'ָ',   # final kaf + dagesh + kamatz (as in מִמֶּךָּ, אוֹדֶךָּ)
    0x4D: 'כ'+DAG, 0x4E: 'ל'+DAG, 0x4F: 'מ'+DAG, 0x50: 'נ'+DAG,
    0x51: 'ס'+DAG, 0x52: 'פ'+DAG, 0x53: 'צ'+DAG, 0x54: 'ק'+DAG,
    0x55: 'ש'+SIN, 0x56: 'ש'+DAG+SIN, 0x57: 'ש'+SHIN, 0x58: 'ש'+DAG+SHIN,
    0x59: 'ת'+DAG, 0x5A: '„', 0x9E: 'ש'+DAG, 0xFB: 'ש'+DAG,
    0x27: "'", 0x2C: ',', 0x2E: '.', 0x2F: '/', 0x3B: ';',
    0xA0: ' ', 0xB1: '–', 0xCE: '־', 0xEB: '־', 0xD0: '—',
    0x83: '›', 0xC8: '‹', 0xC9: '›', 0xE9: '‹',
    0x84: '«', 0xD1: '«', 0xD2: '»', 0xF1: '»',
    0x85: '¢', 0xD6: '¢', 0xCA: '§', 0xCC: '±', 0xED: '±',
    0xCD: '¶', 0xEA: '¶', 0xCF: '©', 0xEC: '©',
    0xD3: '¼', 0xEE: '¼', 0xD4: '½', 0xEF: '½', 0xD5: '¾',
    0xD7: '£', 0xD8: 'µ', 0xD9: '÷', 0xF4: '÷', 0xDA: '×', 0xF2: '×',
    0xDB: '•', 0xF3: '•', 0xF6: '’',
    0x87: '׳',  # geresh, as in ה׳ (Frank Ruhl, Gonen, Adii fonts)
    0x89: '״',  # gershayim, as in א״ב
})
# Vowel points (combining; attach to the preceding letter)
NIKUD = {
    0xA1: 'ֱ', 0xA2: 'ֳ', 0xA3: 'ֲ', 0xA4: 'ֶ', 0xA5: 'ֵ',
    0xA6: 'ִ', 0xA7: 'ְ', 0xA8: 'ָ', 0xA9: 'ַ', 0xAA: 'ֻ',
    0xAB: 'ֽ', 0xB3: '\u05a4', 0xB4: '֣',   # (1.3.27) 0xB3 mahpach (every Davka / GuttmanD font draws "<"), 0xB4 munach
    0xAC: '֥', 0xAD: '֖', 0xAE: '֑', 0xB8: '֨', 0xC6: '֙',   # tipcha, etnachta, qadma, pashta (from a Chayei Sarah posuk)
    0xBC: '֒', 0xBD: '֔', 0xBE: '֕', 0xC0: '֗', 0xC3: '֓',
    0xC4: '֬', 0x80: '֬', 0xC5: '֫', 0x81: '֫', 0xBB: '֮',
}
# (1.3.26) the last codes that came out as U+FFFD, mostly in the Davka FrankRuhl Tanach / Siddur texts.  Each was
# matched against the same verse in a Tanach with trop and checked against the glyph DavkaWriter draws at that code
# (the same in Davka David, FrankRuhl, Rashi and GuttmanD Vilna).  Positional variants become the plain mark.
NIKUD_1326 = {
    0xE8: 'ְ',   # sheva, drawn further right (19660 of 19670 matched words: sheva)
    0x92: 'ׇ',   # kamatz katan (long-legged kamatz): כׇּל, קׇדְשִׁי, וַיָּקׇם
    0x91: 'ֳ',   # hataf kamatz, the long-legged form: אֳנִיָּה, אָהֳלֵי
    0xB2: '֛',   # tevir
    0xB9: '֜',   # geresh (azla geresh)
    0xAF: '֧',   # darga
    0xC1: '֩',   # telisha ketana (on the word's last letter)
    0xC2: '֠',   # telisha gedola (on the word's first letter)
    0xBA: '֞',   # gershayim (the trop)
    0xB5: '֚',   # yetiv (before the vowel, on the first letter: מָ֚ה, זֶ֚ה)
    0xBF: '֡',   # pazer
    0xB6: '֪',   # yerach ben yomo (galgal)
    0x8C: '֝',   # geresh mukdam: the geresh of revia mugrash in Tehilim / Mishlei / Iyov
    0x86: '֭',   # dechi (Tehilim / Mishlei / Iyov)
}
NIKUD.update(NIKUD_1326)
BASE_1326 = {
    0x93: 'ר' + DAG,   # resh with dagesh: לְשָׁרֶּךָ, שֶׁרֹּאשִׁי, הַרְּעִמָהּ
    0x8A: '”',    # opening quotation mark ” (Davka Rashi: ”מֵעַל לָרָקִיעַ״)
    0x88: '’',    # opening single quotation mark ’
    0xB0: '-',         # hyphen, as in א-ל
}
BASE.update(BASE_1326)
NEW_1326 = frozenset(NIKUD_1326) | frozenset(BASE_1326)
# not mapped: 0x8B (a tilde above, once, with no letter under it before "פרק" in Yehoshua): it stays U+FFFD
# (1.3.27) '|' (0x7C) standing between two Hebrew words that have nikud or trop is a paseq (Tanach / Siddur texts):
# U+05C0.  A bar anywhere else (a separator after a full stop, a word without nekudos, English) stays '|'.
PASEQ = '\u05c0'
UPPER_DOT = (0x9F, 0xCB)   # dot above: holam, or shin/sin dot depending on neighbours
SHIN_L = 'ש'

def is_letter(ch):
    return 'א' <= ch <= 'ת'

def decode(b):
    """Decode Davka-encoded bytes (logical order) to Unicode Hebrew."""
    out = []  # list of clusters: [base, marks...]
    n = len(b); i = 0
    pending_shin_dot = False
    while i < n:
        c = b[i]
        if c in UPPER_DOT:
            nxt = b[i+1] if i + 1 < n else None
            nxt_s = BASE.get(nxt, '') if nxt is not None else ''
            prev = out[-1] if out else None
            if nxt_s.startswith(SHIN_L):
                # dot written before a shin = shin dot (right side) of that shin
                if not (SHIN in nxt_s or SIN in nxt_s):
                    pending_shin_dot = True
                    i += 1; continue
            if prev and prev[0] == SHIN_L and SHIN not in prev and SIN not in prev:
                prev.append(SIN)   # dot after a shin = sin dot
            elif prev and is_letter(prev[0]):
                prev.append('ֹ')  # holam
            i += 1; continue
        if c in NIKUD:
            if out and is_letter(out[-1][0]):
                out[-1].append(NIKUD[c])
            else:
                out.append([NIKUD[c]])
            i += 1; continue
        s = BASE.get(c)
        if s is None:
            s = chr(c) if c < 0x80 else '�'
        cl = [s[0]] + list(s[1:])
        if pending_shin_dot and cl[0] == SHIN_L:
            cl.append(SHIN)
        pending_shin_dot = False
        out.append(cl)
        i += 1
    # mark order (the same as the Folio editor): shin/sin dot, dagesh, vowels, then meteg/trop
    res = []
    for cl in out:
        base, marks = cl[0], cl[1:]
        marks.sort(key=mark_rank)
        res.append(base + ''.join(marks))
    if '|' in res:
        _paseq(res)
    return ''.join(res)


def _pointed_word(res, i, step):
    """is the word next to res[i] in direction step (spaces skipped) a Hebrew word with nikud or trop?  It must
    start right there with a letter (to the right: punctuation after the word, as in ":" or ",", is fine; to the
    left: a word that ends in punctuation, as "טוֹב." before the bar, is not one; a keri's brackets are fine)"""
    n = len(res)
    j = i + step
    while 0 <= j < n and res[j] in (' ', '\u00a0'):
        j += step
    if 0 <= j < n and res[j] in ('[', ']'):      # a keri in brackets: ]דְּבָר֣וֹ[ ׀
        j += step
    if not (0 <= j < n) or not is_letter(res[j][0]):
        return False
    pointed = False
    while 0 <= j < n and (is_letter(res[j][0]) or res[j] == '\u05be'):
        pointed = pointed or len(res[j]) > 1
        j += step
    return pointed


def _paseq(res):
    for i, c in enumerate(res):
        if c == '|' and _pointed_word(res, i, -1) and _pointed_word(res, i, 1):
            res[i] = PASEQ


def mark_rank(m):
    """Order of combining marks on a letter: shin/sin dot, dagesh, vowel, meteg/rafe/trop."""
    if m in (SHIN, SIN):
        return 0
    if m == DAG:
        return 1
    if '\u05b0' <= m <= '\u05bb' or m == '\u05c7':
        return 2
    return 3


def is_mark(ch):
    """A Hebrew combining mark (nikud, dagesh, dots, meteg, rafe, trop)."""
    return '\u0591' <= ch <= '\u05c7' and ch not in '\u05be\u05c0\u05c3\u05c6'


def normalize(u):
    """Sort the marks of every letter into mark_rank order (stable)."""
    out = []
    i, n = 0, len(u)
    while i < n:
        j = i + 1
        while j < n and is_mark(u[j]):
            j += 1
        if is_mark(u[i]):
            out.append(u[i]); i += 1; continue
        out.append(u[i] + ''.join(sorted(u[i + 1:j], key=mark_rank)))
        i = j
    return ''.join(out)


_REV_LETTER = {chr(0x05D0 + i): bytes([0x60 + i]) for i in range(27)}
# (1.3.27) every mark has its (zero-width) byte, the 1.3.26 codes too; a mark with no Davka code at all is left out
# (zero width, as DavkaWriter draws marks)
_REV_MARK = {}
for _k, _v in sorted(NIKUD.items(), key=lambda kv: (kv[0] in NEW_1326, kv[0])):
    _REV_MARK.setdefault(_v, bytes([_k]))
def encode(u):
    """Unicode Hebrew text -> Davka bytes, for measuring edited text with the width model.
    Marks become (zero-width) nikud bytes; dagesh and the dots ride on the letter."""
    out = bytearray()
    for ch in u:
        if ch in _REV_LETTER:
            out += _REV_LETTER[ch]
        elif ch in _REV_MARK:
            out += _REV_MARK[ch]
        elif ch in ('\u05bc', '\u05c1', '\u05c2', '\u05b9', '\u200f', '\u200e') or is_mark(ch):
            pass
        elif ch == PASEQ:
            out += b'|'
        elif ch == '\u05be':
            out += b'\xce'
        elif ch in ('\u05f3', "'"):
            out += b'\x27'
        elif ch in ('\u05f4', '"'):
            out += b'\x22'
        else:
            out += ch.encode('cp1252', 'replace')
    return bytes(out)


# ---------------------------------------------------------------- exact encoder (the inverse of decode)
_LETTER_DAG = {}          # (letter, dagesh, shin dot, sin dot, holam) -> byte
for _b, _s in BASE.items():          # (0x93 רּ is the only letter of 1.3.26: no other code has it)
    if len(_s) >= 1 and is_letter(_s[0]):
        _ms = set(_s[1:])
        key = (_s[0], DAG in _ms, SHIN in _ms, SIN in _ms, '\u05b9' in _ms, '\u05b0' in _ms, '\u05b8' in _ms)
        if key not in _LETTER_DAG or _b < _LETTER_DAG[key]:
            _LETTER_DAG[key] = _b
_MARK_BYTE = {}
# a mark or character that already had a code keeps it (hataf kamatz 0xA2, sheva 0xA7, \u2019 0xF6); the 1.3.26 codes
# are written only for what had none (kamatz katan, the new trop, \u201d, \u05e8\u05bc)
for _b, _m in sorted(NIKUD.items(), key=lambda kv: (kv[0] in NEW_1326, kv[0])):
    _MARK_BYTE.setdefault(_m, _b)
_CHAR_BYTE = {}
for _b, _s in sorted(BASE.items(), key=lambda kv: (kv[0] in NEW_1326, kv[0])):
    if len(_s) == 1 and not is_letter(_s) and not (_b in NEW_1326 and ord(_s) < 0x80):
        _CHAR_BYTE.setdefault(_s, _b)     # (0xB0 '-': a hyphen stays ASCII 0x2D)
_CHAR_BYTE[' '] = 0x20
_CHAR_BYTE[PASEQ] = 0x7C        # (1.3.27) paseq: decode gives it back only between pointed Hebrew words
_CHAR_BYTE['\u05be'] = 0xCE
_PASS = set(range(0x00, 0x80)) - set(BASE) - set(NIKUD) - set(UPPER_DOT)


def encode_exact(u):
    """Unicode Hebrew (logical order, as decode returns it) -> (Davka bytes, exact).
    exact is False when something in u has no Davka byte (e.g. Latin letters, rafe, kamatz katan, rare trop);
    those characters are written as '?' and the caller should keep the Unicode text as well."""
    out = bytearray()
    exact = True
    i, n = 0, len(u)
    while i < n:
        ch = u[i]
        j = i + 1
        while j < n and is_mark(u[j]):
            j += 1
        marks = list(u[i + 1:j]) if not is_mark(ch) else []
        if is_mark(ch):
            b = _MARK_BYTE.get(ch)
            if b is None:
                exact = False; b = 0x3F
            out.append(b); i += 1; continue
        if is_letter(ch):
            dg, sh, sn, ho = DAG in marks, SHIN in marks, SIN in marks, '\u05b9' in marks
            b = None
            used = []
            # a letter with dagesh / dots / holam (vav) may have its own byte
            for want in ((dg, sh, sn, ho), (dg, sh, sn, False)):
                key = (ch,) + want + (False, False)
                if key in _LETTER_DAG:
                    b = _LETTER_DAG[key]
                    used = [m for m, on in ((DAG, want[0]), (SHIN, want[1]), (SIN, want[2]), ('\u05b9', want[3])) if on]
                    break
            if b is None:
                exact = False
                b = 0x60 + (ord(ch) - 0x05D0)
                used = [m for m in (DAG, SHIN, SIN) if m in marks]
            out.append(b)
            rest = list(marks)
            for m in used:
                rest.remove(m)
            for m in sorted(rest, key=mark_rank):
                if m == '\u05b9':
                    out.append(0x9F)
                elif m in _MARK_BYTE:
                    out.append(_MARK_BYTE[m])
                else:
                    exact = False
            i = j; continue
        if ch in _CHAR_BYTE:
            out.append(_CHAR_BYTE[ch])
        elif ord(ch) in _PASS:
            out.append(ord(ch))
        else:
            exact = False
            out.append(0x3F)
        for m in marks:
            if m in _MARK_BYTE:
                out.append(_MARK_BYTE[m])
            else:
                exact = False
        i = j
    b = bytes(out)
    if exact and decode(b) != normalize(u):
        exact = False
    return b, exact


# ---------------------------------------------------------------- symbol fonts
# Wingdings & co. keep their pictures on ordinary letter codes ("q" is a box).  Shown as Unicode in the editor;
# written to Word as w:sym (Word on Mac and Windows has these fonts; LibreOffice maps them to OpenSymbol).
_WD = {
    0x21: '✏', 0x22: '✂', 0x23: '✁', 0x26: '\U0001f56e', 0x28: '☎', 0x29: '✆', 0x2a: '✉',
    0x36: '⌛', 0x37: '⌨', 0x3e: '✇', 0x3f: '✍', 0x41: '✌', 0x42: '\U0001f44c', 0x43: '\U0001f44d',
    0x44: '\U0001f44e', 0x45: '☜', 0x46: '☞', 0x47: '☝', 0x48: '☟', 0x4a: '☺', 0x4b: '\U0001f610',
    0x4c: '☹', 0x4d: '\U0001f4a3', 0x4e: '☠', 0x4f: '⚐', 0x50: '\U0001f3f1', 0x51: '✈', 0x52: '☼',
    0x53: '\U0001f4a7', 0x54: '❄', 0x55: '\U0001f546', 0x56: '✞', 0x57: '\U0001f548', 0x58: '✠', 0x59: '✡',
    0x5a: '☪', 0x5b: '☯', 0x5c: 'ॐ', 0x5d: '☸',
    0x5e: '♈', 0x5f: '♉', 0x60: '♊', 0x61: '♋', 0x62: '♌', 0x63: '♍', 0x64: '♎',
    0x65: '♏', 0x66: '♐', 0x67: '♑', 0x68: '♒', 0x69: '♓', 0x6a: '\U0001f670', 0x6b: '\U0001f675',
    0x6c: '●', 0x6d: '❍', 0x6e: '■', 0x6f: '□', 0x70: '⬜', 0x71: '❑', 0x72: '❒',
    0x73: '⬧', 0x74: '⧫', 0x75: '◆', 0x76: '❖', 0x77: '⬥', 0x78: '⌧', 0x79: '⍓',
    0x7a: '⌘', 0x7b: '❀', 0x7c: '✿', 0x7d: '❝', 0x7e: '❞',
    0x80: '⓪', 0x81: '①', 0x82: '②', 0x83: '③', 0x84: '④', 0x85: '⑤', 0x86: '⑥',
    0x87: '⑦', 0x88: '⑧', 0x89: '⑨', 0x8a: '⑩', 0x8b: '⓿', 0x8c: '❶', 0x8d: '❷',
    0x8e: '❸', 0x8f: '❹', 0x90: '❺', 0x91: '❻', 0x92: '❼', 0x93: '❽', 0x94: '❾',
    0x95: '❿', 0x9e: '·', 0x9f: '•', 0xa0: '◾', 0xa1: '○', 0xa2: '⭕', 0xa4: '◉',
    0xa5: '◎', 0xa7: '▪', 0xa8: '◻', 0xaa: '✦', 0xab: '★', 0xac: '✶', 0xad: '✴',
    0xae: '✹', 0xaf: '✵', 0xb1: '⌖', 0xb2: '⟡', 0xb3: '⌑', 0xd5: '⌫', 0xd6: '⌦',
    0xd8: '➢', 0xe0: '➲', 0xe8: '➔', 0xef: '⇦', 0xf0: '⇨', 0xf1: '⇧', 0xf2: '⇩',
    0xf3: '⬄', 0xf4: '⇳', 0xfb: '✗', 0xfc: '✔', 0xfd: '☒', 0xfe: '☑',
    0x2b: '\U0001f583', 0x49: '✋', 0xb9: '\U0001f552', 0xdf: '←',      # (1.3.24) envelope, hand, clock, arrow
}
_WD2 = {0x21: '✒', 0x24: '✐', 0x4a: '☝', 0xea: '★', 0x4f: '✗', 0x50: '✓', 0x51: '⨂', 0x52: '☑', 0x53: '☒', 0x54: '⮽', 0x55: '☐',
        0x97: '●', 0x99: '○', 0xa3: '□', 0xa7: '■'}
_WEB = {0x61: '✓', 0x72: '✖', 0x3d: '□', 0x63: '☐', 0x67: '■', 0x6e: '●', 0xae: '♪', 0xaf: '♫', 0x4c: '\U0001f50d', 0x55: '\U0001f4e2'}   # (1.3.24 ♪ ♫: the music notes)
_SYM = dict(zip(range(0x41, 0x5b), 'ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖ'))
_SYM.update(zip(range(0x61, 0x7b), 'αβχδεφγηιϕκλμνοπθρστυϖωξψζ'))
_SYM.update({0x22: '∀', 0x24: '∃', 0x27: '∋', 0x2a: '∗', 0x2d: '−', 0x40: '≅', 0x5e: '⊥',
             0xa3: '≤', 0xa5: '∞', 0xab: '↔', 0xac: '←', 0xad: '↑', 0xae: '→', 0xaf: '↓',
             0xb0: '°', 0xb1: '±', 0xb3: '≥', 0xb4: '×', 0xb7: '•', 0xb8: '÷', 0xb9: '≠',
             0xba: '≡', 0xbb: '≈', 0xd6: '√', 0xd7: '⋅', 0xe0: '◊'})
SYMBOL_FONTS = {'Wingdings': _WD, 'Wingdings 2': _WD2, 'Webdings': _WEB, 'Symbol': _SYM}
_SYMBOL_REV = {f: {v: k for k, v in m.items()} for f, m in SYMBOL_FONTS.items()}

def is_symbol_font(name):
    return name in SYMBOL_FONTS

def symbol_decode(font, b):
    """bytes of a symbol-font run -> Unicode (other codes: ASCII as is, the rest as Word's private-use form U+F0xx)"""
    m = SYMBOL_FONTS.get(font, {})
    return ''.join(m.get(c) or (chr(c) if c < 0x80 else chr(0xF000 + c)) for c in b)

def symbol_encode(font, u):
    """Unicode -> bytes of a symbol-font run (the inverse of symbol_decode)"""
    rev = _SYMBOL_REV.get(font, {})
    out = bytearray()
    for ch in u:
        if ch in rev:
            out.append(rev[ch])
        elif 0xF020 <= ord(ch) <= 0xF0FF:          # Word's private-use form of a symbol code
            out.append(ord(ch) - 0xF000)
        else:
            out += ch.encode('cp1252', 'replace')
    return bytes(out)
