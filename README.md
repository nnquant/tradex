Tradex
======
基于 Claude Code CLI 开发的面向量化研究与交易基建的实验性项目。

# 安装指南

一键安装（推荐）
----------------

1. 使用管理员权限打开 PowerShell 或命令提示符，切换到仓库根目录。
2. 执行：

```powershell
.\install.cmd
```

脚本会依次完成：

- 检测 Node.js / npm，优先使用 `winget` 安装，若不可用则从 `npmmirror` 下载 LTS 安装包；
- 将 npm registry 切换为 `https://registry.npmmirror.com`，加速后续依赖下载；
- 检测 `claude` 命令，若缺失则通过 `npm install -g @anthropic-ai/claude-code` 全局安装 Claude Code CLI；
- 安装 `uv` 并把 `uv pip` 的 `index-url` 指向清华镜像；
- 运行 `uv sync`，根据 `pyproject.toml` 和 `uv.lock` 同步 Python 依赖。

> 提示：如果系统未自动把 `%APPDATA%\npm` 添加到 PATH，可在脚本结束后手动执行 `setx PATH "%APPDATA%\npm;%PATH%"` 或在环境变量设置界面中补充。

手动安装
--------

如需完全手动操作，可参考以下步骤（同样建议使用管理员窗口）：

### 1. 安装 Node.js 与 npm

- 推荐命令：`winget install -e --id OpenJS.NodeJS.LTS`
- 如需离线，可从 [npmmirror Node 镜像](https://npmmirror.com/mirrors/node/) 下载对应版本 MSI。
- 安装完成后执行：

```powershell
npm config set registry https://registry.npmmirror.com
```

这样后续的全局 npm 安装都会走国内镜像。

### 2. 安装 Claude Code CLI

Claude Code 提供本地 Agent CLI，是 `claude_agent_sdk` 的运行依赖。

```powershell
npm install -g @anthropic-ai/claude-code
claude --version
```

若 `claude` 未被识别，请确认 `%APPDATA%\npm` 或自定义 npm 全局 bin 目录已写入 PATH。可通过 `npm config get prefix` 查询实际安装路径。

### 3. 安装 uv

`uv` 是项目统一的 Python 包/环境管理器：

```powershell
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://astral.sh/uv/install.ps1 -UseBasicParsing | Invoke-Expression"
uv pip config set --global index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

若使用自定义镜像，请将 `index-url` 替换成你的内部源。

### 4. 同步 Python 依赖

在仓库根目录执行：

```powershell
uv sync
```

该命令会根据 `uv.lock` 精确还原虚拟环境，确保算法和工具链具有可复现性。

### 5. 验证

- `node -v` / `npm -v` 显示版本；
- `claude --version` 至少为 2.0.0；
- `uv --version` 正常输出；
- `uv run python run_tradex.py --help` 可验证基础依赖是否齐全。

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

3. 启动应用  
   ```shell
   uv run run_tradex.py
   ```  
   上述命令默认读取 `tradex.config.toml`。如果你创建了自定义文件，可通过 `uv run run_tradex.py --config tradex.config.paper.toml` 显式指定。首次启动建议在终端关注日志，验证模型连通性、扩展加载状态及账户接口是否正常。
