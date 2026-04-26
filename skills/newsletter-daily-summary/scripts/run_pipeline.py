#!/usr/bin/env python3
"""
Newsletter Daily Summary — 完整流水线入口。

一次性完成：Gmail 拉取 → LLM 聚合分析 → 飞书消息 → 飞书云文档 → TTS 语音

依赖工具（按需调用）：
  - text_to_speech : 生成语音（必须有）
  - feishu_doc     : 创建飞书云文档（可选，没有则跳过）
  - send_message   : 发送飞书消息（必须有）

用法：
  python run_pipeline.py
  FEISHU_DM_CHAT_ID=oc_xxx python run_pipeline.py
  FEISHU_DM_CHAT_ID=oc_xxx GMAIL_QUERY="label:newsletter newer_than:2d" python run_pipeline.py
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
FEISHU_DM_CHAT_ID = os.environ.get("FEISHU_DM_CHAT_ID", "oc_a627eed988bd27f34e6d3d3df07b5431")
GMAIL_QUERY       = os.environ.get("GMAIL_QUERY", "label:newsletter newer_than:1d")
TTS_VOICE         = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")

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

# ── Step 2: 构建 LLM 分析 prompt ─────────────────────────
def build_analysis_prompt(newsletters):
    today = datetime.now().strftime("%Y-%m-%d")
    nl = "\n"

    email_list = nl.join([
        f"- **{n.get('source', '未知')}**：{n.get('subject', '')}（{n.get('date', '')}）"
        for n in newsletters
    ])
    email_bodies = nl.join([
        f"### [{n.get('source', '未知')}] {n.get('subject', '')}\n{n.get('body', '')[:600]}"
        for n in newsletters
    ])

    prompt = f"""# Newsletter 日报分析任务

今天是 {today}，共获取 {len(newsletters)} 封 newsletter：

## 邮件清单
{email_list}

## 各邮件正文摘要（各取前600字符）
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

# ── Step 3: 调用 LLM（通过外部脚本）──────────────────────
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
LLM_MODEL    = os.environ.get("LLM_MODEL", "gpt-4o")
LLM_API_KEY  = os.environ.get("OPENAI_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))

def call_llm(prompt: str) -> str:
    """通过 OpenAI-compatible API 调用 LLM 生成分析报告。"""
    print("🤖 正在调用 LLM 进行聚合分析...", flush=True)

    if LLM_PROVIDER == "openai" or not LLM_PROVIDER:
        try:
            import openai
        except ImportError:
            subprocess.check_call([VENV_PYTHON, "-m", "pip", "install", "--quiet", "openai"])
            import openai
        client = openai.OpenAI(api_key=LLM_API_KEY or os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=LLM_MODEL or "gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return response.choices[0].message.content

    elif LLM_PROVIDER == "anthropic":
        try:
            import anthropic
        except ImportError:
            subprocess.check_call([VENV_PYTHON, "-m", "pip", "install", "--quiet", "anthropic"])
            import anthropic
        client = anthropic.Anthropic(api_key=LLM_API_KEY or os.environ.get("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=LLM_MODEL or "claude-sonnet-4",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    else:
        raise ValueError(f"不支持的 LLM_PROVIDER: {LLM_PROVIDER}")

# ── Step 4: 保存分析报告 ─────────────────────────────────
def save_report(report: str, newsletters) -> str:
    today = datetime.now().strftime("%Y%m%d")
    path = f"{OUTPUT_DIR}/newsletter_report_{today}.md"
    with open(path, "w") as f:
        f.write(report)
    print(f"💾 报告已保存: {path}", flush=True)
    return path

# ── Step 5: 提取 TTS 文本 ────────────────────────────────
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

# ── Step 6: 发送飞书消息 ─────────────────────────────────
def feishu_available() -> bool:
    """检测 send_message 工具是否可用（通过检查环境或简单探测）。"""
    # Hermes Agent 总是可以通过 send_message 发送，脚本层返回指令让 Agent 执行
    return True

def format_feishu_message(report: str, count: int) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    header = f"# 📬 Newsletter 日报 · {today}\n> 📊 信息密度：高 | 共 {count} 封\n\n---\n\n"
    return header + report

# ── 工具调用指令（供 Agent 执行）─────────────────────────
def get_tool_instructions(report: str, tts_text: str, feishu_target: str, feishu_msg: str) -> dict:
    """
    返回需要 Agent 执行的工具调用指令。
    返回结构：
      {
        "feishu_message": { "action": "send", "target": "...", "message": "..." },
        "feishu_doc":     { "doc_token": "..." } | None,
        "tts":            { "text": "..." } | None,
      }
    """
    instructions = {
        "feishu_message": {
            "action": "send",
            "target": feishu_target,
            "message": feishu_msg,
        },
        "feishu_doc": None,   # Agent 检测到 feishu_doc 工具可用时创建
        "tts": {
            "text": tts_text,
            "output_path": f"{OUTPUT_DIR}/newsletter_tts_{datetime.now().strftime('%Y%m%d')}.mp3",
            "voice": TTS_VOICE,
        },
    }
    return instructions

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

    # Step 2: 构建 prompt
    prompt = build_analysis_prompt(newsletters)

    # Step 3: 调用 LLM
    try:
        report = call_llm(prompt)
    except Exception as e:
        print(f"❌ LLM 调用失败: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 4: 保存报告
    report_path = save_report(report, newsletters)

    # Step 5: 提取 TTS 文本
    tts_text = extract_tts_text(report)
    tts_path = f"{OUTPUT_DIR}/newsletter_tts_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(tts_path, "w") as f:
        f.write(tts_text)
    print(f"📝 TTS 文本已保存: {tts_path}（{len(tts_text)} 字）", flush=True)

    # Step 6: 准备工具调用指令
    feishu_target = f"feishu:{FEISHU_DM_CHAT_ID}"
    feishu_msg = format_feishu_message(report, len(newsletters))
    instructions = get_tool_instructions(report, tts_text, feishu_target, feishu_msg)

    # 输出指令 JSON（供 Agent 解析）
    print("\n" + "=" * 50)
    print("✅ 流水线执行完成，以下步骤需 Agent 工具执行：")
    print("=" * 50)
    print(json.dumps(instructions, ensure_ascii=False, indent=2))

    # 同时输出文件路径供直接引用
    print(f"\n📄 报告文件: {report_path}")
    print(f"📝 TTS 文本: {tts_path}")
    print(f"🔊 TTS 音频: {instructions['tts']['output_path']}")

if __name__ == "__main__":
    main()