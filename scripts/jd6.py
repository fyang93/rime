"""校验拼好字形码总表并重建索引；不自动猜测拆字。"""

import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / 'scripts/dicts/chaizi_phz.txt'
TARGETS = ROOT / 'scripts/dicts/phz_targets.txt'
INDEX = ROOT / 'scripts/dicts/jd6_index.md'
ROOT_KEYS = {
    '一': 'a', '草': 'c', '丶': 'd', '手': 'f', '火': 'h',
    '金': 'j', '口': 'k', '丨': 'l', '木': 'm',
    '日': 'o', '丿': 'p', '人': 'r', '土': 't', '士': 't',
    '水': 'u', '十': 'x', '乛': 'v', '月': 'y',
}
ROOT_GROUPS = ('一', '丨', '丿', '丶', '乛', '日', '月', '金', '木',
               '水', '火', '土士', '人', '手', '口', '十', '草')
STATUSES = {'沿用', '已核对', '待补'}


def dictionary_characters(names=None):
    if names is None:
        chars = [line.strip() for line in TARGETS.read_text(encoding='utf-8').splitlines()
                 if line.strip() and not line.startswith('#')]
        if any(len(char) != 1 for char in chars) or len(set(chars)) != len(chars):
            raise ValueError('补码目标须每行一字且不能重复')
        return set(chars)
    chars = set()
    for name in names:
        for line in (TABLE.parent / f'{name}.dict.yaml').read_text().splitlines():
            if re.fullmatch(r'.\t[a-z]+(?:\t\d+)?', line):
                chars.add(line.split('\t')[0])
    return chars


def load_table(path=TABLE):
    if len(ROOT_GROUPS) != 17 or set(''.join(ROOT_GROUPS)) != ROOT_KEYS.keys():
        raise ValueError('17组字根白名单与映射不一致')
    rows = {}
    with path.open(encoding='utf-8', newline='') as file:
        for number, fields in enumerate(csv.reader(file, delimiter='\t'), 1):
            if not fields or fields[0].startswith('#'):
                continue
            if len(fields) != 4:
                raise ValueError(f'{path}:{number}: 应为字、拆码、状态、依据四列')
            if any(c in field for field in fields for c in '\t\r\n'):
                raise ValueError(f'{path}:{number}: 字段内不能包含制表符或换行')
            char, shape, status, note = fields
            if len(char) != 1 or char in rows:
                raise ValueError(f'{path}:{number}: 字无效或重复：{char!r}')
            if status not in STATUSES or (status == '待补') != (shape == ''):
                raise ValueError(f'{path}:{number}: 状态与拆码不一致')
            if set(shape) - ROOT_KEYS.keys() or len(shape) > 4:
                raise ValueError(f'{path}:{number}: 非法字根或形码超过四位')
            if not note.strip():
                raise ValueError(f'{path}:{number}: 缺少来源或核对依据')
            if '【存疑】' in note:
                raise ValueError(f'{path}:{number}: 未决问题须先问用户，不能以存疑候选入表')
            rows[char] = (shape, status, note)
    return rows


def build_index(rows):
    counts = Counter(status for _, status, _ in rows.values())
    target = dictionary_characters()
    pending = sorted(char for char in target if char not in rows or not rows[char][0])
    lines = ['# 拼好字形码索引（JD6 衍生）', '',
             '自动生成：`uv run python scripts/jd6.py`。只编辑 `chaizi_phz.txt`。', '',
             f'共 {len(rows)} 字：' + '，'.join(f'{s} {counts[s]}' for s in ('已核对', '沿用', '待补')) + '。', '',
             '**规则不清或冲突须先问用户，未决候选不入表。形码齐备和维护表“已核对”状态不代表逐字审计全部定案。**', '',
             f'phz_targets.txt 补码目标共 {len(target)} 个不同字：已有形码 {len(target) - len(pending)}，待补 {len(pending)}。', '',
             '目标集以外的字不补形码，保留纯音输入。', '',
             f'当前采用 {len(ROOT_GROUPS)} 个字根组，日支持 o/e、丿支持 p/s 别名；合体字两部各最多两码，按天然笔顺输出，两部取完即结束，不满四码不补；穿插字、独体字按整字书写顺序取前四单位。', '',
             '非根部按前两个单位顺取，紧接且不与周围笔画相连的独立完整字根可整取；白中日形不独立，仍取笔画。人下一横归下部，不以亼作上盖：合、命、龠均为人／其余→人一口。', '',
             '最新裁定同步见 [裁定记录](jd6_audit/rulings-sync.md)；历史审核范围与验证见 [前轮报告](recode/REPORT.md)，规则问答见 [问题清单](recode/QUESTIONS.md) 和 [用户答复](recode/ANSWERS.md)。', '']
    for group in ROOT_GROUPS:
        keys = {'日': 'o/e', '丿': 'p/s'}.get(group, ROOT_KEYS[group[0]])
        matches = [(char, shape, status) for char, (shape, status, _) in rows.items()
                   if set(group) & set(shape)]
        lines.extend([f'## {group} · {keys} · {len(matches)} 字', '', '```text', '字\t拆码\t状态'])
        lines.extend('\t'.join(row) for row in matches)
        lines.extend(['```', ''])
    lines.extend(['## 目标字待补清单', '', '按Unicode码位排列，仅列 phz_targets.txt 中的字。', '', '```text'])
    lines.extend(' '.join(pending[i:i + 32]) for i in range(0, len(pending), 32))
    lines.extend(['```', ''])
    return '\n'.join(lines)


if __name__ == '__main__':
    rows = load_table()
    target = dictionary_characters()
    if rows.keys() != target:
        raise ValueError(f'总表与目标集不一致：缺 {len(target - rows.keys())} 字，多 {len(rows.keys() - target)} 字')
    if any(not shape or status != '已核对' for shape, status, _ in rows.values()):
        raise ValueError('本轮目标字必须全部有形码且状态为已核对')
    if list(rows) != sorted(rows):
        raise ValueError('总表须按Unicode码位排序')
    INDEX.write_text(build_index(rows), encoding='utf-8')
    print(f'拼好字：{len(target)} 个目标字，全部已有形码；形码齐备不代表逐字审计全部定案。')
