#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal AI Memory Hub - Core Engine & Smart Path Manager (Version 1.0.1)
Features:
1. 5 Directive Categories: Facts, Commands, Negative Constraints, Tone & Persona, Contextual Directives.
2. Context Files & Local RAG: Project documents, architecture specs, and reference attachments.
3. Priority Reordering: Full control over instruction sequence and model prompt priority.
4. Serverless Cloud Sync: GitHub Gist backup & cross-machine sync.
5. AI Rules Sanity & Conflict Detection: Automated detection of contradictory directives with Gemini.
6. Per-Project Scoping (חוקים ייעודיים לפרויקט ספציפי או גלובליים לכולם).
7. Workspaces & Profiles (פרופילים: ברירת מחדל, פיתוח קוד, עסקי וכו').
8. Automatic Folder Watcher Daemon (ניטור תיקיות פרויקטים חדשות בזמן אמת).
9. Appearance Themes (Dark/Light Mode, Custom Accent Colors).
"""

import os
import sys
import json
import re
import time
import shutil
import hashlib
import functools
import threading
from datetime import datetime
from pathlib import Path
import requests

# TLS verification stays ON for every outgoing request (the GitHub token and the full
# memory database travel over these connections). Users behind a TLS-inspecting proxy
# can point AIMEMORYHUB_CA_BUNDLE at that proxy's root certificate instead of
# disabling verification.
_CA_BUNDLE = os.environ.get("AIMEMORYHUB_CA_BUNDLE", "").strip() if os.environ.get("AIMEMORYHUB_CA_BUNDLE") else ""
REQUEST_VERIFY = _CA_BUNDLE if (_CA_BUNDLE and os.path.exists(_CA_BUNDLE)) else True

# Serializes the read-modify-write cycle on memory.json across the GUI thread,
# the folder-watcher daemon and the cloud-sync workers.
DB_LOCK = threading.RLock()

# Records the last database-read failure so the GUI can surface it to the user
# instead of it disappearing into a console that a windowed build never shows.
LAST_LOAD_ERROR = {"error": None, "preserved_path": None}

# Collects per-folder write failures during the last inject_all() run, so the GUI can
# report a partial sync instead of an unconditional "completed successfully".
INJECTION_FAILURES = []

# Rule files whose injected block was edited by hand since this app last wrote it. The
# write is skipped for those so the edit survives, and they are reported to the user -
# "rules overwritten without me noticing" is the failure this exists to prevent.
INJECTION_DRIFT = []

def synchronized_db(fn):
    """
    Serializes a whole load_db() -> mutate -> save_db() cycle under DB_LOCK.
    Without this, the GUI thread, the folder-watcher daemon (every 5s) and the cloud-sync
    workers can interleave: the last save_db() wins and silently discards the other
    thread's change, because each of them saved a snapshot read before the other wrote.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with DB_LOCK:
            return fn(*args, **kwargs)
    return wrapper


# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Base Paths
WORKSPACE_DIR = Path(__file__).resolve().parent
USER_HOME = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
APPDATA_ROAMING = Path(os.environ.get("APPDATA") or (USER_HOME / "AppData" / "Roaming"))

# Check for primary project workspace database first so that dev & installed versions share the same DB.
# AIMEMORYHUB_DATA_DIR overrides both, so tests (and portable installs) can point at their own
# directory instead of operating on the real database.
DEV_DB = WORKSPACE_DIR / "data" / "memory.json"
_DATA_DIR_OVERRIDE = (os.environ.get("AIMEMORYHUB_DATA_DIR") or "").strip()

if _DATA_DIR_OVERRIDE:
    DATA_DIR = Path(_DATA_DIR_OVERRIDE)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE = DATA_DIR / "memory.json"
elif DEV_DB.exists() and not getattr(sys, "frozen", False):
    # Source checkout only. In a frozen build WORKSPACE_DIR is the PyInstaller extraction
    # folder under %TEMP%, so a database found there would be wiped when the app closes -
    # the installed app always uses %APPDATA% below.
    DATA_DIR = DEV_DB.parent
    MEMORY_FILE = DEV_DB
else:
    APPDATA_HUB = APPDATA_ROAMING / "UniversalAIMemoryHub"
    DATA_DIR = APPDATA_HUB / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE = DATA_DIR / "memory.json"

START_MARKER = "<!-- AI_MEMORY_HUB_START -->"
END_MARKER = "<!-- AI_MEMORY_HUB_END -->"

# The per-project rule files, as (filename, ai_key). Single source of truth: inject and
# clean MUST walk the same list, or removing a project leaves an orphaned frozen block
# behind (which is exactly what happened to .clinerules).
# The no-scanning directive was hardcoded into every generated file. It is a legitimate
# preference, but it belongs to the user, not to the program - so existing installs get it
# migrated once into their own constraints (editable, disableable, visible in the UI), and
# new installs simply never receive a rule nobody asked for.
SCAN_CONSTRAINT_ID = "const_no_scanning"
SCAN_CONSTRAINT_TEMPLATE = {
    "id": SCAN_CONSTRAINT_ID,
    "constraint": ("איסור סריקה וחיפוש קבצים במחשב: חל איסור מוחלט להריץ פקודות סריקה "
                   "(כגון run_command, Get-ChildItem, dir, find, grep) או לבדוק פורטים "
                   "וחיבורי רשת כאשר התשובה מופיעה כבר בזיכרון זה"),
    "alternative_or_why": ("חובה להשיב מיידית מתוך סעיף העובדות (Facts & Data) כפלט טקסט "
                           "ישיר בלבד, ללא שום קריאה לכלי (0 tool calls)"),
    "scope": "global",
    "active": True,
    "target_ais": ["all"],
    "expiresAt": None,
}

RULE_FILES = [
    ("GEMINI.md", "antigravity"),
    ("CLAUDE.md", "claude"),
    (".cursorrules", "cursor"),
    (".windsurfrules", "windsurf"),
    (".clinerules", "cline"),
]


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def is_valid_project_path(folder_path) -> bool:
    """
    Rejects folders that must never become sync targets.

    Most importantly the PyInstaller extraction directory: in a frozen build
    WORKSPACE_DIR resolves to %TEMP%\\_MEIxxxxx, so every run of the packaged .exe used
    to register a brand-new throwaway folder as a "project" and then write six rule files
    into it on every sync - forever, since the folder is deleted when the app closes.
    """
    try:
        p = Path(folder_path).resolve()
    except Exception:
        return False

    name = p.name
    if name.startswith("_MEI") or name.startswith("~"):
        return False

    # Anything inside the system temp directory (or PyInstaller's runtime dir)
    temp_roots = [os.environ.get("TEMP"), os.environ.get("TMP"), getattr(sys, "_MEIPASS", None)]
    for root in temp_roots:
        if not root:
            continue
        try:
            if p == Path(root).resolve() or Path(root).resolve() in p.parents:
                return False
        except Exception:
            continue

    return True


def auto_discover_project_paths():
    discovered = []
    candidates_roots = [
        USER_HOME / "Desktop" / "פרויקטים",
        USER_HOME / "Desktop" / "Projects",
        USER_HOME / "Projects",
        USER_HOME / "Documents" / "Projects",
        USER_HOME / "source" / "repos",
    ]

    for root in candidates_roots:
        if root.exists() and root.is_dir():
            try:
                for entry in root.iterdir():
                    if entry.is_dir() and not entry.name.startswith(".") and is_valid_project_path(entry):
                        discovered.append(str(entry.resolve()))
            except Exception as e:
                print(f"Error scanning {root}: {e}")

    # Only register the workspace itself when it is a real project folder - never the
    # PyInstaller temp extraction directory of a frozen build.
    current_ws = str(WORKSPACE_DIR.resolve())
    if is_valid_project_path(current_ws) and current_ws not in discovered:
        discovered.insert(0, current_ws)

    return list(dict.fromkeys(discovered))


def get_expired_items(profile_id=None):
    """
    Lists items whose expiry date has passed, across all profiles (or one).
    Used by the startup sweep - injection is event-driven, so without a clock trigger an
    expired rule would keep living in every project's rule file until the next edit.
    """
    db = load_db()
    out = []
    for pid, pinfo in db.get("profiles", {}).items():
        if profile_id and pid != profile_id:
            continue
        for cat, items in (pinfo.get("data") or {}).items():
            if not isinstance(items, list):
                continue
            for it in items:
                if item_is_expired(it):
                    out.append({"profile": pid, "profile_name": pinfo.get("name", pid),
                                "category": cat, "item": it})
    return out


def sweep_expired_items():
    """
    Re-injects when rules have expired since the last sync, so they leave the rule files
    without waiting for the user to edit something. Returns the expired entries found.
    """
    expired = get_expired_items()
    if expired:
        inject_all()
    return expired


@synchronized_db
def prune_invalid_paths():
    """
    Removes sync targets that are gone or should never have been added (PyInstaller temp
    folders). Returns the list of removed entry names. Runs automatically at startup.
    """
    db = load_db()
    paths = db.get("targetPaths", [])

    kept, removed = [], []
    for item in paths:
        path = item.get("path", "")
        if not path or not is_valid_project_path(path) or not os.path.isdir(path):
            removed.append(item.get("name") or path)
        else:
            kept.append(item)

    if removed:
        db["targetPaths"] = kept
        add_log(db, "prune_paths", f"הוסרו {len(removed)} נתיבים לא תקינים: {', '.join(removed[:5])}")
        save_db(db)

    return removed


def get_default_profile_data():
    return {
        "facts": [
            {
                "id": "info_default_site",
                "name": "האתר שלי",
                "value": "example.com",
                "scope": "global",
                "active": True,
                "createdAt": datetime.now().isoformat()
            }
        ],
        "commands": [
            {
                "id": "cmd_default_sig",
                "name": "חתימה אישית",
                "details": "לצרף בסוף התשובה: 'בברכה, [שמך]'",
                "trigger_case": "בסיום מענה למיילים, תבניות רשמיות או פונקציות מרכזיות",
                "scope": "global",
                "active": True,
                "createdAt": datetime.now().isoformat()
            }
        ],
        "constraints": [
            {
                "id": "const_default_comments",
                "constraint": "לעולם אל תמחק או תחליף הערות קוד או תיעוד קיים בקוד",
                "alternative_or_why": "שמור על כל התיעוד הקיים במלואו והוסף עליו במידת הצורך",
                "scope": "global",
                "active": True,
                "createdAt": datetime.now().isoformat()
            }
        ],
        "styles": [
            {
                "id": "style_default_lang",
                "aspect": "שפה וניסוח",
                "instruction": "ענה תמיד בעברית רהוטה, טבעית ומקצועית (הימנע לחלוטין מתרגום מכונה צורם)",
                "scope": "global",
                "active": True,
                "createdAt": datetime.now().isoformat()
            }
        ],
        "instructions": [
            {
                "id": "inst_default_lang",
                "instruction": "ענה תמיד בעברית רהוטה וברורה ומסודרת",
                "when_to_apply": "בכל שיחה ומענה",
                "scope": "global",
                "active": True,
                "createdAt": datetime.now().isoformat()
            }
        ],
        "context_files": []
    }


def get_default_database():
    discovered_paths = auto_discover_project_paths()
    path_entries = [
        {
            "path": p,
            "name": Path(p).name,
            "active": True,
            "lastSynced": None
        }
        for p in discovered_paths
    ]

    return {
        "version": "1.0.1",
        "lastUpdated": datetime.now().isoformat(),
        "currentProfile": "default",
        "profiles": {
            "default": {
                "name": "ראשי (כללי)",
                "data": get_default_profile_data()
            },
            "code": {
                "name": "פיתוח קוד",
                "data": {
                    "facts": [],
                    "commands": [
                        {
                            "id": "cmd_code_types",
                            "name": "הקלדה קפדנית",
                            "details": "הקפד על Type Hinting מלא בפייתון או טיפוסי TypeScript ללא שימוש ב-any",
                            "trigger_case": "בכל כתיבת פונקציה או מודול",
                            "scope": "global",
                            "active": True,
                            "createdAt": datetime.now().isoformat()
                        }
                    ],
                    "constraints": [
                        {
                            "id": "const_code_clean",
                            "constraint": "אל תשאיר קוד debug או print/console.log מיותרים",
                            "alternative_or_why": "השתמש ב-logging מסודר בלבד",
                            "scope": "global",
                            "active": True,
                            "createdAt": datetime.now().isoformat()
                        }
                    ],
                    "styles": [
                        {
                            "id": "style_code_brevity",
                            "aspect": "סגנון מענה",
                            "instruction": "היה תמציתי וממוקד בקוד, ללא הסברים ארכניים",
                            "scope": "global",
                            "active": True,
                            "createdAt": datetime.now().isoformat()
                        }
                    ],
                    "instructions": [],
                    "context_files": []
                }
            },
            "business": {
                "name": "עסקי (דוגמה)",
                "data": {
                    "facts": [
                        {
                            "id": "fact_biz_name",
                            "name": "שם העסק",
                            "value": "העסק שלי - פתרונות תוכנה ומחשוב",
                            "scope": "global",
                            "active": True,
                            "createdAt": datetime.now().isoformat()
                        }
                    ],
                    "commands": [],
                    "constraints": [],
                    "styles": [
                        {
                            "id": "style_biz_tone",
                            "aspect": "טון דיבור",
                            "instruction": "טון מכובד, מקצועי ושירותי ברמה הגבוהה ביותר",
                            "scope": "global",
                            "active": True,
                            "createdAt": datetime.now().isoformat()
                        }
                    ],
                    "instructions": [],
                    "context_files": []
                }
            }
        },
        "settings": {
            "geminiApiKey": os.environ.get("GEMINI_API_KEY", ""),
            "githubGistToken": "",
            "githubGistId": "",
            "autoCloudSync": False,
            "appearanceMode": "dark",
            "colorTheme": "blue",
            "syncScopeMode": "macro",
            "cleanProjectsOnMacro": False,
            "injectClaudeMcp": True,
            "injectAntigravityKnowledge": True,
            "injectProjectRules": True,
            "autoSyncOnChange": True,
            "folderWatcherActive": True,
            "minimizeToTray": False,
            "checkUpdatesOnStartup": True,
            "autoInstallUpdates": False,
            "injectGlobalTargets": True,
            "disabledGlobalTargets": [],
            "allowMcpModeSwitch": False,
            "defaultGeminiModel": "פלאש לאסט"
        },
        "targetPaths": path_entries,
        "logs": [
            {
                "timestamp": datetime.now().isoformat(),
                "action": "init",
                "message": "אותחל מאגר הזיכרון החכם v1.0.1"
            }
        ]
    }


def load_db():
    with DB_LOCK:
        return _load_db_unlocked()


def _load_db_unlocked():
    ensure_data_dir()
    if not MEMORY_FILE.exists():
        db = get_default_database()
        save_db(db)
        return db
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        migrated = False

        # Upgrade to v5.0 (Profile-based structure)
        if "profiles" not in data:
            default_data = {
                "facts": data.get("facts", []),
                "commands": data.get("commands", []),
                "constraints": data.get("constraints", []),
                "styles": data.get("styles", []),
                "instructions": data.get("instructions", [])
            }
            # Ensure scope field exists on all items
            for cat in ["facts", "commands", "constraints", "styles", "instructions"]:
                for item in default_data.get(cat, []):
                    if "scope" not in item:
                        item["scope"] = "global"

            data["version"] = "5.0"
            data["currentProfile"] = "default"
            data["profiles"] = {
                "default": {
                    "name": "ראשי (כללי)",
                    "data": default_data
                }
            }
            migrated = True

        # Ensure scopes and context_files exist in all profile items
        for p_id, p_info in data.get("profiles", {}).items():
            p_data = p_info.get("data", {})
            for cat in ["facts", "commands", "constraints", "styles", "instructions", "context_files"]:
                p_data.setdefault(cat, [])
                for item in p_data[cat]:
                    if "scope" not in item:
                        item["scope"] = "global"
                        migrated = True
                    if "active" not in item:
                        item["active"] = True
                        migrated = True

        if data.get("version") != "1.0.1":
            data["version"] = "1.0.1"
            migrated = True

        if "settings" not in data:
            data["settings"] = {}
            migrated = True

        data["settings"].setdefault("folderWatcherActive", True)
        data["settings"].setdefault("minimizeToTray", False)
        data["settings"].setdefault("githubGistToken", "")
        data["settings"].setdefault("githubGistId", "")
        data["settings"].setdefault("autoCloudSync", False)
        data["settings"].setdefault("appearanceMode", "dark")
        data["settings"].setdefault("colorTheme", "blue")
        data["settings"].setdefault("syncScopeMode", "macro")
        data["settings"].setdefault("cleanProjectsOnMacro", False)
        data["settings"].setdefault("checkUpdatesOnStartup", True)
        data["settings"].setdefault("injectGlobalTargets", True)
        data["settings"].setdefault("disabledGlobalTargets", [])
        data["settings"].setdefault("allowMcpModeSwitch", False)
        data["settings"].setdefault("autoInstallUpdates", False)
        data["settings"].setdefault("defaultGeminiModel", "פלאש לאסט")

        # One-time: the no-scanning directive used to be emitted from code on every sync.
        # Hand it to the user as a real constraint so it stays in force but becomes theirs
        # to edit or switch off. Only for existing databases - a fresh install starts clean.
        if not data["settings"].get("migratedScanConstraint"):
            existing_profiles = data.get("profiles", {})
            has_content = any(
                any(len(p.get("data", {}).get(c, [])) for c in
                    ["facts", "commands", "constraints", "styles", "instructions"])
                for p in existing_profiles.values()
            )
            if has_content:
                default_profile = existing_profiles.get("default") or next(iter(existing_profiles.values()), None)
                if default_profile is not None:
                    constraints = default_profile.setdefault("data", {}).setdefault("constraints", [])
                    if not any(c.get("id") == SCAN_CONSTRAINT_ID for c in constraints):
                        item = dict(SCAN_CONSTRAINT_TEMPLATE)
                        item["createdAt"] = datetime.now().isoformat()
                        constraints.append(item)
                        migrated = True
            data["settings"]["migratedScanConstraint"] = True
            migrated = True

        if migrated:
            save_db(data)

        return data
    except Exception as e:
        # The database is unreadable (corrupt JSON, encoding issue, locked by a sync client).
        # Preserve the original file under a timestamped name BEFORE any later save_db()
        # overwrites it with the fresh defaults - otherwise the user's real content is lost
        # silently, with only a console message that a windowed build never shows.
        preserved = None
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            preserved = MEMORY_FILE.with_name(f"{MEMORY_FILE.name}.corrupt-{stamp}")
            shutil.copy2(MEMORY_FILE, preserved)
        except Exception as backup_err:
            print(f"Failed to preserve corrupt memory.json: {backup_err}")
            preserved = None

        LAST_LOAD_ERROR["error"] = str(e)
        LAST_LOAD_ERROR["preserved_path"] = str(preserved) if preserved else None
        print(f"Error reading memory.json: {e}, falling back to defaults "
              f"(a copy of the unreadable file was kept at: {preserved})")
        return get_default_database()



def backup_memory_file(suffix=".bak"):
    """
    Keeps a copy of the current memory.json before it is overwritten, so a corrupted
    write or an unwanted import can always be recovered manually.
    """
    if not MEMORY_FILE.exists():
        return None
    backup_path = MEMORY_FILE.with_name(MEMORY_FILE.name + suffix)
    try:
        shutil.copy2(MEMORY_FILE, backup_path)
        return backup_path
    except Exception as e:
        print(f"Failed to create backup of memory.json: {e}")
        return None


def save_db(db):
    """
    Writes the database atomically: the JSON is fully written to a temp file in the same
    directory and only then swapped in with os.replace(), so a crash or power loss mid-write
    can never leave a truncated/corrupt memory.json behind.
    """
    with DB_LOCK:
        ensure_data_dir()
        db["lastUpdated"] = datetime.now().isoformat()

        backup_memory_file()

        tmp_path = MEMORY_FILE.with_name(MEMORY_FILE.name + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, MEMORY_FILE)


def add_log(db, action, message):
    if "logs" not in db:
        db["logs"] = []
    db["logs"].insert(0, {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "message": message
    })
    db["logs"] = db["logs"][:60]


# =========================================================================
# PROFILE MANAGEMENT (פרופילים וסביבות עבודה)
# =========================================================================
def get_profiles():
    db = load_db()
    return db.get("profiles", {})

def get_current_profile_id():
    db = load_db()
    return db.get("currentProfile", "default")

@synchronized_db
def set_current_profile(profile_id):
    db = load_db()
    if profile_id in db.get("profiles", {}):
        db["currentProfile"] = profile_id
        add_log(db, "switch_profile", f"הוחלף פרופיל פעיל ל: {db['profiles'][profile_id].get('name')}")
        save_db(db)
        if db.get("settings", {}).get("autoSyncOnChange", True):
            inject_all()
        return True
    return False

# Alias for backward compatibility with GUI & external integrations
switch_profile = set_current_profile

@synchronized_db
def add_profile(profile_id, name, trigger_keywords=None, description="", inject_as_mode=True):
    db = load_db()
    if profile_id in db.get("profiles", {}):
        return False, "מזהה פרופיל כבר קיים"
    db.setdefault("profiles", {})[profile_id] = {
        "name": name.strip(),
        "trigger_keywords": trigger_keywords if isinstance(trigger_keywords, list) else [],
        "description": description.strip() if description else "",
        "inject_as_mode": bool(inject_as_mode),
        "data": {
            "facts": [],
            "commands": [],
            "constraints": [],
            "styles": [],
            "instructions": [],
            "context_files": []
        }
    }
    add_log(db, "add_profile", f"נוצר פרופיל חדש: {name}")
    save_db(db)
    return True, db["profiles"][profile_id]

def get_profile_triggers(profile_id):
    db = load_db()
    p = db.get("profiles", {}).get(profile_id, {})
    return p.get("trigger_keywords", []), p.get("description", ""), p.get("inject_as_mode", True)


# =========================================================================
# AUTOMATIC PROFILE SWITCHING (מעבר פרופיל אוטומטי)
#
# Three independent strategies, each switchable on its own:
#   1. schedule  - the app switches by time of day / weekday (e.g. business hours)
#   2. folder    - the app switches to the profile that owns the project folder in use
#   3. keywords  - the AI switches itself when the user's wording matches a profile's
#                  trigger words ("מה המייל העסקי שלי" -> business). This one cannot be
#                  done here: the app never sees the conversation, so the keywords are
#                  written into the generated rules block for the model to act on.
# =========================================================================
AUTO_SWITCH_DEFAULTS = {
    "enabled": False,
    "useSchedule": True,
    "useFolder": True,
    "useKeywords": True,
}


def get_auto_switch_settings():
    settings = load_db().get("settings", {})
    conf = dict(AUTO_SWITCH_DEFAULTS)
    conf.update(settings.get("autoProfileSwitch", {}) or {})
    return conf


@synchronized_db
def set_auto_switch_settings(**changes):
    db = load_db()
    conf = dict(AUTO_SWITCH_DEFAULTS)
    conf.update(db.get("settings", {}).get("autoProfileSwitch", {}) or {})
    conf.update({k: v for k, v in changes.items() if k in AUTO_SWITCH_DEFAULTS})
    db.setdefault("settings", {})["autoProfileSwitch"] = conf
    save_db(db)
    return conf


def get_profile_schedule(profile_id):
    """
    {"enabled": bool, "start": "HH:MM", "end": "HH:MM", "days": [0..6]} - 0 is Monday,
    matching datetime.weekday(). An empty days list means every day.
    """
    p = load_db().get("profiles", {}).get(profile_id, {})
    sched = dict(p.get("schedule") or {})
    sched.setdefault("enabled", False)
    sched.setdefault("start", "09:00")
    sched.setdefault("end", "18:00")
    sched.setdefault("days", [6, 0, 1, 2, 3])  # Sun-Thu, the Israeli work week
    return sched


@synchronized_db
def set_profile_schedule(profile_id, enabled=None, start=None, end=None, days=None):
    db = load_db()
    profiles = db.get("profiles", {})
    if profile_id not in profiles:
        return False, "פרופיל לא נמצא"

    sched = dict(profiles[profile_id].get("schedule") or {})
    sched.setdefault("enabled", False)
    sched.setdefault("start", "09:00")
    sched.setdefault("end", "18:00")
    sched.setdefault("days", [6, 0, 1, 2, 3])

    if enabled is not None: sched["enabled"] = bool(enabled)
    if start is not None: sched["start"] = str(start)
    if end is not None: sched["end"] = str(end)
    if days is not None: sched["days"] = list(days)

    profiles[profile_id]["schedule"] = sched
    add_log(db, "update_profile_schedule",
            f"עודכן לוח זמנים לפרופיל: {profiles[profile_id].get('name', profile_id)}")
    save_db(db)
    return True, sched


def _minutes(hhmm, fallback):
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return fallback


def profile_matches_now(profile_id, now=None):
    """True when this profile's schedule covers the given moment (windows may cross midnight)."""
    sched = get_profile_schedule(profile_id)
    if not sched.get("enabled"):
        return False

    now = now or datetime.now()
    days = sched.get("days") or []
    if days and now.weekday() not in days:
        return False

    start = _minutes(sched.get("start"), 9 * 60)
    end = _minutes(sched.get("end"), 18 * 60)
    current = now.hour * 60 + now.minute

    if start <= end:
        return start <= current < end
    return current >= start or current < end  # window wraps past midnight


def resolve_scheduled_profile(now=None):
    """The profile whose schedule matches right now, or None. First match wins."""
    db = load_db()
    for pid in db.get("profiles", {}):
        if profile_matches_now(pid, now):
            return pid
    return None


def resolve_profile_for_folder(folder_path):
    """The profile that claims this project folder through its folder_patterns."""
    if not folder_path:
        return None
    name = Path(folder_path).name.lower()
    full = str(folder_path).lower()
    for pid, pinfo in load_db().get("profiles", {}).items():
        for pattern in (pinfo.get("folder_patterns") or []):
            p = str(pattern).strip().lower()
            if p and (p in name or p in full):
                return pid
    return None


def apply_auto_profile(now=None, folder_path=None):
    """
    Switches the active profile according to the enabled strategies.
    Returns (changed, profile_id, reason). Never switches when auto-switching is off.
    """
    conf = get_auto_switch_settings()
    if not conf.get("enabled"):
        return False, get_current_profile_id(), "כבוי"

    target, reason = None, ""

    if conf.get("useFolder") and folder_path:
        target = resolve_profile_for_folder(folder_path)
        if target:
            reason = f"לפי תיקיית הפרויקט: {Path(folder_path).name}"

    if not target and conf.get("useSchedule"):
        target = resolve_scheduled_profile(now)
        if target:
            reason = "לפי לוח הזמנים"

    current = get_current_profile_id()
    if not target or target == current:
        return False, current, reason or "אין שינוי"

    set_current_profile(target)
    return True, target, reason


@synchronized_db
def set_profile_folder_patterns(profile_id, patterns):
    db = load_db()
    if profile_id not in db.get("profiles", {}):
        return False, "פרופיל לא נמצא"
    if isinstance(patterns, str):
        patterns = [p.strip() for p in patterns.split(",") if p.strip()]
    db["profiles"][profile_id]["folder_patterns"] = list(patterns or [])
    save_db(db)
    return True, db["profiles"][profile_id]["folder_patterns"]


@synchronized_db
def set_profile_triggers(profile_id, keywords, description=None, inject_as_mode=None):
    db = load_db()
    if profile_id in db.get("profiles", {}):
        p = db["profiles"][profile_id]
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        p["trigger_keywords"] = keywords if isinstance(keywords, list) else []
        if description is not None:
            p["description"] = description.strip()
        if inject_as_mode is not None:
            p["inject_as_mode"] = bool(inject_as_mode)
        add_log(db, "update_profile_triggers", f"עודכנו מילות הפעלה לפרופיל: {p.get('name')}")
        save_db(db)
        if db.get("settings", {}).get("autoSyncOnChange", True):
            inject_all()
        return True, "הטריגרים עודכנו בהצלחה"
    return False, "פרופיל לא נמצא"


@synchronized_db
def delete_profile(profile_id):
    db = load_db()
    if profile_id == "default":
        return False, "לא ניתן למחוק את פרופיל ברירת המחדל"
    if profile_id in db.get("profiles", {}):
        del db["profiles"][profile_id]
        if db.get("currentProfile") == profile_id:
            db["currentProfile"] = "default"
        add_log(db, "delete_profile", f"נמחק פרופיל: {profile_id}")
        save_db(db)
        if db.get("settings", {}).get("autoSyncOnChange", True):
            inject_all()
        return True, "הפרופיל נמחק בהצלחה"
    return False, "פרופיל לא נמצא"

def get_current_profile_data():
    db = load_db()
    cur_id = db.get("currentProfile", "default")
    profiles = db.get("profiles", {})
    if cur_id not in profiles:
        cur_id = "default"
    return profiles.get(cur_id, {}).get("data", {})


# =========================================================================
# GENERIC ITEM CRUD & EDIT
# =========================================================================
def get_items(category):
    return get_current_profile_data().get(category, [])

@synchronized_db
def add_item(category, item_dict):
    db = load_db()
    cur_id = db.get("currentProfile", "default")
    p_data = db["profiles"][cur_id]["data"]

    item_id = f"{category[:4]}_{int(datetime.now().timestamp()*1000)}"
    item_dict["id"] = item_id
    item_dict.setdefault("scope", "global")
    item_dict.setdefault("active", True)
    item_dict.setdefault("expiresAt", None)  # None = never expires
    item_dict["createdAt"] = datetime.now().isoformat()

    p_data.setdefault(category, []).insert(0, item_dict)
    add_log(db, f"add_{category}", f"נוסף פריט ל-{category}: {item_dict.get('name') or item_dict.get('constraint') or item_dict.get('aspect') or item_dict.get('instruction')}")
    save_db(db)

    if db.get("settings", {}).get("autoSyncOnChange", True):
        inject_all()
    return item_dict

@synchronized_db
def update_item(category, item_id, updated_fields):
    db = load_db()
    cur_id = db.get("currentProfile", "default")
    p_data = db["profiles"][cur_id]["data"]
    items = p_data.get(category, [])

    for it in items:
        if it.get("id") == item_id:
            it.update(updated_fields)
            it["updatedAt"] = datetime.now().isoformat()
            add_log(db, f"update_{category}", f"עודכן פריט ב-{category}: {it.get('name') or it.get('constraint') or it.get('aspect') or it.get('instruction')}")
            save_db(db)
            if db.get("settings", {}).get("autoSyncOnChange", True):
                inject_all()
            return True, it
    return False, "פריט לא נמצא"

@synchronized_db
def remove_item(category, item_id):
    db = load_db()
    cur_id = db.get("currentProfile", "default")
    p_data = db["profiles"][cur_id]["data"]
    orig_len = len(p_data.get(category, []))
    p_data[category] = [x for x in p_data.get(category, []) if x.get("id") != item_id]

    if len(p_data[category]) < orig_len:
        add_log(db, f"remove_{category}", f"נמחק פריט מ-{category}")
        save_db(db)
        if db.get("settings", {}).get("autoSyncOnChange", True):
            inject_all()
        return True
    return False

@synchronized_db
def toggle_item(category, item_id, active=None):
    db = load_db()
    cur_id = db.get("currentProfile", "default")
    p_data = db["profiles"][cur_id]["data"]

    for it in p_data.get(category, []):
        if it.get("id") == item_id:
            it["active"] = not it["active"] if active is None else bool(active)
            save_db(db)
            if db.get("settings", {}).get("autoSyncOnChange", True):
                inject_all()
            return it["active"]
    return None


# Conveniences for 5 categories
def get_facts(): return get_items("facts")
def add_info(name, value, scope="global", active=True, target_ais=None, expires_at=None):
    if target_ais is None: target_ais = ["all"]
    return add_item("facts", {"name": name.strip(), "value": value.strip(), "scope": scope, "active": bool(active), "target_ais": target_ais, "expiresAt": expires_at})
def add_fact(name, value, scope="global", active=True, target_ais=None, expires_at=None):
    return add_info(name, value, scope=scope, active=active, target_ais=target_ais, expires_at=expires_at)
def remove_info(item_id): return remove_item("facts", item_id)
def toggle_info(item_id, active=None): return toggle_item("facts", item_id, active)

def get_commands(): return get_items("commands")
def add_command(name, details, trigger_case="", scope="global", active=True, target_ais=None, expires_at=None):
    if target_ais is None: target_ais = ["all"]
    return add_item("commands", {"name": name.strip(), "details": details.strip(), "trigger_case": trigger_case.strip() if trigger_case else "בכל מקרה רלוונטי", "scope": scope, "active": bool(active), "target_ais": target_ais, "expiresAt": expires_at})
def remove_command(item_id): return remove_item("commands", item_id)
def toggle_command(item_id, active=None): return toggle_item("commands", item_id, active)

def get_constraints(): return get_items("constraints")
def add_constraint(constraint, alternative_or_why="", scope="global", active=True, target_ais=None, expires_at=None):
    if target_ais is None: target_ais = ["all"]
    return add_item("constraints", {"constraint": constraint.strip(), "alternative_or_why": alternative_or_why.strip() if alternative_or_why else "הימנע מכך לחלוטין", "scope": scope, "active": bool(active), "target_ais": target_ais, "expiresAt": expires_at})
def remove_constraint(item_id): return remove_item("constraints", item_id)
def toggle_constraint(item_id, active=None): return toggle_item("constraints", item_id, active)

def get_styles(): return get_items("styles")
def add_style(aspect, instruction, scope="global", active=True, target_ais=None, expires_at=None):
    if target_ais is None: target_ais = ["all"]
    return add_item("styles", {"aspect": aspect.strip(), "instruction": instruction.strip(), "scope": scope, "active": bool(active), "target_ais": target_ais, "expiresAt": expires_at})
def remove_style(item_id): return remove_item("styles", item_id)
def toggle_style(item_id, active=None): return toggle_item("styles", item_id, active)

def get_instructions(): return get_items("instructions")
def add_instruction(instruction, when_to_apply="", scope="global", active=True, target_ais=None, expires_at=None):
    if target_ais is None: target_ais = ["all"]
    return add_item("instructions", {"instruction": instruction.strip(), "when_to_apply": when_to_apply.strip() if when_to_apply else "תמיד בכל מצב", "scope": scope, "active": bool(active), "target_ais": target_ais, "expiresAt": expires_at})
def remove_instruction(item_id): return remove_item("instructions", item_id)
def toggle_instruction(item_id, active=None): return toggle_item("instructions", item_id, active)

# 6. Context Files (קבצי הקשר ומסמכים)
def get_context_files(): return get_items("context_files")
def add_context_file(name, file_path, summary="", scope="global", active=True, target_ais=None):
    if target_ais is None: target_ais = ["all"]
    path_obj = Path(file_path)
    size_bytes = 0
    if path_obj.exists():
        try: size_bytes = path_obj.stat().st_size
        except Exception: pass
    item_dict = {
        "name": name.strip() if name else path_obj.name,
        "path": str(path_obj.resolve()) if path_obj.exists() else str(file_path),
        "summary": summary.strip(),
        "scope": scope,
        "active": bool(active),
        "sizeBytes": size_bytes,
        "target_ais": target_ais
    }
    return add_item("context_files", item_dict)
def remove_context_file(item_id): return remove_item("context_files", item_id)
def toggle_context_file(item_id, active=None): return toggle_item("context_files", item_id, active)


@synchronized_db
def reorder_item(category, item_id, direction):
    """
    Moves an item up or down in its category list.
    direction: 'up' (towards index 0) or 'down' (towards higher index).
    """
    db = load_db()
    cur_id = db.get("currentProfile", "default")
    p_data = db["profiles"][cur_id]["data"]
    items = p_data.get(category, [])

    idx = -1
    for i, it in enumerate(items):
        if it.get("id") == item_id:
            idx = i
            break

    if idx == -1:
        return False, "פריט לא נמצא"

    if direction == "up":
        if idx == 0:
            return False, "הפריט כבר נמצא בראש הרשימה"
        items[idx], items[idx - 1] = items[idx - 1], items[idx]
    elif direction == "down":
        if idx >= len(items) - 1:
            return False, "הפריט כבר נמצא בתחתית הרשימה"
        items[idx], items[idx + 1] = items[idx + 1], items[idx]
    else:
        return False, "כיוון לא תקין"

    add_log(db, f"reorder_{category}", f"שונה סדר עדיפויות ב-{category}")
    save_db(db)
    if db.get("settings", {}).get("autoSyncOnChange", True):
        inject_all()
    return True, "סדר עודכן בהצלחה"


# =========================================================================
# CONVERSATIONAL MEMORY ENGINE & CONFLICT DETECTION (הזנה שיחתית וסתירות)
# =========================================================================
def parse_conversational_input(text):
    """
    Intelligently classifies free-text natural input into structured memory categories
    and identifies target modes/profiles without requiring manual forms.
    """
    if not text or not text.strip():
        return None, "טקסט ריק"

    raw = text.strip()
    cleaned = raw

    # 1. Detect target profile/mode
    target_profile = None
    biz_triggers = ["זה לעסקים", "מצב עסקי", "עסקי", "עבור לקוח", "פנייה עסקית", "לעסקים", "business"]
    code_triggers = ["מצב קוד", "פיתוח", "דיבאג", "תכנות", "code mode", "לקוד"]

    for trig in biz_triggers:
        if trig in cleaned.lower():
            target_profile = "business"
            cleaned = re.sub(re.escape(trig), "", cleaned, flags=re.IGNORECASE).strip()
            break
    if not target_profile:
        for trig in code_triggers:
            if trig in cleaned.lower():
                target_profile = "code"
                cleaned = re.sub(re.escape(trig), "", cleaned, flags=re.IGNORECASE).strip()
                break

    # Strip conversational prefixes
    cleaned = re.sub(r"^(תזכור\s*(ש|כי)?|תוסיף\s*(ש|כי|את)?|תגדיר\s*(ש|כי|את)?|שים\s*לב\s*(ש|כי)?|remember\s*(that)?|note\s*(that)?)\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.lstrip(":,-\t ").strip()

    # 2. Classify Category
    # A. Negative Constraints ("אל", "אל ת", "לעולם אל", "אסור", "חל איסור", "don't", "never", "avoid")
    constraint_patterns = [
        r"^(אל\s+ת?[א-ת]+|לעולם\s+אל\s+[א-ת]+|חל\s+איסור\s+[א-ת]+|אסור\s+[א-ת]+|don\'?t\s+\w+|never\s+\w+|avoid\s+\w+)",
        r"(לא\s+למחוק|לא\s+לשנות|אל\s+תיגע)"
    ]
    is_constraint = any(re.search(pat, cleaned, re.IGNORECASE) for pat in constraint_patterns)

    # B. Commands / Signatures ("תחתום", "חתימה", "לצרף בסוף", "פקודה")
    cmd_patterns = [
        r"(תחתום|חתימה|לצרף\s+בסוף|לצרף\s+חתימה|sign\s+off|signature)"
    ]
    is_command = any(re.search(pat, cleaned, re.IGNORECASE) for pat in cmd_patterns)

    # C. Styles / Tone / Language ("טון", "סגנון", "שפה", "תענה ב", "תענה תמיד ב", "עברית רהוטה", "קוד נקי ותמציתי")
    style_patterns = [
        r"(סגנון|טון|שפה|ניסוח|תענה\s+(תמיד\s+)?ב|style|tone|language)"
    ]
    is_style = any(re.search(pat, cleaned, re.IGNORECASE) for pat in style_patterns)

    # D. Instructions / Conditional ("כאשר", "אם", "במקרה ש", "בכל פעם ש", "when", "whenever", "if")
    instruction_patterns = [
        r"(כאשר|בכל\s+פעם\s+ש|במקרה\s+ש|אם\s+[א-ת]+|when\s+|whenever\s+)"
    ]
    is_instruction = any(re.search(pat, cleaned, re.IGNORECASE) for pat in instruction_patterns)

    # Resolve Classification & Extract Fields
    category = "facts"
    item = {}

    if is_constraint:
        category = "constraints"
        constraint_text = cleaned
        alt_why = "שמור על ההנחיה והימנע מכך לחלוטין"
        if " כי " in cleaned:
            parts = cleaned.split(" כי ", 1)
            constraint_text = parts[0].strip()
            alt_why = parts[1].strip()
        elif " אלא " in cleaned:
            parts = cleaned.split(" אלא ", 1)
            constraint_text = parts[0].strip()
            alt_why = f"במקום זאת: {parts[1].strip()}"
        item = {
            "constraint": constraint_text,
            "alternative_or_why": alt_why,
            "scope": "global",
            "active": True
        }

    elif is_command:
        category = "commands"
        name = "חתימה" if "חתימ" in cleaned else "פקודת ביצוע"
        details = cleaned
        trigger_case = "בכל מקרה רלוונטי"
        if "במיילים" in cleaned or "במייל" in cleaned:
            trigger_case = "במענה למיילים"
        elif "בסיום" in cleaned:
            trigger_case = "בסיום תשובה"
        item = {
            "name": name,
            "details": details,
            "trigger_case": trigger_case,
            "scope": "global",
            "active": True
        }

    elif is_style:
        category = "styles"
        aspect = "סגנון מענה וטון"
        if "עברית" in cleaned or "שפה" in cleaned or "אנגלית" in cleaned:
            aspect = "שפה וניסוח"
        elif "קוד" in cleaned:
            aspect = "סגנון קוד"
        item = {
            "aspect": aspect,
            "instruction": cleaned,
            "scope": "global",
            "active": True
        }

    elif is_instruction:
        category = "instructions"
        instruction_text = cleaned
        when_to_apply = "במקרים המתאימים"
        m_when = re.search(r"(כאשר|בכל\s+פעם\s+ש|במקרה\s+ש)\s+([^,]+)", cleaned)
        if m_when:
            when_to_apply = m_when.group(0).strip()
        item = {
            "instruction": instruction_text,
            "when_to_apply": when_to_apply,
            "scope": "global",
            "active": True
        }

    else:
        # Default: Fact / Information
        category = "facts"
        name = "עובדה כללית"
        val = cleaned

        # Key-Value separators (":", "זה", "הוא", "=")
        if ":" in cleaned:
            parts = cleaned.split(":", 1)
            name = parts[0].strip()
            val = parts[1].strip()
        elif " זה " in cleaned or " זו " in cleaned or " הוא " in cleaned or " היא " in cleaned:
            split_word = " זה " if " זה " in cleaned else (" זו " if " זו " in cleaned else (" הוא " if " הוא " in cleaned else " היא "))
            parts = cleaned.split(split_word, 1)
            name = parts[0].strip()
            val = parts[1].strip()
        elif "=" in cleaned:
            parts = cleaned.split("=", 1)
            name = parts[0].strip()
            val = parts[1].strip()
        else:
            if "אתר" in cleaned.lower() or "http" in cleaned.lower() or ".com" in cleaned.lower():
                name = "האתר שלי"
            elif "שם" in cleaned:
                name = "שם"
            elif "טלפון" in cleaned:
                name = "טלפון"
            elif "מייל" in cleaned or "@" in cleaned:
                name = "אימייל"

        item = {
            "name": name,
            "value": val,
            "scope": "global",
            "active": True
        }

    return {
        "raw_text": raw,
        "category": category,
        "target_profile": target_profile,
        "item": item
    }, None


CATEGORY_LABEL_FIELD = {
    "facts": "name", "commands": "name", "constraints": "constraint",
    "styles": "aspect", "instructions": "instruction",
}
CATEGORY_VALUE_FIELD = {
    "facts": "value", "commands": "details", "constraints": "alternative_or_why",
    "styles": "instruction", "instructions": "when_to_apply",
}


def item_label(item):
    return (item.get("name") or item.get("constraint") or item.get("aspect")
            or item.get("instruction") or "")


def item_summary(item, category):
    label = item.get(CATEGORY_LABEL_FIELD.get(category, "name"), "") or item_label(item)
    value = item.get(CATEGORY_VALUE_FIELD.get(category, "value"), "")
    return f"{label}: {value}".strip(": ").strip()


def _normalize_he(text):
    """Cheap Hebrew-aware normalisation for comparing two rules without calling an LLM."""
    s = str(text or "").lower().strip()
    s = re.sub(r"[֑-ׇ]", "", s)                 # strip niqqud/cantillation
    s = s.translate(str.maketrans("ךםןףץ", "כמנפצ"))       # fold final letters
    s = re.sub(r"[^\w֐-׿\s]", " ", s)            # drop punctuation
    return re.sub(r"\s+", " ", s).strip()


def items_contradict(a, b, category):
    """
    Local, zero-cost check for "these two rules fight each other". Deliberately narrow:
    it gates the expensive Gemini pass, so a false positive costs an API call while a
    false negative just means the check stays as good as it was before.
    """
    label_field = CATEGORY_LABEL_FIELD.get(category, "name")
    value_field = CATEGORY_VALUE_FIELD.get(category, "value")

    a_label, b_label = _normalize_he(a.get(label_field)), _normalize_he(b.get(label_field))
    a_value, b_value = _normalize_he(a.get(value_field)), _normalize_he(b.get(value_field))

    if not a_label or not b_label:
        return False

    # Same subject...
    same_subject = a_label == b_label or (len(a_label) > 3 and (a_label in b_label or b_label in a_label))
    if not same_subject:
        return False

    # ...but a different answer.
    return bool(a_value) and bool(b_value) and a_value != b_value


def detect_conflicts(proposed_item=None, category=None, profile_id=None):
    """
    Detects logical contradictions or competing facts in memory.
    Returns a list of conflict dicts with clear actionable resolutions.
    """
    db = load_db()
    cur_id = profile_id or db.get("currentProfile", "default")
    p_data = db.get("profiles", {}).get(cur_id, {}).get("data", {})

    conflicts = []

    # 1. If proposed_item is provided, check if it conflicts with existing items
    if proposed_item and category:
        if category == "facts":
            p_name = proposed_item.get("name", "").strip().lower()
            p_val = proposed_item.get("value", "").strip()
            for ex in p_data.get("facts", []):
                ex_name = ex.get("name", "").strip().lower()
                ex_val = ex.get("value", "").strip()
                if ex.get("active", True) and (ex_name == p_name or (len(p_name) > 3 and p_name in ex_name)):
                    if ex_val.lower() != p_val.lower():
                        conflicts.append({
                            "id": f"conf_{ex.get('id')}",
                            "type": "fact_mismatch",
                            "title": f"סתירה בעובדה: '{ex.get('name')}'",
                            "description": f"הערך הקיים הוא '{ex_val}', אך מוצע ערך חדש: '{p_val}'",
                            "existing_item": ex,
                            "proposed_item": proposed_item,
                            "category": "facts",
                            "profile_id": cur_id
                        })

        elif category == "constraints":
            c_text = proposed_item.get("constraint", "").lower()
            for cmd in p_data.get("commands", []):
                cmd_det = cmd.get("details", "").lower()
                if ("חתימ" in c_text and "חתימ" in cmd_det) or ("אל " in c_text and cmd.get("name", "").lower() in c_text):
                    conflicts.append({
                        "id": f"conf_{cmd.get('id')}",
                        "type": "command_constraint_conflict",
                        "title": f"התנגשות בין איסור לפקודה קיימת",
                        "description": f"האיסור '{proposed_item.get('constraint')}' מתנגש עם הפקודה '{cmd.get('name')}'",
                        "existing_item": cmd,
                        "proposed_item": proposed_item,
                        "category": "commands",
                        "profile_id": cur_id
                    })

    # 1b. Compare the proposed item against the GLOBAL (default) profile too.
    # Profiles are siloed, but generate_prompt_markdown writes the active profile AND every
    # other profile's rules (as "מצבי שיחה") into the same file - so a business rule and a
    # contradicting default rule reach the model side by side with nothing to separate them.
    if proposed_item and category and cur_id != "default":
        base = db.get("profiles", {}).get("default", {}).get("data", {})
        for ex in base.get(category, []):
            if not ex.get("active", True):
                continue
            if items_contradict(proposed_item, ex, category):
                conflicts.append({
                    "id": f"conf_global_{ex.get('id')}",
                    "type": "profile_vs_global",
                    "title": f"סתירה מול הפרופיל הראשי: '{item_label(ex)}'",
                    "description": (f"בפרופיל הראשי מוגדר: '{item_summary(ex, category)}', "
                                    f"ואתה מוסיף כאן: '{item_summary(proposed_item, category)}'"),
                    "existing_item": ex,
                    "proposed_item": proposed_item,
                    "category": category,
                    "profile_id": "default",
                })

    # 2. General database audit (detect existing conflicts among active facts in all profiles)
    for pid, pinfo in db.get("profiles", {}).items():
        facts = pinfo.get("data", {}).get("facts", [])
        seen_names = {}
        for f in facts:
            if not f.get("active", True):
                continue
            fn = f.get("name", "").strip().lower()
            if fn in seen_names:
                prev = seen_names[fn]
                if prev.get("value", "").strip().lower() != f.get("value", "").strip().lower():
                    conflicts.append({
                        "id": f"audit_conf_{f.get('id')}_{prev.get('id')}",
                        "type": "competing_facts",
                        "title": f"קיימות שתי גרסאות שונות עבור: '{f.get('name')}'",
                        "description": f"גרסה א': '{prev.get('value')}' | גרסה ב': '{f.get('value')}'",
                        "item_a": prev,
                        "item_b": f,
                        "category": "facts",
                        "profile_id": pid
                    })
            else:
                seen_names[fn] = f

    return conflicts


@synchronized_db
def resolve_conflict(conflict_id, action, target_item_id=None, profile_id=None):
    """
    Resolves a conflict: 'delete' removes target_item_id, 'keep_both' records the pair as
    accepted so it stops being reported.

    Deletion is scoped to ONE profile (the current one unless profile_id says otherwise) -
    it used to loop over every profile and every category and delete any item sharing that
    id, which silently removed rules the user never looked at.
    """
    db = load_db()

    if action == "delete" and target_item_id:
        target_pid = profile_id or db.get("currentProfile", "default")
        pinfo = db.get("profiles", {}).get(target_pid)
        if not pinfo:
            return False, "הפרופיל לא נמצא"

        pdata = pinfo.get("data", {})
        removed_name = None
        for cat in ["facts", "commands", "constraints", "styles", "instructions"]:
            items = pdata.get(cat, [])
            for it in items:
                if it.get("id") == target_item_id:
                    removed_name = (it.get("name") or it.get("constraint")
                                    or it.get("aspect") or it.get("instruction"))
                    break
            pdata[cat] = [it for it in items if it.get("id") != target_item_id]

        if removed_name is None and not profile_id:
            for other_pid, other_pinfo in db.get("profiles", {}).items():
                if other_pid == target_pid:
                    continue
                other_data = other_pinfo.get("data", {})
                for cat in ["facts", "commands", "constraints", "styles", "instructions"]:
                    items = other_data.get(cat, [])
                    for it in items:
                        if it.get("id") == target_item_id:
                            removed_name = (it.get("name") or it.get("constraint")
                                            or it.get("aspect") or it.get("instruction"))
                            break
                    if removed_name:
                        other_data[cat] = [it for it in items if it.get("id") != target_item_id]
                        break
                if removed_name:
                    break

        if removed_name is None:
            return False, "הפריט לא נמצא במאגר הזיכרון"

        add_log(db, "resolve_conflict", f"הוסר פריט לפתרון סתירה: {removed_name}")
        save_db(db)
        if db.get("settings", {}).get("autoSyncOnChange", True):
            inject_all()
        return True, "הפריט הוסר והסתירה נפתרה בהצלחה"

    if action == "keep_both":
        # Remember the decision, otherwise the same pair is reported again on every check.
        accepted = db.setdefault("acceptedConflicts", [])
        key = conflict_id or target_item_id
        if key and key not in accepted:
            accepted.append(key)
            add_log(db, "accept_conflict", f"סתירה אושרה במודע: {key}")
            save_db(db)
        return True, "הסתירה אושרה ולא תדווח שוב"

    return False, "פעולה לא מוכרת"


@synchronized_db
def add_conversational_memory(text, target_profile=None, auto_save=True):
    """
    High-level entry point to parse, validate, detect conflicts and save memory directly.

    Runs under DB_LOCK: this is the path the MCP server calls, so it can execute
    concurrently with the GUI thread and the folder watcher.
    """
    parsed, err = parse_conversational_input(text)
    if err:
        return False, None, [], err

    category = parsed["category"]
    item = parsed["item"]
    prof_id = target_profile or parsed["target_profile"] or get_current_profile_id()

    # Check for conflicts
    conflicts = detect_conflicts(proposed_item=item, category=category, profile_id=prof_id)

    if auto_save:
        db = load_db()
        profiles = db.setdefault("profiles", {})
        if prof_id not in profiles:
            prof_id = "default"
        p_data = profiles[prof_id].setdefault("data", {})
        p_data.setdefault(category, [])

        item_id = f"{category[:4]}_{int(datetime.now().timestamp()*1000)}"
        item["id"] = item_id
        item["createdAt"] = datetime.now().isoformat()
        p_data[category].insert(0, item)

        prof_name = profiles[prof_id].get("name", prof_id)
        add_log(db, f"conversational_add_{category}", f"נוסף זיכרון בשיחה חופשית ({prof_name}): {item.get('name') or item.get('constraint') or item.get('aspect') or item.get('instruction')}")
        save_db(db)

        if db.get("settings", {}).get("autoSyncOnChange", True):
            inject_all()

    return True, parsed, conflicts, f"הזיכרון נותח בהצלחה כ-{category} ושובץ לפרופיל '{prof_id}'"


# =========================================================================
# GLOBAL TARGETS (קבצי חוקים ברמת המשתמש)
#
# Most AI tools read a single user-level rules file that applies to EVERY project, so the
# directives belong there once - not copied into every project folder. Writing ~20 folders
# x 6 files to achieve "the AI always knows this" is the long way round: it multiplies the
# chances of a failed/overwritten file and leaves rule files scattered across repos.
#
# Per-project injection stays for the tools that genuinely have no global file
# (Cursor's user rules live in its settings DB; Copilot's instructions are per-repo).
# =========================================================================
GLOBAL_TARGETS = [
    {
        "key": "claude_code",
        "name": "Claude Code",
        "ai_key": "claude",
        "detect": lambda: USER_HOME / ".claude",
        "file": lambda: USER_HOME / ".claude" / "CLAUDE.md",
        "note": "זיכרון ברמת המשתמש - חל על כל הפרויקטים",
    },
    {
        "key": "gemini_cli",
        "name": "Gemini CLI",
        "ai_key": "antigravity",
        "detect": lambda: USER_HOME / ".gemini",
        "file": lambda: USER_HOME / ".gemini" / "GEMINI.md",
        "note": "הקשר גלובלי ל-Gemini CLI",
    },
    {
        "key": "codex",
        "name": "Codex",
        "ai_key": "all",
        "detect": lambda: USER_HOME / ".codex",
        "file": lambda: USER_HOME / ".codex" / "AGENTS.md",
        "note": "הנחיות גלובליות ל-Codex",
    },
    {
        "key": "windsurf",
        "name": "Windsurf",
        "ai_key": "windsurf",
        "detect": lambda: USER_HOME / ".codeium" / "windsurf",
        "file": lambda: USER_HOME / ".codeium" / "windsurf" / "memories" / "global_rules.md",
        "note": "כללים גלובליים ל-Windsurf",
    },
]


def get_global_targets():
    """
    Returns the user-level rule files, each marked with whether that tool is installed
    (its config directory exists) and whether the file is already written.
    """
    out = []
    for spec in GLOBAL_TARGETS:
        try:
            detect_dir = spec["detect"]()
            file_path = spec["file"]()
            out.append({
                "key": spec["key"],
                "name": spec["name"],
                "ai_key": spec["ai_key"],
                "note": spec["note"],
                "path": str(file_path),
                "installed": detect_dir.exists(),
                "written": file_path.exists(),
            })
        except Exception as e:
            print(f"Failed to resolve global target {spec.get('key')}: {e}")
    return out


@synchronized_db
def inject_global_targets():
    """
    Writes the directive block into each installed tool's user-level rules file.
    Returns {"written": [...], "skipped": [...], "failed": [...]}.
    """
    db = load_db()
    enabled = db.get("settings", {}).get("injectGlobalTargets", True)
    results = {"written": [], "skipped": [], "failed": []}

    if not enabled:
        results["skipped"] = [t["name"] for t in get_global_targets()]
        return results

    disabled_keys = set(db.get("settings", {}).get("disabledGlobalTargets", []))

    for target in get_global_targets():
        if not target["installed"]:
            results["skipped"].append(f"{target['name']} (לא מותקן)")
            continue
        if target["key"] in disabled_keys:
            results["skipped"].append(f"{target['name']} (הושבת)")
            continue

        try:
            file_path = Path(target["path"])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            existing = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            block = generate_prompt_markdown(target_folder_path=None, target_ai=target["ai_key"])
            file_path.write_text(inject_into_text(existing, block), encoding="utf-8")
            results["written"].append(target["name"])
        except Exception as e:
            results["failed"].append({"name": target["name"], "error": str(e)})
            print(f"Failed to write global target {target['name']}: {e}")

    if results["written"]:
        add_log(db, "sync_global", f"עודכנו {len(results['written'])} קבצי חוקים גלובליים: "
                                   f"{', '.join(results['written'])}")
        save_db(db)

    return results


def clean_global_targets():
    """Removes the injected block from every global rules file (used when disabling them)."""
    removed = []
    for target in get_global_targets():
        file_path = Path(target["path"])
        if not file_path.exists():
            continue
        try:
            cleaned = clean_text_memory(file_path.read_text(encoding="utf-8"))
            if cleaned.strip():
                file_path.write_text(cleaned, encoding="utf-8")
            else:
                file_path.unlink(missing_ok=True)
            removed.append(target["name"])
        except Exception as e:
            print(f"Failed to clean global target {target['name']}: {e}")
    return removed


# =========================================================================
# PROPOSAL QUEUE (הצעות הממתינות לאישור הבעלים)
#
# An AI reaching the app through the MCP server may SUGGEST memory, never write it.
# Its suggestion lands here and only becomes a real directive once the owner approves it
# in the GUI. This is what keeps "the AI proposes, I approve" true rather than aspirational.
# =========================================================================
def get_proposals(status="pending"):
    props = load_db().get("proposals", [])
    if status is None:
        return props
    return [p for p in props if p.get("status", "pending") == status]


def count_pending_proposals():
    return len(get_proposals("pending"))


@synchronized_db
def add_proposal(parsed, origin="mcp", raw_text="", conflicts=None):
    """
    Queues an AI-authored item for approval. Returns the stored proposal record.
    `parsed` is the dict returned by parse_conversational_input / add_conversational_memory.
    """
    db = load_db()
    proposals = db.setdefault("proposals", [])

    item = dict(parsed.get("item") or {})
    category = parsed.get("category")
    prof_id = parsed.get("target_profile") or db.get("currentProfile", "default")
    if prof_id not in db.get("profiles", {}):
        prof_id = "default"

    label = (item.get("name") or item.get("constraint") or item.get("aspect")
             or item.get("instruction") or "")

    prop = {
        "id": f"prop_{int(datetime.now().timestamp() * 1000)}",
        "status": "pending",
        "category": category,
        "item": item,
        "target_profile": prof_id,
        "origin": origin,
        "raw_text": raw_text,
        "conflicts": conflicts or [],
        "createdAt": datetime.now().isoformat(),
    }
    proposals.insert(0, prop)

    add_log(db, "proposal_added", f"הצעה חדשה ממתינה לאישור ({origin}): {label}")
    save_db(db)
    return prop


@synchronized_db
def approve_proposal(proposal_id):
    """Turns a pending proposal into a real directive in its target profile."""
    db = load_db()
    props = db.get("proposals", [])
    prop = next((p for p in props if p.get("id") == proposal_id), None)
    if not prop:
        return False, "ההצעה לא נמצאה"
    if prop.get("status") != "pending":
        return False, "ההצעה כבר טופלה"

    category = prop.get("category")
    prof_id = prop.get("target_profile") or db.get("currentProfile", "default")
    profiles = db.setdefault("profiles", {})
    if prof_id not in profiles:
        prof_id = "default"

    p_data = profiles[prof_id].setdefault("data", {})
    p_data.setdefault(category, [])

    item = dict(prop.get("item") or {})
    item["id"] = f"{category[:4]}_{int(datetime.now().timestamp() * 1000)}"
    item.setdefault("scope", "global")
    item.setdefault("active", True)
    item.setdefault("target_ais", ["all"])
    item["createdAt"] = datetime.now().isoformat()
    item["origin"] = prop.get("origin", "mcp")

    # Appended, not inserted at the top: an approved AI suggestion must not outrank the
    # owner's own directives in the generated prompt, which is ordered by list position.
    p_data[category].append(item)

    prop["status"] = "approved"
    prop["resolvedAt"] = datetime.now().isoformat()

    label = (item.get("name") or item.get("constraint") or item.get("aspect")
             or item.get("instruction") or "")
    add_log(db, "proposal_approved", f"הצעה אושרה ונוספה ל-{category}: {label}")
    save_db(db)

    if db.get("settings", {}).get("autoSyncOnChange", True):
        inject_all()

    return True, item


@synchronized_db
def reject_proposal(proposal_id):
    db = load_db()
    props = db.get("proposals", [])
    prop = next((p for p in props if p.get("id") == proposal_id), None)
    if not prop:
        return False, "ההצעה לא נמצאה"

    prop["status"] = "rejected"
    prop["resolvedAt"] = datetime.now().isoformat()
    add_log(db, "proposal_rejected", "הצעה נדחתה")
    save_db(db)
    return True, "ההצעה נדחתה"


@synchronized_db
def clear_resolved_proposals():
    """Drops approved/rejected records so the queue does not grow without bound."""
    db = load_db()
    props = db.get("proposals", [])
    pending = [p for p in props if p.get("status", "pending") == "pending"]
    removed = len(props) - len(pending)
    if removed:
        db["proposals"] = pending
        save_db(db)
    return removed


# =========================================================================
# PATH MANAGEMENT & RESCAN
# =========================================================================
def get_paths(): return load_db().get("targetPaths", [])

@synchronized_db
def add_path(folder_path, active=True):
    folder_path = str(Path(folder_path).resolve())
    if not os.path.isdir(folder_path): return False, "הנתיב שנבחר אינו תיקייה קיימת"
    if not is_valid_project_path(folder_path):
        return False, "לא ניתן להוסיף תיקייה זמנית של המערכת כנתיב פרויקט"

    db = load_db()
    existing = db.get("targetPaths", [])
    for item in existing:
        if str(Path(item["path"]).resolve()).lower() == folder_path.lower():
            return False, "נתיב זה כבר קיים ברשימה"

    entry = {"path": folder_path, "name": Path(folder_path).name, "active": bool(active), "lastSynced": None}
    existing.append(entry)
    db["targetPaths"] = existing
    add_log(db, "add_path", f"נוסף נתיב יעד חדש: {entry['name']}")
    save_db(db)

    if active:
        prompt_text = generate_prompt_markdown(target_folder_path=folder_path)
        inject_rules_into_folder(folder_path, prompt_text)  # returns (ok, hashes)
    return True, entry

@synchronized_db
def remove_path(folder_path, clean_files=True):
    folder_path = str(Path(folder_path).resolve())
    db = load_db()
    existing = db.get("targetPaths", [])
    found = False
    updated = []
    for item in existing:
        if str(Path(item["path"]).resolve()).lower() == folder_path.lower():
            found = True
        else:
            updated.append(item)

    if found:
        db["targetPaths"] = updated
        add_log(db, "remove_path", f"הוסר נתיב יעד: {folder_path}")
        save_db(db)
        if clean_files and os.path.isdir(folder_path):
            clean_folder_memory(folder_path)
        return True, "הנתיב הוסר בהצלחה"
    return False, "הנתיב לא נמצא"

@synchronized_db
def toggle_path(folder_path, active=None):
    folder_path = str(Path(folder_path).resolve())
    db = load_db()
    for item in db.get("targetPaths", []):
        if str(Path(item["path"]).resolve()).lower() == folder_path.lower():
            item["active"] = not item["active"] if active is None else bool(active)
            save_db(db)
            if item["active"]:
                inject_rules_into_folder(folder_path, generate_prompt_markdown(target_folder_path=folder_path))
            else:
                clean_folder_memory(folder_path)
            return True, item["active"]
    return False, None

@synchronized_db
def rescan_projects():
    db = load_db()
    existing_paths = {str(Path(x["path"]).resolve()).lower(): x for x in db.get("targetPaths", [])}
    discovered = auto_discover_project_paths()
    newly_added = 0
    for p in discovered:
        key = str(Path(p).resolve()).lower()
        if key not in existing_paths:
            db.setdefault("targetPaths", []).append({"path": p, "name": Path(p).name, "active": True, "lastSynced": None})
            newly_added += 1

    if newly_added > 0:
        add_log(db, "rescan", f"אותרו ונוספו {newly_added} פרויקטים חדשים במחשב")
        save_db(db)
    return newly_added, len(db.get("targetPaths", []))


# =========================================================================
# FOLDER WATCHER DAEMON (ניטור תיקיות בזמן אמת)
# =========================================================================
_watcher_running = False
_watcher_thread = None

def start_folder_watcher(on_new_project_callback=None):
    global _watcher_running, _watcher_thread
    if _watcher_running:
        return

    _watcher_running = True

    def watcher_loop():
        while _watcher_running:
            try:
                db = load_db()
                if db.get("settings", {}).get("folderWatcherActive", True):
                    existing = {str(Path(x["path"]).resolve()).lower() for x in db.get("targetPaths", [])}
                    discovered = auto_discover_project_paths()
                    for p in discovered:
                        k = str(Path(p).resolve()).lower()
                        if k not in existing:
                            print(f"[Watcher] Detected new project folder: {p}")
                            ok, entry = add_path(p, active=True)
                            if ok and on_new_project_callback:
                                on_new_project_callback(p, Path(p).name)
            except Exception as e:
                print(f"[Watcher] error: {e}")
            time.sleep(5)

    _watcher_thread = threading.Thread(target=watcher_loop, daemon=True)
    _watcher_thread.start()


# =========================================================================
# BACKUP EXPORT & IMPORT (ייבוא וייצוא גיבוי)
# =========================================================================
def export_backup(target_file_path):
    try:
        db = load_db()
        with open(target_file_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Failed to export backup to {target_file_path}: {e}")
        return False


def validate_db_structure(data):
    """
    Verifies an imported/downloaded database has the shape the rest of the code assumes
    (db["profiles"][id]["data"][category] is a list), so a malformed file can be rejected
    BEFORE it overwrites the live database and starts raising KeyError on every CRUD action.
    Returns (ok, error_message).
    """
    if not isinstance(data, dict):
        return False, "מבנה הקובץ אינו תקין (לא אובייקט JSON)."

    # Legacy flat format (pre-v5) is migrated by load_db, so a flat "facts" list is acceptable.
    if "profiles" not in data:
        if isinstance(data.get("facts"), list):
            return True, ""
        return False, "לא נמצאו פרופילים ולא נמצא מבנה נתונים ישן תקין בקובץ."

    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        return False, "שדה 'profiles' בקובץ אינו תקין או ריק."

    for p_id, p_info in profiles.items():
        if not isinstance(p_info, dict):
            return False, f"הפרופיל '{p_id}' אינו במבנה תקין."
        p_data = p_info.get("data")
        if not isinstance(p_data, dict):
            return False, f"לפרופיל '{p_id}' חסר מקטע 'data' תקין."
        for cat in ["facts", "commands", "constraints", "styles", "instructions", "context_files"]:
            if cat in p_data and not isinstance(p_data[cat], list):
                return False, f"הקטגוריה '{cat}' בפרופיל '{p_id}' אינה רשימה תקינה."

    return True, ""


@synchronized_db
def import_backup(source_file_path):
    try:
        with open(source_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"קובץ הגיבוי אינו קובץ JSON תקין: {e}"
    except Exception as e:
        return False, f"לא ניתן לקרוא את קובץ הגיבוי: {e}"

    ok, err = validate_db_structure(data)
    if not ok:
        return False, f"קובץ גיבוי לא תקין - {err}"

    try:
        # Keep the pre-import database aside so a bad restore is recoverable.
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_memory_file(suffix=f".before-import-{stamp}")

        save_db(data)
        load_db()  # trigger migration check
        inject_all()
        return True, "הגיבוי שוחזר והושתל בהצלחה!"
    except Exception as e:
        return False, f"שחזור הגיבוי נכשל: {e}"


# =========================================================================
# CLOUD SYNC - GITHUB GIST (סנכרון ענן מאובטח ללא שרת)
# =========================================================================
def get_cloud_sync_credentials(token=None, gist_id=None):
    db = load_db()
    st = db.get("settings", {})
    t = (token or st.get("githubGistToken") or "").strip()
    g = (gist_id or st.get("githubGistId") or "").strip()
    return t, g

@synchronized_db
def push_to_cloud(token=None, gist_id=None):
    """
    Backs up the entire memory database to a private GitHub Gist.
    Creates a new Gist if gist_id is empty, otherwise updates the existing Gist.
    """
    tok, gid = get_cloud_sync_credentials(token, gist_id)
    if not tok:
        return False, "לא הוגדר GitHub Personal Access Token. נא להזין טוקן בהגדרות.", ""

    db = load_db()
    cloud_data = json.loads(json.dumps(db))

    # Never ship credentials to the Gist - a "secret" gist is merely unlisted, not private,
    # and these keys stay valid for whoever ends up holding the backup.
    for secret_key in ("geminiApiKey", "githubGistToken"):
        if secret_key in cloud_data.get("settings", {}):
            cloud_data["settings"][secret_key] = ""

    content_str = json.dumps(cloud_data, ensure_ascii=False, indent=2)

    headers = {
        "Authorization": f"token {tok}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Universal-AI-Memory-Hub"
    }

    payload = {
        "description": f"Universal AI Memory Hub Backup - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "public": False,
        "files": {
            "universal_ai_memory.json": {
                "content": content_str
            }
        }
    }

    try:
        if gid:
            # Update existing Gist
            url = f"https://api.github.com/gists/{gid}"
            res = requests.patch(url, json=payload, headers=headers, timeout=20, verify=REQUEST_VERIFY)
            if res.status_code == 200:
                add_log(db, "cloud_push", f"סונכרן בהצלחה לענן (Gist: {gid[:8]}...)")
                save_db(db)
                return True, f"הנתונים הועלו בהצלחה ל-Gist הקיים! (ID: {gid[:8]}...)", gid
            elif res.status_code == 404:
                gid = ""  # Gist was deleted or invalid, fallback to create
            elif res.status_code == 401:
                return False, "שגיאת אימות: ה-GitHub Token שגוי או שחסרה לו הרשאת 'gist'", ""
            else:
                return False, f"שגיאה בעדכון Gist ({res.status_code}): {res.text[:120]}", ""

        if not gid:
            # Create new private Gist
            url = "https://api.github.com/gists"
            res = requests.post(url, json=payload, headers=headers, timeout=20, verify=REQUEST_VERIFY)
            if res.status_code == 201:
                new_gist = res.json()
                new_id = new_gist.get("id")
                db["settings"]["githubGistId"] = new_id
                add_log(db, "cloud_push_new", f"נוצר Gist פרטי חדש בענן (ID: {new_id[:8]}...)")
                save_db(db)
                return True, f"נוצר Gist פרטי חדש בהצלחה! מזהה: {new_id[:8]}...", new_id
            elif res.status_code == 401:
                return False, "שגיאת אימות: ה-GitHub Token שגוי או שחסרה לו הרשאת 'gist'", ""
            else:
                return False, f"שגיאה ביצירת Gist ({res.status_code}): {res.text[:120]}", ""
    except Exception as e:
        return False, f"שגיאת תקשורת עם GitHub API: {str(e)}", ""


@synchronized_db
def pull_from_cloud(token=None, gist_id=None):
    """
    Downloads the database from GitHub Gist, updates local memory, and injects to all folders.
    """
    tok, gid = get_cloud_sync_credentials(token, gist_id)
    if not tok:
        return False, "לא הוגדר GitHub Personal Access Token."
    if not gid:
        return False, "לא הוגדר מזהה Gist ID לשחזור ממנו. נא להזין Gist ID."

    headers = {
        "Authorization": f"token {tok}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Universal-AI-Memory-Hub"
    }

    url = f"https://api.github.com/gists/{gid}"
    try:
        res = requests.get(url, headers=headers, timeout=20, verify=REQUEST_VERIFY)
        if res.status_code == 200:
            data = res.json()
            files = data.get("files", {})
            file_info = files.get("universal_ai_memory.json") or (list(files.values())[0] if files else None)
            if not file_info:
                return False, "לא נמצא קובץ נתונים מתאים ב-Gist זה."

            raw_content = file_info.get("content")
            if not raw_content and file_info.get("raw_url"):
                r2 = requests.get(file_info["raw_url"], timeout=20, verify=REQUEST_VERIFY)
                if r2.status_code == 200:
                    raw_content = r2.text

            if not raw_content:
                return False, "לא ניתן היה לקרוא את תוכן הקובץ משרתי ה-Gist."

            try:
                cloud_db = json.loads(raw_content)
            except Exception as json_err:
                return False, f"תוכן קובץ ה-Gist אינו בפורמט JSON תקין: {json_err}"
            struct_ok, struct_err = validate_db_structure(cloud_db)
            if struct_ok:
                # Preserve local sensitive settings
                local_db = load_db()
                if "settings" in local_db:
                    for k, v in local_db["settings"].items():
                        if v and not cloud_db.get("settings", {}).get(k):
                            cloud_db.setdefault("settings", {})[k] = v

                # Keep the pre-pull database aside so an unwanted cloud restore is recoverable.
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_memory_file(suffix=f".before-pull-{stamp}")

                save_db(cloud_db)
                load_db()
                inject_all()
                return True, "הנתונים הורדו בהצלחה מהענן והושתלו בכל הפרויקטים!"
            else:
                return False, f"מבנה הנתונים בקובץ ה-Gist אינו תואם ל-Universal AI Memory Hub - {struct_err}"
        elif res.status_code == 404:
            return False, f"ה-Gist עם המזהה {gid} לא נמצא ב-GitHub."
        elif res.status_code == 401:
            return False, "שגיאת אימות: ה-GitHub Token שגוי או אינו מורשה."
        else:
            return False, f"שגיאה בהורדת נתונים מ-GitHub ({res.status_code}): {res.text[:120]}"
    except Exception as e:
        return False, f"שגיאה בתקשורת מול GitHub: {str(e)}"



# =========================================================================
# MASTER PROMPT GENERATOR (כולל Per-Project Scoping & Per-AI Targeting)
# =========================================================================
AI_TARGETS = {
    "all": "כל מודלי ה-AI",
    "antigravity": "Google Antigravity",
    "claude": "Claude Desktop / Code",
    "cursor": "Cursor AI",
    "windsurf": "Windsurf",
    "copilot": "GitHub Copilot",
    "cline": "Cline / Roo Code"
}


def item_matches_ai(item, target_ai=None):
    """
    Checks if an item applies to a specific AI tool.
    target_ai: None or 'all' matches everything.
    Otherwise checks if 'all' or target_ai is in item's target_ais list.
    """
    if not target_ai or target_ai == "all":
        return True

    item_ais = item.get("target_ais", ["all"])
    if not item_ais or item_ais == "all":
        return True

    if isinstance(item_ais, str):
        if item_ais.lower() == "all":
            return True
        item_ais = [item_ais]

    target_ai_lower = target_ai.lower()
    return any(a.lower() in ("all", target_ai_lower) for a in item_ais)


def item_is_expired(item, now=None):
    """
    True when the item carries an expiry date that has already passed.

    Fails OPEN: an unparseable or missing date means "not expired", so a bad value can
    never silently delete a directive from every rule file.
    """
    raw = item.get("expiresAt")
    if not raw:
        return False
    try:
        expires = datetime.fromisoformat(str(raw))
    except Exception:
        return False
    return expires <= (now or datetime.now())


def item_matches_target(item, target_folder_path=None, target_ai=None):
    """
    Checks if an item applies to both the target folder and the target AI.
    scope: 'global' (applies to all folders) or a specific project name.
    target_ai: 'all' or specific AI tool key ('antigravity', 'claude', 'cursor', etc.)

    This is the single filter every injection path funnels through, so an expiry check
    here removes an expired rule from every generated file at once.
    """
    # 0. Expired rules are never injected anywhere
    if item_is_expired(item):
        return False

    # 1. Check folder scope
    scope = item.get("scope", "global")
    if scope and scope != "global":
        if not target_folder_path:
            return False
        folder_name = Path(target_folder_path).name.lower()
        if isinstance(scope, list):
            if not any(s.lower() == folder_name for s in scope):
                return False
        else:
            if str(scope).lower() != folder_name:
                return False

    # 2. Check AI target
    return item_matches_ai(item, target_ai)


def generate_prompt_markdown(target_folder_path=None, target_ai=None):
    p_data = get_current_profile_data()

    active_facts = [f for f in p_data.get("facts", []) if f.get("active", True) and item_matches_target(f, target_folder_path, target_ai)]
    active_commands = [c for c in p_data.get("commands", []) if c.get("active", True) and item_matches_target(c, target_folder_path, target_ai)]
    active_constraints = [k for k in p_data.get("constraints", []) if k.get("active", True) and item_matches_target(k, target_folder_path, target_ai)]
    active_styles = [s for s in p_data.get("styles", []) if s.get("active", True) and item_matches_target(s, target_folder_path, target_ai)]
    active_instructions = [i for i in p_data.get("instructions", []) if i.get("active", True) and item_matches_target(i, target_folder_path, target_ai)]
    active_files = [cf for cf in p_data.get("context_files", []) if cf.get("active", True) and item_matches_target(cf, target_folder_path, target_ai)]

    total_active = len(active_facts) + len(active_commands) + len(active_constraints) + len(active_styles) + len(active_instructions) + len(active_files)
    if total_active == 0:
        return f"{START_MARKER}\n<!-- AI Memory Hub: אין כרגע עובדות או הנחיות פעילות בזיכרון -->\n{END_MARKER}"

    lines = [
        START_MARKER,
        "# 🧠 AI Persistent Memory & Master Directives",
        "> מידע קבוע, חוקים מחייבים וכללי התנהגות שחובה ליישם בכל השיחות:",
        "> 🚀 **הוראת עדיפות עליונה ומענה מיידי**: כאשר נשאלת שאלה שהתשובה עליה מופיעה בזיכרון זה (עובדות, הגדרות, קישורים) - ענה מיד ישירות מתוך הזיכרון! אין להריץ פקודות סריקה, PowerShell או לחפש במחשב עבור מידע שכבר מוגדר כאן.",
        ""
    ]

    # 1. מידע ועובדות
    if active_facts:
        lines.append("## 📌 1. מידע ועובדות קבועות (Facts & Data)")
        for item in active_facts:
            suffix = " (כתובת רשמית וסופית - השב מיד ללא שום בדיקה במחשב)" if "אתר" in item['name'] else ""
            lines.append(f"- **{item['name']}**: {item['value']}{suffix}")
        lines.append("")

    # 2. פקודות וכללי התנהגות
    if active_commands:
        lines.append("## ⚡ 2. פקודות וכללי התנהגות (Commands & Behaviors)")
        for cmd in active_commands:
            lines.append(f"### ⚙️ {cmd['name']}")
            lines.append(f"- **פעולה ופירוט**: {cmd['details']}")
            lines.append(f"- **באיזה מקרה לבצע**: {cmd['trigger_case']}")
            lines.append("")

    # 3. מגבלות ואיסורים
    # Only the user's OWN constraints are written here. The no-scanning directive used to be
    # hardcoded and emitted unconditionally, so every install - including someone else's -
    # shipped a rule forbidding grep/dir that its owner never wrote. It is now a real,
    # editable constraint item (see SCAN_CONSTRAINT_TEMPLATE and the migration in load_db).
    if active_constraints:
        lines.append("## ⛔ 3. מגבלות ואיסורים מחייבים - 'אל תעשה' (Negative Constraints)")
        for const in active_constraints:
            lines.append(f"- **איסור**: {const['constraint']}")
            if const.get('alternative_or_why'):
                lines.append(f"  - _הנחיה חלופית_: {const['alternative_or_why']}")
        lines.append("")

    # 4. סגנון, שפה וטון מענה
    if active_styles:
        lines.append("## 🎨 4. סגנון, שפה וטון מענה (Tone & Persona)")
        for st in active_styles:
            lines.append(f"- **{st['aspect']}**: {st['instruction']}")
        lines.append("")

    # 5. הוראות פרטיות ומותנות
    if active_instructions:
        lines.append("## 🛡️ 5. הוראות פרטיות והנחיות מותנות (Contextual Directives)")
        for inst in active_instructions:
            lines.append(f"- **הוראה**: {inst['instruction']}")
            if inst.get('when_to_apply') and inst['when_to_apply'] != "תמיד בכל מצב":
                lines.append(f"  - _מתי ליישם_: {inst['when_to_apply']}")
        lines.append("")

    # 6. מסמכי הקשר וקבצי פרויקט (Context Files)
    if active_files:
        lines.append("## 📚 6. מסמכי הקשר וקבצי פרויקט (Project Context Files)")
        for cf in active_files:
            lines.append(f"### 📄 {cf['name']}")
            if cf.get("summary"):
                lines.append(f"- **תקציר הנחיות**: {cf['summary']}")
            lines.append(f"- **נתיב מקור במחשב**: `{cf.get('path', '')}`")
            lines.append("")

    # 7. מצבי שיחה והתנהגות מותנית (Dynamic Conversational Modes)
    db = load_db()
    all_profiles = db.get("profiles", {})
    cur_id = db.get("currentProfile", "default")

    dynamic_modes = []
    for pid, pinfo in all_profiles.items():
        if pid == cur_id:
            continue
        if not pinfo.get("inject_as_mode", True):
            continue
        triggers = pinfo.get("trigger_keywords", [])
        pdata = pinfo.get("data", {})
        has_items = any(len(pdata.get(cat, [])) > 0 for cat in ["facts", "commands", "constraints", "styles", "instructions"])
        if triggers or has_items:
            dynamic_modes.append((pid, pinfo))

    if dynamic_modes:
        lines.append("## 🎭 7. מצבי שיחה והתנהגות מותנית (Dynamic Conversational Modes)")
        lines.append("> 🧠 **כלל מעבר מצבים אוטונומי וחכם (Zero-Friction Contextual Switching)**:")
        lines.append("> 1. **זיהוי סמנטי אוטונומי**: זהה בעצמך את נושא השיחה – אם השאלה עוסקת בקוד, דיבאגינג או פיתוח, החל אוטומטית את כללי 'פיתוח קוד'. אם מדובר בלקוחות, הצעות מחיר או נושאים עסקיים, החל אוטומטית את כללי הפרופיל העסקי.")
        lines.append("> 2. **הפעלת טריגרים ישירה**: מעבר מיידי בעת שימוש באחת ממילות ההפעלה המפורשות.")
        lines.append("> 3. **ברירת מחדל נקייה**: בכל שיחה יומיומית רגילה – הישאר במצב ראשי ללא חתימות עסקיות או מגבלות עודפות.")
        lines.append("")
        for pid, pinfo in dynamic_modes:
            pname = pinfo.get("name", pid)
            triggers = pinfo.get("trigger_keywords", [])
            desc = pinfo.get("description", "")
            pdata = pinfo.get("data", {})

            lines.append(f"### 🎯 מצב: {pname}")
            if triggers:
                trig_str = ", ".join(f"'{t}'" for t in triggers)
                lines.append(f"- **מילות הפעלה וזיהוי הקשר**: {trig_str}")
            if desc:
                lines.append(f"- **תיאור המצב**: {desc}")

            m_facts = [f for f in pdata.get("facts", []) if f.get("active", True) and item_matches_target(f, target_folder_path, target_ai)]
            m_commands = [c for c in pdata.get("commands", []) if c.get("active", True) and item_matches_target(c, target_folder_path, target_ai)]
            m_constraints = [k for k in pdata.get("constraints", []) if k.get("active", True) and item_matches_target(k, target_folder_path, target_ai)]
            m_styles = [s for s in pdata.get("styles", []) if s.get("active", True) and item_matches_target(s, target_folder_path, target_ai)]
            m_instructions = [i for i in pdata.get("instructions", []) if i.get("active", True) and item_matches_target(i, target_folder_path, target_ai)]

            if m_styles:
                lines.append(f"- **סגנון וטון במצב זה**:")
                for st in m_styles:
                    lines.append(f"  - {st.get('aspect', 'סגנון')}: {st.get('instruction', '')}")
            if m_commands:
                lines.append(f"- **פקודות וחתימות במצב זה**:")
                for cmd in m_commands:
                    lines.append(f"  - {cmd.get('name', 'פקודה')}: {cmd.get('details', '')} (במקרה של: {cmd.get('trigger_case', 'תמיד')})")
            if m_facts:
                lines.append(f"- **עובדות ונתונים ייעודיים למצב זה**:")
                for f in m_facts:
                    lines.append(f"  - {f.get('name', '')}: {f.get('value', '')}")
            if m_constraints:
                lines.append(f"- **מגבלות במצב זה**:")
                for const in m_constraints:
                    lines.append(f"  - איסור: {const.get('constraint', '')}")
            if m_instructions:
                lines.append(f"- **הוראות מיוחדות במצב זה**:")
                for inst in m_instructions:
                    lines.append(f"  - {inst.get('instruction', '')} ({inst.get('when_to_apply', '')})")
            lines.append("")

    now_str = datetime.now().strftime("%d.%m.%Y, %H:%M:%S")
    lines.append(f"_סונכרן אוטומטית באמצעות Universal AI Memory Hub | עודכן: {now_str}_")
    lines.append(END_MARKER)

    return "\n".join(lines)


def extract_block(text):
    """
    Returns the injected block (markers included) from a rule file, or None when the file
    has no complete, well-formed block. A file whose END marker precedes its START marker
    is treated as having none, so it is rewritten rather than mangled further.
    """
    if not text or START_MARKER not in text or END_MARKER not in text:
        return None
    start_idx = text.index(START_MARKER)
    end_idx = text.index(END_MARKER) + len(END_MARKER)
    if end_idx <= start_idx:
        return None
    return text[start_idx:end_idx]


def block_fingerprint(block):
    """
    Stable hash of an injected block, used to notice a human edited it.

    Line endings and surrounding whitespace are normalised first: Windows, git checkouts
    and cloud-sync clients all rewrite those without anyone touching the content, and a
    false "your file was edited" alarm on every folder would be worse than no alarm.
    """
    if not block:
        return None
    normalized = block.replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def inject_into_text(existing_text, new_block):
    # A block without markers could never be located again - it would be appended anew on
    # every sync and clean_folder_memory could not remove it. Wrap it defensively so the
    # injected region always stays replaceable and removable.
    if START_MARKER not in new_block or END_MARKER not in new_block:
        new_block = f"{START_MARKER}\n{new_block.strip()}\n{END_MARKER}"

    if START_MARKER in existing_text and END_MARKER in existing_text:
        start_idx = existing_text.index(START_MARKER)
        end_idx = existing_text.index(END_MARKER) + len(END_MARKER)
        return existing_text[:start_idx] + new_block + existing_text[end_idx:]

    if existing_text.strip():
        return existing_text.strip() + "\n\n" + new_block + "\n"
    return new_block + "\n"


def clean_text_memory(existing_text):
    if START_MARKER in existing_text and END_MARKER in existing_text:
        start_idx = existing_text.index(START_MARKER)
        end_idx = existing_text.index(END_MARKER) + len(END_MARKER)
        cleaned = existing_text[:start_idx].rstrip() + "\n" + existing_text[end_idx:].lstrip()
        return cleaned.strip()
    return existing_text


def inject_rules_into_folder(folder_path, prompt_text=None, known_hashes=None, force=False):
    """
    Writes the directive block into a project folder's rule files.

    known_hashes: {filename: sha} recorded the last time this app wrote each file. When the
    block currently on disk does not match its recorded hash, somebody edited it by hand -
    the write is SKIPPED and the file is reported as drifted, so a manual edit is never
    destroyed silently. Pass force=True to overwrite anyway.

    Returns (ok, written_hashes).
    """
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return False, {}

    known_hashes = known_hashes or {}
    # Track every write so a read-only folder / locked file / full disk is reported to the
    # user instead of the caller being told the sync "completed successfully".
    failures = []
    drifted = []
    written_hashes = {}

    targets = [(rf, ai_key, folder / rf) for rf, ai_key in RULE_FILES]
    targets.append((".github/copilot-instructions.md", "copilot",
                    folder / ".github" / "copilot-instructions.md"))

    for rf, ai_key, fp in targets:
        content = ""
        if fp.exists():
            try:
                content = fp.read_text(encoding="utf-8")
            except Exception as e:
                failures.append(f"{rf}: קריאה נכשלה ({e})")
                continue

        # Was the block on disk edited since we wrote it?
        expected = known_hashes.get(rf)
        if expected and not force:
            current = block_fingerprint(extract_block(content))
            if current and current != expected:
                drifted.append({"file": rf, "path": str(fp),
                                "expected": expected, "found": current})
                continue

        p_text = prompt_text if prompt_text else generate_prompt_markdown(
            target_folder_path=folder_path, target_ai=ai_key)
        new_content = inject_into_text(content, p_text)

        try:
            if fp.parent != folder:
                fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(new_content, encoding="utf-8")
            written_hashes[rf] = block_fingerprint(extract_block(new_content))
        except Exception as e:
            failures.append(f"{rf}: {e}")
            print(f"Failed to write {fp}: {e}")

    if drifted:
        INJECTION_DRIFT.append({"folder": str(folder), "files": drifted})

    if failures:
        INJECTION_FAILURES.append({"folder": str(folder), "errors": failures})
        return False, written_hashes

    return (not drifted), written_hashes


@synchronized_db
def force_resync_folder(folder_path):
    """
    Rewrites one folder's rule files even though their blocks drifted - the explicit
    "overwrite my edit" action. Refreshes the stored baseline so it stops being reported.
    """
    db = load_db()
    ok, hashes = inject_rules_into_folder(folder_path, force=True)

    for item in db.get("targetPaths", []):
        if str(Path(item.get("path", "")).resolve()).lower() == str(Path(folder_path).resolve()).lower():
            if hashes:
                item.setdefault("injected", {}).update(hashes)
            item["lastSynced"] = datetime.now().isoformat()
            break

    add_log(db, "force_resync", f"נדרס ידנית לפי הזיכרון: {folder_path}")
    save_db(db)
    return ok


def clean_folder_memory(folder_path):
    folder = Path(folder_path)
    if not folder.exists(): return

    # Must mirror the inject list in inject_rules_into_folder exactly - .clinerules was
    # missing here, so removing a project folder left a permanently frozen block behind.
    for rf, _ai_key in RULE_FILES:
        fp = folder / rf
        if fp.exists():
            try:
                cleaned = clean_text_memory(fp.read_text(encoding="utf-8"))
                if cleaned.strip(): fp.write_text(cleaned, encoding="utf-8")
                else: fp.unlink(missing_ok=True)
            except Exception as e:
                print(f"Failed to clean {fp}: {e}")

    copilot_fp = folder / ".github" / "copilot-instructions.md"
    if copilot_fp.exists():
        try:
            cleaned = clean_text_memory(copilot_fp.read_text(encoding="utf-8"))
            if cleaned.strip(): copilot_fp.write_text(cleaned, encoding="utf-8")
            else: copilot_fp.unlink(missing_ok=True)
        except Exception: pass


def clean_all_project_folders(db=None):
    """
    Removes injected rule blocks from all registered project folders.
    Used when running in Macro mode (global only) or by manual user request.
    """
    should_save = False
    if db is None:
        db = load_db()
        should_save = True

    target_paths = db.get("targetPaths", [])
    cleaned_count = 0
    for item in target_paths:
        p = item.get("path")
        if p and os.path.isdir(p):
            try:
                clean_folder_memory(p)
                item["lastSynced"] = None
                item.pop("injected", None)
                cleaned_count += 1
            except Exception as e:
                print(f"Failed to clean folder {p}: {e}")

    add_log(db, "clean_projects", f"נוקו קבצי חוקים מ-{cleaned_count} תיקיות פרויקטים (מעבר למאקרו / ניקוי יזום)")
    if should_save:
        save_db(db)
    return {"cleaned_count": cleaned_count, "total_folders": len(target_paths)}


def get_mcp_launch_command():
    """
    Returns (command, args) that start this app's MCP server, valid for the current build.

    In a frozen (PyInstaller) build there is no mcp_server.py on disk to point at:
    WORKSPACE_DIR is the %TEMP%\\_MEIxxxxx extraction folder, which is deleted the moment
    the app closes - so a config written from the installed .exe used to reference a path
    that no longer exists. Frozen builds therefore re-launch the .exe itself with --mcp.
    """
    if getattr(sys, "frozen", False):
        return sys.executable, ["--mcp"]
    return (sys.executable or "python"), [str((WORKSPACE_DIR / "mcp_server.py").resolve())]


def inject_claude_desktop_mcp():
    config_path = APPDATA_ROAMING / "Claude" / "claude_desktop_config.json"
    if not config_path.parent.exists(): return False, "Claude Desktop לא מותקן"
    python_exe, mcp_args = get_mcp_launch_command()
    data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f: data = json.load(f)
        except Exception: data = {}
    data.setdefault("mcpServers", {})
    data["mcpServers"]["ai-memory-hub"] = {"command": python_exe, "args": mcp_args}
    try:
        with open(config_path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
        return True, str(config_path)
    except Exception as e: return False, str(e)


def inject_claude_code_mcp():
    """Injects ai-memory-hub MCP server configuration into Claude Code CLI (~/.claude.json)."""
    config_path = USER_HOME / ".claude.json"
    if not config_path.exists():
        return False, "קובץ .claude.json לא נמצא"
    python_exe, mcp_args = get_mcp_launch_command()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("mcpServers", {})
        data["mcpServers"]["ai-memory-hub"] = {
            "command": python_exe,
            "args": mcp_args
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True, str(config_path)
    except Exception as e:
        return False, str(e)


def inject_antigravity_knowledge(prompt_text):
    knowledge_dir = USER_HOME / ".gemini" / "antigravity" / "knowledge"
    try:
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        target_file = knowledge_dir / "ai_persistent_memory.md"
        content = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
        target_file.write_text(inject_into_text(content, prompt_text), encoding="utf-8")
        return True, str(target_file)
    except Exception as e: return False, str(e)


def inject_antigravity_mcp():
    mcp_dir = USER_HOME / ".gemini" / "antigravity" / "mcp" / "ai_memory_hub"
    try:
        mcp_dir.mkdir(parents=True, exist_ok=True)
        inst_path = mcp_dir / "instructions.md"
        inst_path.write_text(
            "# AI Memory Hub MCP Server\n"
            "This MCP server provides bidirectional access to the user's persistent memory, rules, constraints and dynamic modes.\n"
            "Use `remember` whenever the user asks to remember a fact or rule.\n"
            "Use `get_active_memory` or `search_memory` to fetch context on demand.\n",
            encoding="utf-8"
        )
        schemas = {
            "get_active_memory.json": {
                "name": "get_active_memory",
                "description": "Retrieves the user's active memories, facts, constraints, and dynamic modes from AI Memory Hub.",
                "parameters": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Optional category filter ('facts', 'commands', 'constraints', 'styles', 'instructions')"}
                    }
                }
            },
            "remember.json": {
                "name": "remember",
                "description": "Proposes a new fact, rule, style or negative constraint into persistent memory for user review and approval.",
                "parameters": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string", "description": "The natural language instruction or fact to remember."},
                        "target_profile": {"type": "string", "description": "Optional target profile ID ('default', 'business', 'code')"}
                    }
                }
            },
            "search_memory.json": {
                "name": "search_memory",
                "description": "Searches user persistent memory and project rules by keyword.",
                "parameters": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string", "description": "Search keyword or query."}
                    }
                }
            },
            "switch_mode.json": {
                "name": "switch_mode",
                "description": "Switches the active conversational mode or workspace profile.",
                "parameters": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "required": ["mode_name"],
                    "properties": {
                        "mode_name": {"type": "string", "description": "Name or ID of the mode to activate."}
                    }
                }
            },
            "check_memory_conflicts.json": {
                "name": "check_memory_conflicts",
                "description": "Checks for logical contradictions or competing facts in user memory.",
                "parameters": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {}
                }
            }
        }
        for s_name, s_content in schemas.items():
            (mcp_dir / s_name).write_text(json.dumps(s_content, ensure_ascii=False, indent=2), encoding="utf-8")
        return True, str(mcp_dir)
    except Exception as e:
        return False, str(e)


@synchronized_db
def inject_all():
    db = load_db()
    sync_mode = db.get("settings", {}).get("syncScopeMode", "macro")
    # sync_mode: "macro" (default, global targets only), "micro" (per-project folders only), "both" (hybrid)

    results = {
        "sync_mode": sync_mode,
        "claude_mcp": False,
        "antigravity": False,
        "folders_synced": 0,
        "total_active_folders": 0,
        "failed_folders": [],
        "global_written": [],
        "global_failed": [],
        "drifted_files": []
    }

    INJECTION_FAILURES.clear()
    INJECTION_DRIFT.clear()

    # 1. MACRO / GLOBAL TARGETS (executed in 'macro' or 'both' mode)
    if sync_mode in ("macro", "both"):
        global_res = inject_global_targets()
        results["global_written"] = global_res["written"]
        results["global_failed"] = global_res["failed"]

        if db.get("settings", {}).get("injectClaudeMcp", True):
            ok1, _ = inject_claude_desktop_mcp()
            ok2, _ = inject_claude_code_mcp()
            results["claude_mcp"] = ok1 or ok2

        if db.get("settings", {}).get("injectAntigravityKnowledge", True):
            anti_prompt = generate_prompt_markdown(target_folder_path=None, target_ai="antigravity")
            ok1, _ = inject_antigravity_knowledge(anti_prompt)
            ok2, _ = inject_antigravity_mcp()
            results["antigravity"] = ok1 and ok2

    # If in macro mode and cleanProjectsOnMacro is True, ensure project folders stay clean
    if sync_mode == "macro":
        if db.get("settings", {}).get("cleanProjectsOnMacro", False):
            clean_all_project_folders(db=db)

    # 2. MICRO / PER-PROJECT FOLDERS (executed in 'micro' or 'both' mode)
    if sync_mode in ("micro", "both"):
        target_paths = db.get("targetPaths", [])
        active_paths = [p for p in target_paths if p.get("active", True)]
        results["total_active_folders"] = len(active_paths)

        for item in active_paths:
            p = item.get("path")
            if p and os.path.isdir(p):
                # inject_rules_into_folder generates specific prompts per AI file and per project!
                ok, hashes = inject_rules_into_folder(p, known_hashes=item.get("injected", {}))

                if hashes:
                    item.setdefault("injected", {}).update(hashes)

                if ok:
                    item["lastSynced"] = datetime.now().isoformat()
                    results["folders_synced"] += 1

        results["failed_folders"] = list(INJECTION_FAILURES)
        results["drifted_files"] = list(INJECTION_DRIFT)

    # 3. Log results based on mode
    if sync_mode == "macro":
        g_count = len(results["global_written"])
        add_log(db, "sync_macro", f"סנכרון מאקרו (גלובלי בלבד): עודכנו {g_count} קבצי AI גלובליים + שרתי MCP (0 קבצים בפרויקטים)")
    elif sync_mode == "micro":
        if results["failed_folders"]:
            add_log(db, "sync_micro_partial",
                    f"סנכרון מיקרו חלקי: {results['folders_synced']} מתוך {results['total_active_folders']} נתיבים "
                    f"({len(results['failed_folders'])} נכשלו)")
        else:
            add_log(db, "sync_micro", f"סנכרון מיקרו (פר פרויקט): {results['folders_synced']} נתיבים עודכנו")
    else:  # "both"
        if results["failed_folders"]:
            add_log(db, "sync_both_partial",
                    f"סנכרון היברידי חלקי: גלובלי + {results['folders_synced']} מתוך {results['total_active_folders']} נתיבים")
        else:
            add_log(db, "sync_both", f"סנכרון היברידי מלא: גלובלי + {results['folders_synced']} נתיבי פרויקט + Claude + Antigravity")

    save_db(db)
    return results


if __name__ == "__main__":
    res = inject_all()
    print(f"Universal AI Memory Hub v5.0 Ultimate - עודכנו {res['folders_synced']} נתיבים.")
