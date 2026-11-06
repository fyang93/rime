"""Self-check the append-only audit, source fields, and archived evidence (no network)."""
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

B = Path(__file__).resolve().parent
ROOT = B.parents[3]
E = B / 'evidence'
D = E / 'recovery-03'


def rows(path):
    with path.open() as f:
        return list(csv.reader(f, delimiter='\t'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


state = json.loads((D / 'state-check.json').read_text())
audit = B.with_suffix('.tsv')
data = audit.read_bytes()
assert hashlib.sha256(data[:state['baseline_byte_length']]).hexdigest() == state['baseline_audit_sha256']
assert hashlib.sha256(data[:648036]).hexdigest() == '13a85bab111d2be3aeb7edb1be367a8a67216f0482d69d99e7eb19d1af9ccf95'
history = rows(audit)
assert len(history) == 2659 and all(len(r) == 6 for r in history)
source = rows(ROOT / 'scripts/dicts/chaizi_phz.txt')[3300:4125]
latest = {}
for row in history[1:]:
    latest[row[0]] = row
view = [latest[row[0]] for row in source]
assert rows(B / 'latest-state.tsv') == [history[0]] + view
assert len(view) == len({r[0] for r in view}) == 825
assert all(a[1] == s[1] for a, s in zip(view, source))
assert dict(Counter(r[3] for r in view)) == state['counts']
assert state['counts'] == {'一致（本轮逐字核验）': 822, '字形/笔顺已核，分部待用户裁决': 2, '需复核候选（犀，未改表）': 1}
for path, digest in rows(E / 'inputs-sha256.tsv')[1:]:
    assert sha(ROOT / path) == digest, path
independent = rows(D / 'independent.tsv')
assert len(independent) == 183 and len({r[0] for r in independent[1:]}) == 182
comparison = rows(D / 'comparison.tsv')
assert len(comparison) == 182 and len({r[0] for r in comparison[1:]}) == 181
assert {r[0] for r in independent[1:]} - {r[0] for r in comparison[1:]} == {'燊'}
for c, _, code, current, _ in comparison[1:]:
    assert code.replace('士', '土') == current.replace('士', '土') == latest[c][1].replace('士', '土')
with (D / 'inspection/index.tsv').open() as f:
    index = list(csv.DictReader(f, delimiter='\t'))
assert len(index) == 182 and len({r['本轮图页'] for r in index}) == 16
log = rows(E / 'inspection-log.tsv')
paths_in_log = {r[0] for r in log[1:] if r[1].startswith('补查03实际read')}
for r in index:
    c = r['字符']
    text = (D / r['HTML']).read_text()
    assert int(re.search(r'CJK\s+([0-9A-F]{4,6})', text)[1], 16) == ord(c)
    seq = re.search(r'>笔顺</span>\s*<span[^>]*>([1-5]+)</span>', text)[1]
    assert seq == r['数字笔顺']
    assert int(re.search(r'>总笔画</span>\s*<span[^>]*>(\d+)</span>', text)[1]) == len(seq)
    glyph = ET.fromstring((D / r['字形SVG']).read_text())
    sheet = ET.parse((D / r['本轮图页']).with_suffix('.svg')).getroot()
    cell = sheet.findall('{http://www.w3.org/2000/svg}svg')[int(r['行格']) - 1]
    ns = '{http://www.w3.org/2000/svg}'
    assert [p.attrib['d'] for p in glyph.iter(ns + 'path')] == [p.attrib['d'] for p in cell.iter(ns + 'path')]
    assert seq in ''.join(sheet.itertext())
    assert 'recovery-03/' + r['本轮图页'] in paths_in_log
    assert c == source[int(r['源表行']) - 3301][0]
with (D / 'character-evidence-03.tsv').open() as f:
    evidence = list(csv.DictReader(f, delimiter='\t'))
assert len(evidence) == 182
for r in evidence:
    for path_column, hash_column in [('HTML', 'HTML_SHA256'), ('字形SVG', 'SVG_SHA256'), ('实际已读配对图', '配对图SHA256')]:
        assert sha(D / r[path_column]) == r[hash_column]
for folder, count in [(E / 'json', 643), (D / 'json', 30)]:
    files = list(folder.glob('*.json'))
    assert len(files) == count
    for path in files:
        j = json.loads(path.read_text())
        assert len(j['strokes']) == len(j['medians']) > 0
assert len(rows(B / 'remaining-material-gaps.tsv')) == 153
for name in ['unmapped.tsv', 'missing-strokes.tsv', 'remaining-source-failures.tsv']:
    assert len(rows(B / name)) == 1
assert {r[0] for r in rows(B / 'pending-structure.tsv')[1:]} == {'牚', '燊'}
assert {r[0] for r in rows(B / 'remaining-open.tsv')[1:]} == {'牚', '燊', '犀'}
manifest = rows(E / 'sources-sha256.tsv')
listed = set()
for relative, _, size, digest in manifest[1:]:
    path = E / relative
    assert relative not in listed and path.stat().st_size == int(size) and sha(path) == digest, relative
    listed.add(relative)
actual = {str(p.relative_to(E)) for p in E.rglob('*') if p.is_file() and p != E / 'sources-sha256.tsv'}
assert listed == actual
print(json.dumps({'result': 'PASS', 'unique_characters': 825, 'history_rows': len(history) - 1, 'new_inspected': 182, 'new_decided_compared': 181, 'current_counts': state['counts'], 'archived_files_checked': len(listed)}, ensure_ascii=False, indent=2))
