# Security

## Secrets

- Put secrets in `.env.local`, not in git.
- Keep `.env.example` as the shareable template.
- Do not commit API keys, private keys, or wallet material.

## Variables that deserve attention

- `OPENAI_API_KEY`
- `OPENAI_BACKUP_API_KEY`
- `OPENAI_FALLBACK_API_KEY`
- `ODDPOOL_API_KEY`
- `POLYMARKET_PRIVATE_KEY`
- `POLYMARKET_CLOB_API_KEY`
- `POLYMARKET_CLOB_API_SECRET`
- `POLYMARKET_CLOB_PASSPHRASE`

## Before upload

Run a quick scan for anything sensitive:

```bash
rg -n "sk-[A-Za-z0-9_-]{12,}|PRIVATE_KEY|API_KEY|PASS_PHRASE|passphrase|secret" .
```

If you add a new secret-bearing setting later, update `.gitignore`, `.env.example`, and the docs together.

