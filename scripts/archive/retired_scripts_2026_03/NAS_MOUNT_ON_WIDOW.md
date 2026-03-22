# Mount NAS on Widow so backups and archives use NAS storage

On **Widow**, `/mnt/nas` and the directory layout are already created. Right now they live on Widow's disk. To send backups and log archives to the **NAS** instead:

1. **Mount the NAS** at `/mnt/nas` (NFS or SMB/CIFS).
2. Ensure the same layout exists on the NAS share (or create it after mounting):
   - `backups/daily`, `backups/weekly`
   - `news-intelligence/logs`, `news-intelligence/cold-export`

## Option A: NFS (if your NAS exports NFS)

On Widow:

```bash
sudo apt-get install -y nfs-common
# Add to /etc/fstab (adjust <NAS_HOST_IP> and share path to your NAS):
# <NAS_HOST_IP>:/share/news-platform  /mnt/nas  nfs  defaults,soft,timeo=150,retrans=3,_netdev  0  0
sudo mount -a
```

## Option B: SMB/CIFS

On Widow:

```bash
sudo apt-get install -y cifs-utils
sudo mkdir -p /etc/nas-credentials
echo "username=YourNASUser" | sudo tee /etc/nas-credentials
echo "password=YourNASPass" | sudo tee -a /etc/nas-credentials
sudo chmod 600 /etc/nas-credentials
# Add to /etc/fstab (adjust share path):
# //<NAS_HOST_IP>/share-name  /mnt/nas  cifs  credentials=/etc/nas-credentials,uid=$(id -u),gid=$(id -g),iocharset=utf8,_netdev  0  0
sudo mount -a
```

Then recreate the directory layout on the mounted share (if the share is empty):

```bash
mkdir -p /mnt/nas/backups/daily /mnt/nas/backups/weekly /mnt/nas/news-intelligence/logs /mnt/nas/news-intelligence/cold-export
```

## Verify

```bash
mountpoint /mnt/nas && df -h /mnt/nas
ls /mnt/nas/backups/daily /mnt/nas/news-intelligence/logs
```

After this, `db_backup.sh` and `db_backup_weekly.sh` (cron) and `archive_logs_to_nas.sh` (cron 5 AM) will use NAS storage.
