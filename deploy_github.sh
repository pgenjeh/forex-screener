#!/bin/bash
# Push forex-screener ke GitHub — sekali jalan.
# Pakai: ./deploy_github.sh https://github.com/badasht/forex-screener.git
# Kalau repo belum dibuat di github.com, buat dulu (kosong, tanpa README),
# lalu jalankan script ini. Butuh git + login GitHub (HTTPS token / SSH).
set -e
cd "$(dirname "$0")"

REMOTE="${1:-}"
if [ -z "$REMOTE" ]; then
  echo "Pakai: ./deploy_github.sh <url-repo-github>"
  echo "Contoh: ./deploy_github.sh https://github.com/badasht/forex-screener.git"
  exit 1
fi

# .env tidak boleh ikut — cek dulu
if [ -f .env ]; then
  echo "⚠️  .env ada di folder ini — pastikan TIDAK ter-commit (cek .gitignore)."
fi

if [ ! -d .git ]; then git init -b main; fi
git add .
git status --short
git commit -m "Pip forex screener + Telegram + Railway deploy" || echo "(tidak ada perubahan baru untuk di-commit)"
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
git push -u origin main
echo ""
echo "✅ Pushed ke $REMOTE"
echo "Lanjut ke Railway: DEPLOY.md langkah 3."
