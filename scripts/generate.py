from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent if '__file__' in globals() else Path.cwd().parent
os.chdir(ROOT / 'scripts')

# --- former notebook cell 1 ---
import re
from collections import defaultdict
from itertools import product

from jd6 import dictionary_characters, load_table
from zrm_pinyin import to_double


pattern = re.compile(r'^[a-zA-Z"]+$')
def is_en(text):
    return bool(pattern.match(text))

# 中文分成每一个字，英文分成一个单词
def split_zh_en(text):
    pattern = re.compile(r'[^a-zA-Z]|[a-zA-Z]+')
    return pattern.findall(text)
# --- former notebook cell 3 ---
# 字表与词库均取万象 Lite（无调全拼），见 scripts/dicts/wanxiang
CHARS = 'dicts/wanxiang/zi.lite.dict.yaml'
WORDS = ('jichu', 'cuoyin', 'duoyin', 'diming', 'mingren', 'yiren')

targets = dictionary_characters()
standard = set()

with open(CHARS, encoding='utf-8') as f:
    for line in f:
        line = line.rstrip()
        if re.match(r'^.\t\w+(\t\d+)?$', line):
            standard.add(line.split('\t')[0])

# 拼好字17组字根；别名只在形码中展开，词库使用首个规范码。
parts = {
    '一': 'a', '丨': 'l', '丿': ('p', 's'), '丶': 'd', '乛': 'v',
    '日': ('o', 'e'), '月': 'y', '金': 'j', '木': 'm', '水': 'u',
    '火': 'h', '土': 't', '士': 't', '人': 'r', '手': 'f',
    '口': 'k', '十': 'x', '草': 'c',
}

def get_chaizi(path):
    return {char: shape for char, (shape, status, _) in load_table(Path(path)).items()
            if char in targets and char in standard and status != '待补'}

chaizi_jd6 = get_chaizi('./dicts/chaizi_phz.txt')
xcodes = {key: [''.join(code) for code in product(*(parts[c] if isinstance(parts[c], tuple) else (parts[c],) for c in value))] for key, value in chaizi_jd6.items()}

missing = set()
multiple = set()
seen = set()
predefined = """---
name: zrm
version: "1.0"
sort: by_weight  
import_tables:
  - ./dicts/custom
""" + ''.join(f'  - ./dicts/{name}.lite\n' for name in WORDS) + """...

"""

with open('../zrm.dict.yaml', 'w', encoding='utf-8') as f1, open(CHARS, encoding='utf-8') as f2:
    f1.write(predefined)
    for line in f2:
        line = line.rstrip()
        if re.match(r'^.\t\w+(\t\d+)?$', line):
            fields = line.split('\t')
            char, pinyin = fields[:2]
            freq = fields[2] if len(fields) == 3 else '1'
            if (char, pinyin) in seen:
                continue
            seen.add((char, pinyin))
            if char in xcodes:
                if len(xcodes[char]) > 1:
                    multiple.add(char)
                # 只写规范码（o、p）；e、s 由 schema 的 derive 派生，否则提示码会显示成别名
                f1.write(f"{char}\t{to_double(pinyin)};{xcodes[char][0]}\t{freq}\n")
            else:
                missing.add(char)
                f1.write(f"{char}\t{to_double(pinyin)};\t{freq}\n")

print(f"{len(missing)}个字无形码（仅纯音）")
print(f"{len(xcodes.keys() & standard)}个字有形码，其中{len(multiple)}个有多个（日 o/e、丿 p/s）")
# --- former notebook cell 7 ---
zrm_phones = defaultdict(list)
zrm_codes = {}
zrm_path = '../zrm.dict.yaml'

with open(zrm_path, encoding='utf-8') as f:
  for line in f:
    if len(line.split('\t')) != 3:
      continue
    char, code = line.rstrip().split('\t')[:2]
    yin, xing = code.split(';')
    zrm_phones[char].append(yin)
    zrm_codes.setdefault(char, xing) # 别名中保留首个 o/p 码作为词库规范码

def convert_pinyin(infile, outfile, override_freq=None):
  with open(infile, encoding='utf-8') as f1, open(outfile, 'w', encoding='utf-8') as f2:
    for line in f1:
      if line.startswith("#"):
        continue
      if not re.match(r'^.+\t.+(\t\d+)*$', line):
        f2.write(line)
        continue
      parts = line.rstrip().split('\t')
      chars, phones = split_zh_en(parts[0]), parts[1].split(' ')
      if len(chars) < 1:  # 排除单字
        continue

      if any(is_en(char) for char in chars): # 存在英语
        doubled = (phone if is_en(char) else to_double(phone) for char,phone in zip(chars, phones)) # 存在英语的时候加形码会导致输入框提示异常
        doubled_code = ''.join(doubled)
      # elif all((char in zrm_phones and to_double(phone) in zrm_phones[char]) for char,phone in zip(chars, phones)):
      elif all(char in zrm_phones for char in chars):
        doubled = (phone if is_en(char) else to_double(phone) + ';' + zrm_codes[char] for char,phone in zip(chars, phones))
        # doubled = (phone if is_en(char) else to_double(phone) for char,phone in zip(chars, phones))
        doubled_code = ' '.join(doubled)
      else: # 存在不在字表中的字符
        continue

      if len(parts) < 3:
        if override_freq:
          f2.write(''.join(chars) + '\t' + doubled_code + '\t' + str(override_freq) + '\n')
        else:
          f2.write(''.join(chars) + '\t' + doubled_code + '\n')
      else:
        freq = parts[2]
        f2.write(''.join(chars) + '\t' + doubled_code + '\t' + freq + '\n')
# --- former notebook cell 9 ---
convert_pinyin('./dicts/custom.dict.yaml', '../dicts/custom.dict.yaml', override_freq=10000)

# --- former notebook cell 11 ---
for name in WORDS:
  convert_pinyin(f'./dicts/wanxiang/{name}.lite.dict.yaml', f'../dicts/{name}.lite.dict.yaml')
