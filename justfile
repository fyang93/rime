default:
    @just --list

alias u := update
alias d := download

# 下载万象语法模型（不入库）
download:
    #!/usr/bin/env bash
    set -euo pipefail
    wget -t 5 -O wanxiang-lts-zh-hans.gram.part 'https://github.com/amzxyz/rime-wanxiang-data/releases/download/LTS/wanxiang-lts-zh-hans.gram'
    mv wanxiang-lts-zh-hans.gram.part wanxiang-lts-zh-hans.gram

# 更新万象 Lite 字表与词库，并重新生成自然码词库
wanxiang version="v18.1.8":
    #!/usr/bin/env bash
    set -euo pipefail
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    curl -fL --retry 3 "https://github.com/amzxyz/rime-wanxiang/releases/download/{{version}}/rime-wanxiang-lite.zip" -o "$tmp/lite.zip"
    unzip -q "$tmp/lite.zip" 'dicts/*.lite.dict.yaml' -d "$tmp"
    for name in zi jichu cuoyin duoyin diming mingren yiren; do
        cp "$tmp/dicts/$name.lite.dict.yaml" scripts/dicts/wanxiang/
    done
    uv run python scripts/generate.py

update message="update":
    #!/usr/bin/env bash
    set -euo pipefail
    git add .
    git commit -m "{{message}}"
    git push
