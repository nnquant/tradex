@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "REPO_URL=https://github.com/nnquant/tradex.git"
if not defined TRADEX_INSTALL_DIR (
    set "TRADEX_INSTALL_DIR=%USERPROFILE%\tradex"
) else (
    set "TRADEX_INSTALL_DIR=%TRADEX_INSTALL_DIR%"
)
set "USE_CHINA_MIRROR=Y"

call :ask_mirror_preference
call :ensure_git
call :prepare_repo
pushd "%TRADEX_INSTALL_DIR%"
call :ensure_node
call :configure_npm_registry
call :ensure_claude_code
call :ensure_uv
call :configure_uv_registry
call :run_uv_sync
call :run_config
echo 安装流程结束，可通过命令：uv run tradex
popd
exit /b 0

:ask_mirror_preference
set /p "MIRROR_CHOICE=Switch npm/uv to China mirrors? (Y/n): "
if not defined MIRROR_CHOICE set "MIRROR_CHOICE=Y"
set "MIRROR_CHOICE=!MIRROR_CHOICE:~0,1!"
if /i "!MIRROR_CHOICE!"=="Y" (
    set "USE_CHINA_MIRROR=Y"
    echo Use China mirrors.
) else (
    set "USE_CHINA_MIRROR=N"
    echo Keep official mirrors.
)
goto :eof

:ensure_git
where git >nul 2>nul
if %errorlevel%==0 (
    for /f "tokens=1,*" %%i in ('git --version 2^>nul') do (
        echo Found %%i %%j
        goto :eof
    )
    goto :eof
)
echo Git not found, installing...
call :install_git
where git >nul 2>nul
if not %errorlevel%==0 (
    echo Failed to install git.
    exit /b 1
)
echo Git ready.
goto :eof

:install_git
where winget >nul 2>nul
if %errorlevel%==0 (
    winget install -e --id Git.Git --source winget --accept-package-agreements --accept-source-agreements
    if %errorlevel%==0 goto :eof
)
echo winget installation of git failed, install manually.
exit /b 1

:prepare_repo
if exist "%TRADEX_INSTALL_DIR%\.git" (
    echo Repository exists, running git pull...
    git -C "%TRADEX_INSTALL_DIR%" pull
    if not %errorlevel%==0 (
        echo git pull failed.
        exit /b 1
    )
    goto :eof
)
if exist "%TRADEX_INSTALL_DIR%" (
    echo Target directory exists but is not a git repo.
    exit /b 1
)
echo Cloning Tradex repository to %TRADEX_INSTALL_DIR% ...
git clone "%REPO_URL%" "%TRADEX_INSTALL_DIR%"
if not %errorlevel%==0 (
    echo git clone failed.
    exit /b 1
)
goto :eof

:ensure_node
where node >nul 2>nul
if %errorlevel%==0 (
    for /f %%i in ('node -v 2^>nul') do (
        echo Found Node.js %%i
        goto :eof
    )
    goto :eof
)
echo Node.js not found, installing...
call :install_node
where node >nul 2>nul
if not %errorlevel%==0 (
    echo Failed to install Node.js.
    exit /b 1
)
echo Node.js ready.
goto :eof

:install_node
where winget >nul 2>nul
if %errorlevel%==0 (
    winget install -e --id OpenJS.NodeJS.LTS --source winget --accept-package-agreements --accept-source-agreements
    if %errorlevel%==0 goto :eof
    echo winget install failed, downloading MSI...
)
set "NODE_VERSION=20.11.1"
set "NODE_MSI=%TEMP%\node-%NODE_VERSION%.msi"
set "NODE_URL=https://npmmirror.com/mirrors/node/v%NODE_VERSION%/node-v%NODE_VERSION%-x64.msi"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%NODE_MSI%'"
if not %errorlevel%==0 (
    echo Failed to download Node.js MSI: %NODE_URL%
    exit /b 1
)
msiexec /i "%NODE_MSI%" /qn /norestart
if not %errorlevel%==0 (
    echo Node.js MSI installation failed %errorlevel%.
    exit /b 1
)
goto :eof

:configure_npm_registry
if /i "!USE_CHINA_MIRROR!" NEQ "Y" (
    echo Keep npm default registry.
    goto :eof
)
where npm >nul 2>nul
if not %errorlevel%==0 (
    echo npm not found, skip registry setup.
    goto :eof
)
set "NPM_REGISTRY=https://registry.npmmirror.com"
for /f %%i in ('npm config get registry 2^>nul') do set "CURRENT_NPM_REGISTRY=%%i"
if /i "!CURRENT_NPM_REGISTRY!"=="%NPM_REGISTRY%" (
    echo npm already uses %NPM_REGISTRY%.
    goto :eof
)
echo Set npm registry to %NPM_REGISTRY% ...
npm config set registry %NPM_REGISTRY%
if not %errorlevel%==0 (
    echo Failed to configure npm registry.
    exit /b 1
)
goto :eof

:ensure_claude_code
where claude >nul 2>nul
if %errorlevel%==0 (
    for /f %%i in ('claude --version 2^>nul') do (
        echo Found Claude Code CLI %%i
        goto :eof
    )
    echo Claude Code CLI found.
    goto :eof
)
echo Claude Code CLI not found, installing...
call :install_claude_code
where claude >nul 2>nul
if not %errorlevel%==0 (
    echo Failed to install Claude Code CLI.
    exit /b 1
)
echo Claude Code CLI ready.
goto :eof

:install_claude_code
where npm >nul 2>nul
if not %errorlevel%==0 (
    echo npm not found, cannot install Claude Code CLI.
    exit /b 1
)
npm install -g @anthropic-ai/claude-code
if not %errorlevel%==0 (
    echo npm install @anthropic-ai/claude-code failed.
    exit /b 1
)
goto :eof

:ensure_uv
call :locate_uv
if defined UV_BIN (
    echo Found uv: !UV_BIN!
    goto :eof
)
echo uv not found, installing...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://astral.sh/uv/install.ps1 -UseBasicParsing | Invoke-Expression"
if not %errorlevel%==0 (
    echo uv installer failed.
    exit /b 1
)
call :locate_uv
if not defined UV_BIN (
    echo uv still missing after install.
    exit /b 1
)
echo uv ready: !UV_BIN!
goto :eof

:locate_uv
set "UV_BIN="
for /f "delims=" %%i in ('where uv 2^>nul') do (
    set "UV_BIN=%%i"
    goto :eof
)
if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "UV_BIN=%USERPROFILE%\.local\bin\uv.exe"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
goto :eof

:configure_uv_registry
if /i "!USE_CHINA_MIRROR!" NEQ "Y" (
    echo Keep uv default index.
    goto :eof
)
if not defined UV_BIN call :locate_uv
if not defined UV_BIN (
    echo uv not found, cannot set index.
    exit /b 1
)
set "UV_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
echo Set uv pip index-url to %UV_INDEX_URL% ...
"%UV_BIN%" pip config set --global index-url %UV_INDEX_URL%
if not %errorlevel%==0 (
    echo Failed to configure uv pip index.
    exit /b 1
)
goto :eof

:run_uv_sync
if not defined UV_BIN call :locate_uv
if not defined UV_BIN (
    echo uv not found, cannot run uv sync.
    exit /b 1
)
echo Run uv sync ...
"%UV_BIN%" sync
if not %errorlevel%==0 (
    echo uv sync failed.
    exit /b 1
)
goto :eof

:run_config
if not defined UV_BIN call :locate_uv
if not defined UV_BIN (
    echo uv not found, cannot run config.
    exit /b 1
)
echo Run Tradex config ...
"%UV_BIN%" run tradex config
if not %errorlevel%==0 (
    echo tradex config returned non-zero exit code.
    exit /b 1
)
goto :eof
