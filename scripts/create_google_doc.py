#!/usr/bin/env python3
"""
在 Google Docs 创建 Newsletter 日报文档。

用法：
  python create_google_doc.py --title "Newsletter 日报 · 2026-04-28" --content-file /tmp/report.md
  python create_google_doc.py --title "Newsletter 日报" --content-file /tmp/report.md --folder-id FOLDER_ID

输出 JSON：
  {"documentId": "xxx", "title": "xxx", "webViewLink": "https://docs.google.com/..."}
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# 确保同目录的 _hermes_home 可导入
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    from _hermes_home import get_hermes_home
except ImportError:
    def get_hermes_home():
        return Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))

HERMES_HOME = get_hermes_home()
TOKEN_PATH = HERMES_HOME / "google_token.json"


def markdown_to_docs_content(markdown: str) -> list:
    """
    将 Markdown 文本转换为 Google Docs API 的 content 数组。
    每个段落是一个 element，包含 paragraph 对象。
    """
    content = []
    lines = markdown.split("\n")
    current_heading = None  # 用于追踪当前章节

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # 检测标题（# ## ### 等）
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            heading_level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            # 创建段落元素（作为标题）
            content.append({
                "paragraph": {
                    "elements": [{
                        "textRun": {
                            "content": heading_text,
                            "textStyle": {
                                "bold": True,
                                "fontSize": {
                                    "magnitude": 16 - heading_level * 2 if heading_level <= 3 else 10,
                                    "unit": "pt"
                                } if heading_level <= 3 else None,
                            }
                        }
                    }],
                    "paragraphStyle": {
                        "namedStyleType": f"HEADING_{min(heading_level, 6)}",
                    }
                }
            })
            i += 1
            continue

        # 检测分隔线
        if re.match(r"^---+$", line) or re.match(r"^\*\*\*+$", line):
            i += 1
            continue

        # 检测无序列表项（- 或 * 开头）
        list_match = re.match(r"^[-*+]\s+(.*)", line)
        if list_match:
            item_text = list_match.group(1).strip()
            # 移除加粗/斜体标记
            item_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", item_text)
            item_text = re.sub(r"\*([^*]+)\*", r"\1", item_text)
            item_text = re.sub(r"`([^`]+)`", r"\1", item_text)

            content.append({
                "paragraph": {
                    "elements": [{
                        "textRun": {
                            "content": item_text,
                        }
                    }],
                    "paragraphStyle": {
                        "namedStyleType": "LIST Bullet",
                    }
                }
            })
            i += 1
            continue

        # 表格行（| xxx | xxx |）
        if line.startswith("|"):
            # 跳过分隔行 |---|---|...
            if re.match(r"^\|[-:\s|]+\|$", line):
                i += 1
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            # 简化处理：把表格行作为普通段落输出
            row_text = " | ".join(cells)
            content.append({
                "paragraph": {
                    "elements": [{
                        "textRun": {
                            "content": row_text,
                            "textStyle": {
                                "fontSize": {"magnitude": 10, "unit": "pt"},
                            }
                        }
                    }],
                }
            })
            i += 1
            continue

        # 检测 callout 块（> 开头）
        if line.startswith(">"):
            callout_text = line.lstrip("> ").strip()
            # 移除加粗
            callout_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", callout_text)

            content.append({
                "paragraph": {
                    "elements": [{
                        "textRun": {
                            "content": callout_text,
                            "textStyle": {
                                "italic": True,
                            }
                        }
                    }],
                    "paragraphStyle": {
                        "namedStyleType": "NORMAL_TEXT",
                    }
                }
            })
            i += 1
            continue

        # 空行 -> 跳过
        if not line.strip():
            i += 1
            continue

        # 普通文本
        clean_line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        clean_line = re.sub(r"\*([^*]+)\*", r"\1", clean_line)
        clean_line = re.sub(r"`([^`]+)`", r"\1", clean_line)
        clean_line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean_line)

        content.append({
            "paragraph": {
                "elements": [{
                    "textRun": {
                        "content": clean_line,
                    }
                }],
                "paragraphStyle": {
                    "namedStyleType": "NORMAL_TEXT",
                }
            }
        })
        i += 1

    return content


def build_docs_requests(markdown: str) -> list:
    """
    构建 Google Docs API 的 batchUpdate 请求。
    """
    content = markdown_to_docs_content(markdown)

    # 文档标题从 Markdown 第一行提取（# 标题）
    # 然后用 documents.create 创建文档，最后用 batchUpdate 写入内容
    return [
        {
            "insertText": {
                "location": {"index": 1},
                "text": "\n"
            }
        }
    ]


def create_doc(title: str, content: str, folder_id: str = "") -> dict:
    """使用 Google Docs API 创建文档并写入内容。"""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_PATH.exists():
        print(json.dumps({"error": "Not authenticated. Run setup.py first."}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        import json as _json
        TOKEN_PATH.write_text(_json.dumps({
            "type": "authorized_user",
            **json.loads(creds.to_json())
        }, indent=2))

    service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Step 1: 创建空白文档
    document = {
        "title": title,
    }
    if folder_id:
        document["parents"] = [folder_id]

    created = service.documents().create(body=document).execute()
    doc_id = created.get("documentId")
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    # Step 2: 将 Markdown 转换为 Google Docs 内容并写入
    docs_content = markdown_to_docs_content(content)

    # 使用 batchUpdate 批量插入内容
    requests = []
    index = 1  # 文档从 index 1 开始（0 是特殊位置）

    for element in docs_content:
        if "paragraph" in element:
            para = element["paragraph"]
            text_content = ""
            for elem in para.get("elements", []):
                if "textRun" in elem:
                    text_content += elem["textRun"].get("content", "")

            # 插入段落文本
            requests.append({
                "insertText": {
                    "location": {"index": index},
                    "text": text_content + "\n"
                }
            })

            # 应用段落样式
            style = para.get("paragraphStyle", {})
            style_type = style.get("namedStyleType", "NORMAL_TEXT")

            if style_type.startswith("HEADING"):
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": index, "endIndex": index + len(text_content) + 1},
                        "paragraphStyle": {"namedStyleType": style_type},
                        "fields": "namedStyleType"
                    }
                })
            elif style_type == "LIST Bullet":
                requests.append({
                    "updateParagraphStyle": {
                        "range": {"startIndex": index, "endIndex": index + len(text_content) + 1},
                        "paragraphStyle": {
                            "namedStyleType": "NORMAL_TEXT",
                            "bullet": {"listId": "bullet_list", "nestingLevel": 0}
                        },
                        "fields": "namedStyleType,bullet"
                    }
                })

            index += len(text_content) + 1  # +1 for newline

    if requests:
        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests}
        ).execute()

    result = {
        "documentId": doc_id,
        "title": title,
        "webViewLink": doc_url,
    }

    # 如果指定了文件夹，确保文档移动到该文件夹
    if folder_id:
        try:
            drive_service.files().update(
                fileId=doc_id,
                addParents=folder_id,
                removeParents="root",
            ).execute()
        except Exception as e:
            print(f"⚠️ 移动文档到文件夹失败: {e}", file=sys.stderr)

    return result


def main():
    parser = argparse.ArgumentParser(description="在 Google Docs 创建 Newsletter 日报文档")
    parser.add_argument("--title", required=True, help="文档标题")
    parser.add_argument("--content-file", required=True, help="Markdown 内容文件路径")
    parser.add_argument("--folder-id", default="", help="Google Drive 文件夹 ID（可选）")
    args = parser.parse_args()

    # 读取内容文件
    content_path = Path(args.content_file)
    if not content_path.exists():
        print(json.dumps({"error": f"Content file not found: {args.content_file}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    content = content_path.read_text(encoding="utf-8")

    result = create_doc(args.title, content, args.folder_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()