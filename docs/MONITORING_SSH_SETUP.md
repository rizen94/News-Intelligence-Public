# Monitoring SSH Setup — Passwordless Access to Remote Devices

The resource dashboard (Monitoring tab) can collect **disk usage** and **process list** from remote devices (Widow, NAS, Pi) by SSH-ing from the **API host** (Legion/Primary) and running `df` and `ps`. This requires **passwordless SSH** (key-based) so the API can run commands without a prompt.

---

## 1. Overview

| Machine   | IP            | Role                          |
|-----------|---------------|-------------------------------|
| **Legion** (API host) | <PRIMARY_HOST_IP> (or your dev machine) | Where the API runs; must be able to `ssh user@remote` without password |
| **Widow** | <WIDOW_HOST_IP> | Database server               |
| **NAS**   | <NAS_HOST_IP> | Storage / legacy DB target    |
| **Pi**    | <MONITORING_PI_IP> | Raspberry Pi (monitoring, etc.) |

The API uses:

- `ssh -o BatchMode=yes {user}@{host} "df ..."` and `"ps ..."` to get disk and processes.
- User: per-device `ssh_user` in `api/config/monitoring_devices.yaml`, or env **`MONITORING_SSH_USER`**, or the API process user (e.g. `newsapp`).

---

## 2. Set up SSH keys on the Pi (<MONITORING_PI_IP>)

These steps are for the **Pi**; the same idea applies to Widow and NAS.

### 2.1 On the API host (Legion)

1. **Create an SSH key** (if you don’t already have one for this purpose):

   ```bash
   ssh-keygen -t ed25519 -C "monitoring-api" -f ~/.ssh/monitoring_ed25519 -N ""
   ```

   Or reuse an existing key, e.g. `~/.ssh/id_ed25519`.

2. **Copy the public key to the Pi** (one-time; you’ll need the Pi’s password this time):

   ```bash
   ssh-copy-id -i ~/.ssh/monitoring_ed25519.pub pi@<MONITORING_PI_IP>
   ```

   If the Pi uses a different user, replace `pi` (e.g. `newsapp@<MONITORING_PI_IP>`).  
   If you use a non-default key:

   ```bash
   ssh-copy-id -i ~/.ssh/monitoring_ed25519.pub -o IdentitiesOnly=yes pi@<MONITORING_PI_IP>
   ```

3. **Test passwordless login**:

   ```bash
   ssh -i ~/.ssh/monitoring_ed25519 -o BatchMode=yes pi@<MONITORING_PI_IP> "echo ok"
   ```

   You should see `ok` with no password prompt.

### 2.2 Make the API use this key when calling the Pi

The API runs as a user (e.g. the same user you use on Legion, or `newsapp`). That user must be able to SSH to the Pi without a password.

- **Option A — Same user on Legion and Pi:**  
  If you ran `ssh-copy-id` as the same user that runs the API, and the default key is `~/.ssh/id_ed25519` (or `id_rsa`), the API will usually pick it up automatically.

- **Option B — Dedicated key for monitoring:**  
  If you use a key like `~/.ssh/monitoring_ed25519`, configure SSH to use it for the Pi (and optionally Widow/NAS). As the user that runs the API, create or edit `~/.ssh/config`:

  ```
  Host <MONITORING_PI_IP>
      User pi
      IdentityFile ~/.ssh/monitoring_ed25519
      IdentitiesOnly yes

  Host <WIDOW_HOST_IP>
      User newsapp
      IdentityFile ~/.ssh/monitoring_ed25519
      IdentitiesOnly yes
  ```

  Then test again:

  ```bash
  ssh <MONITORING_PI_IP> "echo ok"
  ```

### 2.3 Configure the monitoring config for the Pi

In `api/config/monitoring_devices.yaml`, set the Pi `host` to the same LAN IP you use above (the Overview table uses placeholders like `<MONITORING_PI_IP>` in docs; the YAML file must contain a **real routable IP** for SSH). If the Pi user is not the same as `MONITORING_SSH_USER` or the API user, set `ssh_user` for the Pi:

```yaml
  - name: Pi
    type: remote
    host: "192.0.2.3"
    description: "Raspberry Pi (monitoring, document source, etc.)"
    ssh_user: pi
```

Use your Pi’s actual IP instead of the documentation example `192.0.2.3`.

Restart the API (or wait for the next dashboard request). The Monitoring tab should show disk and processes for the Pi.

---

## 3. Widow and NAS

Same idea:

1. On the API host, ensure you have a key and copy it to Widow/NAS:
   - Widow: `ssh-copy-id -i ~/.ssh/monitoring_ed25519.pub newsapp@<WIDOW_HOST_IP>` (or whatever user runs there).
   - NAS: `ssh-copy-id ... user@<NAS_HOST_IP>` (user depends on NAS OS).

2. Add `Host` entries in `~/.ssh/config` if you use a non-default key.

3. In `monitoring_devices.yaml`, set `ssh_user` per device if the username differs from the default.

---

## 4. Troubleshooting

| Symptom | What to check |
|--------|----------------|
| Dashboard shows Pi (or other remote) as **error** / **unavailable** | From the API host, run `ssh -o BatchMode=yes pi@<MONITORING_PI_IP> "df -B1"`. If it prompts for a password, key-based login is not in place. |
| Permission denied (publickey) | `ssh-copy-id` not done for that user/host, or wrong key in `~/.ssh/config`, or wrong `ssh_user` in config. |
| Connection timed out | Firewall, or host down, or wrong IP. Ping `<MONITORING_PI_IP>`. |
| `df` or `ps` not found on remote | API uses `df -B1` and `ps -o pid,comm,%mem,%cpu` (Linux). BusyBox/small distros may have different `df`; the code has a fallback. If `ps` format differs, parsing may need adjustment. |

---

## 5. Security notes

- Use a **dedicated key** for monitoring (e.g. `monitoring_ed25519`) with no passphrase so the API can run non-interactively.
- Restrict that key on the Pi (and other remotes) if possible, e.g. in `~/.ssh/authorized_keys`:
  ```
  command="echo read-only" ssh-ed25519 AAAA... monitoring-api
  ```
  Note: the API only runs `df` and `ps` (and optionally `du` for a path). Restricting the key to a single command is possible but more involved; for many setups, key-based access with a limited user is acceptable.
- Ensure the API host’s SSH private key is not readable by other users or services.

---

*After keys are set up, the Monitoring tab’s “Devices” section will show disk usage and top processes for Legion (local), Widow, NAS, and Pi without deploying an HTTP agent on each.*
