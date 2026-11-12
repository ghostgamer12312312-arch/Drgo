#!/data/data/com.termux/files/usr/bin/bash
set -e
mkdir -p handlers

[ -f env.example ] && mv env.example .env.example
[ -f gitignore.txt ] && mv gitignore.txt .gitignore

for f in handlers_*.py; do
    [ -e "$f" ] || continue
    base=${f#handlers_}
    [ "$base" = "init.py" ] && base="__init__.py"
    mv "$f" "handlers/$base"
done

chmod +x run.sh push_to_github.sh 2>/dev/null || true

echo "Project files organized."
echo "Next: cp .env.example .env, edit .env, then run ./run.sh"
