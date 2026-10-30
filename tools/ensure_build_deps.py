"""Prepare py65 for execution tests and optional extraction (not ROM builds)."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'build/python-deps'


def enable_windows_inheritance():
    """Pip moves directories from TEMP, which can carry a private Windows ACL."""
    if sys.platform != 'win32' or not TARGET.exists():
        return
    target = TARGET.resolve()
    if not target.is_relative_to((ROOT/'build').resolve()):
        raise ValueError(f'Refusing to change permissions outside build: {target}')
    # Only generated dependencies: inherit the workspace's existing access
    # rules rather than grant broad permissions or require an administrator.
    # Pip replaces these entries. Their parent may belong to another account,
    # so leave the parent ACL alone (Modify does not include changing ACLs).
    for entry in target.iterdir():
        if not entry.resolve().is_relative_to(target):
            raise ValueError(f'Refusing to change permissions outside dependencies: {entry}')
        subprocess.run(['icacls', str(entry), '/inheritance:e', '/T', '/C'],
                       check=True, stdout=subprocess.DEVNULL)


def check():
    # Use a fresh process, including after pip repairs an incomplete package.
    code = (
        'import sys; sys.path.insert(0, sys.argv[1]); '
        'from py65.devices.mpu6502 import MPU; MPU(); '
        'from py65.devices.mpu65c02 import MPU; MPU()'
    )
    return subprocess.run([sys.executable, '-c', code, str(TARGET)],
                          capture_output=True, text=True)


def main():
    result = check()
    if result.returncode == 0:
        return 0
    print(f'py65 CPU modules unavailable. Installing test/extraction dependencies with {sys.executable}',
          flush=True)
    command = [sys.executable, '-m', 'pip', '--disable-pip-version-check', 'install', '--upgrade',
               '--target', str(TARGET), '-r', str(ROOT/'requirements-build.txt')]
    result = subprocess.run(command)
    if result.returncode:
        print('Dependency installation failed. Retry this command:\n' +
              subprocess.list2cmdline(command), file=sys.stderr)
        return result.returncode
    enable_windows_inheritance()
    result = check()
    if result.returncode:
        print(result.stderr, file=sys.stderr, end='')
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
