# 给 Hermes 和 Claude Code 的提示词

## Hermes 系统提示词补丁

把下面内容加入 Hermes 的长期系统提示词或项目规则中：

```text
你可以使用本机记忆系统。优先使用短命令 `mem`，它连接远程 Qdrant，并用本机 SQLite 队列避免写入丢失。

搜索历史：
mem --client hermes search "查询内容" --limit 5

写入事实：
mem --client hermes add "事实内容" --type fact --importance 3 --tags tag1,tag2

写入用户偏好：
mem --client hermes prefer "用户偏好内容"

写入决策：
mem --client hermes decision "决策内容"

写入修正：
mem --client hermes correct "修正后的内容" --target-id <原记忆id>

健康检查：
mem --client hermes health

队列检查和重试：
mem --client hermes queue
mem --client hermes flush

记忆写入规则：
- 只有长期有用的信息才写入：用户偏好、稳定事实、项目决策、对旧信息的修正。
- 不写入临时聊天、一次性命令输出、敏感值、API key、密码、token、cookie。
- 写入 secret 相关信息时只能写变量名和用途，不能写真实值。
- 如果写入失败，不要反复重试；运行 `mem --client hermes queue` 告知用户本地队列仍保留待写入内容。
```

## Claude Code 项目提示词补丁

把下面内容加入 Claude Code 的用户规则、项目 AGENTS.md，或你每次启动 Claude Code 时贴给它：

```text
本机有一个记忆 CLI：`mem`。它用于读取和写入长期记忆，后端是远程 Qdrant，本机 SQLite 队列用于失败重试。

在开始复杂任务前，先按需搜索相关历史：
mem --client claude_code search "<项目名、错误、用户偏好或关键主题>" --limit 5

当用户表达稳定偏好、项目长期事实、架构决策、部署方式、故障处理结论时，写入记忆：
mem --client claude_code add "内容" --type fact --importance 3 --tags project,topic
mem --client claude_code decision "决策内容" --tags project,decision
mem --client claude_code prefer "用户偏好"

如果发现旧记忆错误，使用 correction，不要直接覆盖：
mem --client claude_code correct "新的正确信息" --target-id <旧记忆id>

写入约束：
- 不记录 secret 值、token、密码、cookie、私钥。
- 只记录之后明显会复用的信息。
- 命令失败时运行 `mem --client claude_code queue`，说明待写入内容已保留在本地队列。
- 不要让记忆命令阻塞主要开发任务；健康检查失败时继续完成当前代码任务，并把失败原因告知用户。
```
