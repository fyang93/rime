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


class JD6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'scripts/generate.py').read_text()
        cls.generator_tree = ast.parse(cls.source)
        cls.parts = next(ast.literal_eval(node.value) for node in cls.generator_tree.body
                         if isinstance(node, ast.Assign)
                         and any(isinstance(t, ast.Name) and t.id == 'parts' for t in node.targets))

    def run_generator(self, scripts):
        previous = Path.cwd()
        namespace = {}
        try:
            os.chdir(scripts)
            with patch('jd6.TARGETS', scripts / 'dicts/phz_targets.txt'), \
                    contextlib.redirect_stdout(io.StringIO()):
                exec(compile(self.source, '<generator>', 'exec'), namespace)
        finally:
            os.chdir(previous)
        return namespace

    def test_target_table_is_complete_sorted_and_uses_17_roots(self):
        rows = load_table()
        target = dictionary_characters()
        self.assertEqual(len(target), 8253)
        self.assertEqual(rows.keys(), target)
        self.assertEqual(list(rows), sorted(rows))
        self.assertEqual(TABLE.name, 'chaizi_phz.txt')
        self.assertFalse((TABLE.parent / 'chaizi_jd6_v2.txt').exists())
        for char, (shape, status, note) in rows.items():
            self.assertEqual(status, '已核对', char)
            self.assertTrue(1 <= len(shape) <= 4, char)
            self.assertFalse(set(shape) - ROOT_KEYS.keys(), char)
            self.assertTrue(note.strip(), char)

    def test_batch_outputs_match_table_without_unresolved_candidates(self):
        folder = TABLE.parent / 'recode'
        rows = load_table()
        combined = {}
        batches = sorted((folder / 'batches').glob('batch-*.tsv'))
        self.assertEqual(len(batches), 42)
        for batch in batches:
            with batch.open(encoding='utf-8', newline='') as file:
                target = [fields[0] for fields in csv.reader(file, delimiter='\t')]
            result = load_table(folder / 'out' / batch.name)
            self.assertEqual(list(result), target, batch.name)
            self.assertFalse(combined.keys() & result.keys(), batch.name)
            combined.update(result)
        self.assertEqual(combined, rows)
        for char, (_, _, note) in rows.items():
            self.assertNotIn('【存疑】', note, char)
            self.assertNotRegex(note, r'(?:JD6|tree)\s*=\s*\?', char)

    def test_specified_special_cases(self):
        rows = load_table()
        for char, shape in {'〇': '乛乛', '卍': '乛乛', '区': '一丿丶乛',
                            '匼': '一人一口', '匜': '一乛丨乛', '𬸘': '一丨丿乛',
                            '戴': '十丨乛', '可': '一口丨', '何': '人一口',
                            '国': '丨乛一一', '式': '一一丨一', '丁': '一丨',
                            '咸': '一丿一口', '囚': '丨乛人一', '困': '丨乛木一',
                            '回': '丨乛口一', '巫': '一丨人人', '白': '丿丨乛一',
                            '威': '一丿一乛', '本': '一丨丿丶', '果': '丨乛一一',
                            '夹': '一丶丿一', '内': '丨乛丿丶', '告': '丿一口',
                            '伯': '人丿丨', '㳚': '水一丿', '㙦': '人土',
                            '傕': '人丶乛', '偾': '人十草', '丞': '乛丨乛丿',
                            '隺': '丶乛丿丨', '相': '木丨乛', '湘': '水木',
                            '河': '水一口', '萤': '草丨乛', '营': '草口口',
                            '劳': '草乛丿', '荣': '草木'}.items():
            if char in rows:
                with self.subTest(char=char):
                    self.assertEqual(rows[char][0], shape)

    def test_current_root_rulings_without_filler(self):
        rows = load_table()
        expected = {
            '曰': '日', '昌': '日日', '倡': '人日日', '唱': '口日日',
            '娼': '乛丿日日', '荤': '草一乛', '治': '水乛丶',
            '脱': '月丶丿', '淳': '水丶一', '吹': '口丿乛',
            '洧': '水一丿', '辐': '一乛一口', '蹴': '口丶一',
            '坎': '土丿乛', '钦': '金丿乛', '炊': '火丿乛',
            '白': '丿丨乛一', '午': '丿一一丨', '王': '一一丨一',
            '主': '丶一一丨', '丑': '乛丨一一', '干': '一一丨',
            '豆': '一口丶丿', '或': '一口一乛',
            '鬲': '一口丨乛', '短': '丿一一口',
        }
        for char, shape in expected.items():
            with self.subTest(char=char):
                self.assertEqual(rows[char][0], shape)

    def test_round_four_examples(self):
        rows = load_table()
        expected = {
            '俗': '人丿丶', '浴': '水丿丶', '谷': '丿丶口', '者': '十日',
            '猪': '丿乛十', '嵘': '丨乛草', '墙': '土十', '蔷': '草十',
            '啬': '十丨乛', '喜': '士口口', '嘻': '口士口', '熹': '士口丶丶',
            '雠': '人丶乛', '高': '丶一口', '常': '丨丶口', '哈': '口人',
            '但': '人日', '呓': '口草', '压': '一丿土', '担': '手日',
            '旦': '日一', '艺': '草乛', '亿': '人乛', '胆': '月日',
            '袒': '丶乛日', '钽': '金日', '㙦': '人土', '弢': '乛一乛丨',
            '卡': '丨一丨丶', '血': '丿丨乛丨', '良': '丶乛一一',
        }
        for char, shape in expected.items():
            with self.subTest(char=char):
                self.assertEqual(rows[char][0], shape)

    def test_latest_user_rulings(self):
        rows = load_table()
        expected = {
            '偾': '人十草', '喷': '口十草', '愤': '丶丶十草',
            '豮': '一丿十草', '贲': '十草丨乛', '鲼': '丿乛十草', '𣸣': '水十草',
            '啬': '十丨乛', '墙': '土十', '嫱': '乛丿十',
            '樯': '木十', '穑': '丿一十', '蔷': '草十',
            '或': '一口一乛', '哥': '一口一口', '白': '丿丨乛一', '伯': '人丿丨',
            '揠': '手一日', '棫': '木一口', '笸': '丿一一口', '蜮': '丨乛一口',
            '蝘': '丨乛一日', '郾': '一日乛丨', '钷': '金一口', '阈': '丶丨一口',
            '严': '一丨丨丶', '产': '丶一丶丿', '截': '十一人丶', '栽': '十一木乛',
            '斗': '丶丶十', '犀': '乛一水', '堂': '丨丶口土', '晕': '日一乛',
            '牚': '丨丶口', '燊': '火火木', '量': '日丨乛', '孽': '草丿丨',
            '赢': '丶一口月', '嬴': '丶一口月', '疐': '十丨乛', '鹿': '丶一乛丨',
            '龠': '人一口', '合': '人一口', '命': '人一口', '𠅤': '丶一丨乛',
            '龢': '人丿一', '瀹': '水人', '爚': '火人', '籥': '丿一人',
            '墀': '土乛一', '樨': '木乛一',
        }
        for char, shape in expected.items():
            with self.subTest(char=char):
                self.assertEqual(rows[char][0], shape)
        self.assertNotIn('【特裁取码', rows['龠'][2])

    def test_round_four_part_ledger_matches_table(self):
        folder = TABLE.parent / 'recode/reviews'
        rows = load_table()
        files = sorted(path for path in folder.glob('round4-*.tsv')
                       if re.fullmatch(r'round4-\d{3}-\d{3}\.tsv', path.name))
        self.assertEqual(len(files), 8)
        combined = {}
        for path in files:
            with path.open(encoding='utf-8', newline='') as file:
                for fields in csv.reader(file, delimiter='\t'):
                    self.assertEqual(len(fields), 7, (path.name, fields))
                    char, branch, first, code1, second, code2, shape = fields
                    with self.subTest(char=char, ledger=path.name):
                        self.assertNotIn(char, combined)
                        self.assertIn(branch, {'两部', '整取', '整根', '特裁'})
                        self.assertTrue(first)
                        self.assertTrue(code1)
                        self.assertEqual(shape, code1 + code2)
                        self.assertEqual(shape, rows[char][0])
                        if branch == '两部':
                            self.assertTrue(second)
                            self.assertTrue(1 <= len(code1) <= 2)
                            self.assertTrue(1 <= len(code2) <= 2)
                            for code in (code1, code2):
                                if len(code) == 2 and code[0] not in '一丨丿丶乛':
                                    self.assertNotIn(code[1], '一丨丿丶乛')
                        else:
                            self.assertEqual((second, code2), ('', ''))
                        combined[char] = shape
        self.assertEqual(combined.keys(), rows.keys())

    def test_whole_roots_are_not_split(self):
        rows = load_table()
        # 草是艹的码名，不是整字草根。
        for root in ROOT_KEYS.keys() & rows.keys() - {'草'}:
            with self.subTest(root=root):
                self.assertEqual(rows[root][0], root)

    def test_invalid_rows_rejected(self):
        for text in ['甲\t木\t已核对\t来源\n' * 2, '甲\t木\t待补\t说明\n',
                     '甲\t\t已核对\t说明\n', '甲\t贝\t已核对\t非法字根\n',
                     '甲\t一一一一一\t沿用\t超长\n', '甲\t木\t已核对\t\n',
                     '甲\t木\t无效状态\t说明\n', '甲乙\t木\t沿用\t无效字\n',
                     '甲\t木\t沿用\n', '甲\t木\t已核对\t【存疑】未问用户\n']:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'table.txt'
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_table(path)

    def test_invalid_targets_rejected(self):
        for text in ['甲\n甲\n', '甲乙\n']:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'targets.txt'
                path.write_text(text, encoding='utf-8')
                with patch('jd6.TARGETS', path), self.assertRaises(ValueError):
                    dictionary_characters()

    def test_index_is_current_and_targets_only_new_scope(self):
        rows = load_table()
        index = build_index(rows)
        self.assertEqual((TABLE.parent / 'jd6_index.md').read_text(), index)
        pending_section = index.split('## 目标字待补清单', 1)[1]
        self.assertEqual(pending_section.split('```text', 1)[1].split('```', 1)[0].split(), [])
        self.assertIn('phz_targets.txt', index)
        self.assertIn('丿支持 p/s', index)
        self.assertNotIn('chaizi_jd6_v2.txt', index)
        self.assertIn('两部取完即结束，不满四码不补', index)
        self.assertNotIn('沿后续笔顺补取', index)
        self.assertIn('龠', index)
        self.assertIn('不代表逐字审计全部定案', index)

    def test_root_mapping_and_shape_aliases(self):
        self.assertEqual(len(ROOT_GROUPS), 17)
        self.assertEqual(set(''.join(ROOT_GROUPS)), ROOT_KEYS.keys())
        self.assertEqual(self.parts.keys(), ROOT_KEYS.keys())
        self.assertEqual(self.parts['日'], ('o', 'e'))
        self.assertEqual(self.parts['丿'], ('p', 's'))
        self.assertEqual(self.parts['火'], 'h')
        with patch('jd6.ROOT_GROUPS', ROOT_GROUPS + ('?',)):
            with self.assertRaises(ValueError):
                load_table()
        shapes = {char: row[0] for char, row in load_table().items()}
        shapes.update({f'fixture-{root}': root * 4 for root in ROOT_KEYS})
        namespace = {'product': product, 'chaizi_jd6': shapes, 'parts': self.parts}
        for node in self.generator_tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                    t.id == 'xcodes' for t in node.targets):
                exec(compile(ast.Module(body=[node], type_ignores=[]), '<generator>', 'exec'), namespace)
        for root, key in ROOT_KEYS.items():
            aliases = self.parts[root]
            aliases = aliases if isinstance(aliases, tuple) else (aliases,)
            self.assertEqual(aliases[0], key, root)
            self.assertEqual(len(aliases), len(set(aliases)), root)
            self.assertTrue(all(re.fullmatch('[a-z]', alias) for alias in aliases), root)
        for char, shape in shapes.items():
            expected = ['']
            for root in shape:
                aliases = self.parts[root]
                aliases = aliases if isinstance(aliases, tuple) else (aliases,)
                expected = [prefix + alias for prefix in expected for alias in aliases]
            self.assertEqual(namespace['xcodes'][char], expected, char)
        self.assertIn(r'derive/^(\w+);\w*$/$1/', (ROOT / 'zrm.schema.yaml').read_text())

    def test_keyboard_svg_matches_root_mapping(self):
        svg = ET.parse(ROOT / 'assets/jiangen-keyboard.svg').getroot()
        keys = [node for node in svg.iter() if 'data-key' in node.attrib]
        self.assertEqual(len(keys), 26)
        actual = {node.attrib['data-key']: set(node.attrib['data-roots']) for node in keys}
        expected = {key: set() for key in 'abcdefghijklmnopqrstuvwxyz'}
        for root, aliases in self.parts.items():
            for key in aliases if isinstance(aliases, tuple) else (aliases,):
                expected[key].add(root)
        expected[ROOT_KEYS['手']].add('扌')
        expected[ROOT_KEYS['金']].add('钅')
        self.assertEqual(actual, expected)

    def test_generator_on_small_dictionary(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            scripts = output / 'scripts'
            data = scripts / 'dicts'
            (data / 'wanxiang').mkdir(parents=True)
            (output / 'dicts').mkdir()
            (data / 'wanxiang/zi.lite.dict.yaml').write_text(
                '甲\tjia\t577\n乙\tyi\t100\n乙\tyi\t100\n乙\tye\t50\n', encoding='utf-8')
            (data / 'phz_targets.txt').write_text('# fixture\n甲\n丙\n', encoding='utf-8')
            (data / 'chaizi_phz.txt').write_text(
                '甲\t日丿\t已核对\t合成fixture\n乙\t木\t已核对\t表外字须纯音\n'
                '丙\t\t待补\t待核对\n', encoding='utf-8')
            (data / 'custom.dict.yaml').write_text('---\nname: custom\n...\n', encoding='utf-8')
            for name in ('jichu', 'cuoyin', 'duoyin', 'diming', 'mingren', 'yiren'):
                (data / f'wanxiang/{name}.lite.dict.yaml').write_text(
                    f'---\nname: {name}.lite\n...\n甲乙\tjia yi\t9\n甲丙\tjia bing\t9\n', encoding='utf-8')
            namespace = self.run_generator(scripts)
            generated = (output / 'zrm.dict.yaml').read_text()
            expected = {'甲\tjw;op\t577'}  # 只写规范码，e、s 由 schema 派生
            expected.update({'乙\tyi;\t100', '乙\tye;\t50'})
            entries = [line for line in generated.splitlines() if '\t' in line]
            self.assertEqual(set(entries), expected)
            self.assertEqual(len(entries), len(expected))
            self.assertEqual(namespace['zrm_codes']['甲'], 'op')
            words = (output / 'dicts/jichu.lite.dict.yaml').read_text()
            self.assertEqual([line for line in words.splitlines() if '\t' in line],
                             ['甲乙\tjw;op yi;\t9'])

    def test_generated_dictionaries_are_current_and_rare_chars_are_sound_only(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            scripts = output / 'scripts'
            scripts.mkdir()
            (scripts / 'dicts').symlink_to(TABLE.parent, target_is_directory=True)
            (output / 'dicts').mkdir()
            namespace = self.run_generator(scripts)
            available = dictionary_characters(('wanxiang/zi.lite',))
            targets = dictionary_characters()
            self.assertEqual(namespace['standard'], available)
            self.assertEqual(namespace['chaizi_jd6'],
                             {char: shape for char, (shape, status, _) in load_table().items()
                              if char in available and char in targets and status != '待补'})
            for char, shape in namespace['zrm_codes'].items():
                if char not in targets:
                    self.assertEqual(shape, '', char)
            for name in ('zrm.dict.yaml', 'dicts/custom.dict.yaml',
                         *(f'dicts/{word}.lite.dict.yaml' for word in namespace['WORDS'])):
                with self.subTest(dictionary=name):
                    mismatches = []
                    with (ROOT / name).open(encoding='utf-8') as actual, \
                            (output / name).open(encoding='utf-8') as expected:
                        for number, (old, new) in enumerate(zip_longest(actual, expected), 1):
                            if old != new:
                                if len(mismatches) < 3:
                                    mismatches.append(f'{number}: {old!r} -> {new!r}')
                    self.assertEqual(mismatches, [], f'{name}: ' + '; '.join(mismatches))

    def test_generator_preserves_polyphones_and_uses_new_table(self):
        self.assertIn('if (char, pinyin) in seen:', self.source)
        self.assertIn('chaizi_phz.txt', self.source)
        self.assertNotIn('chaizi_jd6_v2.txt', self.source)
        self.assertNotIn('flypy', self.source)


if __name__ == '__main__':
    unittest.main()
