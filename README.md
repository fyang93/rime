## 使用方式

复制到用户文件夹并重新部署。

## 主要功能

- 使用自然码双拼输入词句，在需要选字的时候输入`;`和鹤形形码进行筛选。输入长句时通过`tab`键和`shift+tab`键跳转需要选字的字并通过形码筛选。输入形码不会影响后续输入。
- 支持英文单词输入。
- 支持LaTeX符号输入，如`\alpha`可以输入α。
- 支持编码反查，输入`` ` ``和全拼即可，如`` `ha ``可以反查出`哈 ha;kk`。

## 自定义词库

- `scripts/dicts/custom.dict.yaml`：自定义词库，修改后需要通过`scripts/script.ipynb`进行词库转换，转换后的词库会更新到`dicts/custom.dict.yaml`。
- `dicts/custom_phrase.txt`：自定义短词，适用于用缩写编码输入较长的内容，如邮箱、手机号、身份证等。
- `dicts/top_single_char.txt`和`dicts/top_words.txt`：自定义固顶字词。