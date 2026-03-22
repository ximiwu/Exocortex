from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "Exocortex"
APP_VERSION = "0.1.0"
APP_PUBLISHER = "Exocortex"
ENTRY_SCRIPT = "run_web.py"
ICON_FILE = "icon.ico"

STAGE_DEPENDENCIES = "dependencies"
STAGE_FRONTEND = "frontend"
STAGE_PACKAGE = "package"
STAGE_INSTALLER = "installer"
STAGE_VALIDATE = "validate"
VALID_STAGES = (
    STAGE_DEPENDENCIES,
    STAGE_FRONTEND,
    STAGE_PACKAGE,
    STAGE_INSTALLER,
    STAGE_VALIDATE,
)

REPO_ROOT = Path(__file__).resolve().parent
WEB_DIR = REPO_ROOT / "web"
WEB_DIST_DIR = WEB_DIR / "dist"
PROMPTS_DIR = REPO_ROOT / "prompts"
DIST_ROOT = REPO_ROOT / "dist"
INSTALLER_OUTPUT_DIR = REPO_ROOT / "Output_Installers"
ISS_PATH = REPO_ROOT / "setup_script.iss"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Exocortex desktop package in explicit stages.")
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=VALID_STAGES,
        help=(
            "Stages to run in order. Defaults to: "
            "dependencies frontend package installer validate."
        ),
    )
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip dependency install and frontend build stages; use an existing web/dist.",
    )
    parser.add_argument(
        "--skip-installer",
        action="store_true",
        help="Skip installer generation stage.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previous Nuitka and installer outputs before building.",
    )
    return parser.parse_args()


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    printable = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    print(f"> {printable}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def require_path(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")


def find_npm() -> str:
    candidates = ["npm.cmd", "npm"] if sys.platform == "win32" else ["npm"]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("`npm` was not found. Install Node.js first.")


def find_iscc() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Inno Setup compiler `ISCC.exe` was not found.")


def require_python_module(module_name: str) -> None:
    if importlib.util.find_spec(module_name) is None:
        raise ModuleNotFoundError(
            f"Python module `{module_name}` is not installed in the current environment "
            f"({sys.executable})."
        )


def find_nuitka_dist_dir() -> Path:
    direct_candidates = [
        DIST_ROOT / f"{Path(ENTRY_SCRIPT).stem}.dist",
        DIST_ROOT / f"{APP_NAME}.dist",
    ]
    for candidate in direct_candidates:
        if candidate.is_dir():
            return candidate

    matching_dirs = sorted(path for path in DIST_ROOT.glob("*.dist") if path.is_dir())
    if len(matching_dirs) == 1:
        return matching_dirs[0]
    if matching_dirs:
        raise FileNotFoundError(
            "Multiple Nuitka dist directories found, could not determine the correct one: "
            + ", ".join(str(path) for path in matching_dirs)
        )
    raise FileNotFoundError(f"No Nuitka dist directory found under: {DIST_ROOT}")


def expected_installer_path() -> Path:
    return INSTALLER_OUTPUT_DIR / f"{APP_NAME}_Setup_v{APP_VERSION}.exe"


def clean_outputs() -> None:
    if DIST_ROOT.exists():
        print(f"Removing {DIST_ROOT}")
        shutil.rmtree(DIST_ROOT)
    if INSTALLER_OUTPUT_DIR.exists():
        print(f"Removing {INSTALLER_OUTPUT_DIR}")
        shutil.rmtree(INSTALLER_OUTPUT_DIR)
    if ISS_PATH.exists():
        print(f"Removing {ISS_PATH}")
        ISS_PATH.unlink()


def run_dependency_stage(*, expect_installer: bool) -> None:
    require_path(WEB_DIR / "package.json", "Frontend package.json")
    npm = find_npm()
    print("Installing frontend dependencies with npm ci...")
    run([npm, "ci"], cwd=WEB_DIR)
    require_python_module("nuitka")
    if expect_installer:
        find_iscc()


def run_frontend_stage() -> None:
    require_path(WEB_DIR / "package.json", "Frontend package.json")
    npm = find_npm()
    print("Building frontend...")
    run([npm, "run", "build"], cwd=WEB_DIR)
    require_path(WEB_DIST_DIR / "index.html", "Frontend build output")


def build_with_nuitka() -> Path:
    require_python_module("nuitka")
    require_path(REPO_ROOT / ENTRY_SCRIPT, "Entry script")
    require_path(REPO_ROOT / ICON_FILE, "Icon file")
    require_path(PROMPTS_DIR, "Prompts directory")
    require_path(WEB_DIST_DIR, "Frontend dist directory")

    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    build_dir = DIST_ROOT / f"{APP_NAME}.build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    for candidate in (DIST_ROOT / f"{Path(ENTRY_SCRIPT).stem}.dist", DIST_ROOT / f"{APP_NAME}.dist"):
        if candidate.exists():
            shutil.rmtree(candidate)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        f"--output-dir={DIST_ROOT}",
        f"--output-filename={APP_NAME}.exe",
        f"--windows-icon-from-ico={REPO_ROOT / ICON_FILE}",
        "--windows-console-mode=disable",
        "--assume-yes-for-downloads",
        "--msvc=latest",
        "--nofollow-import-to=playwright",
        "--nofollow-import-to=pytest,_pytest",
        "--noinclude-custom-mode=pymupdf.mupdf:bytecode",
        f"--product-name={APP_NAME}",
        f"--company-name={APP_PUBLISHER}",
        f"--file-version={APP_VERSION}",
        f"--product-version={APP_VERSION}",
        f"--file-description={APP_NAME}",
        f"--include-data-dir={WEB_DIST_DIR}=web/dist",
        f"--include-data-dir={PROMPTS_DIR}=prompts",
        f"--include-data-files={REPO_ROOT / ICON_FILE}=icon.ico",
        str(REPO_ROOT / ENTRY_SCRIPT),
    ]

    print("Building standalone app with Nuitka...")
    run(cmd, cwd=REPO_ROOT)

    output_dir = find_nuitka_dist_dir()
    exe_path = output_dir / f"{APP_NAME}.exe"
    require_path(exe_path, "Nuitka output executable")
    return output_dir


def _win(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\")


def generate_iss_script(app_dir: Path) -> Path:
    INSTALLER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    iss_content = f"""
[Setup]
AppName={APP_NAME}
AppVersion={APP_VERSION}
AppPublisher={APP_PUBLISHER}
DefaultDirName={{autopf}}\\{APP_NAME}
DefaultGroupName={APP_NAME}
OutputDir={_win(INSTALLER_OUTPUT_DIR)}
OutputBaseFilename={APP_NAME}_Setup_v{APP_VERSION}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile={_win(REPO_ROOT / ICON_FILE)}
PrivilegesRequired=lowest
UninstallDisplayIcon={{app}}\\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "{_win(app_dir)}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"; IconFilename: "{{app}}\\icon.ico"
Name: "{{group}}\\{{cm:UninstallProgram,{APP_NAME}}}"; Filename: "{{uninstallexe}}"
Name: "{{userdesktop}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"; IconFilename: "{{app}}\\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{APP_NAME}.exe"; Description: "{{cm:LaunchProgram,{APP_NAME}}}"; Flags: nowait postinstall skipifsilent
""".strip()

    ISS_PATH.write_text(iss_content + "\n", encoding="utf-8")
    print(f"Generated installer script: {ISS_PATH}")
    return ISS_PATH


def build_installer(iss_path: Path) -> None:
    iscc = find_iscc()
    print("Building installer with Inno Setup...")
    run([str(iscc), str(iss_path)], cwd=REPO_ROOT)


def run_packaging_stage() -> Path:
    return build_with_nuitka()


def run_installer_stage(app_dir: Path | None) -> Path:
    resolved_app_dir = app_dir or find_nuitka_dist_dir()
    iss_path = generate_iss_script(resolved_app_dir)
    build_installer(iss_path)
    print(f"Installer output: {INSTALLER_OUTPUT_DIR.resolve()}")
    return resolved_app_dir


def run_validation_stage(*, expect_installer: bool) -> None:
    require_path(WEB_DIST_DIR / "index.html", "Frontend build output")
    app_dir = find_nuitka_dist_dir()
    require_path(app_dir / f"{APP_NAME}.exe", "Nuitka output executable")
    if expect_installer:
        require_path(expected_installer_path(), "Installer output")
    print("Artifact validation passed.")


def resolve_stages(args: argparse.Namespace) -> list[str]:
    stages = list(args.stages) if args.stages else list(VALID_STAGES)
    if args.skip_frontend:
        stages = [stage for stage in stages if stage not in {STAGE_DEPENDENCIES, STAGE_FRONTEND}]
    if args.skip_installer:
        stages = [stage for stage in stages if stage != STAGE_INSTALLER]
    if not stages:
        raise ValueError("No stages selected. Remove skip flags or pass explicit --stages values.")
    return stages


def main() -> int:
    args = parse_args()

    try:
        if args.clean:
            clean_outputs()

        stages = resolve_stages(args)
        expect_installer = STAGE_INSTALLER in stages
        app_dir: Path | None = None

        for stage in stages:
            if stage == STAGE_DEPENDENCIES:
                run_dependency_stage(expect_installer=expect_installer)
            elif stage == STAGE_FRONTEND:
                run_frontend_stage()
            elif stage == STAGE_PACKAGE:
                app_dir = run_packaging_stage()
                print(f"Nuitka app output: {app_dir.resolve()}")
            elif stage == STAGE_INSTALLER:
                app_dir = run_installer_stage(app_dir)
            elif stage == STAGE_VALIDATE:
                run_validation_stage(expect_installer=expect_installer)

        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}: {exc.cmd}", file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
