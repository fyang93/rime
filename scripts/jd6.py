"""校验拼好字形码总表并重建索引；不自动猜测拆字。"""

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'scripts/dicts/chaizi_jd6_v2.txt'
INDEX = ROOT / 'scripts/dicts/jd6_index.md'
ROOT_KEYS = {
    '一': 'a', '贝': 'b', '草': 'c', '丶': 'd', '手': 'f', '火': 'h',
    '犭': 'q', '豸': 'q', '金': 'j', '口': 'k', '丨': 'l', '木': 'm',
    '女': 'n', '日': 'o', '丿': 'p', '⺮': 'z', '虫': 'i', '人': 'r', '山': 's', '王': 'w', '工': 'g', '土': 't', '士': 't',
    '水': 'u', '十': 'x', '乛': 'v', '月': 'y',
}
ROOT_GROUPS = ('一', '贝', '草', '丶', '手', '火', '金', '口', '丨', '木',
               '女', '日', '丿', '⺮', '虫', '犭豸', '人', '山', '王', '工', '土士', '水', '十', '乛', '月')
STATUSES = {'沿用', '已核对', '待补'}


def dictionary_characters(names=('8105', '41448')):
    chars = set()
    for name in names:
        for line in (TABLE.parent / f'{name}.dict.yaml').read_text().splitlines():
            if re.fullmatch(r'.\t[a-z]+(?:\t\d+)?', line):
                chars.add(line.split('\t')[0])
    return chars


def load_table(path=TABLE):
    if len(ROOT_GROUPS) > 26 or set(''.join(ROOT_GROUPS)) != ROOT_KEYS.keys():
        raise ValueError('26键字根白名单与映射不一致')
    rows = {}
    with path.open(encoding='utf-8', newline='') as file:
        for number, fields in enumerate(csv.reader(file, delimiter='\t'), 1):
            if not fields or fields[0].startswith('#'):
                continue
            if len(fields) != 4:
                raise ValueError(f'{path}:{number}: 应为字、拆码、状态、依据四列')
            char, shape, status, note = fields
            if len(char) != 1 or char in rows:
                raise ValueError(f'{path}:{number}: 字无效或重复：{char!r}')
            if status not in STATUSES or (status == '待补') != (shape == ''):
                raise ValueError(f'{path}:{number}: 状态与拆码不一致')
            if set(shape) - ROOT_KEYS.keys() or len(shape) > 4:
                raise ValueError(f'{path}:{number}: 非法字根或形码超过四位')
            if not note.strip():
                raise ValueError(f'{path}:{number}: 缺少来源或核对依据')
            rows[char] = (shape, status, note)
    return rows


def build_index(rows):
    counts = Counter(status for _, status, _ in rows.values())
    target = dictionary_characters(('8105',))
    pending = sorted(char for char in target if not rows[char][0])
    lines = ['# 拼好字形码索引（JD6 衍生）', '',
             '自动生成：`uv run python scripts/jd6.py`。只编辑 `chaizi_jd6_v2.txt`。', '',
             f'共 {len(rows)} 字：' + '，'.join(f'{s} {counts[s]}' for s in ('已核对', '沿用', '待补')) + '。', '',
             '**沿用不等于已核对；待补项没有猜测码。**', '',
             f'8105补码目标共 {len(target)} 个不同字：已有形码 {len(target) - len(pending)}，待补 {len(pending)}（含原表未知和缺失项）。', '',
             '41448独有字保留参考记录，不属于本轮补码目标。', '',
             f'当前采用 {len(ROOT_GROUPS)} 个字根组，日支持 o/e 别名；合体字两部各最多两码，按所选单位起笔的实际先后输出，整字最多四码，讠、纟不另设根。', '',
             '审核范围、最终口径及覆盖限制见 [本轮审核摘要](jd6_audit.md)。', '']
    for group in ROOT_GROUPS:
        keys = 'o/e' if group == '日' else ROOT_KEYS[group[0]]
        matches = [(char, shape, status) for char, (shape, status, _) in rows.items()
                   if set(group) & set(shape)]
        lines.extend([f'## {group} · {keys} · {len(matches)} 字', '', '```text', '字\t拆码\t状态'])
        lines.extend('\t'.join(row) for row in matches)
        lines.extend(['```', ''])
    lines.extend(['## 8105待补清单', '', '按Unicode码位排列，包含原表未知和空白；不列41448独有字。', '', '```text'])
    lines.extend(' '.join(pending[i:i + 32]) for i in range(0, len(pending), 32))
    lines.extend(['```', ''])
    return '\n'.join(lines)


if __name__ == '__main__':
    rows = load_table()
    missing = dictionary_characters() - rows.keys()
    if missing:
        raise ValueError(f'总表遗漏 {len(missing)} 字：' + ''.join(sorted(missing)[:20]))
    INDEX.write_text(build_index(rows), encoding='utf-8')
    target = dictionary_characters(('8105',))
    print(f'8105：{len(target)} 个不同字，' +
          f'已有形码 {sum(bool(rows[char][0]) for char in target)}，' +
          f'待补 {sum(not rows[char][0] for char in target)}（含原未知）。')
