---
name: newsletter-daily-summary
description: Newsletter 日报聚合摘要。从 Gmail 拉取 newsletter 进行多邮件聚合分析，生成结构化洞察，创建 Google Docs 文档 + TTS 语音发 Telegram。支持 Hermes 原生 Google Workspace 工具集。
tags: [Gmail, Newsletter, 聚合分析, Google Docs, Telegram, TTS, 语音推送]
version: 2.0.0
author: Hermes
metadata:
  hermes:
    triggers:
      - "帮我看今天的 newsletter"
      - "整理一下 newsletter"
      - "newsletter 日报"
      - "newsletter 摘要"
      - "运行 newsletter"
      - "newsletter 总结"
    schedule: "30 6 * * *"
---

# Newsletter 日报聚合摘要

## 功能概述

从 Gmail 拉取 newsletter 标签邮件，进行多源聚合分析，输出结构化洞察。

**输出通道：**
| 通道 | 依赖 | 说明 |
|------|------|------|
| Telegram 消息 | ✅ Telegram 连接 | 即时阅读，必选 |
| Google Docs 文档 | ✅ Google Workspace（`gws` 或 Python client）| 归档留存，必选 |
| TTS 语音 | ✅ Edge TTS | 语音播报，可选 |

> ℹ️ **TTS 语音通过 `text_to_speech` 工具生成**，Telegram 支持音频附件推送。 |

---

## 安装前提

### 1. Gmail 授权
```bash
python ~/.hermes/skills/productivity/google-workspace/scripts/setup.py --check
```
确认输出包含 `AUTHENTICATED`。

### 2. Telegram 连接
Hermes 已连接 Telegram 即可。检查方式：发送测试消息确认通道可用。

### 3. Google Docs 访问
Google Workspace 授权已包含 `documents` scope。使用 `gws` CLI 或 Python client 创建文档。

---

## 配置（环境变量）

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `HERMES_HOME` | `~/.hermes` | Hermes 安装目录 |
| `VENV_PYTHON` | `HERMES_HOME/hermes-agent/venv/bin/python` | Python venv 路径 |
| `GMAIL_QUERY` | `label:newsletter newer_than:1d` | Gmail 搜索条件 |
| `TTS_VOICE` | `zh-CN-XiaoxiaoNeural` | Edge TTS 语音 |
| `TTS_OUTPUT_DIR` | `HERMES_HOME/cron/output` | TTS 文本缓存目录 |
| `GOOGLE_DOCS_FOLDER_ID` | （可选）| Google Docs 存放文件夹 ID，不填则使用根目录 |

---

## 流水线

### Step 1: 数据获取

从 Gmail 拉取满足 `GMAIL_QUERY` 条件的邮件（默认：标签 `newsletter`，过去 24 小时）。

对每封邮件提取：
- 发件人 / 来源媒体名
- 发送时间
- 邮件标题
- 邮件正文（去除 HTML 标签、追踪链接、页脚等噪音）

### Step 2: 多邮件聚合分析

将所有邮件作为信息语料库进行横向聚合，按以下维度输出：

#### 2.1 共振信号（Cross-Newsletter Signals）
多刊共提的主题 / 技术 / 事件。判定规则：≥2 封来自不同来源的邮件提到同一话题 → **强信号**，优先展示。列出「哪些来源提到」。

#### 2.2 核心洞察提炼
5–10 条最有价值的观点、判断或预测。每条：媒体名 + 1-2 句话浓缩。优先选有明确立场、反常识、或有预测性的观点。

#### 2.3 技术 / 工具 / 产品动态
新工具、新模型、新产品、新版本。格式：`名称` — 一句话说明（来源）。

#### 2.4 市场 / 行业趋势观察
归纳行业、市场方向判断。若不同来源观点有分歧，**并列呈现**，注明分歧所在。

#### 2.5 长尾高价值信息
只有一封邮件提到，但判断为高价值、易被忽视的内容。

#### 2.6 今日信息密度评估
篇数、涉及领域、信息密度（高/中/低）。

### Step 3: 输出

#### 3.1 发送 Telegram 消息
通过 Hermes `send_message` 工具发送到 `telegram:TELEGRAM_CHAT_ID`。

#### 3.2 创建 Google Docs 文档
通过 `google_api.py docs create` 或直接调用 Google Docs API 创建文档，写入 Markdown 格式报告内容。

#### 3.3 生成 TTS 语音
将「共振信号 + 核心洞察」部分（500–800 字）通过 Edge TTS 生成语音文件。使用语音 `TTS_VOICE`（默认 `zh-CN-XiaoxiaoNeural`）。

---

## 输出格式

```markdown
# Newsletter 日报 · {日期}

> 📊 **信息密度：{高/中/低}** | 涉及领域：{领域列表}

---

## 🔔 共振信号
...

---

## 💡 核心洞察
...

---

## 🛠️ 技术 / 产品动态
...

---

## 📈 市场 / 行业趋势
...

---

## 🔎 长尾高价值信息
...

---

## 📋 来源邮件清单
| 来源 | 标题 | 日期 |
|------|------|------|
| ... | ... | ... |
```

---

## 脚本

| 脚本 | 说明 |
|------|------|
| `scripts/run_pipeline.py` | **推荐入口** — 一键完成全流程：Gmail 拉取 → LLM 分析 → Telegram 消息 → Google Docs 文档 → TTS |
| `scripts/fetch_newsletters.py` | 从 Gmail 获取 newsletter 列表 |
| `scripts/analyze_newsletters.py` | 聚合分析（输出分析 prompt 供 LLM 使用） |
| `scripts/send_to_telegram.py` | 格式化 Telegram 消息 |
| `scripts/create_google_doc.py` | 在 Google Docs 创建文档 |
| `scripts/generate_tts.py` | 生成 TTS 语音 |

**推荐用法（一条命令完成数据获取，分析由 Agent 自动完成）：**
```bash
python ~/.hermes/skills/newsletter-daily-summary/scripts/run_pipeline.py
```

---

## 关键实现细节

### google_api.py 是 CLI 脚本，不能 import
```python
VENV_PYTHON = os.environ.get("VENV_PYTHON", f"{HERMES_HOME}/hermes-agent/venv/bin/python")
cmd = [VENV_PYTHON, f"{HERMES_HOME}/skills/productivity/google-workspace/scripts/google_api.py", "gmail", "search", query]
result = subprocess.run(cmd, capture_output=True, text=True)
data = json.loads(result.stdout)
```

### TTS 语音语言问题
Edge TTS 对中英混合文本可能自动切换语言包，导致英文词被机器腔读出。**必须显式指定 `voice=zh-CN-XiaoxiaoNeural`**，且输入文本中尽量将英文缩写转为中文（如 "GPT-5.4" → "GPT 五点四"），或用纯英文 API（Azure TTS）。

### Google Docs 文档创建
使用 `scripts/create_google_doc.py` 创建文档，支持：
- 传入文档标题和内容（Markdown 格式）
- 可指定文件夹 ID（`GOOGLE_DOCS_FOLDER_ID`）
- 返回文档 URL 供 Agent 分享

### Gmail label 搜索
`label:newsletter newer_than:1d` 直接有效，`gmail labels` 返回空不代表标签不存在。

### Telegram 音频推送
`send_message` 支持 `media` 参数，Telegram 可直接推送 MP3 音频文件作为语音消息。

### Pipeline LLM 调用超时
`run_pipeline.py` 调用 OpenAI API 超时时（如无 API Key 或网络问题），应 fallback 到用 Hermes 内置 LLM 能力手动完成分析：直接用 `fetch_newsletters.py` 拉取数据 → Hermes 内置分析 → `send_message` + `text_to_speech` 推送。

### Gmail fetch 超时
`fetch_newsletters.py` 逐封获取正文，单次 API 调用超时 30s，15 封邮件最多约 450s。若超时可调小 `GMAIL_QUERY --max` 参数（如 `--max 5`），或直接用 `google_api.py` 单次搜索减少循环次数。

### HTML 邮件清洗
`strip_html()` 去除标签后需再用 `html.unescape()` 解码 HTML 实体，追踪参数残留用正则过滤。

### 状态标记

- ✅ Gmail 拉取（`fetch_newsletters.py`）— 单封超时 30s，整批约 5-8 分钟
- ⚠️ 多邮件聚合分析 — 由 Agent 自身大模型自动完成（无需外部 API Key）
- ✅ Telegram 消息推送（`send_message`）
- ✅ Google Docs 文档创建（`create_google_doc.py`）
- ✅ TTS 生成 — `text_to_speech` 工具可用，Telegram 支持音频附件推送
- ✅ 环境变量配置
- ❌ 不依赖飞书 MCP / lark-cli