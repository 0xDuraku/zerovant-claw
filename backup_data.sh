#!/bin/bash
# Safe backup — tidak pakai git checkout, pakai worktree terpisah
cd /root/zerovantclaw

BACKUP_DIR="/tmp/zerovant-backup-worktree"

# Buat worktree jika belum ada
if [ ! -d "$BACKUP_DIR" ]; then
  git worktree add $BACKUP_DIR data-backup
fi

# Copy data ke worktree
cp -r /root/zerovantclaw/data $BACKUP_DIR/
cp /var/www/zerovantclaw/index.html $BACKUP_DIR/ 2>/dev/null || true
cp /var/www/zerovantclaw/mascot.png $BACKUP_DIR/ 2>/dev/null || true

# Commit & push dari worktree (tidak ganggu main)
cd $BACKUP_DIR
git add -f .
git commit -m "backup $(date '+%Y-%m-%d %H:%M')" --allow-empty
git push origin data-backup

echo "Backup done: $(date)"
