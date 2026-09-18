# Windows installation (WSL2)

Native Windows is **not** a supported runtime. The kit installs into **WSL2 Ubuntu** with **Docker Desktop**.

## Steps

1. Double-click **`INSTALL-WINDOWS.bat`** (Run as Administrator on first run).
2. If prompted, reboot after WSL installation.
3. Start **Docker Desktop** and wait until it is running.
4. Run **`INSTALL-WINDOWS.bat`** again — it copies the kit to `~/news-intelligence-kit` in WSL and runs `./install.sh`.
5. Browser opens **http://localhost:8080/setup/**

## Repair from Windows

```bat
powershell -ExecutionPolicy Bypass -File install-windows.ps1 -Repair
```

## Manual WSL path

```powershell
wsl -d Ubuntu
cd ~/news-intelligence-kit
./install.sh
```

## Tips

- Keep the project under the Linux home directory, not `/mnt/c/...`
- Allocate ≥ 8 GB RAM to WSL in `.wslconfig`
- Enable WSL integration for Docker Desktop

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if Postgres or Ollama fail to start.
