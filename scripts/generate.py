from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent if '__file__' in globals() else Path.cwd().parent
os.chdir(ROOT / 'scripts')

# --- former notebook cell 1 ---
import re
from collections import defaultdict
from itertools import chain, product

from zrm_pinyin import to_double


pattern = re.compile(r'^[a-zA-Z"]+$')
def is_en(text):
    return bool(pattern.match(text))

# 中文分成每一个字，英文分成一个单词
def split_zh_en(text):
    pattern = re.compile(r'[^a-zA-Z]|[a-zA-Z]+')
    return pattern.findall(text)
# --- former notebook cell 3 ---
# 是否使用41448大字表
enable_40k = False

standard = set()

with open('dicts/8105.dict.yaml', encoding='utf-8') as f:
    for line in f:
        line = line.rstrip()
        if re.match(r'^.\t\w+(\t\d+)?$', line):
            standard.add(line.split('\t')[0])

if enable_40k:
    with open('dicts/41448.dict.yaml', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip()
            if re.match(r'^.\t\w+(\t\d+)?$', line):
                standard.add(line.split('\t')[0])

# 键道6
parts = {
    '一': 'a', # jd6默认 v
    '贝': 'b', # jd6默认 ao
    '草': 'c', # jd6默认 ii
    '丶': 'd',
    # e
    '手': 'f', # jd6默认 iu
    # g
    '火': 'h',
    '犭': 'q',
    '豸': 'q',
    '虫': 'i', # i=ch
    '金': 'j', # jd6默认 io
    '口': 'k', # jd6默认 o
    '丨': 'l',
    '木': 'm', # jd6默认 v
    '女': 'n',
    '⺮': 'z',
    '山': 's',
    '王': 'w',
    '工': 'g',
    '日': ('o', 'e'), # 两码均可表达日
    '丿': 'p',
    # q
    '人': 'r', # jd6默认 i
    '土': 't', # jd6默认 vo
    '士': 't', # jd6默认 vo
    # u=sh
    '水': 'u', # jd6默认 a
    '十': 'x', # jd6默认 uo
    '乛': 'v',
    '月': 'y', # jd6默认 u
}

def get_chaizi(path):
    with open(path, 'r', encoding='utf-8') as f:
        chaizi = {}
        for line in f:
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue
            char, decomposition, status, _ = line.split('\t', 3)
            if char not in standard or status == '待补':
                continue
            chaizi[char] = decomposition
        return chaizi

chaizi_jd6 = get_chaizi('./dicts/chaizi_jd6_v2.txt')
xcodes = {key: [''.join(code) for code in product(*(parts[c] if isinstance(parts[c], tuple) else (parts[c],) for c in value))] for key, value in chaizi_jd6.items()}

missing = set()
multiple = set()
seen = set()
predefined = """---
name: zrm
version: "1.0"
sort: by_weight  
use_preset_vocabulary: true
min_phrase_weight: 100
import_tables:
  - ./dicts/custom
  - ./dicts/base
  - ./dicts/ext
...

"""

with open('../zrm.dict.yaml', 'w', encoding='utf-8') as f1, open('dicts/8105.dict.yaml', encoding='utf-8') as f2, open('dicts/41448.dict.yaml', encoding='utf-8') as f3:
    f1.write(predefined)
    lines = chain(f2, f3) if enable_40k else f2
    for line in lines:
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
                for code in xcodes[char]:
                    f1.write(f"{char}\t{to_double(pinyin)};{code}\t{freq}\n")
            else:
                missing.add(char)
                f1.write(f"{char}\t{to_double(pinyin)};\t{freq}\n")

print(f"{len(missing)}个字的辅助码缺失：{missing}")
print(f"{len(multiple)}个字存在多个辅助码：{multiple}")
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
    zrm_codes.setdefault(char, xing) # 多个日别码中保留首个 o 码作为词库规范码

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
convert_pinyin('./dicts/base.dict.yaml', '../dicts/base.dict.yaml')
convert_pinyin('./dicts/ext.dict.yaml', '../dicts/ext.dict.yaml')
