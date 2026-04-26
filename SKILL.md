---
name: newsletter-daily-summary
description: Newsletter 日报聚合摘要。从 Gmail 拉取 newsletter 进行多邮件聚合分析，生成结构化洞察，推送到飞书消息 + 云文档 + TTS 语音。支持 Hermes 原生飞书工具集（如未接入飞书 MCP 则跳过文档步骤）。
tags: [Gmail, Newsletter, 聚合分析, 飞书, TTS, 语音推送]
version: 1.0.0
author: Hermes
metadata:
  hermes:
    triggers:
      - "帮我看今天的 newsletter"
      - "整理一下 newsletter"
      - "newsletter 日报"
      - "newsletter 摘要"
    schedule: "30 6 * * *"
---

# Newsletter 日报聚合摘要

## 功能概述

从 Gmail 拉取 newsletter 标签邮件，进行多源聚合分析，输出结构化洞察。

**输出通道：**
| 通道 | 依赖 | 说明 |
|------|------|------|
| 飞书消息 | ✅ 飞书连接 | 即时阅读，必选 |
| 飞书云文档 | ⚠️ 飞书 MCP (`feishu_doc`) | 归档留存，可选 |
| TTS 语音 | ✅ Edge TTS | 语音播报，可选 |

> ℹ️ **无飞书 MCP 时也能运行** — 仅跳过「创建飞书文档」步骤，消息推送和 TTS 不受影响。

---

## 安装前提

### 1. Gmail 授权
```bash
python ~/.hermes/skills/productivity/google-workspace/scripts/setup.py --check
```
确认输出包含 `AUTHENTICATED`。

### 2. 飞书连接（消息推送）
Hermes 已连接飞书即可。检查方式：发送测试消息确认通道可用。

### 3. 飞书云文档（可选，需飞书 MCP）
如需创建飞书云文档，需要 Hermes 已接入飞书 MCP（`feishu_doc` 工具集可用）。

**检查飞书 MCP 是否可用：**
- 在本对话中尝试调用 `feishu_doc` 工具
- 或查看 Hermes 配置中 MCP servers 是否包含飞书

如未接入飞书 MCP，文档创建步骤自动跳过，不影响消息和 TTS 功能。

---

## 配置（环境变量）

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `HERMES_HOME` | `~/.hermes` | Hermes 安装目录 |
| `VENV_PYTHON` | `HERMES_HOME/hermes-agent/venv/bin/python` | Python venv 路径 |
| `FEISHU_DM_CHAT_ID` | （必填）| 飞书 DM chat_id，格式 `oc_xxxxxxxx` |
| `GMAIL_QUERY` | `label:newsletter newer_than:1d` | Gmail 搜索条件 |
| `TTS_VOICE` | `zh-CN-XiaoxiaoNeural` | Edge TTS 语音 |
| `TTS_OUTPUT_DIR` | `HERMES_HOME/cron/output` | TTS 文本缓存目录 |

**获取 FEISHU_DM_CHAT_ID**：
在飞书打开与 Bot 的对话，URL 中 `im/p2p` 后的 `oc_` 开头 ID 即为 chat_id。

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

#### 3.1 发送飞书消息
通过 Hermes `send_message` 工具发送到 `feishu:FEISHU_DM_CHAT_ID`。

#### 3.2 创建飞书云文档（可选）
**仅当 `feishu_doc` 工具集可用时执行。** 使用 Hermes 原生飞书 MCP 工具创建云文档（无需 lark-cli）。

如飞书 MCP 未接入，跳过此步骤，不影响其他输出。

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
| `scripts/run_pipeline.py` | **推荐入口** — 一键完成全流程：Gmail 拉取 → LLM 分析 → 飞书消息 → 飞书文档 → TTS |
| `scripts/fetch_newsletters.py` | 从 Gmail 获取 newsletter 列表 |
| `scripts/analyze_newsletters.py` | 聚合分析（输出分析 prompt 供 LLM 使用） |
| `scripts/send_to_feishu.py` | 格式化飞书消息 |
| `scripts/generate_tts.py` | 生成 TTS 语音 |

**推荐用法（一条命令完成全流程）：**
```bash
FEISHU_DM_CHAT_ID=oc_xxx OPENAI_API_KEY=sk-xxx \
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

### 飞书 MCP 可用性检测
在 Agent 执行时检测：
- 检查工具列表中是否存在 `feishu_doc` 工具
- 或尝试调用 `feishu_doc create` 微调操作，失败则跳过文档步骤

### Gmail label 搜索
`label:newsletter newer_than:1d` 直接有效，`gmail labels` 返回空不代表标签不存在。

### 飞书音频限制
`send_message` 的 media 参数**飞书不支持音频附件**，TTS 文件保存到本地 `TTS_OUTPUT_DIR` 供手动播放。

### HTML 邮件清洗
`strip_html()` 去除标签后需再用 `html.unescape()` 解码 HTML 实体，追踪参数残留用正则过滤。

---

## 状态标记

- ✅ Gmail 拉取（`fetch_newsletters.py`）
- ✅ 多邮件聚合分析（`analyze_newsletters.py`）
- ✅ 飞书消息推送（`send_to_feishu.py`）
- ✅ TTS 生成（`generate_tts.py`）
- ✅ 飞书文档写入 — 使用 Hermes 原生 `feishu_doc` 工具（如已接入飞书 MCP）
- ✅ 环境变量配置
- ❌ 不依赖 lark-cli