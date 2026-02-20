import subprocess
from datetime import datetime
import os

ARCHIVOS_BACKUP = ["inventario.db", "escaneos.csv"]

def backup_to_github():
    try:
        existentes = [f for f in ARCHIVOS_BACKUP if os.path.exists(f)]
        if not existentes:
            return
        
        subprocess.run(["git", "add"] + existentes, check=True)
        subprocess.run(["git", "commit", "-m", f"Backup automático {datetime.now()}"], check=True)
        subprocess.run(["git", "push"], check=True)
        
    except Exception as e:
        print("Error backup:", e)


def restore_from_github():
    try:
        subprocess.run(["git", "pull"], check=True)
    except:
        pass
