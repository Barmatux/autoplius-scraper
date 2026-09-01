# GitHub Actions: deploy to VM

Workflow: [`.github/workflows/deploy-vm.yml`](../.github/workflows/deploy-vm.yml)

Triggers:

- every push to `main`
- manual run (**Actions → Deploy to VM → Run workflow**)

## One-time setup

### 1. Repository secrets

In **Settings → Secrets and variables → Actions**, add:

| Secret | Example | Purpose |
|--------|---------|---------|
| `VM_HOST` | `84.252.139.137` | VM address |
| `VM_USER` | `romanshleg` | SSH login |
| `VM_SSH_PRIVATE_KEY` | contents of `id_ed25519` | key must match `~/.ssh/authorized_keys` on VM |

Generate a deploy key pair if needed:

```bash
ssh-keygen -t ed25519 -C "github-actions-autoplius" -f autoplius-deploy -N ""
# Append autoplius-deploy.pub to VM: ~romanshleg/.ssh/authorized_keys
# Paste autoplius-deploy private key into VM_SSH_PRIVATE_KEY secret
```

### 2. VM prerequisites

The VM must already have:

- git checkout at `/opt/autoplius-scraper` tracking `origin/main`
- `autoplius` user and `sudo -u autoplius git pull` working
- passwordless `sudo` for `VM_USER` to run `deploy-from-git.sh`
- Python venv at `/opt/autoplius-scraper/.venv`

Test manually:

```bash
ssh romanshleg@84.252.139.137 "sudo bash /opt/autoplius-scraper/deploy/deploy-from-git.sh"
```

### 3. What the pipeline does

1. SSH to VM
2. `deploy/deploy-from-git.sh`:
   - `git fetch` + `git pull --ff-only origin main`
   - `pip install -r requirements.txt`
   - refresh systemd units
   - `deploy/post-deploy-vm.sh` (SQL/pagination patches)
   - restart `autoplius-ui.service`
3. smoke tests: HTTP 200 on Flask `:8080` and nginx `:80`

Scraper code is picked up on the next timer run; the workflow does not restart an active scrape.

## Troubleshooting

- **pull fails (dirty tree)** — SSH to VM, inspect `git status`, commit or stash local changes, then re-run workflow.
- **patch WARN lines** — some deploy patches target VM-specific `app.py` blocks; merge VM UI changes into git to remove drift.
- **smoke test fails** — check `sudo journalctl -u autoplius-ui.service -n 50` on the VM.
