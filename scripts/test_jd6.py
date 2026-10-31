import ast
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from itertools import product
from pathlib import Path
from unittest.mock import patch

from jd6 import ROOT, ROOT_GROUPS, ROOT_KEYS, TABLE, build_index, dictionary_characters, load_table


class JD6Tests(unittest.TestCase):
    def test_table_covers_both_dictionaries_and_keeps_unknowns_honest(self):
        rows = load_table()
        self.assertTrue(dictionary_characters() <= rows.keys())
        self.assertEqual(list(rows), sorted(rows))
        self.assertTrue(any(status == '待补' for _, status, _ in rows.values()))
        for char, (shape, status, _) in rows.items():
            if status == '已核对':
                self.assertTrue(shape, char)
            self.assertFalse(set(shape) - ROOT_KEYS.keys(), char)

    def test_structures_and_non_fire_dots(self):
        rows = load_table()
        for char, shape in {'昇': '日丿一', '猹': '犭木日', '姓': '女丿一', '灿': '火山',
                            '灶': '火土', '淡': '水火火', '谈': '丶乛火火',
                            '剡': '火火丨丨', '怒': '女乛丶乛', '安': '丶丶女',
                            '狄': '犭火', '红': '乛乛工', '笑': '⺮丿一',
                            '语': '丶乛一丨', '明': '日月', '日': '日'}.items():
            self.assertEqual(rows[char][:2], (shape, '已核对'), char)
        expected = {'点': '丨一丶丶', '焦': '人丶丶丶', '然': '丿乛丶丶',
                    '烈': '一丿丶丶', '煮': '十一丶丶', '照': '日乛丶丶',
                    '黑': '丨乛丶丶', '熊': '乛丶丶丶'}
        for char, shape in expected.items():
            self.assertEqual(rows[char][0], shape, char)
            self.assertTrue(shape.endswith('丶丶'), char)
            self.assertNotIn('火', shape, char)

    def test_parallel_review_corrections(self):
        rows = load_table()
        expected = {'喆': '士口士口', '翙': '山丿乛丶', '炟': '火日一',
                    '疍': '乛丨日一', '𬭊': '金木土', '浡': '水十丶', '𬭛': '金水乛',
                    '𤭢': '丶一一乛', '颎': '丿乛一丿', '𪨊': '乛一人人', '卍': '乛乛',
                    '𫓧': '金一一', '嚚': '口口一丨', '卬': '丿乛乛丨', '𬶋': '丿乛丿乛',
                    '𬀪': '日丨乛', '𬭎': '金丶丶', '𫠆': '十乛一丿', '屮': '乛丨丨',
                    '車': '一丨乛一', '叚': '乛一乛一',
                    '燊': '火火木', '夐': '丿乛丿乛', '疐': '十丶乛丨',
                    '𬸚': '犭丶丿乛', '𰻝': '丶丶丶乛',
                    '䦃': '金草十', '墘': '土十日', '萳': '草十丨', '𬭳': '金士口',
                    '甪': '丿丿乛', '癿': '丿丨乛', '箖': '⺮木木',
                    '婆': '水乛女', '煲': '人口火', '棪': '木火火',
                    '如': '女口', '给': '乛乛人一', '婪': '木木女', '嚄': '口草人',
                    '栒': '木丿乛', '𬇙': '水贝', '榰': '木十一', '猪': '犭十一',
                    '匜': '一乛丨乛', '匼': '一人一', '瀔': '水士丶', '孌': '丶一女', '斝': '口丶乛',
                    '〇': '乛乛', '卿': '丿乛乛一', '彬': '木木丿丿', '班': '王丶丿',
                    '斑': '王丶一', '楙': '木乛丶', '雠': '人丶丶乛',
                    '衍': '丿丿水一', '衒': '丿丿丶一', '衔': '丿丿金一', '街': '丿丿土土',
                    '亵': '丶一手丿', '衮': '丶一丿丶', '余': '人一一', '佥': '人一丶',
                    '寒': '丶丶丶丶', '充': '丶一丿乛', '兽': '丶丿一口',
                    '莽': '草一丿', '葬': '草一丿', '鸿': '水工丿',
                    '营': '草丶口口', '萤': '草丶虫', '笨': '⺮一丨', '者': '十一日',
                    '草': '草日十', '玉': '王丶', '璈': '王一一', '攥': '手⺮丨'}
        for char, shape in expected.items():
            self.assertEqual(rows[char][:2], (shape, '已核对'), char)

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
                self.assertIn('复审存疑', note, char)
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
            self.assertEqual(after, first + second, char)
            self.assertEqual(before == after, verdict == '保留', char)
            if part1.startswith(('【独体】', '【裁决】', '【顺取】')):
                self.assertFalse(part2 or second, char)
            else:
                self.assertTrue(part2, char)
                self.assertTrue(1 <= len(first) <= 2 and 1 <= len(second) <= 2, char)
            for part, code in ((part1, first), (part2, second)):
                if part in {'⺮', '山', '王', '工'}:
                    self.assertEqual(code, part, char)
                if part == '灬':
                    self.assertEqual(code, '丶丶', char)
        self.assertTrue((TABLE.parent / 'jd6_review_first_root.tsv').is_file())

    def test_invalid_rows_rejected(self):
        for text in ['字\t日\t沿用\t旧表\n字\t日\t沿用\t旧表\n',
                     '字\t日\t待补\t未知\n', '字\t\t已核对\t说明\n',
                     '字\t未知\t沿用\t未知不能充当有效形码\n',
                     '字\t?\t已核对\t占位不能充当有效形码\n',
                     '字\t灬\t已核对\t不是火\n', '字\t日日日日日\t沿用\t旧表\n',
                     '字\t日\t已核对\t\n',
                     '红\t纟一丨\t已核对\t不单独建根\n',
                     '笑\t心丿一\t已核对\t未列根\n',
                     '谈\t讠火\t已核对\t不单独建根\n']:
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
        source = (ROOT / 'scripts/generate.py').read_text()
        tree = ast.parse(source)
        namespace = {'product': product, 'chaizi_jd6': {'日': '日', '昌': '日日', '昇': '日丿一',
                     '红': '乛乛工', '笑': '⺮丿一', '豹': '豸丿乛', '谈': '丶乛火火',
                     '营': '草丶口口', '萤': '草丶虫', '湘': '水木丨', '相': '木丨乛',
                     '峰': '山丿乛', '岸': '山一丿', '玩': '王一一', '全': '人王', '江': '水工',
                     '者': '十一日', '虫': '虫'}}
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                    t.id in {'parts', 'xcodes'} for t in node.targets):
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<generator>', 'exec'), namespace)
        self.assertEqual(set(namespace['xcodes']['日']), {'o', 'e'})
        self.assertEqual(set(namespace['xcodes']['昌']), {'oo', 'oe', 'eo', 'ee'})
        self.assertEqual(set(namespace['xcodes']['昇']), {'opa', 'epa'})
        self.assertEqual(namespace['xcodes']['红'], ['vvg'])
        self.assertEqual(namespace['xcodes']['笑'], ['zpa'])
        self.assertEqual(namespace['xcodes']['江'], ['ug'])
        self.assertEqual(namespace['xcodes']['峰'], ['spv'])
        self.assertEqual(namespace['xcodes']['玩'], ['waa'])
        self.assertEqual(namespace['xcodes']['豹'], ['qpv'])
        self.assertEqual(namespace['xcodes']['谈'], ['dvhh'])
        self.assertEqual(namespace['xcodes']['营'], ['cdkk'])
        self.assertEqual(namespace['xcodes']['萤'], ['cdi'])
        self.assertEqual(namespace['xcodes']['湘'], ['uml'])
        self.assertEqual(namespace['xcodes']['相'], ['mlv'])
        self.assertEqual(set(namespace['xcodes']['者']), {'xao', 'xae'})
        self.assertEqual(namespace['xcodes']['虫'], ['i'])
        self.assertEqual(namespace['parts'].keys(), ROOT_KEYS.keys())
        self.assertEqual(namespace['parts']['⺮'], 'z')
        self.assertEqual(namespace['parts']['山'], 's')
        self.assertEqual(namespace['parts']['王'], 'w')
        self.assertEqual(namespace['parts']['工'], 'g')
        for root, key in ROOT_KEYS.items():
            actual = namespace['parts'][root]
            self.assertEqual(actual[0] if isinstance(actual, tuple) else actual, key)
        self.assertIn(r'derive/^(\w+);\w*$/$1/', (ROOT / 'zrm.schema.yaml').read_text())

    def test_root_mapping_budget(self):
        self.assertEqual(len(ROOT_GROUPS), 25)
        self.assertEqual(set(''.join(ROOT_GROUPS)), ROOT_KEYS.keys())
        with patch('jd6.ROOT_GROUPS', ROOT_GROUPS + ('新',) * 7):
            with self.assertRaises(ValueError):
                load_table()

    def test_keyboard_svg_matches_root_mapping(self):
        image = ROOT / 'assets/jiangen-keyboard.svg'
        svg = ET.parse(image).getroot()
        keys = [node for node in svg.iter() if 'data-key' in node.attrib]
        self.assertEqual(len(keys), 26)
        actual = {node.attrib['data-key']: set(node.attrib['data-roots']) for node in keys}
        expected = {}
        for root, key in ROOT_KEYS.items():
            expected.setdefault(key, set()).add(root)
        expected['e'] = {'日'}
        expected['f'].add('扌')
        expected['j'].add('钅')
        self.assertEqual(actual, expected)
        self.assertIn('(assets/jiangen-keyboard.svg)', (ROOT / 'README.md').read_text())

    def test_generator_on_small_dictionary(self):
        source = (ROOT / 'scripts/generate.py').read_text()
        with tempfile.TemporaryDirectory() as folder:
            scripts = Path(folder) / 'scripts'
            data = scripts / 'dicts'
            data.mkdir(parents=True)
            (Path(folder) / 'dicts').mkdir()
            (data / '8105.dict.yaml').write_text('昇\tsheng\t577\n乐\tle\t100\n乐\tyue\t50\n', encoding='utf-8')
            (data / '41448.dict.yaml').write_text('昇\tsheng\n乐\tyue\n龘\tda\n', encoding='utf-8')
            (data / 'chaizi_jd6_v2.txt').write_text('昇\t日丿一\t已核对\t日与升\n乐\t\t待补\t待核对\n龘\t\t待补\t待核对\n', encoding='utf-8')
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
            self.assertIn('昇\tug;opa\t577', generated)
            self.assertIn('昇\tug;epa\t577', generated)
            self.assertIn('乐\tle;\t100', generated)
            self.assertIn('乐\tyt;\t50', generated)
            self.assertEqual(generated.count('乐\tyt;'), 1)
            self.assertNotIn('龘\tda;\t1', generated)

    def test_generator_preserves_polyphones(self):
        source = (ROOT / 'scripts/generate.py').read_text()
        self.assertIn('if (char, pinyin) in seen:', source)
        self.assertIn('chaizi_jd6_v2.txt', source)
        self.assertNotIn('flypy', source)


if __name__ == '__main__':
    unittest.main()
