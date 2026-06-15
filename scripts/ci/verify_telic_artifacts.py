from __future__ import annotations

import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
import re

from packaging.version import Version


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
_ARTIFACT_VERSION_RE = re.compile(r"^telic-(?P<version>.+?)(?:-py3-none-any)?(?:\.tar\.gz|\.whl)$")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _artifact_paths() -> tuple[Path, Path]:
    wheels = sorted(DIST.glob("telic-*.whl"))
    sdists = sorted(DIST.glob("telic-*.tar.gz"))
    _assert(bool(wheels), "no wheel artifact found in dist/")
    _assert(bool(sdists), "no sdist artifact found in dist/")
    return _latest_artifact(wheels), _latest_artifact(sdists)


def _artifact_version(path: Path) -> Version:
    match = _ARTIFACT_VERSION_RE.match(path.name)
    _assert(match is not None, f"unrecognized artifact filename: {path.name}")
    version_text = str(match.group("version"))
    return Version(version_text)


def _latest_artifact(paths: list[Path]) -> Path:
    return max(paths, key=lambda current: _artifact_version(current))


def verify_wheel_contents(wheel_path: Path) -> None:
    with zipfile.ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
    expected = {
        "telic/__init__.py",
        "telic/assets/model_catalog.json",
        "telic/assets/model_catalog.schema.json",
        "telic/assets/model_catalog.schema.v2.json",
        "telic/assets/provider_source_manifest.json",
        "telic/py.typed",
    }
    missing = [name for name in expected if name not in names]
    _assert(not missing, f"wheel missing expected files: {missing}")


def verify_sdist_contents(sdist_path: Path) -> None:
    with tarfile.open(sdist_path, "r:gz") as archive:
        names = set(archive.getnames())
    expected_suffixes = [
        "/pyproject.toml",
        "/telic/__init__.py",
        "/telic/assets/model_catalog.json",
        "/telic/assets/model_catalog.schema.json",
        "/telic/assets/model_catalog.schema.v2.json",
        "/telic/assets/provider_source_manifest.json",
        "/telic/py.typed",
    ]
    for suffix in expected_suffixes:
        _assert(
            any(name.endswith(suffix) for name in names),
            f"sdist missing expected file suffix: {suffix}",
        )


def install_and_smoke_test(wheel_path: Path) -> None:
    expected_version = str(_artifact_version(wheel_path))
    with tempfile.TemporaryDirectory(prefix="telic-wheel-") as tmpdir:
        smoke = "\n".join(
            [
                "from importlib.metadata import version",
                "import sys",
                f"wheel_path = {str(wheel_path)!r}",
                f"repo_root = {str(ROOT)!r}",
                f"expected_version = {expected_version!r}",
                "sys.path = [p for p in sys.path if p not in ('', repo_root)]",
                "sys.path.insert(0, wheel_path)",
                "import telic",
                "import telic.content",
                "import telic.providers",
                "import telic.budgets",
                "import telic.cache",
                "import telic.agent",
                "import telic.observability",
                "assert version('telic') == expected_version",
                "print('telic wheel import smoke passed')",
            ]
        )
        subprocess.run(
            [sys.executable, "-c", smoke],
            check=True,
            cwd=tmpdir,
            text=True,
        )


def main() -> int:
    wheel_path, sdist_path = _artifact_paths()
    print(f"[telic artifacts] verifying wheel: {wheel_path.name}")
    verify_wheel_contents(wheel_path)
    print(f"[telic artifacts] verifying sdist: {sdist_path.name}")
    verify_sdist_contents(sdist_path)
    print("[telic artifacts] verifying wheel install smoke")
    install_and_smoke_test(wheel_path)
    print("[telic artifacts] verification complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
