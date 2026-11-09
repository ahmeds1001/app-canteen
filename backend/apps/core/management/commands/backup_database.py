"""Back up the SQL Server database and the dish photos into a folder (Windows server without Docker, run every night
by the task "Cantine - Sauvegarde" through setup/windows/backup.cmd, docs/installation-vm-windows.pdf step 12).

    python manage.py backup_database --dir D:\\CantineBackups

Writes <db>_<date>.bak (verified with RESTORE VERIFYONLY) and media_<date>\\ (a copy of the photos). Nothing is ever
deleted here: IT copies the folder off the server and decides how long to keep the files.
The SQL Server service account must be allowed to write into the folder (icacls, step 12 of the guide).
"""
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Back up the SQL Server database (verified) and the dish photos."

    def add_arguments(self, parser):
        parser.add_argument("--dir", required=True, help="Backup folder, e.g. D:\\CantineBackups")

    def handle(self, *args, dir: str, **options):
        if connection.vendor != "microsoft":
            raise CommandError("backup_database works with SQL Server only (DB_ENGINE=mssql).")
        folder = Path(dir)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M")
        name = connection.settings_dict["NAME"]
        target = folder / f"{name}_{stamp}.bak"
        with connection.cursor() as cursor:
            # BACKUP cannot run inside a transaction: Django's connections are in autocommit mode.
            cursor.execute(f"BACKUP DATABASE [{name}] TO DISK = %s WITH INIT, CHECKSUM", [str(target)])
            while cursor.nextset():  # drain the progress messages so the backup finishes before we check it
                pass
            cursor.execute("RESTORE VERIFYONLY FROM DISK = %s WITH CHECKSUM", [str(target)])
            while cursor.nextset():
                pass
        size = target.stat().st_size // 1024
        self.stdout.write(f"Database {name}: {target} ({size} KB, verified).")

        media = Path(settings.MEDIA_ROOT)
        if media.exists():
            copy = folder / f"media_{stamp}"
            shutil.copytree(media, copy)
            count = sum(1 for p in copy.rglob("*") if p.is_file())
            self.stdout.write(f"Photos: {copy} ({count} files).")
        else:
            self.stdout.write("Photos: none yet.")
