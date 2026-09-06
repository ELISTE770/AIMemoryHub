#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Conversation & Email Memory Miner for Universal AI Memory Hub.
Scans, extracts, and parses conversations and emails from Antigravity, Claude, Cursor,
Windsurf, ChatGPT, folder archives, and .eml mailboxes to discover actionable rules,
facts, constraints, styles, and instructions.
"""

import os
import glob
import json
import re
import email
from email import policy
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


# =========================================================================
# 1. Multi-App Chat Discovery
# =========================================================================

def discover_antigravity_chats(max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Scans the Antigravity local brain directory for conversation transcripts.
    Returns a list of conversation metadata dicts sorted by modification date (newest first).
    """
    brain_dir = os.path.expanduser("~/.gemini/antigravity/brain")
    if not os.path.isdir(brain_dir):
        return []

    pattern = os.path.join(brain_dir, "*", ".system_generated", "logs", "transcript.jsonl")
    matched_files = glob.glob(pattern)

    conversations: List[Dict[str, Any]] = []
    for fpath in matched_files:
        try:
            mtime = os.path.getmtime(fpath)
            conv_id = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(fpath))))
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            title = _extract_first_user_title(fpath)
            if not title:
                title = f"שיחה ({conv_id[:8]}...)"

            conversations.append({
                "id": conv_id,
                "title": title,
                "path": fpath,
                "app": "Google Antigravity",
                "mtime": mtime,
                "time_str": time_str,
                "size_kb": size_kb
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations[:max_results]


def discover_claude_chats(max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Scans Claude Code and Claude Desktop conversation logs and transcripts.
    Locations: ~/.claude/projects/, ~/.claude/transcripts/, ~/.claude/history/
    """
    home = os.path.expanduser("~")
    claude_dir = os.path.join(home, ".claude")
    if not os.path.isdir(claude_dir):
        return []

    search_patterns = [
        os.path.join(claude_dir, "projects", "**", "*.jsonl"),
        os.path.join(claude_dir, "projects", "**", "*.json"),
        os.path.join(claude_dir, "transcripts", "*.jsonl"),
        os.path.join(claude_dir, "history", "*.jsonl"),
    ]

    matched_files: List[str] = []
    for pat in search_patterns:
        matched_files.extend(glob.glob(pat, recursive=True))

    conversations: List[Dict[str, Any]] = []
    for fpath in matched_files:
        try:
            mtime = os.path.getmtime(fpath)
            conv_id = os.path.splitext(os.path.basename(fpath))[0]
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            title = _extract_first_user_title(fpath)
            if not title:
                title = f"שיחת Claude ({conv_id[:12]})"

            conversations.append({
                "id": conv_id,
                "title": title,
                "path": fpath,
                "app": "Claude Code",
                "mtime": mtime,
                "time_str": time_str,
                "size_kb": size_kb
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations[:max_results]


def discover_cursor_chats(max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Scans Cursor IDE workspace storage and user directories for chat sessions.
    Locations: %APPDATA%/Cursor/User/workspaceStorage/, ~/.cursor/
    """
    appdata = os.environ.get("APPDATA", "")
    home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(appdata, "Cursor", "User", "workspaceStorage"),
        os.path.join(home, ".cursor"),
    ]

    matched_files: List[str] = []
    for sdir in search_dirs:
        if os.path.isdir(sdir):
            for pat in ["**/*.jsonl", "**/*.json"]:
                matched_files.extend(glob.glob(os.path.join(sdir, pat), recursive=True))

    conversations: List[Dict[str, Any]] = []
    for fpath in matched_files:
        try:
            base = os.path.basename(fpath).lower()
            if not any(k in base or k in fpath.lower() for k in ["chat", "conversation", "prompt", "history"]):
                continue

            mtime = os.path.getmtime(fpath)
            conv_id = os.path.splitext(base)[0]
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            title = _extract_first_user_title(fpath) or f"שיחת Cursor ({conv_id[:12]})"
            conversations.append({
                "id": conv_id,
                "title": title,
                "path": fpath,
                "app": "Cursor IDE",
                "mtime": mtime,
                "time_str": time_str,
                "size_kb": size_kb
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations[:max_results]


def discover_windsurf_chats(max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Scans Windsurf / Codeium directories for chat and cascade transcripts.
    Locations: %APPDATA%/Windsurf/User/workspaceStorage/, ~/.codeium/windsurf/
    """
    appdata = os.environ.get("APPDATA", "")
    home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(appdata, "Windsurf", "User", "workspaceStorage"),
        os.path.join(home, ".codeium", "windsurf"),
    ]

    matched_files: List[str] = []
    for sdir in search_dirs:
        if os.path.isdir(sdir):
            for pat in ["**/*.jsonl", "**/*.json", "**/*.txt"]:
                matched_files.extend(glob.glob(os.path.join(sdir, pat), recursive=True))

    conversations: List[Dict[str, Any]] = []
    for fpath in matched_files:
        try:
            base = os.path.basename(fpath).lower()
            if not any(k in base or k in fpath.lower() for k in ["cascade", "chat", "conversation", "memories"]):
                continue

            mtime = os.path.getmtime(fpath)
            conv_id = os.path.splitext(base)[0]
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            title = _extract_first_user_title(fpath) or f"שיחת Windsurf ({conv_id[:12]})"
            conversations.append({
                "id": conv_id,
                "title": title,
                "path": fpath,
                "app": "Windsurf IDE",
                "mtime": mtime,
                "time_str": time_str,
                "size_kb": size_kb
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations[:max_results]


def discover_chatgpt_exports(max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Discovers ChatGPT conversations.json exports in user folders (Downloads, Documents, Desktop).
    """
    home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Desktop"),
        home
    ]

    matched_files: List[str] = []
    for sdir in search_dirs:
        if os.path.isdir(sdir):
            c_file = os.path.join(sdir, "conversations.json")
            if os.path.isfile(c_file):
                matched_files.append(c_file)
            for sub in glob.glob(os.path.join(sdir, "*chatgpt*", "conversations.json")):
                matched_files.append(sub)

    conversations: List[Dict[str, Any]] = []
    for fpath in matched_files:
        try:
            mtime = os.path.getmtime(fpath)
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            conversations.append({
                "id": os.path.basename(fpath),
                "title": f"קובץ יצוא שיחות ChatGPT ({size_kb} KB)",
                "path": fpath,
                "app": "ChatGPT Export",
                "mtime": mtime,
                "time_str": time_str,
                "size_kb": size_kb
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations[:max_results]


def discover_copilot_chats(max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Scans VS Code storage for GitHub Copilot Chat conversations.
    Locations:
    - %APPDATA%/Code/User/globalStorage/emptyWindowChatSessions/*.jsonl
    - %APPDATA%/Code/User/globalStorage/chat-sessions/**/*.jsonl
    - %APPDATA%/Code/User/workspaceStorage/**/chatSessions/*.jsonl
    """
    appdata = os.environ.get("APPDATA", "")
    code_dir = os.path.join(appdata, "Code", "User")
    if not os.path.isdir(code_dir):
        return []

    search_patterns = [
        os.path.join(code_dir, "globalStorage", "emptyWindowChatSessions", "*.jsonl"),
        os.path.join(code_dir, "globalStorage", "chat-sessions", "**", "*.jsonl"),
        os.path.join(code_dir, "workspaceStorage", "*", "chatSessions", "*.jsonl"),
    ]

    matched_files: List[str] = []
    for pat in search_patterns:
        matched_files.extend(glob.glob(pat, recursive=True))

    conversations: List[Dict[str, Any]] = []
    for fpath in matched_files:
        try:
            mtime = os.path.getmtime(fpath)
            conv_id = os.path.splitext(os.path.basename(fpath))[0]
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            title = _extract_copilot_first_title(fpath) or f"שיחת Copilot ({conv_id[:12]})"
            conversations.append({
                "id": conv_id,
                "title": title,
                "path": fpath,
                "app": "GitHub Copilot",
                "mtime": mtime,
                "time_str": time_str,
                "size_kb": size_kb
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations[:max_results]


def discover_cline_chats(max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Scans Cline and Roo Code tasks in VS Code globalStorage.
    Locations:
    - %APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/*/ui_messages.json
    - %APPDATA%/Code/User/globalStorage/rooveterinaryinc.roo-cline/tasks/*/ui_messages.json
    """
    appdata = os.environ.get("APPDATA", "")
    code_dir = os.path.join(appdata, "Code", "User", "globalStorage")
    if not os.path.isdir(code_dir):
        return []

    search_patterns = [
        os.path.join(code_dir, "saoudrizwan.claude-dev", "tasks", "*", "ui_messages.json"),
        os.path.join(code_dir, "rooveterinaryinc.roo-cline", "tasks", "*", "ui_messages.json"),
        os.path.join(code_dir, "saoudrizwan.claude-dev", "tasks", "*", "api_conversation_history.json"),
        os.path.join(code_dir, "rooveterinaryinc.roo-cline", "tasks", "*", "api_conversation_history.json"),
    ]

    matched_files: List[str] = []
    for pat in search_patterns:
        matched_files.extend(glob.glob(pat))

    seen_tasks = set()
    conversations: List[Dict[str, Any]] = []
    for fpath in matched_files:
        try:
            task_dir = os.path.dirname(fpath)
            if task_dir in seen_tasks:
                continue
            seen_tasks.add(task_dir)

            mtime = os.path.getmtime(fpath)
            task_id = os.path.basename(task_dir)
            time_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)

            app_label = "Roo Code" if "roo" in fpath.lower() else "Cline"
            title = _extract_cline_first_title(fpath) or f"משימת {app_label} ({task_id[:12]})"

            conversations.append({
                "id": task_id,
                "title": title,
                "path": fpath,
                "app": f"{app_label} (VS Code)",
                "mtime": mtime,
                "time_str": time_str,
                "size_kb": size_kb
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["mtime"], reverse=True)
    return conversations[:max_results]


def discover_chats(app_name: str = "antigravity", max_results: int = 30) -> List[Dict[str, Any]]:
    """
    Unified dispatcher for discovering chats across various AI tools.
    Supports: "antigravity", "claude", "cursor", "windsurf", "copilot", "cline", "chatgpt", or "all".
    """
    app_lower = (app_name or "antigravity").lower()
    if "all" in app_lower or "הכל" in app_lower:
        all_chats: List[Dict[str, Any]] = []
        for fn in [discover_antigravity_chats, discover_copilot_chats, discover_cline_chats,
                   discover_claude_chats, discover_cursor_chats, discover_windsurf_chats, discover_chatgpt_exports]:
            try:
                all_chats.extend(fn(max_results=max_results))
            except Exception:
                pass
        all_chats.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return all_chats[:max_results]
    elif "copilot" in app_lower or "github" in app_lower or "vscode" in app_lower:
        return discover_copilot_chats(max_results=max_results)
    elif "cline" in app_lower or "roo" in app_lower:
        return discover_cline_chats(max_results=max_results)
    elif "antigravity" in app_lower or "google" in app_lower:
        return discover_antigravity_chats(max_results=max_results)
    elif "claude" in app_lower:
        return discover_claude_chats(max_results=max_results)
    elif "cursor" in app_lower:
        return discover_cursor_chats(max_results=max_results)
    elif "windsurf" in app_lower or "codeium" in app_lower:
        return discover_windsurf_chats(max_results=max_results)
    elif "chatgpt" in app_lower or "openai" in app_lower:
        return discover_chatgpt_exports(max_results=max_results)
    else:
        return discover_antigravity_chats(max_results=max_results)


# =========================================================================
# 2. Parsing Helpers (Transcripts, JSON, Plain Text)
# =========================================================================

def _extract_text_content(content: Any) -> str:
    """Safely extracts plain string from various LLM content types (str, list of parts, dict)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                parts.append(str(p.get("text") or p.get("content") or ""))
        return " ".join(parts)
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    return str(content or "")


def _extract_first_user_title(fpath: str, max_lines: int = 60) -> Optional[str]:
    """Helper to extract a short preview title from a transcript or JSON file."""
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i > max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "USER_INPUT":
                        content = _extract_text_content(data.get("content", ""))
                        req_match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
                        raw = req_match.group(1).strip() if req_match else re.sub(r"<[^>]+>", "", content).strip()
                        first_line = raw.split("\n")[0].strip()
                        if first_line and not first_line.startswith("{{"):
                            return first_line[:60] + ("..." if len(first_line) > 60 else "")
                    elif "title" in data:
                        return str(data["title"])[:60]
                    # Also handle Copilot format
                    v = data.get("v")
                    if isinstance(v, dict):
                        if v.get("customTitle") and v.get("customTitle") != "New Chat":
                            return str(v.get("customTitle"))[:60]
                        if "message" in v and isinstance(v["message"], dict):
                            txt = v["message"].get("text", "").strip()
                            if txt:
                                return txt.split("\n")[0][:60]
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _extract_copilot_first_title(fpath: str) -> Optional[str]:
    """Extracts first user message or session title from a VS Code Copilot Chat session."""
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    v = d.get("v")
                    if isinstance(v, dict):
                        if v.get("customTitle") and v.get("customTitle") != "New Chat":
                            return str(v.get("customTitle"))[:60]
                        if "message" in v and isinstance(v["message"], dict):
                            txt = v["message"].get("text", "").strip()
                            if txt:
                                return txt.split("\n")[0][:60]
                        if "requests" in v and isinstance(v["requests"], list) and v["requests"]:
                            r0 = v["requests"][0]
                            if isinstance(r0, dict) and "message" in r0 and isinstance(r0["message"], dict):
                                txt = r0["message"].get("text", "").strip()
                                if txt:
                                    return txt.split("\n")[0][:60]
                except Exception:
                    pass
    except Exception:
        pass
    return None


def _extract_cline_first_title(fpath: str) -> Optional[str]:
    """Extracts first user message title from a Cline or Roo Code task."""
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        if item.get("text"):
                            txt = str(item.get("text", "")).strip()
                            if txt:
                                return txt.split("\n")[0][:60]
                        if item.get("role") == "user":
                            content = item.get("content")
                            txt = _extract_text_content(content).strip()
                            if txt:
                                return txt.split("\n")[0][:60]
    except Exception:
        pass
    return None


def parse_copilot_chat(fpath: str, max_chars: int = 24000) -> str:
    """
    Parses a VS Code Copilot Chat jsonl file into clean dialogue.
    """
    if not os.path.isfile(fpath):
        return ""

    messages: List[str] = []
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue

                k = data.get("k")
                v = data.get("v")

                if isinstance(v, dict) and "message" in v and isinstance(v["message"], dict):
                    txt = str(v["message"].get("text") or "").strip()
                    if txt:
                        messages.append(f"משתמש (User):\n{txt}")
                elif k and len(k) == 3 and k[0] == "requests" and k[2] == "response" and isinstance(v, list):
                    resp_parts = [it.get("value", "") for it in v if isinstance(it, dict) and isinstance(it.get("value"), str)]
                    resp_txt = "".join(resp_parts).strip()
                    if resp_txt:
                        snippet = resp_txt[:500] + ("\n[...]" if len(resp_txt) > 500 else "")
                        messages.append(f"עוזר (Assistant):\n{snippet}")
    except Exception as e:
        return f"שגיאה בפענוח שיחת Copilot: {e}"

    if not messages:
        return ""

    full_text = "\n\n---\n\n".join(messages)
    if len(full_text) > max_chars:
        half = max_chars // 2
        return full_text[:half] + "\n\n[... דילוג על חלק מהשיחה ...]\n\n" + full_text[-half:]
    return full_text


def parse_cline_chat(fpath: str, max_chars: int = 24000) -> str:
    """
    Parses a Cline or Roo Code task JSON file into clean dialogue.
    """
    if not os.path.isfile(fpath):
        return ""

    messages: List[str] = []
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                if "say" in item or "type" in item:
                    say_type = item.get("say") or item.get("type")
                    txt = str(item.get("text") or "").strip()
                    if txt:
                        if say_type in ["task", "user_feedback"]:
                            messages.append(f"משתמש (User):\n{txt}")
                        elif say_type in ["text", "completion_result", "assistant"]:
                            snippet = txt[:500] + ("\n[...]" if len(txt) > 500 else "")
                            messages.append(f"עוזר (Assistant):\n{snippet}")
                elif "role" in item:
                    role = item.get("role")
                    content = item.get("content")
                    txt = _extract_text_content(content).strip()
                    if txt:
                        prefix = "משתמש (User):" if role == "user" else "עוזר (Assistant):"
                        snippet = txt[:500] + ("\n[...]" if len(txt) > 500 else "")
                        messages.append(f"{prefix}\n{snippet}")
    except Exception as e:
        return f"שגיאה בפענוח שיחת Cline/Roo: {e}"

    if not messages:
        return ""

    full_text = "\n\n---\n\n".join(messages)
    if len(full_text) > max_chars:
        half = max_chars // 2
        return full_text[:half] + "\n\n[... דילוג על חלק מהשיחה ...]\n\n" + full_text[-half:]
    return full_text


def parse_transcript_file(fpath: str, max_chars: int = 24000) -> str:
    """
    Parses a transcript.jsonl file into clean dialogue text suitable for LLM analysis.
    Preserves user demands, corrections, questions, and model explanations.
    """
    if not os.path.isfile(fpath):
        return ""

    # Check if this is a VS Code Copilot session file
    if "emptyWindowChatSessions" in fpath or "chatSessions" in fpath:
        return parse_copilot_chat(fpath, max_chars=max_chars)

    messages: List[str] = []
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue

                stype = data.get("type")
                content = _extract_text_content(data.get("content", ""))

                if stype == "USER_INPUT" and content:
                    req_match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
                    if req_match:
                        text = req_match.group(1).strip()
                    else:
                        text = re.sub(r"<[^>]+>", "", content).strip()

                    # Filter out purely automatic system messages
                    if text and not text.startswith("{{ CHECKPOINT"):
                        messages.append(f"משתמש (User):\n{text}")

                elif stype == "PLANNER_RESPONSE" and content:
                    text = content.strip()
                    if text:
                        snippet = text[:500] + ("\n[...]" if len(text) > 500 else "")
                        messages.append(f"עוזר (Assistant):\n{snippet}")

    except Exception as e:
        return f"שגיאה בקריאת הקובץ: {e}"

    if not messages:
        return ""

    full_text = "\n\n---\n\n".join(messages)
    if len(full_text) > max_chars:
        half = max_chars // 2
        return full_text[:half] + "\n\n[... דילוג על חלק מהשיחה ...]\n\n" + full_text[-half:]

    return full_text


# =========================================================================
# 3. Email Archive & Threads Parser (.eml and Raw Email)
# =========================================================================

def parse_email_file(fpath: str, max_chars: int = 24000) -> str:
    """
    Parses an RFC822 / .eml email file into structured text containing headers,
    body, sender, recipient, and signature blocks.
    """
    if not os.path.isfile(fpath):
        return ""

    try:
        with open(fpath, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)

        subject = msg.get("Subject", "(ללא נושא)")
        from_hdr = msg.get("From", "(שולח לא ידוע)")
        to_hdr = msg.get("To", "(נמען לא ידוע)")
        date_hdr = msg.get("Date", "")

        body_parts: List[str] = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    try:
                        body_parts.append(part.get_content())
                    except Exception:
                        pass
                elif ctype == "text/html" and not body_parts:
                    try:
                        raw_html = part.get_content()
                        clean = re.sub(r"<[^>]+>", " ", raw_html)
                        clean = re.sub(r"\s+", " ", clean).strip()
                        body_parts.append(clean)
                    except Exception:
                        pass
        else:
            try:
                body_parts.append(msg.get_content())
            except Exception:
                pass

        full_body = "\n\n".join(p.strip() for p in body_parts if p.strip())

        output = (
            f"=== אימייל: {subject} ===\n"
            f"מאת (From): {from_hdr}\n"
            f"אל (To): {to_hdr}\n"
            f"תאריך: {date_hdr}\n"
            f"נושא: {subject}\n\n"
            f"תוכן ההודעה:\n{full_body}"
        )

        if len(output) > max_chars:
            output = output[:max_chars] + "\n\n[... תוכן המייל קוצר ...]"
        return output

    except Exception as e:
        return f"שגיאה בפענוח קובץ המייל: {e}"


def parse_raw_email(raw_text: str, max_chars: int = 24000) -> str:
    """
    Parses pasted email text or email thread, identifying sender, subject,
    salutations, and signature lines.
    """
    text = raw_text.strip()
    if not text:
        return ""

    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > max_chars:
        half = max_chars // 2
        return text[:half] + "\n\n[... דילוג על חלק מהמייל ...]\n\n" + text[-half:]
    return text


# =========================================================================
# 4. Folder Batch Parser (Entire Folder of Chats/Emails)
# =========================================================================

def parse_folder_chats(folder_path: str, max_chars: int = 30000, max_files: int = 25) -> str:
    """
    Recursively scans a directory for chat transcripts, notes, and emails (.jsonl, .json, .txt, .md, .eml).
    Combines excerpts from each into a coherent, organized corpus for memory extraction.
    """
    if not os.path.isdir(folder_path):
        return f"התיקייה אינה קיימת: {folder_path}"

    valid_exts = {".jsonl", ".json", ".txt", ".md", ".eml"}
    found_files: List[Tuple[str, float]] = []

    for root, _, files in os.walk(folder_path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in valid_exts:
                full_p = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(full_p)
                    found_files.append((full_p, mtime))
                except Exception:
                    continue

    if not found_files:
        return f"לא נמצאו קובצי שיחה או מיילים נתמכים בתיקייה: {folder_path}"

    found_files.sort(key=lambda x: x[1], reverse=True)
    selected_files = found_files[:max_files]

    combined_sections: List[str] = []
    budget_per_file = max(500, max_chars // len(selected_files))

    for fpath, _ in selected_files:
        fname = os.path.basename(fpath)
        ext = os.path.splitext(fname)[1].lower()

        if ext == ".jsonl":
            parsed = parse_transcript_file(fpath, max_chars=budget_per_file)
        elif ext == ".eml":
            parsed = parse_email_file(fpath, max_chars=budget_per_file)
        else:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if len(content) > budget_per_file:
                    content = content[:budget_per_file] + "\n[...]"
                parsed = content
            except Exception:
                continue

        if parsed.strip():
            combined_sections.append(f"### [קובץ: {fname}]\n{parsed.strip()}")

    result = "\n\n" + ("=" * 40) + "\n\n".join(combined_sections)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n[... המשך התיקייה נקטם ...]"
    return result


def parse_raw_or_file_chat(file_or_text: str, max_chars: int = 24000, is_email: bool = False) -> str:
    """
    Accepts either a file path, folder path, or raw text string and returns prepared chat/email text.
    Handles single files (.jsonl, .json, .txt, .md, .eml), whole folders, or copy-pasted strings.
    Supports Antigravity, Copilot, Cline, Roo, Claude, Cursor, Windsurf, and ChatGPT.
    """
    if os.path.isdir(file_or_text):
        return parse_folder_chats(file_or_text, max_chars=max_chars)
    elif os.path.isfile(file_or_text):
        fname_lower = os.path.basename(file_or_text).lower()
        if "ui_messages" in fname_lower or "api_conversation_history" in fname_lower:
            return parse_cline_chat(file_or_text, max_chars=max_chars)

        ext = os.path.splitext(file_or_text)[1].lower()
        if ext == ".jsonl":
            return parse_transcript_file(file_or_text, max_chars=max_chars)
        elif ext == ".eml":
            return parse_email_file(file_or_text, max_chars=max_chars)
        elif ext == ".json":
            try:
                with open(file_or_text, "r", encoding="utf-8", errors="ignore") as f:
                    content_head = f.read(800)
                if '"say"' in content_head or '"api_conversation"' in fname_lower or ('"role"' in content_head and '"content"' in content_head):
                    return parse_cline_chat(file_or_text, max_chars=max_chars)
            except Exception:
                pass
            try:
                with open(file_or_text, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if is_email:
                    return parse_raw_email(content, max_chars=max_chars)
                if len(content) > max_chars:
                    half = max_chars // 2
                    return content[:half] + "\n\n[... דילוג על חלק מהתוכן ...]\n\n" + content[-half:]
                return content
            except Exception as e:
                return f"שגיאה בקריאת הקובץ: {e}"
        else:
            try:
                with open(file_or_text, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if is_email:
                    return parse_raw_email(content, max_chars=max_chars)
                if len(content) > max_chars:
                    half = max_chars // 2
                    return content[:half] + "\n\n[... דילוג על חלק מהתוכן ...]\n\n" + content[-half:]
                return content
            except Exception as e:
                return f"שגיאה בקריאת הקובץ: {e}"
    else:
        if is_email:
            return parse_raw_email(file_or_text, max_chars=max_chars)
        text = file_or_text.strip()
        if len(text) > max_chars:
            half = max_chars // 2
            return text[:half] + "\n\n[... דילוג על חלק מהתוכן ...]\n\n" + text[-half:]
        return text


# =========================================================================
# 5. Offline Heuristic Rule Extractor (No API Key Required)
# =========================================================================

def _classify_target_profile(text: str) -> str:
    """Classifies an extracted memory into code, business, or default workspace profile."""
    t = (text or "").lower()
    code_terms = [
        "קוד", "פונקציה", "python", "typescript", "javascript", "code", "bug", "any", "class",
        "async", "await", "import", "type hint", "test", "git", "docker", "css", "html",
        "react", "vue", "backend", "frontend", "api", "console", "debug", "variable"
    ]
    if any(k in t for k in code_terms):
        return "code"

    biz_terms = [
        "עסק", "מחיר", "הצעה", "לקוח", "חתימה", "מחשוב", "תמחור", "שירות", "חשבונית",
        "הזמנה", "ספק", "מכירה", "תשלום", "חוזה", "מייל רשמי"
    ]
    if any(k in t for k in biz_terms):
        return "business"

    return "default"


def extract_heuristic_memories(text: str, source_type: str = "chat") -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Performs fast, rule-based heuristic memory extraction from text/emails without requiring
    an active Gemini API key or network connection.
    Extracts facts (URLs, emails, tech environment), email signatures, constraints,
    commands, styles, and instructions, auto-classifying target profile.
    """
    if not text or not text.strip():
        return False, []

    suggestions: List[Dict[str, Any]] = []
    lines = text.split("\n")

    # 1. URL / Domain Facts
    url_pattern = re.compile(r"https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?")
    for match in url_pattern.finditer(text):
        full_url = match.group(0).rstrip(".,'\")")
        domain = match.group(1)
        if "example.com" in domain:
            continue
        if not any(s.get("data", {}).get("value") == full_url for s in suggestions):
            suggestions.append({
                "category": "facts",
                "title": f"אתר אינטרנט: {domain}",
                "data": {
                    "name": f"אתר {domain}",
                    "value": full_url
                },
                "reason": "זוהה קישור לאתר אינטרנט המוזכר בהתכתבות",
                "quote": full_url[:80],
                "confidence": 0.95,
                "target_profile": _classify_target_profile(full_url)
            })

    # 2. Email Address Facts
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    for match in email_pattern.finditer(text):
        em = match.group(0)
        if "example.com" in em:
            continue
        if not any(s.get("data", {}).get("value") == em for s in suggestions):
            suggestions.append({
                "category": "facts",
                "title": f"כתובת דוא\"ל: {em}",
                "data": {
                    "name": "דוא\"ל קבוע",
                    "value": em
                },
                "reason": "זוהתה כתובת דואר אלקטרוני בהתכתבות",
                "quote": em,
                "confidence": 0.90,
                "target_profile": "business"
            })

    # 3. Tech Stack & Environment Facts
    env_patterns = [
        (r"(?:סביבת הפיתוח שלי היא|מערכת ההפעלה שלי היא|אני עובד על|אני מפתח על|running on)\s+([^\n.?!]{3,50})", "סביבת פיתוח / מערכת הפעלה"),
        (r"(?:שפת הפיתוח המרכזית היא|שפת התכנות שלי היא|אני מתכנת ב|אני כותב ב)\s+([^\n.?!]{3,50})", "שפת פיתוח עיקרית"),
        (r"(?:בסיס הנתונים שלנו הוא|מסד הנתונים הוא|השרת רץ על)\s+([^\n.?!]{3,50})", "בסיס נתונים ותשתית")
    ]
    for pat, label in env_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if val and len(val) <= 60 and not any(s.get("data", {}).get("value") == val for s in suggestions):
                suggestions.append({
                    "category": "facts",
                    "title": f"עובדה טכנית: {label}",
                    "data": {
                        "name": label,
                        "value": val
                    },
                    "reason": f"זוהתה עובדה טכנית לגבי {label}",
                    "quote": match.group(0),
                    "confidence": 0.90,
                    "target_profile": "code"
                })

    # 4. Email Signatures & Greetings (Hebrew & English)
    sig_patterns = [
        (r"(?:בברכה|בברכת [^,\n]+|בכבוד רב|תודה רבה|תודה|שלך)[,:\s]+([^\n]{2,35})", "חתימה בעברית"),
        (r"(?:Best regards|Regards|Sincerely|Thanks & regards|Cheers)[,:\s]+([^\n]{2,35})", "חתימה באנגלית")
    ]
    for pat, label in sig_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            sig_name = match.group(1).strip()
            if sig_name and len(sig_name.split()) <= 8 and len(sig_name) <= 50:
                full_sig = f"בברכה, {sig_name}" if "עברית" in label else f"Best regards, {sig_name}"
                suggestions.append({
                    "category": "commands",
                    "title": f"חתימה אוטומטית: {sig_name}",
                    "data": {
                        "name": "חתימה אישית בסיום",
                        "details": f"לצרף בסיום: '{full_sig}'",
                        "trigger_case": "במענה למיילים, תבניות רשמיות או פניות"
                    },
                    "reason": f"זוהתה חתימת סיום ב-{label}",
                    "quote": match.group(0),
                    "confidence": 0.92,
                    "target_profile": "business"
                })
                break

    # 5. Constraints (איסורים מחייבים: אל ת..., לעולם אל..., אסור..., אל תשתמש ב...)
    constraint_pattern = re.compile(
        r"(?:לעולם אל|אל ת|אל תעשה|אל תשתמש ב|אין להשתמש ב|אסור ל|לא ל|בלי ל|הימנע מ|אל תמחק|ללא שימוש ב|don't|never|do not|avoid|refrain from)\s+([^\n.?!]{5,80})",
        re.IGNORECASE
    )
    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith(("#", "//", "<!--")):
            continue
        c_match = constraint_pattern.search(line_s)
        if c_match:
            stmt = c_match.group(0).strip()
            stmt = re.sub(r"^[-*•\s]+", "", stmt)
            t_prof = _classify_target_profile(stmt)
            suggestions.append({
                "category": "constraints",
                "title": f"איסור: {stmt[:40]}...",
                "data": {
                    "constraint": stmt,
                    "alternative_or_why": "הנחיה זו הוגדרה כאיסור מפורש בשיחה"
                },
                "reason": "זוהה איסור או תיקון מפורש שנאמר בהתכתבות",
                "quote": line_s[:100],
                "confidence": 0.88,
                "target_profile": t_prof
            })
            if len([s for s in suggestions if s["category"] == "constraints"]) >= 4:
                break

    # 6. Commands & Instructions (תקפיד על..., תמיד ת..., וודא ש..., הקפד על..., חובה ל...)
    cmd_pattern = re.compile(
        r"(?:תקפיד על|תמיד ת|תמיד ל|הקפד על|שים לב ש|וודא ש|חובה ל|יש להקפיד על|always|make sure to|ensure that|strictly follow)\s+([^\n.?!]{5,80})",
        re.IGNORECASE
    )
    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        m = cmd_pattern.search(line_s)
        if m:
            stmt = m.group(0).strip()
            stmt = re.sub(r"^[-*•\s]+", "", stmt)
            t_prof = _classify_target_profile(stmt)
            suggestions.append({
                "category": "commands",
                "title": f"הקפדה: {stmt[:40]}...",
                "data": {
                    "name": stmt[:35],
                    "details": stmt,
                    "trigger_case": "בכל משימה או מענה רלוונטי"
                },
                "reason": "זוהתה בקשת הקפדה או נוהל עבודה בשיחה",
                "quote": line_s[:100],
                "confidence": 0.85,
                "target_profile": t_prof
            })
            if len([s for s in suggestions if s["category"] == "commands"]) >= 4:
                break

    # 7. Style Directives (שפה, טון, תמצות, רהיטות)
    style_pattern = re.compile(
        r"(?:ענה תמיד ב|טון דיבור|סגנון מענה|תענה ב|כתוב ב|כתוב תמיד ב|דבר בטון|reply in|always reply in|keep responses)\s+([^\n.?!]{4,60})",
        re.IGNORECASE
    )
    for line in lines:
        m = style_pattern.search(line)
        if m:
            stmt = m.group(0).strip()
            t_prof = _classify_target_profile(stmt)
            suggestions.append({
                "category": "styles",
                "title": f"סגנון: {stmt[:35]}",
                "data": {
                    "aspect": "סגנון ושפה",
                    "instruction": stmt
                },
                "reason": "זוהתה העדפת סגנון וטון דיבור בשיחה",
                "quote": line.strip()[:100],
                "confidence": 0.90,
                "target_profile": t_prof
            })
            break

    return (len(suggestions) > 0), suggestions
