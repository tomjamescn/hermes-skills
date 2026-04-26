#!/usr/bin/env python3
"""
生成 TTS 语音文件。
将 Newsletter 日报的「共振信号 + 核心洞察」部分转化为语音文件。
"""

import sys
import re
import os
from datetime import datetime

HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
OUTPUT_DIR = os.environ.get("TTS_OUTPUT_DIR", f"{HERMES_HOME}/cron/output")

def extract_core_sections(markdown_text):
    """
    从 Markdown 报告中提取核心章节（共振信号 + 核心洞察）用于 TTS。
    控制在 500-800 字以内。
    """
    lines = markdown_text.split('\n')
    sections = {}
    current_section = None
    current_content = []
    
    for line in lines:
        # 检测章节标题
        if re.match(r'^##?\s+(?:🔔|💡|共振信号|核心洞察)', line):
            if current_section and current_content:
                sections[current_section] = '\n'.join(current_content)
            current_section = line
            current_content = []
        elif current_section:
            current_content.append(line)
    
    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content)
    
    # 提取核心内容
    core_text = ""
    
    for section_title, content in sections.items():
        # 清理 Markdown 格式
        clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)  # 链接
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean)  # 粗体
        clean = re.sub(r'\*([^*]+)\*', r'\1', clean)  # 斜体
        clean = re.sub(r'^[-*+]\s+', '', clean, flags=re.MULTILINE)  # 列表标记
        clean = re.sub(r'^#+\s+', '', clean, flags=re.MULTILINE)  # 标题标记
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        if clean:
            core_text += f"{section_title}\n{clean}\n\n"
    
    # 截断到 800 字
    if len(core_text) > 800:
        core_text = core_text[:800] + "..."
    
    return core_text

def generate_tts_source(text, output_path=None):
    """
    生成 TTS 源文本文件。
    Hermes Agent 会用 text_to_speech 工具将其转化为语音。
    """
    if not text or len(text.strip()) < 20:
        return None
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{OUTPUT_DIR}/newsletter_tts_{timestamp}.txt"
    
    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(text)
    
    return output_path

if __name__ == "__main__":
    markdown = sys.stdin.read()
    core = extract_core_sections(markdown)
    
    if not core:
        print("# Newsletter 日报\n今日无核心内容可供播报。", file=sys.stderr)
        sys.exit(0)
    
    output_path = generate_tts_source(core)
    print(f"📝 TTS 源文本已保存: {output_path}")
    print(f"📝 字符数: {len(core)}")
    print("---TTS_SOURCE---")
    print(core)