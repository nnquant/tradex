Tradex
======
基于 Claude Code CLI 开发的面向量化研究与交易基建的实验性项目。

# 安装指南

一键安装（推荐）
----------------

1. 以管理员权限打开 PowerShell 或 CMD，定位到存放 `install.cmd` 的目录。
2. 可选：若想把仓库放在自定义目录，先执行 `set TRADEX_INSTALL_DIR=D:\quant\tradex`（未设置时默认克隆到 `%USERPROFILE%\tradex`）。
3. 运行脚本：

```powershell
.\install.cmd
```

脚本按照最少输出的原则完成以下任务：

1. 检测/安装 Git；缺失时优先使用 `winget install -e --id Git.Git`。
2. `git clone https://github.com/nnquant/tradex.git %TRADEX_INSTALL_DIR%`（已存在则执行 `git pull`），并切换到该目录。
3. 安装 Node.js / npm（优先 `winget install -e --id OpenJS.NodeJS.LTS`，失败则回落至 npmmirror 安装包）。
4. 按需把 npm registry 设置为 `https://registry.npmmirror.com`，安装/检测 `@anthropic-ai/claude-code` CLI。
5. 安装 `uv`，并在选择加速的情况下把 `uv pip` 的 index 指向清华镜像。
6. 执行 `uv sync` 还原 Python 依赖。
7. 自动运行 `uv run tradex config`，引导你创建/校验 `tradex.config.toml`。

配置向导顺利结束后，终端会提示命令 `uv run tradex` 以启动主应用。若脚本无法把 `%APPDATA%\npm` 等目录加入 PATH，请根据提示手动处理。

手动安装
--------

如需完全手动操作，可参考以下步骤（建议使用管理员窗口）：

### 1. 安装 Git 并克隆仓库

```powershell
winget install -e --id Git.Git
git clone https://github.com/nnquant/tradex.git
cd tradex
```

### 2. 安装 Node.js 与 npm

- 推荐命令：`winget install -e --id OpenJS.NodeJS.LTS`
- 如需离线，可从 [npmmirror Node 镜像](https://npmmirror.com/mirrors/node/) 下载对应版本 MSI。
- 安装完成后执行：

```powershell
npm config set registry https://registry.npmmirror.com
```

这样后续的全局 npm 安装都会走国内镜像。

### 3. 安装 Claude Code CLI

Claude Code 提供本地 Agent CLI，是 `claude_agent_sdk` 的运行依赖。

```powershell
npm install -g @anthropic-ai/claude-code
claude --version
```

若 `claude` 未被识别，请确认 `%APPDATA%\npm` 或自定义 npm 全局 bin 目录已写入 PATH。可通过 `npm config get prefix` 查询实际安装路径。

### 4. 安装 uv

`uv` 是项目统一的 Python 包/环境管理器：

```powershell
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://astral.sh/uv/install.ps1 -UseBasicParsing | Invoke-Expression"
uv pip config set --global index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

若使用自定义镜像，请将 `index-url` 替换成你的内部源。

### 5. 同步 Python 依赖

在仓库根目录执行：

```powershell
uv sync
```

该命令会根据 `uv.lock` 精确还原虚拟环境，确保算法和工具链具有可复现性。

### 6. CLI 验证与配置

- `node -v` / `npm -v` 显示版本；
- `claude --version` 至少为 2.0.0；
- `uv --version` 正常输出；
- `uv run tradex config` 打开配置助手，完成后即可通过 `uv run tradex` 启动主应用。

开始使用
--------

1. 复制配置模板  
   将目录下的配置文件 `tradex.config.example.toml` 重命名为 `tradex.config.toml`  

   建议使用与运行环境匹配的文件名，如需多份配置可命名为 `tradex.config.paper.toml`、`tradex.config.live.toml` 等。

2. 根据真实环境填写配置  
   - `model.api_key`：替换为你的真实大模型密钥，必要时也可自建代理并更新 `model.base_url`。  
   - `environment.cwd`：保持为仓库根目录或设为运行脚本/数据所在路径，确保相对路径可解析。  
   - `extensions` 与 `extension.tradex_easytrader`：仅保留需要的扩展，像 `xiadan_path` 等字段必须指向实际可执行程序。  
   完成修改后请把配置文件保存在安全位置，并根据团队合规策略设置访问权限。

3. 配置与启动  
   ```shell
   uv run tradex config --config tradex.config.toml
   uv run tradex --config tradex.config.toml
   ```  
   第一个命令调用统一 CLI 的配置子命令，可扫描扩展目录、生成/校验配置并写入 `tradex.config.toml`。  
   第二个命令启动主应用；若维护多份配置，可使用 `--config path/to/xxx.toml` 切换。首次运行请观察终端日志，确认模型连通性、扩展加载状态及账户接口是否正常。
