from pathlib import Path
import re
import unittest

from zrm_pinyin import to_double

ROOT = Path(__file__).resolve().parents[1]


class NaturalCodeTests(unittest.TestCase):
    def test_current_single_character_readings_unchanged(self):
        generated = {}
        for line in (ROOT / 'zrm.dict.yaml').read_text(encoding='utf-8').splitlines():
            fields = line.split('\t')
            if len(fields) >= 2 and len(fields[0]) == 1 and ';' in fields[1]:
                generated.setdefault(fields[0], set()).add(fields[1].split(';')[0])
        count = 0
        for line in (ROOT / 'scripts/dicts/wanxiang/zi.lite.dict.yaml').read_text(encoding='utf-8').splitlines():
            fields = line.split('\t')
            if len(fields) >= 2 and len(fields[0]) == 1 and re.fullmatch('[a-z]+', fields[1]):
                self.assertIn(to_double(fields[1]), generated[fields[0]], line)
                count += 1
        self.assertGreater(count, 8500)

    def test_fixed_weight_in_generated_main_dictionary(self):
        weights = {}
        for line in (ROOT / 'zrm.dict.yaml').read_text(encoding='utf-8').splitlines():
            fields = line.split('\t')
            if len(fields) == 3 and fields[0] in ('盯', '鼎'):
                weights[fields[0], fields[1].split(';')[0]] = int(fields[2])
        self.assertEqual(weights['盯', 'dy'], 2200)
        self.assertGreater(weights['盯', 'dy'], weights['鼎', 'dy'])

    def test_examples_and_invalid_inputs(self):
        for pinyin, expected in {'a': 'aa', 'ang': 'ah', 'eng': 'eg', 'chuang': 'id',
                                  'zhong': 'vs', 'lv': 'lv', 'lve': 'lt', 'shi': 'ui'}.items():
            self.assertEqual(to_double(pinyin), expected)
        for value in ('', None, 1, 'lüe', 'SHI', 'a1', 'not-pinyin'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                to_double(value)


if __name__ == '__main__':
    unittest.main()
