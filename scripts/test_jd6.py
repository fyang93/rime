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
    """说明可前缀【选码顺序:1221】：1/2各取对应部下一码，省略则先一后二。

    标记后仍须写笔顺依据，说明先写、中断、穿插和续写；标记本身不是证据。
    """
    if '【选码顺序' not in reason:
        return first + second
    match = re.fullmatch(r'【选码顺序:([12]+)】(.+)', reason)
    if not match or not match[2].strip() or '【选码顺序' in match[2]:
        raise ValueError('选码顺序须是说明开头的唯一标记，且附有笔顺依据')
    order = match[1]
    if order.count('1') != len(first) or order.count('2') != len(second):
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
            self.assertEqual(before == after, verdict == '保留', char)
            if part1.startswith(('【独体】', '【裁决】', '【顺取】')):
                self.assertFalse(part2 or second, char)
            else:
                self.assertTrue(part2, char)
                self.assertTrue(1 <= len(first) <= 2 and 1 <= len(second) <= 2, char)
        self.assertTrue((TABLE.parent / 'jd6_review_first_root.tsv').is_file())

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
