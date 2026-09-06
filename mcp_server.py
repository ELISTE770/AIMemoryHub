#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Universal AI Memory Hub - Model Context Protocol (MCP) Server
Runs via stdio for Claude Desktop, Claude Code, Antigravity, Cursor, etc.
Zero external dependencies - built with Python standard library.
"""

import sys
import os
import json
from pathlib import Path

# Ensure memory_hub is importable
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

import memory_hub

# Force UTF-8 on Windows stdio
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# stdout IS the JSON-RPC channel: a single stray print() corrupts the stream and the client
# drops the connection. memory_hub prints diagnostics on several paths (watcher errors,
# failed writes, corrupt database), so the real stdout is kept private here and everything
# else is pushed to stderr, where MCP clients collect logs.
_PROTOCOL_OUT = sys.stdout
sys.stdout = sys.stderr


def log(message):
    """Diagnostics go to stderr - never to the protocol channel."""
    try:
        sys.stderr.write(f"[ai-memory-hub] {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def send_response(response):
    _PROTOCOL_OUT.write(json.dumps(response, ensure_ascii=False) + "\n")
    _PROTOCOL_OUT.flush()

def get_tools_list():
    return [
        {
            "name": "get_active_memory",
            "description": "שליפת כל הזיכרונות, העובדות, המגבלות והסגנון של המשתמש עבור הפרופיל והמצב הפעיל כרגע",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "אופציונלי: סינון לפי קטגוריה ('facts', 'commands', 'constraints', 'styles', 'instructions')"
                    }
                }
            }
        },
        {
            "name": "remember",
            "description": (
                "הצעת עובדה, איסור, הנחיה או סגנון חדש לזיכרון הקבוע של המשתמש, בטקסט חופשי "
                "(למשל: 'האתר שלי הוא X', 'אל תמחק הערות קוד'). "
                "חשוב: הכלי אינו שומר לזיכרון - הוא רושם הצעה שממתינה לאישור ידני של המשתמש "
                "באפליקציה. יש לדווח למשתמש שההצעה נרשמה וממתינה לאישורו, ולא שהמידע נשמר."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {
                        "type": "string",
                        "maxLength": 2000,
                        "description": "המשפט או ההנחיה להצעה (המערכת תסווג ותשבץ אוטומטית)"
                    },
                    "target_profile": {
                        "type": "string",
                        "description": "אופציונלי: מזהה פרופיל יעד ('default', 'business', 'code')"
                    }
                }
            }
        },
        {
            "name": "search_memory",
            "description": "חיפוש עובדות, הנחיות או חוקים ספציפיים בכל בסיס הזיכרון של המשתמש לפי מילת מפתח",
            "inputSchema": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "מילת חיפוש (למשל: 'אתר', 'חתימה', 'הערות', 'עסקים')"
                    }
                }
            }
        },
        {
            "name": "switch_mode",
            "description": (
                "החלפת סביבת העבודה (הפרופיל) הפעילה של המשתמש. "
                "שים לב: פעולה זו משנה את קובצי החוקים בכל הפרויקטים של המשתמש, ולכן היא "
                "מושבתת כברירת מחדל ותחזיר שגיאה עד שהמשתמש יאפשר אותה בהגדרות."
            ),
            "inputSchema": {
                "type": "object",
                "required": ["mode_name"],
                "properties": {
                    "mode_name": {
                        "type": "string",
                        "description": "שם המצב או מזהה הפרופיל להפעלה"
                    }
                }
            }
        },
        {
            "name": "check_memory_conflicts",
            "description": "בדיקת סתירות לוגיות או כפילויות קיימות בזיכרון המשתמש",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ]

def handle_tool_call(tool_name, args):
    if tool_name == "get_active_memory":
        cat = args.get("category")
        p_data = memory_hub.get_current_profile_data()
        cur_id = memory_hub.get_current_profile_id()
        profiles = memory_hub.get_profiles()
        cur_name = profiles.get(cur_id, {}).get("name", cur_id)

        if cat:
            if cat not in p_data:
                # Used to fall through and silently return the ENTIRE memory instead.
                return {
                    "error": f"קטגוריה לא מוכרת: '{cat}'",
                    "valid_categories": sorted(k for k, v in p_data.items() if isinstance(v, list)),
                }
            items = p_data[cat]
            return {
                "profile": cur_name,
                "category": cat,
                "count": len(items),
                "items": items
            }
        return {
            "active_profile": cur_name,
            "profile_id": cur_id,
            "memory": p_data
        }

    elif tool_name == "remember":
        text = (args.get("text") or "").strip()
        if not text:
            return {"success": False, "error": "לא התקבל טקסט לזכירה"}
        if len(text) > 2000:
            return {"success": False, "error": "הטקסט ארוך מדי (מקסימום 2000 תווים)"}

        target_prof = args.get("target_profile")

        # Parse and conflict-check WITHOUT writing: an AI may propose memory, never store it.
        ok, parsed, conflicts, msg = memory_hub.add_conversational_memory(
            text, target_profile=target_prof, auto_save=False
        )
        if not ok:
            return {"success": False, "error": msg}

        prop = memory_hub.add_proposal(parsed, origin="mcp", raw_text=text, conflicts=conflicts)

        res = {
            "success": True,
            "status": "pending_approval",
            "message": "ההצעה נרשמה וממתינה לאישור המשתמש באפליקציה. היא אינה בזיכרון עדיין.",
            "proposal_id": prop["id"],
            "classified_category": prop["category"],
            "target_profile": prop["target_profile"],
            "proposed_item": prop["item"],
            "pending_total": memory_hub.count_pending_proposals(),
        }
        if conflicts:
            res["warnings"] = f"שים לב: זוהו {len(conflicts)} סתירות מול מידע קיים בזיכרון."
            res["conflicts"] = conflicts
        return res

    elif tool_name == "search_memory":
        query = (args.get("query") or "").strip().lower()
        if not query:
            return {"query": "", "count": 0, "results": []}
        tokens = [t for t in query.split() if len(t) > 1]
        db = memory_hub.load_db()
        matches = []
        for pid, pinfo in db.get("profiles", {}).items():
            pname = pinfo.get("name", pid)
            pdata = pinfo.get("data", {})
            for cat, items in pdata.items():
                if not isinstance(items, list): continue
                for it in items:
                    it_str = json.dumps(it, ensure_ascii=False).lower()
                    score = 0
                    if query in it_str:
                        score += 10
                    for token in tokens:
                        if token in it_str:
                            score += 2
                    if score > 0:
                        matches.append({
                            "score": score,
                            "profile": pname,
                            "profile_id": pid,
                            "category": cat,
                            "item": it
                        })
        matches.sort(key=lambda x: x["score"], reverse=True)
        return {
            "query": query,
            "count": len(matches),
            "results": matches[:20]
        }

    elif tool_name == "switch_mode":
        mode_name = (args.get("mode_name") or "").strip()
        profiles = memory_hub.get_profiles()
        target_id = None
        for pid, pinfo in profiles.items():
            if pid.lower() == mode_name.lower() or pinfo.get("name", "").lower() == mode_name.lower():
                target_id = pid
                break
        if not target_id:
            return {"success": False, "error": f"מצב '{mode_name}' לא נמצא",
                    "available_modes": [p.get("name", pid) for pid, p in profiles.items()]}

        # Switching the active profile rewrites the rule files of EVERY project folder,
        # so it stays off unless the owner explicitly enables it in the settings.
        settings = memory_hub.load_db().get("settings", {})
        if not settings.get("allowMcpModeSwitch", False):
            return {
                "success": False,
                "status": "not_allowed",
                "error": "החלפת מצב דרך MCP מושבתת. ניתן להפעיל אותה בהגדרות האפליקציה.",
                "requested_mode": profiles[target_id].get("name", target_id),
            }

        ok = memory_hub.set_current_profile(target_id)
        if ok:
            return {"success": True, "message": f"הוחלף מצב פעיל בהצלחה ל: {profiles[target_id].get('name')}"}
        return {"success": False, "error": "שגיאה בעת החלפת הפרופיל"}

    elif tool_name == "check_memory_conflicts":
        conflicts = memory_hub.detect_conflicts()
        return {
            "conflict_count": len(conflicts),
            "conflicts": conflicts
        }

    raise ValueError(f"כלי לא מוכר: {tool_name}")

def handle_request(request):
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "ai-memory-hub",
                    "version": "1.0.1"
                }
            }
        })

    if method == "notifications/initialized":
        return

    if method == "tools/list":
        return send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": get_tools_list()
            }
        })

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        try:
            result_data = handle_tool_call(tool_name, tool_args)
            return send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result_data, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            })
        except Exception as e:
            return send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            })

    if req_id is not None:
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        })

def main():
    log("server started")
    for line in sys.stdin:
        line_str = line.strip()
        if not line_str:
            continue

        try:
            req = json.loads(line_str)
        except json.JSONDecodeError as e:
            # Malformed frame: answer per JSON-RPC instead of silently ignoring it, or the
            # client waits forever for a reply that never comes.
            log(f"parse error: {e}")
            send_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            })
            continue

        try:
            handle_request(req)
        except Exception as e:
            log(f"internal error handling {req.get('method')}: {e}")
            req_id = req.get("id") if isinstance(req, dict) else None
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": f"Internal error: {e}"}
                })
    log("stdin closed, shutting down")

if __name__ == "__main__":
    main()
