import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jd6 import load_table
from recode import merge, prepare


class RecodeTests(unittest.TestCase):
    def test_prepare_and_merge_preserve_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            original = '乙\t乛\n甲\t丨乛\n'
            (data / 'chaizi_jd6.txt').write_text(original, encoding='utf-8')
            with patch('recode.dictionary_characters', return_value={'甲', '乙', '丙'}):
                self.assertEqual(prepare(data), 3)
                self.assertEqual((data / 'recode/batches/batch-001.tsv').read_text(),
                                 '丙\t无\n乙\t乛\n甲\t丨乛\n')
                path = data / 'recode/out/batch-001.tsv'
                path.write_text('丙\t一丨\t已核对\t合成部件取前两笔\n'
                                '乙\t乛\t已核对\t独体一笔\n'
                                '甲\t丨乛一一\t已核对\t独体前四笔，改原版省略\n', encoding='utf-8')
                result = merge(data)
                self.assertEqual(result, {'处理字数': 3, '与原版不同': 2, '原版缺字': 1, '存疑字数': 0})
                self.assertEqual((data / 'chaizi_phz.txt').read_text(), path.read_text())
                self.assertFalse((data / 'recode/doubtful.tsv').exists())
                self.assertEqual((data / 'chaizi_jd6.txt').read_text(), original)

    def test_merge_rejects_missing_empty_duplicate_and_invalid_rows(self):
        bad = ['', '甲\t\t待补\t没有候选\n', '甲\t贝\t已核对\t非法根\n',
               '甲\t木\t沿用\t未复核\n', '甲\t木\t已核对\t说明【存疑】\n',
               '甲\t木\t已核对\t【存疑】未决候选\n',
               '甲\t木\t已核对\t重复\n' * 2, '乙\t木\t已核对\t错误字集\n']
        for text in bad:
            with self.subTest(text=text), tempfile.TemporaryDirectory() as folder:
                data = Path(folder)
                (data / 'chaizi_jd6.txt').write_text('甲\t丨乛\n', encoding='utf-8')
                with patch('recode.dictionary_characters', return_value={'甲'}):
                    prepare(data)
                    (data / 'recode/out/batch-001.tsv').write_text(text, encoding='utf-8')
                    with self.assertRaises(ValueError):
                        merge(data)
                    self.assertFalse((data / 'chaizi_phz.txt').exists())

    def test_merge_preserves_existing_table_on_reference_failure(self):
        for reference in (None, '无制表符的坏行\n'):
            with self.subTest(reference=reference), tempfile.TemporaryDirectory() as folder:
                data = Path(folder)
                source = data / 'chaizi_jd6.txt'
                source.write_text('甲\t一\n', encoding='utf-8')
                with patch('recode.dictionary_characters', return_value={'甲'}):
                    prepare(data)
                    (data / 'recode/out/batch-001.tsv').write_text(
                        '甲\t木\t已核对\t合成测试\n', encoding='utf-8')
                    table = data / 'chaizi_phz.txt'
                    previous = b'previous table\n'
                    table.write_bytes(previous)
                    if reference is None:
                        source.unlink()
                    else:
                        source.write_text(reference, encoding='utf-8')
                    with self.assertRaises((FileNotFoundError, ValueError)):
                        merge(data)
                    self.assertEqual(table.read_bytes(), previous)

    def test_merge_rejects_delimited_notes_without_overwriting(self):
        for note in ('依据\t附注', '依据\n附注', '依据\r附注'):
            with self.subTest(note=note), tempfile.TemporaryDirectory() as folder:
                data = Path(folder)
                (data / 'chaizi_jd6.txt').write_text('甲\t一\n', encoding='utf-8')
                with patch('recode.dictionary_characters', return_value={'甲'}):
                    prepare(data)
                    (data / 'recode/out/batch-001.tsv').write_text(
                        f'甲\t木\t已核对\t"{note}"\n', encoding='utf-8')
                    table = data / 'chaizi_phz.txt'
                    previous = b'previous table\n'
                    table.write_bytes(previous)
                    with self.assertRaises(ValueError):
                        merge(data)
                    self.assertEqual(table.read_bytes(), previous)

    def test_merge_round_trips_quoted_notes(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'chaizi_jd6.txt').write_text('甲\t一\n', encoding='utf-8')
            with patch('recode.dictionary_characters', return_value={'甲'}):
                prepare(data)
                result = data / 'recode/out/batch-001.tsv'
                result.write_text('甲\t木\t已核对\t"""有引号""的依据"\n', encoding='utf-8')
                expected = load_table(result)
                merge(data)
                self.assertEqual(load_table(data / 'chaizi_phz.txt'), expected)


if __name__ == '__main__':
    unittest.main()
