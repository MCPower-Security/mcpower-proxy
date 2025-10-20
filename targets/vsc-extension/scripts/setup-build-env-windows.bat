@echo off
setlocal enabledelayedexpansion

echo 🔧 Setting up MCPower Security build environment for Windows...

REM Check if we're on Windows
if "%OS%" neq "Windows_NT" (
    echo ❌ This script is designed for Windows.
    exit /b 1
)

REM Check if git is installed
where git >nul 2>&1
if errorlevel 1 (
    echo 📦 Installing Git...
    winget install --id Git.Git -e --source winget --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo ❌ Failed to install Git
        exit /b 1
    )
    echo ✅ Git installed
    
    REM Refresh PATH
    call refreshenv >nul 2>&1 || (
        set "PATH=%PATH%;C:\Program Files\Git\cmd"
    )
    
    REM Verify git is now available
    where git >nul 2>&1
    if errorlevel 1 (
        echo ❌ Git installed but not in PATH. Restart terminal.
        exit /b 1
    )
)

REM Function to check if a command exists
where python >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH.
    echo Please install Python from https://python.org/downloads/
    exit /b 1
)

REM Check Python version (force 3.10.3 for Nuitka compatibility)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python !PYTHON_VERSION!

REM Check if we need to install Python 3.10.3
echo !PYTHON_VERSION! | findstr /C:"3.10.3" >nul
if errorlevel 1 (
    echo ⚠️  Python !PYTHON_VERSION! found, but 3.10.3 is required for Nuitka compatibility
    echo 📦 Installing Python 3.10.3...

    REM Download and install Python 3.10.3
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.3/python-3.10.3-amd64.exe' -OutFile 'python-3.10.3-amd64.exe'"
    if errorlevel 1 (
        echo ❌ Failed to download Python 3.10.3
        exit /b 1
    )

    echo 📦 Installing Python 3.10.3...
    python-3.10.3-amd64.exe /quiet InstallAllUsers=1 PrependPath=1
    if errorlevel 1 (
        echo ❌ Failed to install Python 3.10.3
        exit /b 1
    )

    echo ✅ Python 3.10.3 installed
    del python-3.10.3-amd64.exe

    REM Update PATH for current session
    set "PATH=C:\Program Files\Python310\Scripts;C:\Program Files\Python310;%PATH%"
) else (
    echo ✅ Python 3.10.3 found
)

REM Navigate to src directory
cd ..\..\src
if not exist . (
    echo ❌ Source directory not found
    exit /b 1
)

echo 📦 Setting up Python virtual environment...

REM Remove existing virtual environment if present
if exist .venv (
    echo Removing existing virtual environment...
    rmdir /s /q .venv 2>nul || rd /s /q .venv 2>nul || echo.
    if exist .venv (
        powershell -Command "Remove-Item -Path '.venv' -Recurse -Force -ErrorAction SilentlyContinue"
    )
)

REM Create virtual environment with Python 3.10.3
echo 📦 Creating virtual environment with Python 3.10.3...
python -m venv .venv
if errorlevel 1 (
    echo ❌ Failed to create virtual environment
    exit /b 1
)
echo ✅ Created Python virtual environment with Python 3.10.3

REM Activate virtual environment
call .venv\Scripts\activate
if errorlevel 1 (
    echo ❌ Failed to activate virtual environment
    exit /b 1
)

echo ✅ Activated Python virtual environment

REM Clone Nuitka-commercial
if not exist ..\.nuitka-commercial (
    if not defined NUITKA_COMMERCIAL_TOKEN (
        echo ❌ NUITKA_COMMERCIAL_TOKEN not set. Required to clone Nuitka Commercial.
        exit /b 1
    )
    
    echo 📦 Cloning Nuitka Commercial...
    
    git clone https://%NUITKA_COMMERCIAL_TOKEN%@github.com/Nuitka/Nuitka-commercial.git ..\.nuitka-commercial >nul 2>&1
    if errorlevel 1 (
        echo ❌ Failed to clone Nuitka Commercial. Check your token and repository access.
        exit /b 1
    )
    
    REM Add safe.directory for network/shared drives
    for /f "delims=" %%i in ('cd') do set CURRENT_DIR=%%i
    git config --global --add safe.directory "%CURRENT_DIR%\..\.nuitka-commercial"
    
    cd ..\.nuitka-commercial
    git checkout 2.7.16
    if errorlevel 1 (
        echo ❌ Failed to checkout Nuitka Commercial version 2.7.16
        exit /b 1
    )
    cd ..\src
    echo ✅ Nuitka Commercial cloned and checked out to version 2.7.16
) else (
    echo ✅ Nuitka Commercial already exists
)

REM Upgrade pip
python -m pip install --upgrade pip

REM Install Python dependencies
if exist requirements.txt (
    echo 📦 Installing Python dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ Failed to install Python dependencies
        exit /b 1
    )
    echo ✅ Python dependencies installed
) else (
    echo ⚠️  requirements.txt not found, skipping Python dependency installation
)

REM Verify critical imports
echo ✅ Verifying Python dependencies...
python -c "import fastmcp; import mcp; print('All Python dependencies work!')" || (echo ❌ Python dependency verification failed & exit /b 1)

REM Navigate back to extension directory
cd ..\targets\vsc-extension

REM Clean old Nuitka build artifacts that may have permission issues
if exist executables (
    echo Cleaning old Nuitka build artifacts...
    rmdir /s /q executables 2>nul || rd /s /q executables 2>nul || echo.
    if exist executables (
        powershell -Command "Remove-Item -Path 'executables' -Recurse -Force -ErrorAction SilentlyContinue"
    )
)

REM Install Node.js dependencies
if exist package.json (
    echo 📦 Installing Node.js dependencies...

    REM Force remove node_modules before npm ci (handles stubborn files)
    if exist node_modules (
        echo Force removing existing node_modules...
        REM Try multiple removal methods
        rmdir /s /q node_modules 2>nul || rd /s /q node_modules 2>nul || (
            echo Standard removal failed, trying PowerShell...
            powershell -Command "Remove-Item -Path 'node_modules' -Recurse -Force -ErrorAction SilentlyContinue" 2>nul
        )
        REM Final check and cleanup
        if exist node_modules (
            echo Final cleanup attempt...
            powershell -Command "Get-ChildItem -Path 'node_modules' -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue" 2>nul
            rmdir /s /q node_modules 2>nul
        )
    )

    npm ci
    if errorlevel 1 (
            echo ❌ Failed to install Node.js dependencies
            exit /b 1
    )
    echo ✅ Node.js dependencies installed
    echo 📥 Updating Gitleaks rules...
    node scripts\update-gitleaks-rules.mjs || echo ⚠️ Failed to update Gitleaks rules
) else (
    echo ⚠️  package.json not found, skipping Node.js dependency installation
)

REM Check for MSVC installation
echo 🔍 Checking for MSVC installation...
set MSVC_FOUND=0

REM Try common vswhere locations
set VSWHERE="%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist %VSWHERE% (
    for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        set MSVC_PATH=%%i
        set MSVC_FOUND=1
    )
)

if !MSVC_FOUND!==1 (
    echo ✅ MSVC found: !MSVC_PATH!
) else (
    echo ❌ MSVC not found. Installing Visual Studio Build Tools...
    
    REM Download VS Build Tools installer
    set VS_BUILDTOOLS_URL=https://aka.ms/vs/17/release/vs_buildtools.exe
    set VS_INSTALLER=vs_buildtools.exe
    
    echo 📦 Downloading Visual Studio Build Tools...
    powershell -Command "Invoke-WebRequest -Uri '%VS_BUILDTOOLS_URL%' -OutFile '%VS_INSTALLER%'"
    if errorlevel 1 (
        echo ❌ Failed to download Visual Studio Build Tools
        exit /b 1
    )
    
    echo 📦 Installing Visual Studio Build Tools with C++ Desktop Development...
    echo This may take 10-15 minutes...
    %VS_INSTALLER% --quiet --wait --norestart --nocache ^
        --installPath "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools" ^
        --add Microsoft.VisualStudio.Workload.VCTools ^
        --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 ^
        --add Microsoft.VisualStudio.Component.Windows11SDK.22000
    
    if errorlevel 1 (
        echo ❌ Failed to install Visual Studio Build Tools
        del %VS_INSTALLER%
        exit /b 1
    )
    
    echo ✅ Visual Studio Build Tools installed
    del %VS_INSTALLER%
    
    REM Verify installation
    if exist %VSWHERE% (
        for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
            set MSVC_PATH=%%i
            echo ✅ MSVC verified: !MSVC_PATH!
        )
    )
)

REM Check/create signing configuration
echo 🔍 Checking code signing configuration...
if not exist signing-config.json (
    (
        echo {
        echo   "windows": {
        echo     "certificateFile": "",
        echo     "certificatePassword": "",
        echo     "certificateSha1": "",
        echo     "certificateName": ""
        echo   }
        echo }
    ) > signing-config.json
    echo ✅ Created signing-config.json template
) else (
    echo ✅ signing-config.json exists
)

echo.
echo ✅ Build environment setup completed successfully!
echo 💡 You can now run: npm run bundle-executables -- --platform=win32

endlocal
