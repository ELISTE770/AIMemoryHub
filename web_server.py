#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Universal AI Memory Hub - Modern Web Dashboard Server
Runs a lightweight, zero-dependency HTTP server over localhost:3456.
Provides full REST API and serves the modern Fluent Web Dashboard.
"""

import sys
import os
import json
import threading
from pathlib import Path
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure local imports work
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import memory_hub
import chat_miner

PORT = int(os.environ.get("AIMEMORY_PORT", 3456))

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BUNDLE_DIR = CURRENT_DIR

HTML_FILE = BUNDLE_DIR / "web" / "index.html"
if not HTML_FILE.exists():
    HTML_FILE = CURRENT_DIR / "web" / "index.html"


def set_windows_autostart(enable=True):
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "AIMemoryHub"
        exe_path = str((CURRENT_DIR / "AIMemoryHub.exe").resolve())
        installed_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "AIMemoryHub" / "AIMemoryHub.exe"
        if installed_exe.exists():
            exe_path = str(installed_exe)

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"Error setting autostart: {e}")
        return False


def get_windows_autostart():
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "AIMemoryHub"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, app_name)
            return True
    except Exception:
        return False


def simulate_prompt(prompt_text):
    text_lower = (prompt_text or "").strip().lower()
    db = memory_hub.load_db()
    profiles = db.get("profiles", {})

    detected_id = "default"
    reason = "שיחה יומיומית רגילה (ברירת מחדל)"

    biz_triggers = profiles.get("business", {}).get("trigger_keywords", []) + ["מחיר", "הצעה", "תמחור", "לקוח", "מחשוב", "עסק"]
    for bt in biz_triggers:
        if bt.lower() in text_lower:
            detected_id = "business"
            reason = f"זוהה הקשר עסקי עקב התאמה לביטוי '{bt}'"
            break

    if detected_id == "default":
        code_triggers = profiles.get("code", {}).get("trigger_keywords", []) + ["קוד", "פונקציה", "קומפוננטה", "script", "typescript", "javascript", "python", "bug", "שגיאה", "class"]
        for ct in code_triggers:
            if ct.lower() in text_lower:
                detected_id = "code"
                reason = f"זוהה הקשר פיתוח קוד עקב התאמה לביטוי '{ct}'"
                break

    target_prof = profiles.get(detected_id, {})
    pdata = target_prof.get("data", {})

    active_facts = [f for f in pdata.get("facts", []) if f.get("active", True)]
    active_constraints = [c for c in pdata.get("constraints", []) if c.get("active", True)]
    active_commands = [m for m in pdata.get("commands", []) if m.get("active", True)]
    active_styles = [s for s in pdata.get("styles", []) if s.get("active", True)]

    signature = ""
    if detected_id == "business":
        for cmd in active_commands:
            if "חתימה" in cmd.get("name", "") or "בברכה" in cmd.get("details", ""):
                signature = cmd.get("details", "")
                break

    return {
        "prompt": prompt_text,
        "detected_profile_id": detected_id,
        "detected_profile_name": target_prof.get("name", detected_id),
        "reason": reason,
        "signature": signature,
        "rules_applied": {
            "facts": active_facts,
            "constraints": active_constraints,
            "commands": active_commands,
            "styles": active_styles
        }
    }


class MemoryHubHTTPHandler(BaseHTTPRequestHandler):
    server_version = "AIMemoryHub/1.0.1"

    def log_message(self, format, *args):
        # Silence routine request logging to prevent terminal clutter
        pass

    def send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, file_path, content_type="text/html; charset=utf-8"):
        if not file_path.exists():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found")
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html", ""]:
            return self.send_file(HTML_FILE)

        if path in ["/app_icon.png", "/favicon.ico"]:
            icon_file = BUNDLE_DIR / ("app_icon.png" if path == "/app_icon.png" else "app_icon.ico")
            if not icon_file.exists():
                icon_file = CURRENT_DIR / ("app_icon.png" if path == "/app_icon.png" else "app_icon.ico")
            content_type = "image/png" if path == "/app_icon.png" else "image/x-icon"
            return self.send_file(icon_file, content_type=content_type)

        # REST API endpoints
        if path == "/api/status":
            db = memory_hub.load_db()
            cur_id = db.get("currentProfile", "default")
            profiles = db.get("profiles", {})
            conflicts = memory_hub.detect_conflicts()
            settings = db.get("settings", {})
            return self.send_json({
                "success": True,
                "currentProfile": cur_id,
                "profiles": profiles,
                "conflicts": conflicts,
                "settings": settings,
                "version": db.get("version", "1.0.1")
            })

        if path == "/api/memory":
            cur_id = memory_hub.get_current_profile_id()
            p_data = memory_hub.get_current_profile_data()
            return self.send_json({
                "success": True,
                "currentProfile": cur_id,
                "data": p_data
            })

        if path == "/api/conflicts":
            conflicts = memory_hub.detect_conflicts()
            return self.send_json({"success": True, "conflicts": conflicts})

        if path == "/api/settings":
            db = memory_hub.load_db()
            return self.send_json({"success": True, "settings": db.get("settings", {})})

        if path == "/api/search":
            query = parse_qs(parsed.query).get("q", [""])[0].strip()
            if not query:
                return self.send_json({"success": True, "query": "", "count": 0, "results": []})
            tokens = [t.lower() for t in query.split() if len(t) > 1]
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
                        if query.lower() in it_str: score += 10
                        for token in tokens:
                            if token in it_str: score += 2
                        if score > 0:
                            matches.append({"score": score, "profile": pname, "profile_id": pid, "category": cat, "item": it})
            matches.sort(key=lambda x: x["score"], reverse=True)
            return self.send_json({"success": True, "query": query, "count": len(matches), "results": matches[:25]})

        if path == "/api/miner/chats":
            qs = parse_qs(parsed.query)
            app = qs.get("app", ["antigravity"])[0]
            chats = chat_miner.discover_chats(app_name=app, max_results=35)
            return self.send_json({"success": True, "chats": chats, "app": app})

        if path == "/api/analytics":
            db = memory_hub.load_db()
            active_pid = db.get("activeProfile", "default")
            profiles = db.get("profiles", {})
            target_paths = db.get("targetPaths", [])

            categories = {
                "facts": {"name": "עובדות ונתונים", "total": 0, "active": 0, "icon": "📌", "color": "#0ea5e9"},
                "constraints": {"name": "איסורים ומגבלות", "total": 0, "active": 0, "icon": "⛔", "color": "#ef4444"},
                "commands": {"name": "פקודות והתנהגות", "total": 0, "active": 0, "icon": "⚡", "color": "#f59e0b"},
                "styles": {"name": "סגנון וטון מענה", "total": 0, "active": 0, "icon": "🎨", "color": "#8b5cf6"},
                "rules": {"name": "הנחיות מותנות", "total": 0, "active": 0, "icon": "🛡️", "color": "#10b981"},
                "contextFiles": {"name": "מסמכי הקשר", "total": 0, "active": 0, "icon": "📚", "color": "#ec4899"},
            }

            scope_counts = {"global": 0, "project": 0}
            total_items = 0
            active_items = 0

            active_pdata = profiles.get(active_pid, {}).get("data", {})
            for cat_key in categories:
                items = active_pdata.get(cat_key)
                if items is None:
                    if cat_key == "rules":
                        items = active_pdata.get("instructions", [])
                    elif cat_key == "contextFiles":
                        items = active_pdata.get("context_files", [])
                    else:
                        items = []

                if isinstance(items, list):
                    for item in items:
                        total_items += 1
                        categories[cat_key]["total"] += 1
                        is_active = item.get("active", True)
                        if is_active:
                            active_items += 1
                            categories[cat_key]["active"] += 1
                        sc = item.get("scope", "global")
                        if sc == "global":
                            scope_counts["global"] += 1
                        else:
                            scope_counts["project"] += 1

            profile_stats = []
            for pid, pinfo in profiles.items():
                pdata = pinfo.get("data", {})
                count = sum(len(items) for items in pdata.values() if isinstance(items, list))
                profile_stats.append({
                    "id": pid,
                    "name": pinfo.get("name", pid),
                    "is_active": (pid == active_pid),
                    "total_directives": count
                })

            active_projects = sum(1 for p in target_paths if p.get("active", True))

            analytics_data = {
                "success": True,
                "active_profile": {
                    "id": active_pid,
                    "name": profiles.get(active_pid, {}).get("name", active_pid)
                },
                "totals": {
                    "total_directives": total_items,
                    "active_directives": active_items,
                    "inactive_directives": total_items - active_items,
                    "total_projects": len(target_paths),
                    "active_projects": active_projects,
                    "total_profiles": len(profiles)
                },
                "categories": categories,
                "profiles": profile_stats,
                "scope_counts": scope_counts,
                "recent_logs": db.get("logs", [])[-6:] if isinstance(db.get("logs"), list) else []
            }
            return self.send_json(analytics_data)

        if path == "/api/paths":
            paths = memory_hub.get_paths()
            return self.send_json({"success": True, "paths": paths})

        if path == "/api/autostart":
            return self.send_json({"success": True, "enabled": get_windows_autostart()})

        if path == "/api/export":
            db = memory_hub.load_db()
            body = json.dumps(db, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="ai_memory_backup.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body_data = self._read_json_body()

        if path == "/api/paths":
            fpath = (body_data or {}).get("path")
            if not fpath:
                return self.send_json({"success": False, "error": "נתיב תיקייה חסר"}, 400)
            ok, res = memory_hub.add_path(fpath)
            return self.send_json({"success": ok, "entry": res if ok else None, "error": "" if ok else str(res)})

        if path == "/api/paths/toggle":
            fpath = (body_data or {}).get("path")
            active = (body_data or {}).get("active")
            if not fpath:
                return self.send_json({"success": False, "error": "נתיב תיקייה חסר"}, 400)
            ok, state = memory_hub.toggle_path(fpath, active)
            return self.send_json({"success": ok, "active": state})

        if path == "/api/paths/rescan":
            added, total = memory_hub.rescan_projects()
            return self.send_json({"success": True, "newly_added": added, "total": total})

        if path == "/api/cloud/push":
            token = (body_data or {}).get("token")
            gist_id = (body_data or {}).get("gist_id")
            ok, msg, gid = memory_hub.push_to_cloud(token, gist_id)
            return self.send_json({"success": ok, "message": msg, "gist_id": gid})

        if path == "/api/cloud/pull":
            token = (body_data or {}).get("token")
            gist_id = (body_data or {}).get("gist_id")
            ok, msg = memory_hub.pull_from_cloud(token, gist_id)
            return self.send_json({"success": ok, "message": msg})

        if path == "/api/autostart":
            enable = (body_data or {}).get("enable", True)
            ok = set_windows_autostart(enable)
            return self.send_json({"success": ok, "enabled": get_windows_autostart()})

        if path == "/api/simulate":
            prompt = (body_data or {}).get("prompt", "")
            return self.send_json({"success": True, "simulation": simulate_prompt(prompt)})

        if path == "/api/miner/analyze":
            fpath = (body_data or {}).get("path")
            raw_text = (body_data or {}).get("text")
            target = fpath if fpath else (raw_text or "")
            clean_dialogue = chat_miner.parse_raw_or_file_chat(target)
            candidates = []
            if clean_dialogue:
                # 1. Use advanced offline heuristic extraction
                ok, heu_suggestions = chat_miner.extract_heuristic_memories(clean_dialogue)
                if heu_suggestions:
                    for s in heu_suggestions:
                        candidates.append({
                            "text": s.get("quote") or s.get("title") or "",
                            "category": s.get("category") or "facts",
                            "title": s.get("title") or "",
                            "target_profile": s.get("target_profile") or "default",
                            "reason": s.get("reason") or "",
                            "data": s.get("data") or {}
                        })
                # 2. Also check conversational triggers
                lines = clean_dialogue.split("\n")
                for line in lines:
                    line_s = line.strip()
                    if line_s.startswith("משתמש (User):") or line_s.startswith("---") or line_s.startswith("עוזר (Assistant):"):
                        continue
                    if len(line_s) > 8 and any(k in line_s for k in ["תזכור", "אל ", "לעולם לא", "חובה", "האתר שלי", "תמיד", "בבקשה תחתום", "זה לעסקים"]):
                        p_parsed, _p_err = memory_hub.parse_conversational_input(line_s)
                        if p_parsed and p_parsed.get("category") in ["facts", "constraints", "styles", "commands", "instructions"]:
                            if not any(c.get("text") == line_s for c in candidates):
                                candidates.append({
                                    "text": line_s,
                                    "category": p_parsed["category"],
                                    "title": line_s[:50],
                                    "target_profile": p_parsed.get("target_profile") or "default",
                                    "reason": "זוהתה פקודת שיחה ישירה",
                                    "parsed": p_parsed
                                })
            return self.send_json({
                "success": True,
                "candidates": candidates,
                "dialogue_preview": clean_dialogue[:1500] if clean_dialogue else ""
            })

        if path == "/api/remember":
            text = (body_data or {}).get("text", "")
            if not text:
                return self.send_json({"success": False, "error": "טקסט ריק"}, 400)
            ok, p_info, conflicts, msg = memory_hub.add_conversational_memory(text)
            return self.send_json({
                "success": ok,
                "parsed": p_info,
                "conflicts": conflicts,
                "message": msg
            })

        if path == "/api/items":
            cat = (body_data or {}).get("category")
            data = (body_data or {}).get("data", {})
            if not cat or not data:
                return self.send_json({"success": False, "error": "נתונים חסרים"}, 400)
            new_item = memory_hub.add_item(cat, data)
            return self.send_json({"success": True, "item": new_item})

        if path == "/api/toggle":
            cat = (body_data or {}).get("category")
            i_id = (body_data or {}).get("item_id")
            active = (body_data or {}).get("active")
            res = memory_hub.toggle_item(cat, i_id, active)
            return self.send_json({"success": res is not None, "active": res})

        if path == "/api/profile/switch":
            p_id = (body_data or {}).get("profile_id")
            if not p_id:
                return self.send_json({"success": False, "error": "מזהה פרופיל חסר"}, 400)
            ok = memory_hub.set_current_profile(p_id)
            return self.send_json({"success": ok})

        if path == "/api/sync":
            res = memory_hub.inject_all()
            return self.send_json({"success": True, **res})

        if path == "/api/clean_projects":
            res = memory_hub.clean_all_project_folders()
            return self.send_json({"success": True, **res, "message": f"נוקו קבצי חוקים מ-{res.get('cleaned_count', 0)} תיקיות פרויקטים"})

        if path == "/api/conflicts/resolve":
            c_id = (body_data or {}).get("conflict_id")
            action = (body_data or {}).get("action", "delete")
            t_id = (body_data or {}).get("target_item_id")
            p_id = (body_data or {}).get("profile_id")
            ok, msg = memory_hub.resolve_conflict(c_id, action, target_item_id=t_id, profile_id=p_id)
            return self.send_json({"success": ok, "message": msg})

        if path == "/api/settings":
            db = memory_hub.load_db()
            db.setdefault("settings", {}).update(body_data or {})
            memory_hub.save_db(db)
            if db.get("settings", {}).get("autoSyncOnChange", True):
                memory_hub.inject_all()
            return self.send_json({"success": True, "settings": db.get("settings", {})})

        if path == "/api/import":
            if not body_data or not isinstance(body_data, dict):
                return self.send_json({"success": False, "error": "קובץ JSON לא תקין"}, 400)
            ok_struct, err_struct = memory_hub.validate_db_structure(body_data)
            if not ok_struct:
                return self.send_json({"success": False, "error": f"קובץ גיבוי לא תקין: {err_struct}"}, 400)
            try:
                from datetime import datetime
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                memory_hub.backup_memory_file(suffix=f".before-web-import-{stamp}")
                memory_hub.save_db(body_data)
                memory_hub.load_db()
                memory_hub.inject_all()
                return self.send_json({"success": True, "message": "הגיבוי שוחזר וסונכרן בהצלחה"})
            except Exception as e:
                return self.send_json({"success": False, "error": f"שגיאה בשמירת הגיבוי: {e}"}, 500)

        self.send_response(404)
        self.end_headers()

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body_data = self._read_json_body()

        if path == "/api/items":
            cat = (body_data or {}).get("category")
            i_id = (body_data or {}).get("item_id")
            data = (body_data or {}).get("data", {})
            ok, msg = memory_hub.update_item(cat, i_id, data)
            return self.send_json({"success": ok, "message": msg})

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body_data = self._read_json_body()

        if path == "/api/items":
            cat = (body_data or {}).get("category")
            i_id = (body_data or {}).get("item_id")
            ok = memory_hub.remove_item(cat, i_id)
            return self.send_json({"success": ok})

        if path == "/api/paths":
            fpath = (body_data or {}).get("path")
            clean_files = (body_data or {}).get("clean_files", True)
            if not fpath:
                return self.send_json({"success": False, "error": "נתיב תיקייה חסר"}, 400)
            ok, msg = memory_hub.remove_path(fpath, clean_files=clean_files)
            return self.send_json({"success": ok, "message": msg})

        self.send_response(404)
        self.end_headers()

    def _read_json_body(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 0:
                raw = self.rfile.read(content_len).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}


_server_instance = None


def start_server(port=PORT, background=True):
    global _server_instance
    if _server_instance:
        return _server_instance

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), MemoryHubHTTPHandler)
        server.daemon_threads = True
        _server_instance = server
        if background:
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            print(f"🚀 Universal AI Memory Hub Web Dashboard running at: http://localhost:{port}")
            return server
        else:
            print(f"🚀 Universal AI Memory Hub Web Dashboard running at: http://localhost:{port}")
            server.serve_forever()
    except Exception as e:
        print(f"⚠️ Could not start Web Dashboard server on port {port}: {e}")
        return None


if __name__ == "__main__":
    start_server(PORT, background=False)
