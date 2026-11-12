#!/data/data/com.termux/files/usr/bin/bash
# Publish this project to GitHub from Termux.
# Usage: ./push_to_github.sh https://github.com/USER/REPO.git
set -e
cd "$(dirname "$0")"
REPO_URL="$1"
if [ -z "$REPO_URL" ]; then
    echo "Usage: ./push_to_github.sh https://github.com/USER/REPO.git"
    exit 1
fi
[ -f .env ] && echo "Note: .env is ignored by .gitignore and will not be uploaded."
git init -b main 2>/dev/null || true
git add .
git commit -m "Anime RPG bot: large catalog build" || echo "Nothing new to commit."
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
echo "Use your GitHub username and a Personal Access Token when prompted."
git push -u origin main
echo "Done. Confirm that .env is absent from the repository."
