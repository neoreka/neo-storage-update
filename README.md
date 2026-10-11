# desknet's NEO storage check & pages update

Fixes and redesigns for the NET-ING storage-usage tooling on hosted desknet's NEO servers (EC2).
First applied to TH_dneo on 2026-10-11.

## What it changes

| File on the server | Change |
|---|---|
| `/root/scripts/contractcheck.pl` | Counts the PostgreSQL database in storage usage. The original only looked in fixed paths (`/var/lib/pgsql16/data` and similar), so servers with PostgreSQL elsewhere (for example `/var/pgsql/data`) under-reported usage. It now asks the running PostgreSQL for its data directory (`-D`), falling back to the old paths. |
| `/var/www/html/diskuse.cgi` | Redesigned customer storage page: usage bar, Normal / Approaching limit / Exceeded status, usage by app (with a "Database & other data" row), UTC+0 timestamps, mobile and dark-mode support. |
| `/var/www/html/contract/index.cgi` | Redesigned administrator page: customer name and allocated size form, usage summary, 7-day history. Alert threshold and contract type are no longer shown, but are kept when saving. Shows an "Only for internal use" banner. |

The calculations, the alert rule and the save behaviour are unchanged. Nothing is customer-specific: the customer name and allocation come from each server's `contract/.data`.

## Deploy to a server

```bash
scp -i KEY.pem deploy_storage_update.sh ec2-user@SERVER_IP:/tmp/
```

On the server:

```bash
sudo bash /tmp/deploy_storage_update.sh --dry-run
```

```bash
sudo bash /tmp/deploy_storage_update.sh
```

Options:

- `--dry-run`: show what would change, change nothing.
- `--no-run`: install only; don't run the usage check now (it runs daily at 06:00 UTC anyway).

For each file, the script skips it if it's missing or already up to date. Otherwise it tests the new version with that server's Perl (CGI pages are test-run as the web server user), backs up the current file to `/root/backup-storage-update-<time>/`, and replaces it, keeping the owner and permissions. Locally modified versions are also replaced; check the dry run first. At the end it prints a summary and the exact rollback commands.

After running, customer usage jumps by the size of their database. That's the fix taking effect, not growth.

## Roll back

Run the `sudo cp -p ...` lines printed at the end of the deploy. Backups are in `/root/backup-storage-update-<time>/`, with the original paths kept underneath.

## Editing

1. Edit the files in `src/`.
2. Rebuild the deploy script: `python3 build/build.py`.
3. Test with `--dry-run` on a server, then commit `src/`, `build/` and `deploy_storage_update.sh` together.

`deploy_storage_update.sh` is generated. Don't edit it directly.

## Layout

```
deploy_storage_update.sh    generated, self-contained deploy script (copy this to servers)
src/contractcheck.pl        -> /root/scripts/contractcheck.pl
src/diskuse.cgi             -> /var/www/html/diskuse.cgi
src/contract/index.cgi      -> /var/www/html/contract/index.cgi
build/deploy_template.sh    deploy logic, with placeholders for the embedded files
build/build.py              embeds src/ into the template
```

## Not included

- **Zabbix CPU trigger override** for TH_dneo: configured in the Zabbix UI per host, not on servers.
- **Security issues still open on these servers:** `/root/scripts/` is world-writable but run by root's cron, and `/contract/` has no access restriction.
- **Tested on:** Amazon Linux 2023, PostgreSQL 16.3.
