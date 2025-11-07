# Tradex 使用指南

本文面向首次接触 Tradex 的用户，涵盖安装准备、配置说明、运行步骤以及扩展机制，帮助你在本地快速搭建一套可编程的量化研究与交易助手。

## 1. 安装与依赖

### 1.1 一键安装（推荐）

在仓库根目录打开具有管理员权限的 PowerShell 或 CMD，执行：

```powershell
.\install.cmd
```

脚本会自动：

1. 检查 Node.js / npm，缺失时通过 `winget` 或 npmmirror LTS 安装包补齐；
2. 将 npm registry 设置为 `https://registry.npmmirror.com`；
3. 检测 `@anthropic-ai/claude-code` CLI 并在缺失时全局安装；
4. 安装 `uv`，同时把 `uv pip` 的索引切换到清华镜像；
5. 运行 `uv sync`，根据 `pyproject.toml` 与 `uv.lock` 同步 Python 依赖。

若 `claude` 命令无法直接使用，请确保 `%APPDATA%\npm` 或自定义 npm 全局 bin 目录已加入 PATH。

### 1.2 手动安装（可选）

若需手动控制各步骤，可参照下列顺序：

1. 安装 Node.js（建议 `winget install -e --id OpenJS.NodeJS.LTS`），并使用 `npm config set registry https://registry.npmmirror.com` 设置镜像；
2. 安装 Claude Code CLI：`npm install -g @anthropic-ai/claude-code && claude --version`；
3. 安装 `uv`：`Invoke-WebRequest https://astral.sh/uv/install.ps1 -UseBasicParsing | Invoke-Expression`，随后执行 `uv pip config set --global index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple`；
4. 在仓库根目录运行 `uv sync`；
5. 通过 `uv run python run_tradex.py --help` 验证依赖是否齐全。

## 2. 配置 Tradex

### 2.1 准备配置文件

1. 复制 `tradex.config.example.toml` 为 `tradex.config.toml`（或任意自定义文件，通过 `--config` 参数指定）；
2. 按以下章节逐项填写。

### 2.2 `[environment]`

| 字段 | 说明 |
| --- | --- |
| `cwd` | Tradex 在 Claude Agent 中工作的根目录。未填写时默认使用当前用户目录。 |
| `project` | 可选的子目录名，如填写则最终工作目录为 `cwd/project`。所有日志会写入该目录下 `.tradex/tradex.log`。 |

### 2.3 `[model]`（模型配置详细说明）

Tradex 通过 `claude_agent_sdk` 调用 Claude/DeepSeek 兼容接口，本节决定底层模型参数：

| 字段 | 用途 | 说明 |
| --- | --- | --- |
| `base_url` | API 基地址 | 例如 `https://api.deepseek.com/anthropic` 或 Anthropic 官方地址。若接入私有网关，请填写对应域名。 |
| `api_key` | 授权密钥 | 由模型服务方颁发，Tradex 启动时会转换为 `ANTHROPIC_AUTH_TOKEN` 环境变量。务必妥善保密。 |
| `model_name` | 主模型 | 默认 `deepseek-chat`，用于长对话与复杂任务。可以填 `claude-3-5-sonnet` 等其他兼容模型。 |
| `fast_model_name` | 快速模型 | 用于补全、轻量级工具调用或审核请求，可与 `model_name` 相同。 |

> 提示：如需频繁切换模型，可维护多份 `*.toml`，通过 `uv run python run_tradex.py --config path/to/xxx.toml` 自由切换。

### 2.4 `[agent]`

| 字段 | 说明 |
| --- | --- |
| `permission_mode` | 与 Claude Code CLI 的权限策略一致，例如 `acceptEdits` 表示自动接受代码编辑，`ask` 则每次需要确认。 |
| `extension_enabled` | 要启用的扩展名称数组，必须与 `[extensions]` 中的 key 对应。未列出的扩展不会加载。 |

### 2.5 `[extensions]` 与 `[extension.<name>]`

1. `[extensions]`：声明模块路径，例如 `tradex_akshare = { path = "src.extension.tradex_akshare" }`。Tradex 会动态导入该模块并注册其 MCP 工具。
2. `[extension.<name>]`：针对特定扩展的私有配置。以 `tradex_easytrader` 为例：

```toml
[extension.tradex_easytrader]
client_name = "ths"
xiadan_path = "D:/software/同花顺远航版/transaction/xiadan.exe"
```

此处传入的参数会在扩展的 `init_extension(config, ctl)` 中读取，用于连接外部客户端或保存 token。

## 3. 运行与交互

### 3.1 启动方式

```bash
uv run python run_tradex.py --config tradex.config.toml
```

- `--config` 指向你的配置文件，默认为仓库根目录下的 `tradex.config.toml`；
- 首次运行时将初始化日志目录并加载所有启用的扩展。

### 3.2 界面快速导览

Tradex 基于 Textual TUI，核心区域包含：

1. **日志面板**：展示系统提示、工具调用、扩展初始化状态。可用来确认模型与扩展是否加载成功。
2. **消息区**：显示 AI 助手与用户的对话，代码片段和工具返回值会以区块形式呈现。
3. **输入框**：位于底部，支持多行 Paste。输入完成按 Enter 即可提交。

### 3.3 常见操作示例

| 目标 | 操作示例 |
| --- | --- |
| 获取数据 | 输入“查询今天涨停股池”，Tradex 会调用 `tradex_akshare` 提供的 `stock_zt_pool` 工具并输出结果。 |
| 分析策略 | 将需求用自然语言描述，Tradex 会生成 Python 代码并在本地虚拟环境中执行，可查看代码块及运行日志。 |
| 调试脚本 | 让 Tradex 修改、运行仓库内脚本，必要时手动授权其读写文件或执行命令。 |
| 交易操作 | 在启用 `tradex_easytrader` 并完成客户端连接后，直接让 Tradex 下达买入/卖出指令，输入参数会在 UI 中可视化。 |

## 4. 扩展程序

- Tradex 原生支持通过 MCP 扩展能力扩展数据源与执行器。启用方式：在 `[extensions]` 中添加模块路径，并在 `[agent].extension_enabled` 中列出名称。
- 若需自定义扩展，请参考 `docs/extension_develop_guide.md`，其中描述了 `@tool` 装饰器、`create_sdk_mcp_server`、`init_extension` 钩子的用法以及配置示例。
- 启动后可在 TUI 日志看到诸如“tradex - 加载扩展 tradex_akshare”的信息，若出现错误请检查配置或查看 `.tradex/tradex.log`。

## 5. 故障排查

| 场景 | 处理建议 |
| --- | --- |
| 启动立即退出 | 检查 `tradex.config.toml` 是否存在，`uv sync` 是否已执行。 |
| 模型请求失败 | 确认 `api_key` 有效且 `base_url` 可访问，如使用代理需在系统层面配置。 |
| 工具未显示 | 核对 `extension_enabled` 与 `[extensions]` 中的 key 是否一致，并确认扩展模块内导出了 `__mcp_allowed_tools__`。 |
| easytrader 无法连接 | 保证 `xiadan_path` 指向正确可执行文件，并在 Windows 上以管理员身份运行 Tradex。 |

完成以上配置后，你即可把 Tradex 作为本地量化助手：通过自然语言驱动代码生成、数据分析与下单流程，并结合扩展机制接入更多内部系统。
