@echo off
REM -------------------------------------------
REM  Tradex 一键安装脚本
REM  功能：
REM    1. 检测并安装 Node.js / npm
REM    2. 设置 npm 中国镜像源
REM    3. 安装并检测 Claude Code CLI
REM    4. 检测并安装 uv，并设置中国镜像源
REM    5. 执行 uv sync 同步依赖
REM  注意：请以管理员身份运行，以便 winget/msiexec 能顺利安装软件
REM -------------------------------------------

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

pushd "%~dp0"
call :ensure_node
call :configure_npm_registry
call :ensure_claude_code
call :ensure_uv
call :configure_uv_registry
call :run_uv_sync
echo.
echo 所有依赖处理完成。
popd
exit /b 0

:ensure_node
REM 检测 Node.js 是否可用
where node >nul 2>nul
if %errorlevel%==0 (
    for /f %%i in ('node -v 2^>nul') do (
        set "NODE_VERSION_FOUND=%%i"
        goto :node_found
    )
:node_found
    echo 已检测到 Node.js !NODE_VERSION_FOUND!。
    goto :eof
)

echo 未检测到 Node.js，开始自动安装...
call :install_node
where node >nul 2>nul
if not %errorlevel%==0 (
    echo 无法自动安装 Node.js，请手动安装后重试。
    exit /b 1
)
goto :eof

:install_node
REM 优先尝试使用 winget 安装
where winget >nul 2>nul
if %errorlevel%==0 (
    echo 使用 winget 安装 Node.js（LTS）。
    winget install -e --id OpenJS.NodeJS.LTS --source winget --accept-package-agreements --accept-source-agreements
    if %errorlevel%==0 (
        goto :eof
    )
    echo winget 安装失败，将尝试镜像下载安装包。
) else (
    echo 未检测到 winget，尝试镜像下载安装包。
)

set "NODE_VERSION=20.11.1"
set "NODE_MSI=%TEMP%\node-%NODE_VERSION%.msi"
set "NODE_URL=https://npmmirror.com/mirrors/node/v%NODE_VERSION%/node-v%NODE_VERSION%-x64.msi"
echo 从中国镜像下载 Node.js %NODE_VERSION% 安装包...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%NODE_MSI%'"
if not %errorlevel%==0 (
    echo Node.js 安装包下载失败：%NODE_URL%
    exit /b 1
)
echo 运行静默安装（可能需要几分钟）...
msiexec /i "%NODE_MSI%" /qn /norestart
if not %errorlevel%==0 (
    echo Node.js 安装失败，错误码 %errorlevel%。
    exit /b 1
)
echo Node.js 安装完成。
goto :eof

:configure_npm_registry
REM 设置 npm 中国镜像源
where npm >nul 2>nul
if not %errorlevel%==0 (
    echo 未检测到 npm，跳过镜像配置。
    goto :eof
)
set "NPM_REGISTRY=https://registry.npmmirror.com"
for /f %%i in ('npm config get registry 2^>nul') do set "CURRENT_NPM_REGISTRY=%%i"
if /i "!CURRENT_NPM_REGISTRY!"=="%NPM_REGISTRY%" (
    echo npm 已使用国内镜像源：%NPM_REGISTRY%
    goto :eof
)
echo 将 npm registry 设置为 %NPM_REGISTRY% ...
npm config set registry %NPM_REGISTRY%
if %errorlevel%==0 (
    echo npm 镜像源设置完成。
) else (
    echo npm 镜像源设置失败，请手动执行：npm config set registry %NPM_REGISTRY%
)
goto :eof

:ensure_claude_code
REM 检测 Claude Code CLI（命令行名称：claude）
where claude >nul 2>nul
if %errorlevel%==0 (
    for /f %%i in ('claude --version 2^>nul') do (
        set "CLAUDE_VERSION=%%i"
        goto :claude_found
    )
:claude_found
    if defined CLAUDE_VERSION (
        echo 已检测到 Claude Code CLI 版本 !CLAUDE_VERSION!。
    ) else (
        echo 已检测到 Claude Code CLI。
    )
    goto :eof
)

echo 未检测到 Claude Code CLI，开始使用 npm 全局安装...
call :install_claude_code
where claude >nul 2>nul
if not %errorlevel%==0 (
    echo Claude Code CLI 安装失败，请确认 npm 全局 bin 目录已加入 PATH。
    exit /b 1
)
echo Claude Code CLI 安装完成。
goto :eof

:install_claude_code
where npm >nul 2>nul
if not %errorlevel%==0 (
    echo 未检测到 npm，无法安装 Claude Code CLI。
    exit /b 1
)
echo 正在安装 @anthropic-ai/claude-code（可能需要几分钟）...
npm install -g @anthropic-ai/claude-code
if not %errorlevel%==0 (
    echo npm 安装 Claude Code CLI 失败，请手动执行：npm install -g @anthropic-ai/claude-code
    exit /b 1
)
goto :eof

:ensure_uv
REM 检测 uv 是否可用
call :locate_uv
if defined UV_BIN (
    echo 已检测到 uv，可执行文件：!UV_BIN!
    goto :eof
)

echo 未检测到 uv，开始自动安装...
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://astral.sh/uv/install.ps1 -UseBasicParsing | Invoke-Expression"
if not %errorlevel%==0 (
    echo uv 安装脚本执行失败。
    exit /b 1
)
REM 尝试再次定位 uv
call :locate_uv
if not defined UV_BIN (
    echo 无法找到 uv，请确认安装是否成功。
    exit /b 1
)
echo uv 安装完成：!UV_BIN!
goto :eof

:locate_uv
REM 寻找 uv 命令路径
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
REM 为 uv 配置中国镜像源
if not defined UV_BIN (
    call :locate_uv
)
if not defined UV_BIN (
    echo 未检测到 uv，无法配置镜像源。
    exit /b 1
)
set "UV_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
echo 将 uv pip index-url 设置为 %UV_INDEX_URL% ...
"%UV_BIN%" pip config set --global index-url %UV_INDEX_URL%
if not %errorlevel%==0 (
    echo 设置 uv 镜像源失败，请手动执行：uv pip config set --global index-url %UV_INDEX_URL%
    exit /b 1
)
echo uv 镜像源设置完成。
goto :eof

:run_uv_sync
REM 使用 uv 同步依赖
if not defined UV_BIN (
    call :locate_uv
)
if not defined UV_BIN (
    echo 未检测到 uv，无法执行 uv sync。
    exit /b 1
)
echo 运行 uv sync，同步 Python 依赖...
"%UV_BIN%" sync
if not %errorlevel%==0 (
    echo uv sync 执行失败，请检查上方日志。
    exit /b 1
)
echo uv sync 完成。
goto :eof
