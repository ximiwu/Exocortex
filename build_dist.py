import os
import subprocess
import shutil

# ================= 配置区域 =================
APP_NAME = "Exocortex"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "MyCompany" 
MAIN_SCRIPT = "Exocortex.py"
ICON_FILE = "icon.ico"     # 确保这个文件就在当前脚本旁边
OUTPUT_DIR = "dist"

# Nuitka 生成的文件夹名称
NUITKA_OUTPUT_FOLDER = os.path.join(OUTPUT_DIR, f"{os.path.splitext(MAIN_SCRIPT)[0]}.dist")
ISCC_PATH = r"C:/Program Files (x86)/Inno Setup 6/ISCC.exe"
# ===========================================

def run_nuitka():
    print(f"🚀 开始 Nuitka 编译: {MAIN_SCRIPT}...")
    # 如果已经编译过且不想重新编译，可以临时注释掉下面这块
    cmd = [
        "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--include-data-dir=prompts=prompts",
        "--include-data-dir=pdf_block_gui_lib/static=pdf_block_gui_lib/static",
        f"--output-dir={OUTPUT_DIR}",
        "--msvc=latest",
        f"--windows-icon-from-ico={ICON_FILE}",
        "--windows-console-mode=disable",
        "--assume-yes-for-downloads", 
        MAIN_SCRIPT
    ]
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print("❌ Nuitka 编译失败！")
        exit(1)
    print("✅ Nuitka 编译完成。")

def generate_iss_script():
    print("📝 正在生成 Inno Setup 脚本 (.iss)...")
    
    source_path = os.path.abspath(NUITKA_OUTPUT_FOLDER)
    icon_abs_path = os.path.abspath(ICON_FILE) # 获取图标的绝对路径
    output_path = os.path.abspath("Output_Installers")
    
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    iss_content = f"""
[Setup]
AppName={APP_NAME}
AppVersion={APP_VERSION}
AppPublisher={APP_PUBLISHER}
DefaultDirName={{autopf}}\\{APP_NAME}
DefaultGroupName={APP_NAME}
OutputDir={output_path}
OutputBaseFilename={APP_NAME}_Setup_v{APP_VERSION}
Compression=lzma2
SolidCompression=yes
SetupIconFile={icon_abs_path}
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; 修改点1：去掉了 Flags: unchecked，现在默认就是勾选状态
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
; 核心程序文件
Source: "{source_path}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 修改点2：显式地把 icon.ico 文件拷贝到安装目录，确保快捷方式能找到它
Source: "{icon_abs_path}"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
; 开始菜单快捷方式
Name: "{{group}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"; IconFilename: "{{app}}\\{ICON_FILE}"
; 卸载快捷方式
Name: "{{group}}\\{{cm:UninstallProgram,{APP_NAME}}}"; Filename: "{{uninstallexe}}"
; 桌面快捷方式
Name: "{{userdesktop}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"; IconFilename: "{{app}}\\{ICON_FILE}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{APP_NAME}.exe"; Description: "{{cm:LaunchProgram,{APP_NAME}}}"; Flags: nowait postinstall skipifsilent
    """

    with open("setup_script.iss", "w", encoding="utf-8") as f:
        f.write(iss_content)
    
    print("✅ ISS 脚本已生成 (已修复图标和默认勾选)")

def build_installer():
    print("📦 开始调用 Inno Setup 制作安装包...")
    if not os.path.exists(ISCC_PATH):
        print(f"❌ 找不到编译器: {ISCC_PATH}")
        exit(1)
    
    cmd = [ISCC_PATH, "setup_script.iss"]
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("❌ 制作失败！")
        exit(1)
    
    print(f"🎉 成功！请查看文件夹: {os.path.abspath('Output_Installers')}")

if __name__ == "__main__":

    run_nuitka()
    generate_iss_script()
    build_installer()