#!/usr/bin/env python3
"""
Newsletter Daily Summary — 完整流水线入口。

数据获取 + 报告生成（由 Agent 自身 LLM 完成分析）
→ Telegram 消息 + Google Docs 文档 + TTS 语音

用法：
  python run_pipeline.py
  GMAIL_QUERY="label:newsletter newer_than:2d" python run_pipeline.py
"""

import os
import sys
import json
import re
import subprocess
import html
from datetime import datetime

# ── 路径配置 ──────────────────────────────────────────────
HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
VENV_PYTHON = os.environ.get("VENV_PYTHON", f"{HERMES_HOME}/hermes-agent/venv/bin/python")
SKILL_DIR   = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = SKILL_DIR

OUTPUT_DIR = os.environ.get("TTS_OUTPUT_DIR", f"{HERMES_HOME}/cron/output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 环境变量 ──────────────────────────────────────────────
GMAIL_QUERY          = os.environ.get("GMAIL_QUERY", "label:newsletter newer_than:1d")
GOOGLE_DOCS_FOLDER_ID = os.environ.get("GOOGLE_DOCS_FOLDER_ID", "")

# ── Step 1: Gmail 拉取 ────────────────────────────────────
def fetch_newsletters():
    print("📥 正在从 Gmail 获取 newsletter...", flush=True)
    cmd = [
        VENV_PYTHON,
        f"{SCRIPTS_DIR}/fetch_newsletters.py",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "GMAIL_QUERY": GMAIL_QUERY})
    if result.returncode != 0:
        print(f"❌ fetch 失败: {result.stderr[:300]}", file=sys.stderr)
        return []
    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict) and "error" in data:
            print(f"❌ Gmail API 错误: {data['error']}", file=sys.stderr)
            return []
        print(f"✅ 获取到 {len(data)} 封 newsletter", flush=True)
        return data
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}\nstdout: {result.stdout[:200]}", file=sys.stderr)
        return []

# ── Step 2: 生成分析 prompt（供 Agent LLM 使用）──────────
def build_analysis_prompt(newsletters):
    today = datetime.now().strftime("%Y-%m-%d")
    nl = "\n"

    email_list = nl.join([
        f"- **{n.get('source', '未知')}**：{n.get('subject', '')}（{n.get('date', '')}）"
        for n in newsletters
    ])
    email_bodies = nl.join([
        f"### [{n.get('source', '未知')}] {n.get('subject', '')}\n{n.get('body', '')[:800]}"
        for n in newsletters
    ])

    prompt = f"""# Newsletter 日报分析任务

今天是 {today}，共获取 {len(newsletters)} 封 newsletter：

## 邮件清单
{email_list}

## 各邮件正文摘要（各取前800字符）
{email_bodies}

---

请对以上 newsletter 进行横向聚合分析，生成以下格式的 Markdown 报告。**这份文档是给人读的，务必注重结构与可读性**：

> 📊 **信息密度：{{高/中/低}}** | 涉及领域：{{领域列表，用顿号分隔}}

---

## 🔔 共振信号
≥2 个来源共同提到的主题，注明「哪些来源提到」。

---

## 💡 核心洞察
每条：媒体名 + 核心观点（1-2句话）。优先选有立场、反常识、有预测性的内容。

---

## 🛠️ 技术 / 产品动态
新工具、新模型、新产品、新版本。格式：`名称` — 一句话说明（来源）。

---

## 📈 市场 / 行业趋势
行业方向判断。若来源有分歧，并列呈现并注明分歧所在。

---

## 🔎 长尾高价值信息
只有一封邮件提到但判断为高价值、易被忽视的内容。

---

## 📋 来源邮件清单
| 来源 | 标题 | 日期 |
|------|------|------|
""" + "".join([
        f"| {n.get('source', '未知')} | {n.get('subject', '')} | {n.get('date', '')} |\n"
        for n in newsletters
    ]) + f"""
---

**规则：**
- 各章节之间用 `---` 分隔
- 列表项每条不超过 3 行
- callout 块用于元信息摘要
"""
    return prompt

# ── Step 3: 保存原始邮件数据（供 Agent 后续使用）────────
def save_raw_data(newsletters) -> str:
    """将原始 newsletter 数据保存为 JSON，供 Agent 分析使用。"""
    today = datetime.now().strftime("%Y%m%d")
    path = f"{OUTPUT_DIR}/newsletters_raw_{today}.json"
    with open(path, "w") as f:
        json.dump(newsletters, f, ensure_ascii=False, indent=2)
    print(f"💾 原始数据已保存: {path}", flush=True)
    return path

# ── Step 4: 提取 TTS 文本（通用提取函数）────────────────
def extract_tts_text(report: str) -> str:
    """从报告中提取「共振信号 + 核心洞察」用于 TTS，限制在 800 字以内。"""
    lines = report.split("\n")
    sections = {}
    current = None
    content = []

    for line in lines:
        m = re.match(r"^##?\s+(?:[🔔💡]|共振信号|核心洞察)", line)
        if m:
            if current:
                sections[current] = "\n".join(content)
            current = line
            content = []
        elif current:
            content.append(line)

    if current:
        sections[current] = "\n".join(content)

    tts_parts = []
    for title in ["## 🔔 共振信号", "## 💡 核心洞察", "共振信号", "核心洞察"]:
        if title in sections:
            tts_parts.append(sections[title])

    text = "\n\n".join(tts_parts)

    # 清理 Markdown 格式
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > 800:
        text = text[:800] + "..."

    return text

# ── 输出指令（供 Agent 执行）──────────────────────────────
def get_agent_instructions(newsletters, raw_data_path, tts_text, analysis_prompt) -> dict:
    """
    返回供 Hermes Agent 执行的所有指令。
    Agent 使用自身大模型完成分析，然后推送结果。
    """
    return {
        "telegram": {
            "action": "send",
            "target": "telegram",  # 使用 home channel，由 Agent 自动路由
        },
        "tts": {
            "text": tts_text,
            "output_path": f"{OUTPUT_DIR}/newsletter_tts_{datetime.now().strftime('%Y%m%d')}.mp3",
        },
        "google_docs": {
            "folder_id": GOOGLE_DOCS_FOLDER_ID or None,
        },
        "raw_data": {
            "path": raw_data_path,
            "count": len(newsletters),
            "sources": [{"source": n.get("source"), "subject": n.get("subject")} for n in newsletters],
        },
        "analysis_prompt": analysis_prompt,
    }

# ── 主流水线 ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("📬 Newsletter Daily Summary Pipeline")
    print("=" * 50)

    # Step 1: 获取 newsletter
    newsletters = fetch_newsletters()
    if not newsletters:
        print("❌ 没有获取到任何 newsletter，退出。", file=sys.stderr)
        sys.exit(1)

    # Step 2: 保存原始数据
    raw_data_path = save_raw_data(newsletters)

    # Step 3: 构建分析 prompt（供 Agent 使用）
    analysis_prompt = build_analysis_prompt(newsletters)
    prompt_path = f"{OUTPUT_DIR}/newsletter_prompt_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(prompt_path, "w") as f:
        f.write(analysis_prompt)
    print(f"📝 分析 prompt 已保存: {prompt_path}", flush=True)

    # Step 4: 预提取 TTS 文本（从各邮件摘要中提取共振/洞察）
    # 在 Agent 完成分析前，尝试从现有 newsletter 内容中提取关键信息作为 TTS 候选
    tts_candidates = []
    for n in newsletters:
        body = n.get("body", "")[:500]
        if body:
            tts_candidates.append(body)
    pre_tts_text = "\n\n".join(tts_candidates)[:800] if tts_candidates else ""

    # Step 5: 生成 Agent 指令
    instructions = get_agent_instructions(newsletters, raw_data_path, pre_tts_text, analysis_prompt)

    # 输出指令 JSON
    print("\n" + "=" * 50)
    print("✅ 数据获取完成，以下步骤由 Agent 智能体执行：")
    print("=" * 50)
    print(json.dumps(instructions, ensure_ascii=False, indent=2))

    print(f"\n📋 Newsletter 数量: {len(newsletters)}")
    print(f"📄 原始数据: {raw_data_path}")
    print(f"📝 分析 prompt: {prompt_path}")
    print(f"🔊 TTS 候选文本: （{len(pre_tts_text)} 字）")

if __name__ == "__main__":
    main()