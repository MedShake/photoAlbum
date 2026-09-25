from pathlib import Path
import shutil
import subprocess
import sys


FIXTURES = Path(__file__).parent / "fixtures"


def run_pack_lifecycle(package_root, work_directory):
    destination = package_root / "photoalbum/templates/testpack"
    if not destination.exists():
        shutil.copytree(FIXTURES / "template_packs/testpack", destination)
    result = subprocess.run(
        [sys.executable, "-I", str(FIXTURES / "run_pack_lifecycle.py"),
         str(package_root), str(work_directory)],
        cwd=work_directory, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
