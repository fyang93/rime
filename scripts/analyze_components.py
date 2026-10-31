"""分析人工组件树初稿；仅导出实验表和报告，不生成拆法或修改输入方案。"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from jd6 import ROOT, dictionary_characters

DATA = ROOT / 'scripts/dicts'
TABLE = DATA / 'component_tree_8105.tsv'
STROKE_KEYS = dict(zip(('横', '竖', '撇', '点', '折'), 'alpdv'))
# 仅这些替代形按用户熟悉的汉字取音；其他部首字形不靠部件名称取音。
ALIASES = dict(zip('犭亻扌氵氺艹艸钅釒', '犬人手水水草草金金'))
ALIAS_PHONES = {'犬': 'quan', '人': 'ren', '手': 'shou', '水': 'shui',
                '草': 'cao', '金': 'jin'}
# 人工确定的部首笔画兜底；只处理未展开的叶子，已有子树的不重复加笔。
STROKE_FALLBACK = {
    '宀': '点 点 折', '冖': '点 折', '勹': '撇 折', '匚': '横 折',
    '囗': '竖 折 横', '亠': '点 横', '彳': '撇 撇 竖', '廴': '折 点',
    '辶': '点 折 点', '阝': '折 竖', '衤': '点 折 竖 撇 点',
    '礻': '点 折 竖 点', '饣': '撇 折 折', '忄': '点 点 竖',
    '㣺': '竖 点 点 点', '灬': '点 点 点 点', '⺌': '竖 点 撇',
    '⺈': '撇 折', '⺊': '竖 横', '⺮': '撇 横 点 撇 横 点',
    '爫': '撇 点 点 撇', '纟': '折 折 横', '糹': '折 折 点 点 点 点',
    '龵': '撇 横 横 撇', '夂': '撇 折 点', '攵': '撇 横 撇 点',
    '讠': '点 折', '訁': '点 折', '冂': '竖 折', '厶': '折 点', '彡': '撇 撇 撇', '彐': '折 横 横',
    '罒': '竖 折 竖 竖 横', '冫': '点 横', '虍': '竖 横 折 撇 横 折',
    '廾': '横 撇 竖', '凵': '折 竖', '卩': '折 竖', '㔾': '折 折',
    '耂': '横 竖 横 撇', '覀': '横 竖 折 竖 竖 横',
    '疒': '点 横 撇 点 横', '丬': '点 横 竖', '屮': '折 竖 竖',
    '癶': '折 点 撇 撇 点', '巛': '折 折 折',
    '糸': '折 折 点 竖 撇 点', '彑': '折 折 横', '刂': '竖 竖',
    '丷': '点 撇', '䒑': '点 撇 横', '丌': '横 撇 竖',
    '丂': '横 折', '尢': '横 撇 折', '㐅': '撇 点',
    '冃': '竖 折 横 横', '肀': '折 横 横 竖', '爿': '折 竖 横 撇',
}
READABLE_CHARACTERS = dictionary_characters()


def readable_component(name):
    if name in ALIASES:
        return True
    return name not in STROKE_FALLBACK and name in READABLE_CHARACTERS


def parse_tree(text):
    tokens = re.findall(r'[^\[\],]+|[\[\],]', text)
    pos = 0

    def node():
        nonlocal pos
        if pos == len(tokens) or tokens[pos] in '[],':
            raise ValueError('树节点缺名称')
        label = tokens[pos]
        pos += 1
        children = []
        if pos < len(tokens) and tokens[pos] == '[':
            pos += 1
            children.append(node())
            while pos < len(tokens) and tokens[pos] == ',':
                pos += 1
                children.append(node())
            if pos == len(tokens) or tokens[pos] != ']':
                raise ValueError('树括号未配对')
            pos += 1
        return label, tuple(children)

    result = node()
    if pos != len(tokens):
        raise ValueError('树有多余内容')
    return result


def flatten(tree):
    yield tree
    for child in tree[1]:
        yield from flatten(child)


def initial(phone):
    if not re.fullmatch('[a-z]+', phone):
        raise ValueError(f'无效组件拼音：{phone}')
    return {'zh': 'v', 'ch': 'i', 'sh': 'u'}.get(phone[:2], phone[0])


def components(row, leaf_only):
    phones = {ALIASES.get(name, name): phone
              for item in row[3].split() if item != '-'
              for name, phone in [item.split(':')]}
    selected = []
    # 依据树中的原形判断，不能把衤误当作已被初稿命名的完整“衣”。
    for label, children in list(flatten(parse_tree(row[2])))[1:]:
        if label in STROKE_KEYS or (leaf_only and children) or not readable_component(label):
            continue
        name = ALIASES.get(label, label)
        if label in ALIASES:
            selected.append((name, ALIAS_PHONES[name]))
        elif name in phones:
            selected.append((name, phones[name]))
    return selected


def residual_strokes(row):
    strokes = [s for s in row[4].split() if s != '-']
    for label, children in list(flatten(parse_tree(row[2])))[1:]:
        if not children and label in STROKE_FALLBACK:
            strokes.extend(STROKE_FALLBACK[label].split())
    return strokes


def feature_sequence(row, leaf_only=True):
    phones = {ALIASES.get(name, name): phone
              for item in row[3].split() if item != '-'
              for name, phone in [item.split(':')]}
    sequence = []

    def visit(node, root=False):
        label, children = node
        if root:
            for child in children:
                visit(child)
            return
        if label in STROKE_KEYS and not children:
            sequence.append(STROKE_KEYS[label])
            return
        if not children:
            if readable_component(label):
                name = ALIASES.get(label, label)
                if label in ALIASES:
                    sequence.append(initial(ALIAS_PHONES[name]))
                elif name in phones:
                    sequence.append(initial(phones[name]))
            else:
                sequence.extend(STROKE_KEYS[s] for s in STROKE_FALLBACK.get(label, '').split())
            return
        if not leaf_only and readable_component(label):
            name = ALIASES.get(label, label)
            if label in ALIASES:
                sequence.append(initial(ALIAS_PHONES[name]))
            elif name in phones:
                sequence.append(initial(phones[name]))
        for child in children:
            visit(child)

    visit(parse_tree(row[2]), root=True)
    return sequence


def ordered_matches(query, candidate):
    """True when query is an order-preserving, possibly gapped subsequence."""
    pos = iter(candidate)
    return all(any(value == key for value in pos) for key in query)


def feature_keys(row, leaf_only=False):
    return Counter(feature_sequence(row, leaf_only))


def signature(bag):
    return ''.join(sorted(bag.elements()))


def bucket_results(chars, bags):
    """包含匹配，保留重复数；另找最多3键的最短唯一条件。"""
    masks = defaultdict(int)
    for i, char in enumerate(chars):
        for key, count in bags[char].items():
            for n in range(1, count + 1):
                masks[key, n] |= 1 << i
    all_bits = (1 << len(chars)) - 1
    results = []
    for i, char in enumerate(chars):
        bag = bags[char]
        full_mask = all_bits
        for key, count in bag.items():
            full_mask &= masks[key, count]
        matches = [c for j, c in enumerate(chars) if full_mask & (1 << j)]
        if len(chars) == 1:
            minimum, query = '0', ''
        elif len(matches) > 1:
            minimum, query = '全部条件仍不唯一', ''
        else:
            minimum, query = '4+', ''
            available = signature(bag)
            for n in range(1, min(3, len(available)) + 1):
                for trial in sorted(set(combinations(available, n))):
                    mask = all_bits
                    for key, count in Counter(trial).items():
                        mask &= masks[key, count]
                    if mask == 1 << i:
                        minimum, query = str(n), ''.join(trial)
                        break
                if query:
                    break
        results.append((char, signature(bag), len(matches), ''.join(matches), minimum, query))
    return results


def summarize(rows, groupings, leaf_only):
    bags = {c: feature_keys(row, leaf_only) for c, row in rows.items()}
    raw = defaultdict(list)
    for c, bag in bags.items():
        raw[signature(bag)].append(c)
    output = {
        '字数': len(rows),
        '纯形完整特征相同组数': sum(len(v) > 1 for v in raw.values()),
        '纯形完整特征相同涉及字数': sum(len(v) for v in raw.values() if len(v) > 1),
    }
    for name, groups in groupings.items():
        all_results = []
        ordered_results = []
        profiles = defaultdict(list)
        ordered_profiles = defaultdict(list)
        baseline = 0
        for phone, chars in sorted(groups.items()):
            chars = sorted(set(chars) & rows.keys())
            baseline += len(chars) ** 2
            all_results.extend((phone, *r) for r in bucket_results(chars, bags))
            sequences = {c: feature_sequence(rows[c], leaf_only) for c in chars}
            for c in chars:
                seq = sequences[c]
                matches = ''.join(other for other in chars if ordered_matches(seq, sequences[other]))
                ordered_results.append((phone, c, ''.join(seq), len(matches), matches))
                profiles[phone, signature(bags[c])].append(c)
                ordered_profiles[phone, ''.join(seq)].append(c)
        units = len(all_results)
        output[name] = {
            '字音对数': units,
            '筛选前平均同音候选数': round(baseline / units, 4),
            '同音完整特征相同组数': sum(len(v) > 1 for v in profiles.values()),
            '同音完整特征相同涉及字音对': sum(len(v) for v in profiles.values() if len(v) > 1),
            '全部条件仍匹配多个候选的字音对': sum(r[3] > 1 for r in all_results),
            '全部条件筛选后平均候选数': round(sum(r[3] for r in all_results) / units, 4),
            '最短唯一条件键数分布': dict(Counter(r[5] for r in all_results)),
            '允许跳过且顺序必须一致': {
                '顺序完整码相同组数': sum(len(v) > 1 for v in ordered_profiles.values()),
                '顺序完整码相同字音对': sum(len(v) for v in ordered_profiles.values() if len(v) > 1),
                '输入自身全部顺序线索后仍多候选': sum(r[3] > 1 for r in ordered_results),
                '全部顺序线索筛选后平均候选数': round(sum(r[3] for r in ordered_results) / units, 4),
            },
        }
        if leaf_only and name == '全拼':
            with (DATA / 'components_8105_collisions.tsv').open('w', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter='\t', lineterminator='\n')
                writer.writerow(('音', '字', '全部无序键', '包含匹配候选数', '候选字', '最短唯一键数', '查询例'))
                writer.writerows(r for r in all_results if r[3] > 1)
            with (DATA / 'components_8105_ordered_collisions.tsv').open('w', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter='\t', lineterminator='\n')
                writer.writerow(('音', '字', '顺序键', '匹配数', '匹配字'))
                writer.writerows(r for r in ordered_results if r[3] > 1)
    return output


def analyze():
    with TABLE.open(encoding='utf-8', newline='') as f:
        records = list(csv.reader(f, delimiter='\t'))
    if not records or any(len(r) != 7 for r in records):
        raise ValueError('人工树表应为7列')
    rows = {r[0]: r for r in records[1:]}
    if len(rows) != len(records) - 1 or set(rows) != dictionary_characters(('8105',)):
        raise ValueError('人工树表与8105字集合不符或存在重复')
    for c, row in rows.items():
        if parse_tree(row[2])[0] != c or row[5] not in {'候选', '待核'}:
            raise ValueError(f'{c}: 树根或状态错误')
    candidates = {c: r for c, r in rows.items() if r[5] == '候选'}
    with (DATA / 'components_8105.tsv').open('w', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(('字', '字音', '小组件及读音', '残余笔画', '顺序键', '无序键', '状态', '组件树', '说明'))
        for c, row in rows.items():
            small = ' '.join(f'{n}:{p}' for n, p in components(row, True)) or '-'
            strokes = ' '.join(residual_strokes(row)) or '-'
            writer.writerow((c, row[1], small, strokes, ''.join(feature_sequence(row, True)), signature(feature_keys(row, True)), row[5], row[2], row[6]))
    pinyin = defaultdict(list)
    for c, row in candidates.items():
        for phone in row[1].split('/'):
            pinyin[phone].append(c)
    double = defaultdict(set)
    for line in (ROOT / 'zrm.dict.yaml').read_text().splitlines():
        fields = line.split('\t')
        if len(fields) >= 2 and len(fields[0]) == 1 and ';' in fields[1]:
            double[fields[1].split(';')[0]].add(fields[0])
    if set().union(*double.values()) & rows.keys() != rows.keys():
        raise ValueError('现有zrm字典未覆盖全部实验目标，不能统计双拼')
    result = {'范围': len(rows), '候选': len(candidates),
              '待核': ''.join(c for c, r in rows.items() if r[5] == '待核'),
              '声明': '人工初稿，未经全量主审；仅统计候选子集。跨字拆分深度和部分部件命名尚未统一，排除待核字也会使结果偏乐观。'}
    for mode, leaf_only in [('全树节点', False), ('仅已登记叶节点', True)]:
        result[mode] = summarize(candidates, {'全拼': pinyin, '双拼': double}, leaf_only)
    (DATA / 'components_8105_statistics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    stats = result['仅已登记叶节点']['全拼']
    units = stats['字音对数']
    same = stats['同音完整特征相同涉及字音对']
    ambiguous = stats['全部条件仍匹配多个候选的字音对']
    distribution = stats['最短唯一条件键数分布']
    lines = [
        '# 无序小组件筛选：人工初稿评估', '',
        f'覆盖 **{len(rows)} 字**：人工候选 {len(candidates)} 字、待核 {len(rows) - len(candidates)} 字。', '',
        '**不是全量验收结果或最终重码率。** 20批人工判断已汇总，主审只做了关键例、格式、一致性问题和部分笔画/读音修订；未逐字外部核验。',
        '同一组件在不同字中的展开深度尚未统一；仅叶节点表示各字当前树的叶子，不代表全库统一的最小组件。待核字排除也会使结果偏乐观。', '',
        '## 文件和复现', '',
        '- `component_tree_8105.tsv`：人工树初稿及原始可读节点；这是实验的维护源，不是现有简根表。',
        '- `components_8105.tsv`：导出的小组件、残余笔画、无序键；大组件留在参考树中，不计入小组件键。待核行可能只有部分线索。',
        '- `components_8105_collisions.tsv`：小组件无序包含匹配仍不唯一的逐字全拼明细。',
        '- `components_8105_ordered_collisions.tsv`：顺序可跳过仍不唯一的逐字全拼明细。',
        '- `components_8105_statistics.json`：完整指标，含全树节点和双拼对照。',
        '- 仓库根目录运行 `uv run python scripts/analyze_components.py`；自检加 `--self-test`。只写上述实验导出文件和本报告，不修改输入法字典或配置。', '',
        '## 统计口径', '',
        '无序但保留次数；输入条件按包含匹配。组件用拼音声母，zh/ch/sh用自然码v/i/u；零声母暂用拼音首字母。笔画横/竖/撇/点/折用a/l/p/d/v，竖钩归竖、竖提归折。不同组件同键时合并计数，因此按键重码不等于字形组件相同。',
        '根字不作自己的搜索组件；成字中间节点仅在全树对照口径中使用。',
        '保留熟悉别名：扌→手、氵/氺→水、艹→草（固定cao）、钅/釒→金；讠/訁用点折笔画，不映射言；犭→犬、亻→人沿用猹和以等例子的约定。',
        '宀、冖、勹、匚、彳等部首名不取音；按人工部首笔画表补充未展开叶节点，已展开的子树不重复补笔。按树的原形识别，衤不会因初稿标为衣而偷带yi。',
        '其余可读字仍沿人工候选读音；陌生部件清理名单不是全库可识读性的逐字验收。',
        '按全拼统计时，一个字每个读音算一个“字音对”；双拼按现有zrm单字音码合并。没有词语、频率加权、运行时截断或实机候选排序。', '',
        '## 小组件结果（候选子集，全拼）', '',
        '| 指标 | 结果 |', '|---|---:|',
        f'| 字音对 | {units} |',
        f'| 无序特征相同（不算最终重码） | {stats["同音完整特征相同组数"]}组，{same}字音对（{same / units:.2%}） |',
        f'| 输入全部条件仍匹配多个字 | {ambiguous}字音对（{ambiguous / units:.2%}） |',
        f'| 理论同音候选均数：筛选前→全部条件筛选后 | {stats["筛选前平均同音候选数"]:.2f} → {stats["全部条件筛选后平均候选数"]:.2f} |', '',
        '### 顺序可跳过（不计键的排列变化）', '',
        '用户可以省略任意线索，但输入线索必须保持组件树的从前到后顺序；按最长完整特征串作为查询，候选串能按序包含查询时即匹配。', '',
        '| 指标 | 结果 |', '|---|---:|',
        f'| **完整有序特征相同（真正无法区分）** | **{stats["允许跳过且顺序必须一致"]["顺序完整码相同组数"]}组，{stats["允许跳过且顺序必须一致"]["顺序完整码相同字音对"]}字音对（{stats["允许跳过且顺序必须一致"]["顺序完整码相同字音对"] / units:.2%}）** |',
        f'| 输完自身全部顺序线索仍多候选 | {stats["允许跳过且顺序必须一致"]["输入自身全部顺序线索后仍多候选"]}字音对 |',
        f'| 筛选后平均候选数 | {stats["允许跳过且顺序必须一致"]["全部顺序线索筛选后平均候选数"]:.2f} |', '',
        '| 最少需要的条件键数 | 字音对数 |', '|---|---:|',
    ]
    lines.extend(f'| {n} | {distribution.get(n, 0)} |' for n in ('0', '1', '2', '3', '4+', '全部条件仍不唯一'))
    lines.extend(['',
        '“完整有序特征相同”才计真正重码；输入自身全部特征后仍有其他候选，是更宽的子序列包含匹配指标，不等于无法区分。吗=km、骂=kkm，输入km也匹配骂，但追加第二个k可区分。',
        '候选集均数下降不保证每个字能唯一定位；声母碰撞、少组件被多组件包含、无序丢失位置都会造成残余歧义。', '',
        '## 数据来源及下一步', '',
        '目标是本项目8105.dict.yaml的8177个不同字（含其扩展条目），不是标准字表恰好8105字。20个worker逐字判断，IDS与旧简根只作参考；未用递归IDS程序生成拆法。原批次、说明和主审修订记录保留在 `/tmp/component-tree-review/`。',
        'IDS参考：https://github.com/cjkvi/cjkvi-ids/blob/master/ids.txt；源文件SHA256：bfc70a8c09f9f5616ebf0543bd6681e67314e9f7ae2307e5ae8c6f15bdc5c6a6。IDS不是笔顺或字形正确性的证明。',
        '下一步先统一小组件的停止层级、处理待核字，再重算；不先接Lua或替换活动方案。', '',
    ])
    (DATA / 'components_8105_report.md').write_text('\n'.join(lines))
    print(json.dumps(result, ensure_ascii=False, indent=2))


def self_test():
    assert initial('cha') == 'i' and initial('cun') == 'c' and initial('ri') == 'r'
    sample = {'吗': Counter('km'), '骂': Counter('kkm')}
    tested = {r[0]: r for r in bucket_results(['吗', '骂'], sample)}
    assert tested['吗'][2] == 2 and tested['吗'][4] == '全部条件仍不唯一'
    assert tested['骂'][2] == 1 and tested['骂'][4:] == ('2', 'kk')
    assert signature(Counter('mkk')) == signature(Counter('kkm'))
    bags = {str(i): Counter(s) for i, s in enumerate(('km', 'kkm', 'kmr', 'rr', ''))}
    for char, _, count, matches, minimum, query in bucket_results(list(bags), bags):
        expected = [c for c in bags if not (bags[char] - bags[c])]
        assert count == len(expected) and matches == ''.join(expected)
        if query:
            assert not (Counter(query) - bags[char])
            assert [c for c in bags if not (Counter(query) - bags[c])] == [char]
            assert len(query) == int(minimum)
    tree_sample = ['猹', 'cha', '猹[犭,查[木,旦[日,横]]]',
                   '犬:quan 查:cha 木:mu 旦:dan 日:ri', '横', '候选', '']
    assert feature_keys(tree_sample) == Counter('qimdra')
    assert feature_keys(tree_sample, True) == Counter('qmra')
    assert feature_sequence(tree_sample, True) == list('qmra')
    assert ordered_matches('qm', 'qim') and not ordered_matches('mq', 'qim')
    assert ordered_matches('qm', 'qm') and not ordered_matches('qmm', 'qm')
    other = ['侘', 'cha', '侘[亻,宅[宀,乇[撇,七]]]',
             '人:ren 宅:zhai 宀:mian 乇:tuo 七:qi', '撇', '候选', '']
    assert feature_keys(other, True) == Counter('rqpddv')
    assert Counter('qm') - feature_keys(other, True)
    assert not (Counter('qm') - feature_keys(tree_sample, True))
    clothing = ['某', 'mou', '某[衤,衣]', '衣:yi 衣:yi', '-', '候选', '']
    assert components(clothing, True) == [('衣', 'yi')]
    assert Counter(residual_strokes(clothing)) == Counter('点 折 竖 撇 点'.split())
    grass = ['某', 'mou', '某[艹]', '草:tao', '-', '候选', '']
    assert components(grass, True) == [('草', 'cao')]
    expanded = ['某', 'mou', '某[宀[点,点,折]]', '-', '点 点 折', '候选', '']
    assert residual_strokes(expanded) == ['点', '点', '折']
    try:
        parse_tree('骂[口,口')
    except ValueError:
        pass
    else:
        raise AssertionError('未拒绝不完整树')


if __name__ == '__main__':
    self_test()
    if sys.argv[1:] == ['--self-test']:
        print('统计自检通过。')
    elif sys.argv[1:]:
        raise SystemExit('用法：uv run python scripts/analyze_components.py [--self-test]')
    else:
        analyze()
