"""
build_wheels.py — mono SDK protected wheel builder.

Usage:
    python build_wheels.py          # Build wheel for current platform
    python build_wheels.py --check  # Verify Nuitka is available

What this does:
    1. Compiles mono_sdk/internal/ → native .so/.pyd via Nuitka
    2. Copies compiled extensions + public stubs into dist/wheel_staging/
    3. Builds a wheel from the staging area (no Python source for internal/)
    4. Output: dist/mono_m2m_sdk-*.whl  (ready to upload to PyPI)

Source protection model:
    PUBLIC  (shipped as .py):  __init__.py, errors.py, models.py, cli.py
    PRIVATE (compiled to .so): client.py, langchain_tools.py, openai_functions.py
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

SDK_ROOT    = Path(__file__).parent
DIST_DIR    = SDK_ROOT / "dist"
STAGING_DIR = DIST_DIR / "wheel_staging"

# Files compiled to binary (source stays private)
PRIVATE_MODULES = [
    "client.py",
    "langchain_tools.py",
    "openai_functions.py",
]

# Files shipped as plain Python (public API surface)
PUBLIC_MODULES = [
    "__init__.py",
    "errors.py",
    "models.py",
    "cli.py",
]

PACKAGE_NAME    = "mono-m2m-sdk"
PACKAGE_IMPORT  = "mono_sdk"


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=False)


def check_nuitka() -> None:
    """Verify Nuitka is installed and print version."""
    result = subprocess.run(
        [sys.executable, "-m", "nuitka", "--version"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("ERROR: Nuitka not found. Install with:")
        print("  pip install nuitka ordered-set zstandard")
        sys.exit(1)
    print(f"Nuitka: {result.stdout.strip()}")


def nuitka_compile(source: Path, output_dir: Path) -> Path:
    """Compile a single .py file to a native extension via Nuitka.

    Returns the path to the compiled .so/.pyd file.
    """
    module_name = source.stem
    cmd = [
        sys.executable, "-m", "nuitka",
        "--module",                          # Output: importable extension
        f"--output-dir={output_dir}",
        "--remove-output",                   # Clean intermediate C files
        "--no-pyi-file",                     # No stub files in output
        "--python-flag=no_docstrings",       # Strip docstrings
        "--python-flag=no_asserts",          # Strip asserts
        f"--module-name-choice=runtime",
        str(source),
    ]

    # Platform-specific: use clang on macOS for smaller binaries
    if platform.system() == "Darwin":
        cmd.append("--clang")

    run(cmd)

    # Nuitka outputs e.g. client.cpython-311-darwin.so
    compiled = next(output_dir.glob(f"{module_name}*.so"), None) or \
               next(output_dir.glob(f"{module_name}*.pyd"), None)
    if not compiled:
        raise RuntimeError(f"Nuitka did not produce an extension for {source.name}")
    return compiled


def get_version() -> str:
    """Read version from pyproject.toml."""
    toml_path = SDK_ROOT / "sdk" / "pyproject.toml"
    for line in toml_path.read_text().splitlines():
        if line.strip().startswith("version"):
            return line.split("=")[1].strip().strip('"')
    raise RuntimeError("Version not found in pyproject.toml")


def build_protected_wheel() -> Path:
    """Full build pipeline → returns path to the built .whl file."""
    version = get_version()
    print(f"\n{'='*60}")
    print(f"  mono-m2m-sdk {version} — protected wheel build")
    print(f"{'='*60}\n")

    check_nuitka()

    # 1. Clean and recreate staging
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    pkg_dir = STAGING_DIR / PACKAGE_IMPORT
    pkg_dir.mkdir(parents=True)
    DIST_DIR.mkdir(exist_ok=True)

    # 2. Compile private modules with Nuitka
    compile_dir = DIST_DIR / "_nuitka_build"
    compile_dir.mkdir(exist_ok=True)

    print("Step 1/3: Compiling private modules with Nuitka...\n")
    for module_file in PRIVATE_MODULES:
        src = SDK_ROOT / "mono_sdk" / module_file
        if not src.exists():
            print(f"  SKIP {module_file} (not found)")
            continue
        print(f"  Compiling {module_file}...")
        compiled = nuitka_compile(src, compile_dir)
        dest = pkg_dir / compiled.name
        shutil.copy2(compiled, dest)
        print(f"  → {dest.name}")

    # 3. Copy public Python files as-is
    print("\nStep 2/3: Copying public Python modules...\n")
    for module_file in PUBLIC_MODULES:
        src = SDK_ROOT / "mono_sdk" / module_file
        if src.exists():
            shutil.copy2(src, pkg_dir / module_file)
            print(f"  → {module_file}")

    # 4. Copy examples/ and docs/ if present
    for extra in ["examples", "docs"]:
        src_dir = SDK_ROOT.parent / extra
        if src_dir.exists():
            shutil.copytree(src_dir, STAGING_DIR / extra, dirs_exist_ok=True)

    # 5. Write minimal pyproject.toml for wheel build (no sdist include)
    staging_pyproject = f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mono-m2m-sdk"
version = "{version}"
description = "Financial infrastructure for autonomous AI agents"
readme = "README.md"
requires-python = ">=3.9"
license = {{ text = "MIT" }}
authors = [{{ name = "mono", email = "hello@monospay.com" }}]
keywords = ["ai", "agents", "payments", "usdc", "settlement", "langchain"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
]
dependencies = []

[project.optional-dependencies]
langchain = ["langchain-core>=0.1.0"]

[project.scripts]
mono = "mono_sdk.cli:main"

[project.urls]
Homepage      = "https://monospay.com"
Documentation = "https://monospay.com/docs"
Repository    = "https://github.com/monospay/mono-sdk-examples"

[tool.hatch.build.targets.wheel]
packages = ["mono_sdk"]

[tool.hatch.build.targets.sdist]
# No sdist — wheels only. Source stays private.
include = []
"""
    (STAGING_DIR / "pyproject.toml").write_text(staging_pyproject)

    # Copy README
    readme = SDK_ROOT / "README.md"
    if readme.exists():
        shutil.copy2(readme, STAGING_DIR / "README.md")

    # 6. Build wheel from staging
    print("\nStep 3/3: Building wheel...\n")
    run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "."], cwd=STAGING_DIR)

    # Move wheel to dist/
    built = next((STAGING_DIR / "dist").glob("*.whl"), None)
    if not built:
        raise RuntimeError("Wheel build failed — no .whl found in staging dist/")

    final = DIST_DIR / built.name
    shutil.move(str(built), final)

    print(f"\n{'='*60}")
    print(f"  Built: {final}")
    print(f"  Size:  {final.stat().st_size / 1024:.1f} KB")
    print(f"{'='*60}\n")
    print("Upload to PyPI:")
    print(f"  twine upload dist/{final.name}")
    print("  (or: gh workflow run publish.yml)\n")

    return final


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build protected mono-m2m-sdk wheel")
    parser.add_argument("--check", action="store_true", help="Check Nuitka availability only")
    args = parser.parse_args()

    if args.check:
        check_nuitka()
        print("OK — Nuitka is available")
    else:
        build_protected_wheel()
