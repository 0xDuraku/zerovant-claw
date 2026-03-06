#!/bin/bash
while true; do
  if ! systemctl is-active --quiet zerovant-grid.service; then
    echo "$(date): Grid bot down, restarting..." >> /var/log/zerovant-watchdog.log
    systemctl restart zerovant-grid.service
  fi
  if ! systemctl is-active --quiet zerovant-tgbot.service; then
    echo "$(date): TG bot down, restarting..." >> /var/log/zerovant-watchdog.log
    systemctl restart zerovant-tgbot.service
  fi
  sleep 60
done
