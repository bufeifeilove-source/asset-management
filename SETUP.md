# 本机安装步骤

以下步骤在你的电脑上执行，不是在远程 Qdrant 服务器上执行。

## 1. 准备目录

```bash
mkdir -p ~/memory-system
cd ~/memory-system
```

把这些文件放进目录：

- `pyproject.toml`
- `.env.example`
- `memory_config.py`
- `memory_queue.py`
- `memory_client.py`
- `memctl.py`
- `PROMPTS.md`

## 2. 安装依赖

推荐使用 uv：

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

如果你的 shell 找不到 `mem`，可以直接使用：

```bash
python memctl.py health
```

## 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填：

```bash
SILICONFLOW_API_KEY=sk-...
MEMORY_QDRANT_URL=http://100.81.130.84:6333
```

## 4. 自检

```bash
mem health
mem add "记忆系统本机 CLI 已安装完成" --type fact --importance 3 --tags setup
mem search "本机 CLI"
mem queue
```

## 5. 推荐 shell alias

```bash
alias mem='python ~/memory-system/memctl.py'
```

如果你使用 PowerShell，需要换成对应的函数或直接调用 Python 脚本。
