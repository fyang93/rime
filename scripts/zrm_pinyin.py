"""自然码音节转换；供字典生成和模型注音共用，无生成/切换目录副作用。"""

FIRST = {'ch': 'i', 'sh': 'u', 'zh': 'v'}
SECOND = {
    'ua': 'w', 'ei': 'z', 'e': 'e', 'ou': 'b', 'iu': 'q', 've': 't',
    'ue': 't', 'u': 'u', 'i': 'i', 'o': 'o', 'uo': 'o', 'ie': 'x',
    'a': 'a', 'ong': 's', 'iong': 's', 'ai': 'l', 'ing': 'y', 'uai': 'y',
    'ang': 'h', 'uan': 'r', 'an': 'j', 'en': 'f', 'ia': 'w', 'iang': 'd',
    'uang': 'd', 'eng': 'g', 'in': 'n', 'ao': 'k', 'v': 'v', 'ui': 'v',
    'un': 'p', 'iao': 'c', 'ian': 'm',
}
SPECIAL = {'a': 'aa', 'ai': 'ai', 'an': 'an', 'ang': 'ah', 'ao': 'ao',
           'e': 'ee', 'ei': 'ei', 'en': 'en', 'er': 'er', 'o': 'oo',
           'ou': 'ou', 'ong': 'os', 'eng': 'eg'}


def to_double(s: str) -> str:
    if not isinstance(s, str) or not s or not s.isascii() or not s.isalpha() or s != s.lower():
        raise ValueError(f'非法拼音音节：{s!r}')
    if len(s) <= 3 and s[0] in 'aeo' and s in SPECIAL:
        return SPECIAL[s]
    if s[:2] in FIRST:
        return FIRST[s[:2]] + SECOND.get(s[2:], '')
    return s[0] + SECOND.get(s[1:], s[1:])
