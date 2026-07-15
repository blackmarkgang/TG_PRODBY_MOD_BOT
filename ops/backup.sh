#!/bin/sh
set -eu

case "${BACKUP_RETENTION_DAYS:-14}" in
  *[!0-9]*|"") echo "BACKUP_RETENTION_DAYS must be a positive integer" >&2; exit 1 ;;
esac

case "${BACKUP_INTERVAL_SECONDS:-86400}" in
  *[!0-9]*|"") echo "BACKUP_INTERVAL_SECONDS must be a positive integer" >&2; exit 1 ;;
esac

mkdir -p /backups

create_backup() {
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="/backups/prodby_${timestamp}.dump"
  temporary="${target}.tmp"

  rm -f "$temporary"
  pg_dump --format=custom --no-owner --no-privileges --file "$temporary"
  pg_restore --list "$temporary" >/dev/null
  mv "$temporary" "$target"

  find /backups -maxdepth 1 -type f -name 'prodby_*.dump' \
    -mtime "+${BACKUP_RETENTION_DAYS}" -delete
  find /backups -maxdepth 1 -type f -name '*.tmp' -mtime +1 -delete
  echo "Backup created: $target"
}

if [ "${1:-}" = "--once" ]; then
  create_backup
  exit 0
fi

create_backup
while sleep "$BACKUP_INTERVAL_SECONDS"; do
  create_backup
done
