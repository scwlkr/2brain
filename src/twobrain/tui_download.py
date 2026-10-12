"""Install a pinned Bun binary from a checksum-verified npm distribution."""

import base64
import hashlib
import hmac
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from .errors import BrainError


def platform_package():
    system = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}.get(platform.system())
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "aarch64", "aarch64": "aarch64"}.get(platform.machine().lower())
    if not system or not arch:
        raise BrainError("OpenTUI supports macOS, Windows, and Linux on x64 or arm64.")
    musl = system == "linux" and (platform.libc_ver()[0] == "musl" or bool(list(Path("/lib").glob("ld-musl-*.so.1"))))
    return f"bun-{system}-{arch}" + ("-musl" if musl else "") + ("-baseline" if arch == "x64" else "")


def cache_home():
    if os.environ.get("TWOBRAIN_TUI_CACHE"):
        return Path(os.environ["TWOBRAIN_TUI_CACHE"]).expanduser().absolute()
    if sys.platform == "darwin":
        root = Path.home() / "Library/Caches"
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Cache"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "2brain/opentui"


def verify_integrity(path, integrity):
    algorithm, expected = integrity.split("-", 1)
    if algorithm != "sha512":
        raise BrainError("The Bun distribution must have a pinned SHA-512 checksum.")
    digest = hashlib.sha512()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if not hmac.compare_digest(base64.b64encode(digest.digest()).decode("ascii"), expected):
        raise BrainError("Bun download checksum mismatch. The unverified artifact was not installed.")


def install_bun(cache, metadata):
    package = platform_package()
    version = metadata["bun"]
    folder = cache / "bun" / f"{version}-{package}"
    target = folder / ("bun.exe" if os.name == "nt" else "bun")
    if target.is_file():
        try:
            result = subprocess.run([str(target), "--version"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BrainError(f"Cached Bun could not start: {target}. Remove this runtime directory and retry setup.") from exc
        if result.returncode == 0 and result.stdout.strip() == version:
            return target
        raise BrainError(f"Cached Bun is unusable: {target}. Remove this runtime directory and run 2brain tui --setup again.")
    distribution = metadata["distributions"][package]
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bun-download-", dir=cache) as temporary:
        archive = Path(temporary) / "bun.tgz"
        request = urllib.request.Request(distribution["url"], headers={"User-Agent": "2brain-runtime-setup"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        except OSError as exc:
            raise BrainError(f"Could not download the Bun runtime: {exc}. Check access to registry.npmjs.org and retry 2brain tui --setup.") from exc
        verify_integrity(archive, distribution["integrity"])
        candidate = Path(temporary) / target.name
        try:
            with tarfile.open(archive, "r:gz") as bundle:
                member = bundle.getmember(distribution["binary"])
                if not member.isfile():
                    raise BrainError("The verified Bun distribution did not contain a regular executable.")
                with bundle.extractfile(member) as source, candidate.open("wb") as output:
                    shutil.copyfileobj(source, output)
        except (tarfile.TarError, KeyError) as exc:
            raise BrainError("The verified Bun distribution could not be unpacked. Retry 2brain tui --setup.") from exc
        candidate.chmod(0o755)
        folder.mkdir(parents=True, exist_ok=True)
        os.replace(candidate, target)
    return target
