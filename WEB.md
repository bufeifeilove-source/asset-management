# Memory Web 可视化管理台

这个 Web 管理台给 Hermes 和 Claude Code 的记忆系统提供浏览器界面。

## 功能

- 搜索 `memory_claude_code`、`memory_hermes` 和 `memory_shared`
- 新增 `fact`、`preference`、`decision`、`correction`
- 对选中的旧记忆追加 correction
- 查看 Qdrant、collection、SiliconFlow embedding 和本地队列状态
- 手动 flush 本地失败重试队列

## 本地开发

后端：

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
cp .env.example .env
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。前端开发服务器会把 `/api` 转发到 `http://127.0.0.1:8000`。

## 服务器部署

编辑 `.env`：

```bash
SILICONFLOW_API_KEY=sk-...
MEMORY_QDRANT_URL=http://100.81.130.84:6333
MEMORY_CLIENT_NAME=claude_code
MEMORY_WEB_TOKEN=换成一个长随机字符串
```

启动：

```bash
docker compose up -d --build
```

访问：

```text
http://服务器IP:8000
```

网页左侧填写 `MEMORY_WEB_TOKEN`，请求会用 `Authorization: Bearer <token>` 调后端。

## 安全建议

- 不要把 Qdrant 和 SiliconFlow API key 暴露给前端。
- 如果要公网访问，建议放到 Nginx/Caddy 后面并启用 HTTPS。
- 删除和直接覆盖功能暂不开放；修正旧记忆使用追加 `correction`。
- 不要在记忆里写入真实 secret、token、cookie、私钥。
