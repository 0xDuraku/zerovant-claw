#!/bin/bash
cd /root/zerovantclaw
git add .
git diff --cached --quiet || git commit -m "auto-backup $(date '+%Y-%m-%d %H:%M')"
git push origin main
