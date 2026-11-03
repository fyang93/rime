import ast
import contextlib
import csv
import io
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from itertools import product, zip_longest
from pathlib import Path
from unittest.mock import patch

from jd6 import ROOT, ROOT_GROUPS, ROOT_KEYS, TABLE, build_index, dictionary_characters, load_table


def review_shape(first, second, reason):
    """核对分支与部码，再消费选码顺序；说明标记不替代人工字形证据。"""
    labels = ('选码顺序', '非根顺取', '起首根', '特裁取码')
    markers = {}
    while match := re.match(r'【(' + '|'.join(labels) + r'):([^】]*)】', reason):
        label, value = match.groups()
        if label in markers:
            raise ValueError('同类审核标记不得重复')
        markers[label] = value
        reason = reason[match.end():]
    if any('【' + label in reason for label in labels) or (markers and not reason.strip()):
        raise ValueError('审核标记须连续位于说明开头，且附有取码依据')
    codes = {'1': first, '2': second}
    assigned = set()
    for label in labels[1:]:
        if label not in markers:
            continue
        value = markers[label]
        if not re.fullmatch(r'[12](?:,[12])?', value):
            raise ValueError('分支须列出存在的部号1、2')
        for part in value.split(','):
            if part in assigned or not codes[part]:
                raise ValueError('部号不得重复、缺失或同时属于不同分支')
            assigned.add(part)
            if label == '非根顺取' and (not 1 <= len(codes[part]) <= 2
                                      or set(codes[part]) - set('一丨丿丶乛')):
                raise ValueError('非根部只能取真实前两笔，不能夹带后置完整根')
    order = markers.get('选码顺序', '1' * len(first) + '2' * len(second))
    if not re.fullmatch('[12]+', order) or order.count('1') != len(first) or order.count('2') != len(second):
        raise ValueError('选码顺序须恰好用完两部取码，不得遗漏或重复')
    parts = {'1': iter(first), '2': iter(second)}
    return ''.join(next(parts[part]) for part in order)


class JD6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator_tree = ast.parse((ROOT / 'scripts/generate.py').read_text())
        cls.parts = next(ast.literal_eval(node.value) for node in cls.generator_tree.body
                         if isinstance(node, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == 'parts'
                                 for t in node.targets))

    def test_table_covers_both_dictionaries_and_keeps_unknowns_honest(self):
        rows = load_table()
        self.assertTrue(dictionary_characters() <= rows.keys())
        self.assertEqual(list(rows), sorted(rows))
        for char, (shape, status, note) in rows.items():
            self.assertEqual(status == '待补', not shape, char)
            self.assertLessEqual(len(shape), 4, char)
            self.assertTrue(note.strip(), char)
            self.assertFalse(set(shape) - ROOT_KEYS.keys(), char)

    def test_8105_shapes_are_valid_or_explicitly_pending(self):
        rows = load_table()
        target = dictionary_characters(('8105',))
        self.assertTrue(target)
        self.assertTrue(target <= rows.keys())
        for char in target:
            shape, status, note = rows[char]
            self.assertFalse(set(shape) - ROOT_KEYS.keys(), char)
            if status == '待补':
                self.assertEqual(shape, '', char)
                self.assertTrue(note.strip(), char)
            else:
                self.assertTrue(shape, char)

    def test_review_ledger_covers_the_entire_change_scope(self):
        rows = load_table()
        path = TABLE.parent / 'jd6_review.tsv'
        with path.open(encoding='utf-8', newline='') as file:
            reader = csv.reader(file, delimiter='\t')
            self.assertEqual(next(reader), '字 字音 现拆码 拟拆码 结论 第一部分 第一部取码 第二部分 第二部取码 说明'.split())
            ledger = list(reader)
        target = dictionary_characters(('8105',))
        self.assertEqual(len(ledger), len(target))
        self.assertEqual(len({row[0] for row in ledger}), len(ledger))
        self.assertEqual({row[0] for row in ledger}, target)
        self.assertEqual(target, {c for c, (_, _, note) in rows.items()
                                  if note.startswith('JD6-25根复审')})
        for char, phone, before, after, verdict, part1, first, part2, second, reason in ledger:
            self.assertTrue(phone and part1 and reason, char)
            self.assertIn(verdict, {'保留', '修改', '待核'}, char)
            self.assertEqual(rows[char][:2], (after, '待补' if verdict == '待核' else '已核对'), char)
            if verdict == '待核':
                self.assertEqual(after, '', char)
                continue
            self.assertTrue(1 <= len(after) <= 4, char)
            self.assertFalse(set(after) - ROOT_KEYS.keys(), char)
            with self.subTest(char=char):
                self.assertEqual(after, review_shape(first, second, reason), char)
                for part, code in [('1', first), ('2', second)]:
                    if code and code[0] in '一丨丿丶乛' and set(code[1:]) - set('一丨丿丶乛'):
                        qualified = re.findall(r'【(?:起首根|特裁取码):([12](?:,[12])?)】', reason)
                        self.assertTrue(any(part in value.split(',') for value in qualified),
                                        '实笔后接根须逐项说明直接起首根资格或用户特裁：' + char)
            self.assertEqual(before == after, verdict == '保留', char)
            if part1.startswith(('【独体】', '【裁决】', '【顺取】')):
                self.assertFalse(part2 or second, char)
            else:
                self.assertTrue(part2, char)
                self.assertTrue(1 <= len(first) <= 2 and 1 <= len(second) <= 2, char)
        self.assertTrue((TABLE.parent / 'jd6_review_first_root.tsv').is_file())

    def test_nonroot_parts_stop_at_two_strokes(self):
        self.assertEqual(review_shape('丿一', '口', '【非根顺取:1】合成非根部取真实前两笔'), '丿一口')
        self.assertEqual(review_shape('木丨', '口', '合成起首完整根加余部首笔'), '木丨口')
        self.assertEqual(review_shape('一口', '水', '【起首根:1】合成独立根直接相接'), '一口水')
        self.assertEqual(review_shape('一乛', '口', '【选码顺序:121】【非根顺取:1】合成两部交错'), '一口乛')
        for code in ['丿木', '丿日', '丿土', '丿十', '丿士', '丶王', '一十', '乛十', '丿一丨']:
            with self.subTest(code=code), self.assertRaises(ValueError):
                review_shape(code, '口', '【非根顺取:1】合成错误抽根或超额')
        for marker in ['【非根顺取:1,1】', '【非根顺取:3】', '【非根顺取:】',
                       '【非根顺取:1】【起首根:1】', '【非根顺取:1】【非根顺取:1】']:
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                review_shape('丿一', '口', marker + '合成非法分支')
        with self.assertRaises(ValueError):
            review_shape('丿一', '', '【非根顺取:2】不存在的部')
        with self.assertRaises(ValueError):
            review_shape('丿一', '口', '【非根顺取:1】')

    def test_review_shape_order(self):
        a, b, c, d = tuple(ROOT_KEYS)[:4]
        first, second = a + b, c + d
        self.assertEqual(review_shape(first, second, '普通两部记录'), first + second)
        self.assertEqual(review_shape(first, '', '独体记录'), first)
        for order, expected in [('1122', a + b + c + d), ('1212', a + c + b + d),
                                ('1221', a + c + d + b), ('2121', c + a + d + b)]:
            with self.subTest(order=order):
                self.assertEqual(review_shape(first, second, f'【选码顺序:{order}】合成笔顺依据'),
                                 expected)
        self.assertEqual(review_shape(first, c, '【选码顺序:121】合成笔顺依据'), a + c + b)
        self.assertEqual(review_shape(a + a, a, '【选码顺序:121】重复根合成依据'), a * 3)
        for reason in ['【选码顺序:121】遗漏', '【选码顺序:11222】重复',
                       '【选码顺序:1112】部码数量错误', '【选码顺序:1231】无效部号',
                       '【选码顺序:】空顺序', '【选码顺序:1212】', '【选码顺序:1212】  ',
                       '【选码顺序1212】缺分隔符', '说明【选码顺序:1212】位置错误',
                       '【选码顺序:1212】依据【选码顺序:1122】重复标记']:
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                review_shape(first, second, reason)

    def test_invalid_rows_rejected(self):
        root = next(iter(ROOT_KEYS))
        for text in [f'甲\t{root}\t沿用\t来源\n' * 2,
                     f'甲\t{root}\t待补\t说明\n',
                     '甲\t\t已核对\t说明\n',
                     '甲\t?\t已核对\t非法字根\n',
                     f'甲\t{root * 5}\t沿用\t超长\n',
                     f'甲\t{root}\t已核对\t\n',
                     f'甲\t{root}\t无效状态\t说明\n',
                     f'甲乙\t{root}\t沿用\t无效字\n',
                     f'甲\t{root}\t沿用\n']:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'table.txt'
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_table(path)

    def test_pending_index_targets_8105_including_old_unknowns(self):
        rows = load_table()
        target = dictionary_characters(('8105',))
        expected = sorted(char for char in target if not rows[char][0])
        index = build_index(rows)
        pending_section = index.split('## 8105待补清单', 1)[1]
        listed = pending_section.split('```text', 1)[1].split('```', 1)[0].split()
        self.assertEqual(listed, expected)
        self.assertIn('含原表未知和缺失项', index)

    def test_index_is_reproducible(self):
        self.assertEqual((TABLE.parent / 'jd6_index.md').read_text(), build_index(load_table()))

    def test_key_aliases_are_generated_for_shape_only(self):
        rows = load_table()
        shapes = {char: shape for char, (shape, status, _) in rows.items()
                  if status != '待补'}
        # 合成重复根验证别名的笛卡尔积，不裁决任何实际汉字的拆法。
        shapes.update({f'fixture-{root}': root * 4 for root in ROOT_KEYS})
        namespace = {'product': product, 'chaizi_jd6': shapes, 'parts': self.parts}
        for node in self.generator_tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                    t.id == 'xcodes' for t in node.targets):
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<generator>', 'exec'), namespace)
        self.assertEqual(self.parts.keys(), ROOT_KEYS.keys())
        for root, key in ROOT_KEYS.items():
            aliases = self.parts[root]
            aliases = aliases if isinstance(aliases, tuple) else (aliases,)
            self.assertTrue(aliases, root)
            self.assertEqual(aliases[0], key, root)
            self.assertEqual(len(aliases), len(set(aliases)), root)
            self.assertTrue(all(re.fullmatch('[a-z]', alias) for alias in aliases), root)
        self.assertEqual(namespace['xcodes'].keys(), shapes.keys())
        for char, shape in shapes.items():
            expected = ['']
            for root in shape:
                aliases = self.parts[root]
                aliases = aliases if isinstance(aliases, tuple) else (aliases,)
                expected = [prefix + alias for prefix in expected for alias in aliases]
            self.assertEqual(namespace['xcodes'][char], expected, char)
        self.assertIn(r'derive/^(\w+);\w*$/$1/', (ROOT / 'zrm.schema.yaml').read_text())

    def test_whole_roots_are_not_split(self):
        rows = load_table()
        # 草是艹的码名，不是整字草根。
        for root in ROOT_KEYS.keys() & dictionary_characters(('8105',)) - {'草'}:
            with self.subTest(root=root):
                self.assertEqual(rows[root][0], root)

    def test_root_mapping_budget(self):
        self.assertTrue(0 < len(ROOT_GROUPS) <= 26)
        self.assertEqual(set(''.join(ROOT_GROUPS)), ROOT_KEYS.keys())
        with patch('jd6.ROOT_GROUPS', ROOT_GROUPS + ('?',) * 27):
            with self.assertRaises(ValueError):
                load_table()

    def test_keyboard_svg_matches_root_mapping(self):
        image = ROOT / 'assets/jiangen-keyboard.svg'
        svg = ET.parse(image).getroot()
        keys = [node for node in svg.iter() if 'data-key' in node.attrib]
        self.assertEqual(len(keys), 26)
        actual = {node.attrib['data-key']: set(node.attrib['data-roots']) for node in keys}
        expected = {}
        for root, aliases in self.parts.items():
            for key in aliases if isinstance(aliases, tuple) else (aliases,):
                expected.setdefault(key, set()).add(root)
        expected[ROOT_KEYS['手']].add('扌')
        expected[ROOT_KEYS['金']].add('钅')
        self.assertEqual(actual, expected)
        self.assertIn('(assets/jiangen-keyboard.svg)', (ROOT / 'README.md').read_text())

    def test_generator_on_small_dictionary(self):
        source = (ROOT / 'scripts/generate.py').read_text()
        shape = next((root for root, keys in self.parts.items() if isinstance(keys, tuple)),
                     next(iter(ROOT_KEYS))) * 2
        with tempfile.TemporaryDirectory() as folder:
            scripts = Path(folder) / 'scripts'
            data = scripts / 'dicts'
            data.mkdir(parents=True)
            (Path(folder) / 'dicts').mkdir()
            (data / '8105.dict.yaml').write_text('甲\tjia\t577\n乙\tyi\t100\n乙\tyi\t100\n乙\tye\t50\n', encoding='utf-8')
            (data / '41448.dict.yaml').write_text('甲\tjia\n乙\tye\n丙\tbing\n', encoding='utf-8')
            (data / 'chaizi_jd6_v2.txt').write_text(f'甲\t{shape}\t已核对\t合成fixture\n乙\t\t待补\t待核对\n丙\t\t待补\t待核对\n', encoding='utf-8')
            for name in ('custom.dict.yaml', 'base.dict.yaml', 'ext.dict.yaml'):
                (data / name).write_text('---\nname: test\n...\n', encoding='utf-8')
            previous = Path.cwd()
            namespace = {}
            try:
                os.chdir(scripts)
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(source, '<generator>', 'exec'), namespace)
            finally:
                os.chdir(previous)
            generated = (Path(folder) / 'zrm.dict.yaml').read_text()
            self.assertNotIn('use_preset_vocabulary:', generated)
            self.assertNotIn('min_phrase_weight:', generated)
            expected = {f'甲\tjw;{"".join(keys)}\t577'
                        for keys in product(*(self.parts[root] for root in shape))}
            expected.update({'乙\tyi;\t100', '乙\tye;\t50'})
            entries = [line for line in generated.splitlines() if '\t' in line]
            self.assertEqual(set(entries), expected)
            self.assertEqual(len(entries), len(expected))

    def test_generated_dictionaries_are_current(self):
        source = (ROOT / 'scripts/generate.py').read_text()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            scripts = output / 'scripts'
            scripts.mkdir()
            (scripts / 'dicts').symlink_to(TABLE.parent, target_is_directory=True)
            (output / 'dicts').mkdir()
            previous = Path.cwd()
            namespace = {}
            try:
                os.chdir(scripts)
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(source, '<generator>', 'exec'), namespace)
            finally:
                os.chdir(previous)
            names = ('8105', '41448') if namespace['enable_40k'] else ('8105',)
            target = dictionary_characters(names)
            self.assertEqual(namespace['standard'], target)
            self.assertEqual(namespace['chaizi_jd6'],
                             {char: shape for char, (shape, status, _) in load_table().items()
                              if char in target and status != '待补'})
            for name in ('zrm.dict.yaml', 'dicts/custom.dict.yaml',
                         'dicts/base.dict.yaml', 'dicts/ext.dict.yaml'):
                with self.subTest(dictionary=name):
                    mismatches = 0
                    examples = []
                    with (ROOT / name).open(encoding='utf-8') as actual, \
                            (output / name).open(encoding='utf-8') as expected:
                        for number, (old, new) in enumerate(zip_longest(actual, expected), 1):
                            if old != new:
                                mismatches += 1
                                if len(examples) < 3:
                                    examples.append(f'{number}: {old!r} -> {new!r}')
                    self.assertEqual(mismatches, 0,
                                     f'{name}: {mismatches} 行未同步；' + '; '.join(examples))

    def test_generator_preserves_polyphones(self):
        source = (ROOT / 'scripts/generate.py').read_text()
        self.assertIn('if (char, pinyin) in seen:', source)
        self.assertIn('chaizi_jd6_v2.txt', source)
        self.assertNotIn('flypy', source)


if __name__ == '__main__':
    unittest.main()
