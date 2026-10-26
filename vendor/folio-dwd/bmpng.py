"""Decode a Windows .bmp (1/4/8-bit paletted, RLE4/RLE8, 16/24/32-bit) to PNG bytes.  Pure Python: it runs in the
browser too.  Paletted bitmaps become paletted PNGs (the packed index bytes are copied as they are: BMP and PNG
pack 1- and 4-bit pixels the same way), so a 400 KB bitmap takes milliseconds, not seconds."""
import struct, zlib

def _rle(data, w, h, bits):
    """RLE8 / RLE4 -> one bytearray of 8-bit indices per row (slice assignment keeps the loops short)."""
    rows = [bytearray(w) for _ in range(h)]
    x = y = 0; i = 0; n = len(data)
    while i + 1 < n and y < h:
        c, v = data[i], data[i + 1]; i += 2
        if c:
            if x < w:
                k = min(c, w - x)
                if bits == 8:
                    rows[y][x:x + k] = bytes((v,)) * k
                else:
                    rows[y][x:x + k] = (bytes((v >> 4, v & 15)) * ((k + 1) // 2))[:k]
            x += c
        elif v == 0:
            x = 0; y += 1
        elif v == 1:
            break
        elif v == 2:
            x += data[i]; y += data[i + 1]; i += 2
        else:
            if bits == 8:
                if x < w:
                    k = min(v, w - x)
                    rows[y][x:x + k] = data[i:i + k]
                x += v
                i += v + (v & 1)
            else:
                nb = (v + 1) // 2
                px = bytearray()
                for b in data[i:i + nb]:
                    px.append(b >> 4); px.append(b & 15)
                if x < w:
                    k = min(v, w - x)
                    rows[y][x:x + k] = px[:k]
                x += v
                i += nb + (nb & 1)
    return rows

def _chunk(tag, body):
    return struct.pack('>I', len(body)) + tag + body + struct.pack('>I', zlib.crc32(tag + body) & 0xffffffff)

_CACHE = {}     # the editor and the Word file convert the same pictures: keep the last few

def bmp_to_png(bmp):
    key = (len(bmp), hash(bytes(bmp[:4096])), hash(bytes(bmp[-4096:])))
    if key in _CACHE:
        return _CACHE[key]
    off = struct.unpack_from('<I', bmp, 10)[0]
    hsz, w, h, planes, bpp, comp, isz = struct.unpack_from('<IiiHHII', bmp, 14)
    flip = h > 0; h = abs(h)
    if w <= 0 or h <= 0 or w * h > 400_000_000:
        raise ValueError('bad bitmap size %dx%d' % (w, h))
    pal = b''
    if bpp <= 8:
        ncol = struct.unpack_from('<I', bmp, 46)[0] or (1 << bpp)
        ncol = min(ncol, 1 << bpp)
        p = 14 + hsz
        pal = b''.join(bytes((bmp[p + 4 * k + 2], bmp[p + 4 * k + 1], bmp[p + 4 * k])) for k in range(ncol))
        pal += b'\0\0\0' * ((1 << bpp) - ncol)
    data = bmp[off:]
    rows = []
    if comp in (1, 2):
        rows = [bytes(r) for r in _rle(data, w, h, 8 if comp == 1 else 4)]
        depth, ctype = 8, 3
    elif comp == 0 and bpp in (1, 4, 8):
        stride = ((w * bpp + 31) // 32) * 4
        rb = (w * bpp + 7) // 8
        for y in range(h):
            line = data[y * stride:y * stride + rb]
            if len(line) < rb:
                line = line + b'\0' * (rb - len(line))
            rows.append(line)
        depth, ctype = bpp, 3
    elif comp in (0, 3) and bpp in (24, 32):
        stride = ((w * bpp + 31) // 32) * 4
        step = bpp // 8
        for y in range(h):
            line = data[y * stride:(y + 1) * stride]
            if len(line) < stride:
                line = line + b'\0' * (stride - len(line))
            out = bytearray(3 * w)
            out[0::3] = line[2:step * w:step]
            out[1::3] = line[1:step * w:step]
            out[2::3] = line[0:step * w:step]
            rows.append(bytes(out))
        depth, ctype = 8, 2
    elif comp in (0, 3) and bpp == 16:
        stride = ((w * bpp + 31) // 32) * 4
        for y in range(h):
            line = data[y * stride:(y + 1) * stride]
            px = struct.unpack_from('<%dH' % w, line + b'\0' * (2 * w), 0)
            out = bytearray()
            for v in px:                       # 5-5-5
                out += bytes((((v >> 10) & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, (v & 31) * 255 // 31))
            rows.append(bytes(out))
        depth, ctype = 8, 2
    else:
        raise ValueError('unsupported bitmap depth %d / compression %d' % (bpp, comp))
    if flip:
        rows.reverse()
    raw = b'\0'.join([b''] + rows) if False else b''.join(b'\0' + r for r in rows)
    png = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, 0))
    if ctype == 3:
        png += _chunk(b'PLTE', pal)
    png += _chunk(b'IDAT', zlib.compress(raw, 1)) + _chunk(b'IEND', b'')   # fast: the .docx is zipped again anyway
    _CACHE[key] = png
    if len(_CACHE) > 64:
        _CACHE.pop(next(iter(_CACHE)))
    return png
