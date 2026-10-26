"""Validate an exported ODT against the official OASIS ODF 1.3 schemas.

Usage: python scripts/validate_odt.py examples/example.odt --schemas PATH
Requires lxml. Obtain schemas from:
https://docs.oasis-open.org/office/OpenDocument/v1.3/os/schemas/
"""
import argparse
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
from lxml import etree

parser = argparse.ArgumentParser()
parser.add_argument('document')
parser.add_argument('--schemas', required=True, type=Path)
args = parser.parse_args()
schema = etree.RelaxNG(etree.parse(str(args.schemas / 'odf.rng')))
manifest = etree.RelaxNG(etree.parse(str(args.schemas / 'manifest.rng')))
failed = False
with ZipFile(args.document) as package:
    assert package.infolist()[0].filename == 'mimetype'
    assert package.infolist()[0].compress_type == ZIP_STORED
    assert package.read('mimetype') == b'application/vnd.oasis.opendocument.text'
    for name in ['content.xml', 'styles.xml', 'meta.xml', 'META-INF/manifest.xml']:
        validator = manifest if name.startswith('META-INF') else schema
        valid = validator.validate(etree.fromstring(package.read(name)))
        print(f'{name}: {"valid" if valid else "INVALID"}')
        if not valid:
            print(validator.error_log)
            failed = True
sys.exit(1 if failed else 0)
