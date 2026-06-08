# Database Password File Fix (archived, redacted)

**Archived:** 2026-06-06. Original contained plaintext credentials — removed for security.

## Issue (historical)

The application could not connect to PostgreSQL because `.db_password_widow` was not found from the expected project directory.

## Resolution (historical)

- Password file location: project root `.db_password_widow` or `configs/.env` (`DB_PASSWORD`)
- Symlink created if file lived elsewhere

## Current authority

See [SECRETS_AND_SETTINGS_INDEX.md](../SECRETS_AND_SETTINGS_INDEX.md) and [DATABASE.md](../DATABASE.md). Passwords live only in Widow `configs/.env` or `.db_password_widow` — never in git-tracked markdown.

**Recommendation:** Rotate the Widow DB password if the original plaintext file was ever committed or shared.
