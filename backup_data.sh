#!/bin/bash
cd /root/zerovantclaw

# Copy data ke temp
cp -r data /tmp/zerovant-data-tmp

# Switch ke backup branch
git checkout data-backup

# Update data
rm -rf data
cp -r /tmp/zerovant-data-tmp data
rm -rf /tmp/zerovant-data-tmp

# Commit & push
git add -f data/
git commit -m "backup $(date '+%Y-%m-%d %H:%M')" --allow-empty
git push origin data-backup

# Backup website juga
cp /var/www/zerovantclaw/index.html /root/zerovantclaw/index.html
cp /var/www/zerovantclaw/mascot.png /root/zerovantclaw/mascot.png 2>/dev/null || true
git add index.html mascot.png

# Balik ke main
git checkout main
echo "Backup done: $(date)"
