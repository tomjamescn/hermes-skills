#!/usr/bin/env python3
"""
Newsletter 聚合分析脚本。
接收 fetch_newsletters.py 的 JSON 输出，进行多邮件横向聚合分析，
生成结构化洞察，输出 Markdown 格式报告。
"""

import sys
import json
import re
from datetime import datetime

def load_newsletters():
    """从 stdin 读取 fetch_newsletters.py 的 JSON 输出。"""
    try:
        data = sys.stdin.read()
        newsletters = json.loads(data)
        if isinstance(newsletters, dict) and "error" in newsletters:
            print(f"❌ 错误: {newsletters['error']}", file=sys.stderr)
            return []
        return newsletters if isinstance(newsletters, list) else []
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        return []

def build_analysis_prompt(newsletters, today):
    """构建分析 prompt。"""
    sources = [n.get("source", "未知") for n in newsletters]
    subjects = [n.get("subject", "") for n in newsletters]
    bodies = [n.get("body", "")[:500] for n in newsletters]

    nl = "\n"
    email_list = nl.join([f"- **{n.get('source', '未知')}**：{n.get('subject', '')}（{n.get('date', '')}）" for n in newsletters])
    email_bodies = nl.join([f"### [{n.get('source', '未知')}] {n.get('subject', '')}\n{n.get('body', '')[:500]}" for n in newsletters])

    rules = (
        "**规则：**\n"
        "- 各章节之间用 `---` 分隔，确保视觉上有呼吸感\n"
        "- 列表项每条不超过 3 行，避免信息过密\n"
        "- 不要用装饰性分隔符，用标准 Markdown 标题\n"
        "- callout 块用于元信息摘要，方便快速扫读"
    )

    prompt = f"""# Newsletter 日报分析任务

今天是 {today}，共获取 {len(newsletters)} 封 newsletter：

## 邮件清单
{email_list}

## 各邮件正文摘要（各取前500字符）
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
""" + "".join([f"| {n.get('source', '未知')} | {n.get('subject', '')} | {n.get('date', '')} |\n" for n in newsletters]) + f"""
---

{rules}"""

    return prompt

def analyze_newsletters(newsletters):
    """
    对 newsletters 进行聚合分析。
    返回包含所有分析维度的字典。
    """
    if not newsletters:
        return {
            "error": "没有找到 newsletter，无法进行分析",
            "sections": {}
        }

    today = datetime.now().strftime("%Y-%m-%d")
    analysis_prompt = build_analysis_prompt(newsletters, today)

    return {
        "analysis_prompt": analysis_prompt,
        "count": len(newsletters),
        "sources": [n.get("source", "未知") for n in newsletters],
        "subjects": [n.get("subject", "") for n in newsletters],
        "date": today
    }

def main():
    newsletters = load_newsletters()
    result = analyze_newsletters(newsletters)

    if "error" in result:
        print(result["error"])
        sys.exit(0)

    print(result["analysis_prompt"])

if __name__ == "__main__":
    main()