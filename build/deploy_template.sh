#!/bin/bash
# =============================================================================
# desknet's NEO storage check & pages update (Neoreka, 2026-10-11)
#
# Applies the changes made on TH_dneo:
#   1. /root/scripts/contractcheck.pl   - counts the PostgreSQL database
#                                         (auto-detects the running data dir)
#   2. /var/www/html/diskuse.cgi        - redesigned customer storage page (UTC+0)
#   3. /var/www/html/contract/index.cgi - redesigned administrator page
#   4. root crontab: fixes the broken certbot schedule "* */12 * * *" (runs every
#      minute for an hour, twice a day) to "30 4,16 * * *" (04:30 and 16:30 UTC)
#   5. Runs contractcheck.pl once so both pages show corrected usage now
#
# Usage (on the server):   sudo bash deploy_storage_update.sh
#   --no-run        install only; don't run contractcheck.pl now
#   --skip-certbot  leave the root crontab untouched
#   --dry-run       check everything and show what would change; change nothing
#
# Every replaced file (and the crontab) is backed up first to /root/backup-<timestamp>/.
# Existing owner and permissions of each file are kept.
# =============================================================================
set -u

RUN_CHECK=1
DRY_RUN=0
FIX_CERTBOT=1
for a in "$@"; do
  case "$a" in
    --no-run)       RUN_CHECK=0 ;;
    --skip-certbot) FIX_CERTBOT=0 ;;
    --dry-run)      DRY_RUN=1 ;;
    -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root:  sudo bash $0" >&2
  exit 1
fi

TS=$(date +%Y%m%d-%H%M%S)
BACKUP=/root/backup-storage-update-$TS
WORK=$(mktemp -d /tmp/storage-update.XXXXXX)
chmod 755 "$WORK"
trap 'rm -rf "$WORK"' EXIT
CRON_PATH=/sbin:/bin:/usr/sbin:/usr/bin
OK=0; SKIP=0; FAIL=0
RESULTS=()
ROLLBACK=()

say()  { printf '%s\n' "$*"; }
ok()   { RESULTS+=("OK    $*"); OK=$((OK+1)); }
skip() { RESULTS+=("SKIP  $*"); SKIP=$((SKIP+1)); }
fail() { RESULTS+=("FAIL  $*"); FAIL=$((FAIL+1)); }

# ---- embedded files (base64) -------------------------------------------------
decode() { base64 -d > "$2" <<<"$1"; }

B64_CONTRACTCHECK='__B64_CONTRACTCHECK__'
B64_DISKUSE='__B64_DISKUSE__'
B64_ADMIN='__B64_ADMIN__'
MD5_CONTRACTCHECK='__MD5_CONTRACTCHECK__'
MD5_DISKUSE='__MD5_DISKUSE__'
MD5_ADMIN='__MD5_ADMIN__'

decode "$B64_CONTRACTCHECK" "$WORK/contractcheck.pl"
decode "$B64_DISKUSE"       "$WORK/diskuse.cgi"
decode "$B64_ADMIN"         "$WORK/index.cgi"
chmod 644 "$WORK"/*

for f in contractcheck.pl:$MD5_CONTRACTCHECK diskuse.cgi:$MD5_DISKUSE index.cgi:$MD5_ADMIN; do
  n=${f%%:*}; m=${f#*:}
  if [ "$(md5sum "$WORK/$n" | cut -d' ' -f1)" != "$m" ]; then
    echo "ERROR: embedded $n is corrupted (checksum mismatch). Re-copy this script." >&2
    exit 1
  fi
done

say "== desknet's NEO storage update =="
say "Host:    $(hostname)"
say "Mode:    $([ $DRY_RUN -eq 1 ] && echo 'DRY RUN (no changes)' || echo 'APPLY')"

# ---- pre-checks --------------------------------------------------------------
command -v perl >/dev/null || { echo "ERROR: perl not found" >&2; exit 1; }
if ! perl -MCGI -e 1 2>/dev/null; then
  say "WARN: Perl CGI module missing; the admin page needs it (the original page did too)."
fi
WEBUSER=apache
id "$WEBUSER" >/dev/null 2>&1 || WEBUSER=$(stat -c %U /var/www/html 2>/dev/null || echo root)

PGDATA=$(ps -C postgres,postmaster -o args= 2>/dev/null | sed -n 's#^[^ ]*\(postgres\|postmaster\) .*-D *\(/[^ ]*\).*#\2#p' | head -1)
say "PostgreSQL data dir: ${PGDATA:-not detected (script falls back to its fixed path list)}"
say ""

# ---- back up one file (same path under $BACKUP) and remember how to restore it
backup() {
  local f=$1
  mkdir -p "$BACKUP" && chmod 700 "$BACKUP"
  cp -p --parents "$f" "$BACKUP/"
  ROLLBACK+=("cp -p '$BACKUP$f' '$f'")
}

# ---- install one file ----------------------------------------------------------
# install_file <new file> <target> <label> <cgi:0|1> <cgi working dir>
install_file() {
  local src=$1 dst=$2 label=$3 is_cgi=$4 cwd=$5
  if [ ! -e "$dst" ]; then
    skip "$label: $dst not found on this server (left as is)"
    return
  fi
  if cmp -s "$src" "$dst"; then
    skip "$label: already up to date"
    return
  fi
  if ! perl -c "$src" >/dev/null 2>&1; then
    fail "$label: syntax check failed on this server's Perl (not installed)"
    return
  fi
  if [ "$is_cgi" = 1 ]; then
    local out
    out=$(cd "$cwd" && sudo -u "$WEBUSER" env HTTP_HOST=localhost REQUEST_METHOD=GET perl "$src" 2>&1 | head -1)
    if [[ "$out" != Content-Type:* ]]; then
      fail "$label: test run failed (not installed): $out"
      return
    fi
  fi
  if [ $DRY_RUN -eq 1 ]; then
    ok "$label: would be updated ($dst)"
    return
  fi
  backup "$dst"
  # write into the existing file so its owner and permissions stay the same
  if cat "$src" > "$dst"; then
    ok "$label: updated ($dst)"
  else
    fail "$label: could not write $dst"
  fi
}

install_file "$WORK/contractcheck.pl" /root/scripts/contractcheck.pl   "Usage check script" 0 /
install_file "$WORK/diskuse.cgi"      /var/www/html/diskuse.cgi        "Customer page"      1 /var/www/html
install_file "$WORK/index.cgi"        /var/www/html/contract/index.cgi "Admin page"         1 /var/www/html/contract

# ---- fix the certbot schedule in root's crontab -----------------------------------
# "* */12 * * *" means every minute during hours 00 and 12 (120 runs a day, piling up
# in the morning business hours of UTC+7/+8 customers). Replace it with two runs a day.
CERTBOT_GOOD='30 4,16 * * * /usr/bin/certbot renew -q >/dev/null 2>&1'
CERTBOT_BAD_RE='^\*[[:space:]]+\*/12[[:space:]]+\*[[:space:]]+\*[[:space:]]+\*[[:space:]]+.*certbot[[:space:]]+renew'
fix_certbot() {
  local cur new
  if ! cur=$(crontab -l 2>/dev/null); then
    skip "certbot schedule: root has no crontab"
    return
  fi
  if ! grep -q 'certbot' <<<"$cur"; then
    skip "certbot schedule: no certbot line in root's crontab"
    return
  fi
  if ! grep -Eq "$CERTBOT_BAD_RE" <<<"$cur"; then
    skip "certbot schedule: already OK or customised (left as is): $(grep -m1 certbot <<<"$cur")"
    return
  fi
  local line
  new=$(while IFS= read -r line; do
          if [[ $line =~ $CERTBOT_BAD_RE ]]; then printf '%s\n' "$CERTBOT_GOOD"; else printf '%s\n' "$line"; fi
        done <<<"$cur")
  if [ $DRY_RUN -eq 1 ]; then
    ok "certbot schedule: would change to '$CERTBOT_GOOD'"
    return
  fi
  mkdir -p "$BACKUP" && chmod 700 "$BACKUP"
  printf '%s\n' "$cur" > "$BACKUP/root.crontab"
  if printf '%s\n' "$new" | crontab -; then
    # verify: the fixed line is there and the broken one is gone, otherwise put the original back
    cur=$(crontab -l 2>/dev/null)
    if grep -qxF "$CERTBOT_GOOD" <<<"$cur" && ! grep -Eq "$CERTBOT_BAD_RE" <<<"$cur"; then
      ROLLBACK+=("crontab '$BACKUP/root.crontab'")
      ok "certbot schedule: changed to '$CERTBOT_GOOD'"
    else
      crontab "$BACKUP/root.crontab"
      fail "certbot schedule: verification failed, original crontab restored"
    fi
  else
    fail "certbot schedule: could not write root's crontab (unchanged)"
  fi
}
if [ $FIX_CERTBOT -eq 1 ]; then
  fix_certbot
fi

# ---- run the usage check once ---------------------------------------------------
USAGE=/var/www/html/contract/.usage
BEFORE=""; AFTER=""
[ -f "$USAGE" ] && BEFORE=$(cut -d'|' -f3 "$USAGE")
if [ $RUN_CHECK -eq 1 ] && [ $DRY_RUN -eq 0 ] && [ -x /root/scripts/contractcheck.pl ]; then
  for f in "$USAGE" /var/www/html/contract/.old; do
    [ -f "$f" ] && backup "$f"
  done
  if env -i PATH=$CRON_PATH SHELL=/bin/bash /root/scripts/contractcheck.pl; then
    AFTER=$(cut -d'|' -f3 "$USAGE" 2>/dev/null)
    ok "Usage check: ran once"
  else
    fail "Usage check: contractcheck.pl exited with an error"
  fi
elif [ $RUN_CHECK -eq 1 ] && [ $DRY_RUN -eq 0 ]; then
  skip "Usage check: /root/scripts/contractcheck.pl not found or not executable"
fi

# ---- summary -----------------------------------------------------------------
gb() { awk -v k="$1" 'BEGIN{ printf "%.2f GB", int(k/1024/1024*100)/100 }'; }
say "== Result =="
for r in "${RESULTS[@]}"; do say "  $r"; done
if [ -n "$BEFORE" ] && [ -n "$AFTER" ]; then
  say ""
  say "Measured usage: $(gb "$BEFORE")  ->  $(gb "$AFTER")"
fi
if [ -d "$BACKUP" ]; then
  say ""
  say "Backups: $BACKUP"
  say "To roll back, run:"
  for r in "${ROLLBACK[@]}"; do say "  sudo $r"; done
fi
say ""
say "Done: $OK ok, $SKIP skipped, $FAIL failed."
[ $FAIL -eq 0 ]
