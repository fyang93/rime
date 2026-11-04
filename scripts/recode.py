"""切分或校验合并拼好字逐字重建批次；不生成或推断拆码。"""

import argparse
import csv
import io
from pathlib import Path

from jd6 import ROOT, dictionary_characters, load_table

DATA = ROOT / 'scripts/dicts'


def original_codes(data):
    return dict(line.split('\t', 1) for line in
                (data / 'chaizi_jd6.txt').read_text(encoding='utf-8').splitlines() if line)


def prepare(data=DATA):
    chars = sorted(dictionary_characters())
    original = original_codes(data)
    folder = data / 'recode/batches'
    folder.mkdir(parents=True, exist_ok=True)
    (data / 'recode/out').mkdir(exist_ok=True)
    for start in range(0, len(chars), 200):
        batch = folder / f'batch-{start // 200 + 1:03d}.tsv'
        text = ''.join(f'{char}\t{original.get(char, "无")}\n' for char in chars[start:start + 200])
        batch.write_text(text, encoding='utf-8')
    return len(chars)


def merge(data=DATA):
    target = dictionary_characters()
    batches = sorted((data / 'recode/batches').glob('batch-*.tsv'))
    if len(batches) != (len(target) + 199) // 200:
        raise ValueError('批次数量与目标字集不符')
    rows = {}
    for batch in batches:
        expected = [line.split('\t')[0] for line in batch.read_text(encoding='utf-8').splitlines()]
        result = load_table(data / 'recode/out' / batch.name)
        if list(result) != expected:
            raise ValueError(f'{batch.name}: 输出字集或排序不符')
        if rows.keys() & result.keys():
            raise ValueError(f'{batch.name}: 批次之间有重复字')
        for char, (shape, status, note) in result.items():
            if not shape or status != '已核对':
                raise ValueError(f'{batch.name}: {char} 必须有非空形码且状态已核对')
        rows.update(result)
    if rows.keys() != target:
        raise ValueError(f'覆盖率不完整：缺 {len(target - rows.keys())}，多 {len(rows.keys() - target)}')
    rows = dict(sorted(rows.items()))
    original = original_codes(data)
    changed = sum(shape != original.get(char) for char, (shape, _, _) in rows.items())
    text = io.StringIO(newline='')
    csv.writer(text, delimiter='\t', lineterminator='\n').writerows(
        (char, *row) for char, row in rows.items())
    (data / 'chaizi_phz.txt').write_text(text.getvalue(), encoding='utf-8')
    return {'处理字数': len(rows), '与原版不同': changed,
            '原版缺字': len(target - original.keys()),
            '存疑字数': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'merge'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else merge())
