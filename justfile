default:
    @just --list

alias u := update

update message="update":
    #!/usr/bin/env bash
    set -euo pipefail
    git add .
    git commit -m "{{message}}"
    git push
