#!/usr/bin/env python3
"""
发送分析结果到飞书。
接收 LLM 生成的 Markdown 报告，发送到飞书 DM。
"""

import os
import sys
import json

FEISHU_TARGET = f"feishu:{os.environ.get('FEISHU_DM_CHAT_ID', '')}"

def format_feishu_message(analysis_text, source_count, info_density=None, domains=None):
    """
    将分析文本格式化为飞书消息。
    analysis_text: LLM 生成的 Markdown 报告
    """
    today = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
    
    header = f"📬 **Newsletter 日报 · {today}**\n"
    header += f"（共 {source_count} 封）\n"
    
    if info_density:
        header += f"📊 信息密度：{info_density}"
    if domains:
        header += f" | 涉及领域：{', '.join(domains)}"
    header += "\n\n"
    
    return header + analysis_text

def send_feishu_message(message):
    """
    格式化消息，返回格式化的消息内容供 Agent 发送。
    Agent 会通过 send_message 工具发送到飞书。
    """
    return {
        "action": "send",
        "target": FEISHU_TARGET,
        "message": message
    }

if __name__ == "__main__":
    # 从 stdin 读取 LLM 分析结果
    analysis = sys.stdin.read()
    
    # 从环境或参数获取邮件数量
    source_count = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    
    formatted = format_feishu_message(analysis, source_count)
    print(formatted)