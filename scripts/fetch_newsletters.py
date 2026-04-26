#!/usr/bin/env python3
"""从 Gmail 获取过去 24 小时所有 newsletter 标签的邮件。"""

import sys
import re
import json
import html
import subprocess
import os

HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
VENV_PYTHON = os.environ.get("VENV_PYTHON", f"{HERMES_HOME}/hermes-agent/venv/bin/python")
GMAIL_QUERY = os.environ.get("GMAIL_QUERY", "label:newsletter newer_than:1d")

def strip_html(text):
    """去除 HTML 标签、特殊字符、追踪链接等噪音。"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'<img[^>]*>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_sender_name(sender):
    """从 sender 字符串提取媒体名。格式: "媒体名 <email@domain.com>" """
    match = re.search(r'"?([^"<]+)"?\s*<', sender)
    if match:
        return match.group(1).strip()
    return sender.split('<')[0].strip().strip('"') if '<' in sender else sender

def run_gapi(args):
    """运行 google_api.py 并返回 JSON 结果。"""
    cmd = [VENV_PYTHON, f"{HERMES_HOME}/skills/productivity/google-workspace/scripts/google_api.py"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Gmail API 错误: {result.stderr[:200]}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"❌ JSON 解析失败: {result.stdout[:200]}", file=sys.stderr)
        return None

def fetch_newsletters():
    """获取过去 24 小时所有 newsletter 标签的邮件。"""
    print("📥 正在从 Gmail 获取 newsletter...", file=sys.stderr, flush=True)
    
    emails = run_gapi(["gmail", "search", GMAIL_QUERY, "--max", "20"])
    if not emails:
        print("📭 没有找到新的 newsletter", file=sys.stderr)
        return []
    
    if isinstance(emails, dict) and "error" in emails:
        print(f"❌ Gmail API 错误: {emails['error']}", file=sys.stderr)
        return []
    
    print(f"✅ 找到 {len(emails)} 封 newsletter，开始获取正文...", file=sys.stderr, flush=True)
    
    newsletters = []
    for email in emails:
        msg_id = email.get("id")
        sender = email.get("from", "未知来源")
        subject = email.get("subject", "(无标题)")
        date = email.get("date", "")
        snippet = email.get("snippet", "")
        
        try:
            full_email = run_gapi(["gmail", "get", msg_id])
            if full_email and isinstance(full_email, dict):
                body = full_email.get("body", "")
            else:
                body = snippet
            if not body or len(body) < 50:
                body = snippet
            body = strip_html(body)
        except Exception as e:
            print(f"⚠️ 获取邮件 {msg_id} 正文失败: {e}", file=sys.stderr)
            body = strip_html(snippet)
        
        source = extract_sender_name(sender)
        
        newsletters.append({
            "id": msg_id,
            "source": source,
            "sender": sender,
            "subject": subject,
            "date": date,
            "body": body,
            "char_count": len(body)
        })
        print(f"  ✓ {source}: {subject[:50]}", file=sys.stderr)
    
    return newsletters

if __name__ == "__main__":
    newsletters = fetch_newsletters()
    print(json.dumps(newsletters, ensure_ascii=False, indent=2))