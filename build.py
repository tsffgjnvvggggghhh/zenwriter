import os
import subprocess

def build():
    print("Starting PyInstaller build for ZenWriter...")

    # Configure PyInstaller arguments
    args = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed", # Don't show a console window
        "--name", "ZenWriter",
        "--clean",
        "zenwriter.py"
    ]

    # Run PyInstaller
    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode == 0:
        print("Build completed successfully!")
        print(f"Executable can be found in the 'dist' folder.")
    else:
        print("Build failed!")
        print("Error output:")
        print(result.stderr)

if __name__ == "__main__":
    build()
