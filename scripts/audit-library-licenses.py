"""Read-only inventory of bundled text rights; never grants redistribution rights."""
import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=root / 'docs/signpath/license-audit')
args = parser.parse_args()
database = root / 'src-tauri/resources/library.sqlite'
with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
    connection.row_factory = sqlite3.Row
    books = [dict(row) for row in connection.execute(
        'SELECT title, he_title, collection, version, license, source_url, sha256, segments '
        'FROM books ORDER BY sort_order, id')]
    metadata = dict(connection.execute('SELECT key,value FROM metadata'))

counts = Counter()
passages = Counter()
for book in books:
    label = book['license'].strip() or 'unknown'
    counts[label] += 1
    passages[label] += book['segments']
    if label.lower() in ('unknown', 'unspecified'):
        book['review'] = 'Redistribution permission unspecified; obtain evidence.'
    elif 'NC' in label.upper():
        book['review'] = 'Noncommercial restriction; disclose to SignPath and resolve eligibility/redistribution.'
    elif label == 'Public Domain':
        book['review'] = 'Upstream public-domain label; verify edition and jurisdiction.'
    else:
        book['review'] = 'Verify exact license version, attribution and other obligations.'

args.output.mkdir(parents=True, exist_ok=True)
with (args.output / 'books.csv').open('w', encoding='utf-8-sig', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=list(books[0]))
    writer.writeheader()
    writer.writerows(books)
report = {
    'status': 'review-required',
    'database_sha256': hashlib.file_digest(database.open('rb'), 'sha256').hexdigest(),
    'source_metadata': metadata,
    'books': len(books),
    'passages': sum(passages.values()),
    'licenses': {label: {'books': counts[label], 'passages': passages[label]} for label in sorted(counts)},
    'unknown_titles': [book['title'] for book in books if book['license'].lower() in ('unknown', 'unspecified', '')],
    'notice': 'Inventory only. No permission is inferred and no source database or text is modified.',
}
(args.output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: report[key] for key in ('status', 'books', 'passages', 'licenses')}, ensure_ascii=False, indent=2))
