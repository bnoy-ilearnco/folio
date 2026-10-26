"""Build Folio's offline Hebrew library from a pinned TorahLM download snapshot.

Python standard library only. Downloads are cached outside the source tree.
No network code is used by the installed reader.
"""
import argparse, concurrent.futures, hashlib, html, json, re, sqlite3, time, unicodedata
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

TANAKH = {
    'Torah': 'Genesis|Exodus|Leviticus|Numbers|Deuteronomy',
    'Neviim': 'Joshua|Judges|I Samuel|II Samuel|I Kings|II Kings|Isaiah|Jeremiah|Ezekiel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi',
    'Ketuvim': 'Psalms|Proverbs|Job|Song of Songs|Ruth|Lamentations|Ecclesiastes|Esther|Daniel|Ezra|Nehemiah|I Chronicles|II Chronicles',
}
ORDERS = {
    'Zeraim': 'Berakhot|Peah|Demai|Kilayim|Sheviit|Terumot|Maasrot|Maaser Sheni|Challah|Orlah|Bikkurim',
    'Moed': 'Shabbat|Eruvin|Pesachim|Shekalim|Yoma|Sukkah|Beitzah|Rosh Hashanah|Taanit|Megillah|Moed Katan|Chagigah',
    'Nashim': 'Yevamot|Ketubot|Nedarim|Nazir|Sotah|Gittin|Kiddushin',
    'Nezikin': 'Bava Kamma|Bava Metzia|Bava Batra|Sanhedrin|Makkot|Shevuot|Avodah Zarah|Horayot',
    'Kodashim': 'Zevachim|Menachot|Chullin|Bekhorot|Arakhin|Temurah|Keritot|Meilah|Tamid',
    'Tohorot': 'Niddah',
}

def fetch(url):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Folio-Library-Builder/0.3'}), timeout=90) as r:
                return r.read()
        except Exception:
            if attempt == 3: raise
            time.sleep(2 ** attempt)

def normalize(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c))
    return re.sub(r'[^\w\s]', ' ', text).translate(str.maketrans('ךםןףץ', 'כמנפצ')).lower()

def plain(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    return html.unescape(re.sub(r'[*_`]', '', text)).strip()

def parse_book(raw, title):
    source = raw.decode('utf-8-sig')
    header = source.split('\n## ', 1)[0]
    he_title = next((l.strip() for l in header.splitlines()[1:] if re.search('[א-ת]', l)), title)
    versions = re.findall(r'^Version \(He\): (.+)$', header, re.M)
    if len(versions) != 1: raise ValueError(f'{title}: expected one explicit Hebrew version')
    version = versions[0].strip()
    license_match = re.search(r'License: ([^)]+)', version)
    if not license_match: raise ValueError(f'{title}: Hebrew license is unspecified')
    license_name = license_match[1].strip()
    if license_name not in ('Public Domain', 'CC0', 'CC-BY', 'CC-BY-SA', 'CC-BY-NC', 'CC-BY-NC-SA', 'unknown'):
        raise ValueError(f'{title}: review license {license_name}')
    expected = int(re.search(r'Segments: (\d+)', version)[1])
    segments = []
    for match in re.finditer(r'^###### (.+)\n([\s\S]*?)(?=^###### |\Z)', source, re.M):
        full_ref, body = match.groups()
        if not full_ref.startswith(title + ' '): raise ValueError(f'{title}: unexpected reference {full_ref}')
        ref = full_ref[len(title)+1:].strip()
        # The export contract puts Hebrew first, followed by English versions.
        # Retain Hebrew paragraphs only; never bundle translations with unknown rights.
        body = re.sub(r'^\[https://torahapp\.org/[^\n]+\n', '', body, count=1, flags=re.M).strip()
        # TorahLM separates language/version blocks with THREE newlines. A
        # translated comment may begin with a Hebrew dibbur hamatchil, so its
        # first character cannot distinguish it from the Hebrew source block.
        hebrew_block = re.split(r'\n[ \t]*\n[ \t]*\n', body, maxsplit=1)[0]
        paragraphs = []
        for block in re.split(r'\n\s*\n', hebrew_block):
            text = plain(block)
            if not text: continue
            first_letter = next((c for c in text if c.isalpha()), '')
            if text not in ('—', '–') and not ('א' <= first_letter <= 'ת'): break
            paragraphs.append(text)
        if paragraphs:
            segments.append((ref, '\n\n'.join(paragraphs)))
    # Blank Hebrew cells can have English content. Record those rather than invent text.
    if len(segments) != expected:
        raise ValueError(f'{title}: Hebrew count {len(segments)} differs from declared {expected}')
    return he_title, version, license_name, segments

def main():
    args = argparse.ArgumentParser()
    args.add_argument('--cache', type=Path, required=True)
    args.add_argument('--commit', default='0b913ff6b83ed3ca4f4728c16b88662a74d2856e',help='Pinned source commit; use main explicitly to update')
    args.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'src-tauri/resources/library.sqlite')
    args = args.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    commit = json.loads(fetch('https://api.github.com/repos/TorahApp/TorahLM-download/commits/' + quote(args.commit)))['sha']
    tree = json.loads(fetch(f'https://api.github.com/repos/TorahApp/TorahLM-download/git/trees/{commit}?recursive=1'))
    if tree.get('truncated'): raise ValueError('Incomplete upstream file index')
    available = {x['path']: x for x in tree['tree'] if x['type'] == 'blob'}
    selections = []
    rank = 0
    for collection, groups in [('Tanakh', TANAKH), ('Bavli', ORDERS)]:
        for group, titles in groups.items():
            for base in titles.split('|'):
                title = ('Jerusalem Talmud ' if collection == 'Yerushalmi' else '') + base
                category = 'Tanakh' if collection == 'Tanakh' else 'Talmud'
                path = f'books/{category}/{title}.md'
                if path not in available:
                    if collection == 'Tanakh': raise ValueError('Missing ' + path)
                    continue
                rank += 1
                selections.append((title, collection, group, rank, None, path))
                rashi = f'books/{category}/Rashi on {title}.md'
                if rashi in available:
                    selections.append(('Rashi on ' + title, collection, group, rank, title, rashi))
    def download(item):
        path = item[-1]
        target = args.cache / path
        target.parent.mkdir(parents=True, exist_ok=True)
        expected_sha = available[path]['sha']
        if target.exists():
            raw = target.read_bytes()
            digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if digest == expected_sha: return item, raw
        raw = fetch(f'https://raw.githubusercontent.com/TorahApp/TorahLM-download/{commit}/' + quote(path))
        digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if digest != expected_sha: raise ValueError('Download hash mismatch: ' + path)
        target.write_bytes(raw)
        return item, raw
    print(f'Downloading {len(selections)} texts from snapshot {commit}', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        downloads = list(pool.map(download, selections))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix('.building')
    if temp.exists(): temp.unlink()
    db = sqlite3.connect(temp)
    db.executescript('''
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT UNIQUE NOT NULL,he_title TEXT NOT NULL,collection TEXT NOT NULL,category TEXT NOT NULL,sort_order INTEGER NOT NULL,base_title TEXT,version TEXT NOT NULL,license TEXT NOT NULL,source_url TEXT NOT NULL,sha256 TEXT NOT NULL,segments INTEGER NOT NULL);
      CREATE TABLE passages(id INTEGER PRIMARY KEY,book_id INTEGER NOT NULL REFERENCES books(id),section TEXT NOT NULL,ref TEXT NOT NULL,text TEXT NOT NULL,base_ref TEXT,ordinal INTEGER NOT NULL);
      CREATE INDEX passage_section ON passages(book_id,section,ordinal);
      CREATE INDEX passage_commentary ON passages(book_id,base_ref);
      CREATE VIRTUAL TABLE passage_search USING fts5(normalized,content='',tokenize='unicode61');
    ''')
    failures = []
    for item, raw in downloads:
        title, collection, category, rank, base_title, path = item
        try:
            he_title, version, license_name, segments = parse_book(raw, title)
        except ValueError as e:
            failures.append(str(e)); continue
        source_url = 'https://torahlm.org/web/book/' + quote(title)
        book_id = db.execute('INSERT INTO books VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)', (title, he_title, collection, category, rank, base_title, version, license_name, source_url, hashlib.sha256(raw).hexdigest(), len(segments))).lastrowid
        for ordinal, (ref, text) in enumerate(segments):
            section = ref.split(':')[0]
            base_ref = ref.rsplit(':', 1)[0] if base_title else None
            rowid = db.execute('INSERT INTO passages VALUES(NULL,?,?,?,?,?,?)', (book_id,section,ref,text,base_ref,ordinal)).lastrowid
            db.execute('INSERT INTO passage_search(rowid,normalized) VALUES(?,?)',(rowid, normalize(text)))
        print(f'{title}: {len(segments)} Hebrew passages ({license_name})', flush=True)
    if failures:
        db.close()
        args.cache.joinpath('import-errors.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')
        raise ValueError('\n'.join(failures))
    manifest = {'source':'TorahLM / TorahApp; upstream Sefaria', 'commit':commit,'downloaded_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'language':'Hebrew / Aramaic only; English translations excluded','notes':'Tanakh and Babylonian Talmud only. Names and commentary attributions follow the source catalog. Rashi is included where the source has a Rashi text; no replacement is labeled Rashi.'}
    for k,v in manifest.items(): db.execute('INSERT INTO metadata VALUES(?,?)',(k,v))
    db.execute("INSERT INTO passage_search(passage_search) VALUES('optimize')")
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    db.execute('VACUUM')
    counts = dict(db.execute('SELECT collection,count(*) FROM books GROUP BY collection'))
    print('Finished:', counts, db.execute('SELECT count(*) FROM passages').fetchone()[0], 'passages', flush=True)
    columns=[d[0] for d in db.execute('SELECT * FROM books').description]
    books=[dict(zip(columns,r)) for r in db.execute('SELECT * FROM books ORDER BY sort_order,base_title IS NOT NULL,id')]
    report=Path(__file__).resolve().parents[1]/'docs/library-manifest.json'
    report.write_text(json.dumps({'metadata':manifest,'books':books},ensure_ascii=False,indent=2),encoding='utf-8')
    db.close()
    temp.replace(args.output)

if __name__ == '__main__': main()
