#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal AI Memory Hub v5.0 - Ultimate Desktop GUI (CustomTkinter)
Commercial-grade, feature-rich Windows application.
Includes:
1. 5 Core Directive Categories (Facts, Commands, Constraints, Styles, Instructions).
2. Modern Sidebar Navigation with Profile/Workspace Switcher.
3. Per-Project Scoping (תחולה גלובלית או לפרויקט ספציפי).
4. System Tray integration with pystray.
5. Global Hotkey (Ctrl+Alt+M) triggering Spotlight Quick-Add.
6. Automatic Project Folder Watcher.
7. In-Place Editing, Live Search Filtering, and Full Backup Export/Import.
"""

import os
import sys
import threading
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import memory_hub
import gemini_optimizer
import spotlight
import chat_miner
import updater
import webbrowser
import web_server

# External Tray & Hotkey
try:
    import pystray
except ImportError:
    pystray = None

try:
    import keyboard
except ImportError:
    keyboard = None

# CustomTkinter Theme & Settings Init
try:
    _init_db = memory_hub.load_db()
    _settings = _init_db.get("settings", {})
    _mode = _settings.get("appearanceMode", "light")
    _theme = _settings.get("colorTheme", "blue")
    ctk.set_appearance_mode(_mode)
    ctk.set_default_color_theme(_theme)
except Exception:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

# BiDi & theme hardening for DropdownMenu in CustomTkinter
try:
    from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu
    from customtkinter import ThemeManager
    if "DropdownMenu" in ThemeManager.theme:
        ThemeManager.theme["DropdownMenu"]["fg_color"] = ["#ffffff", "#252526"]
        ThemeManager.theme["DropdownMenu"]["hover_color"] = ["#f0f0f0", "#3e3e42"]
        ThemeManager.theme["DropdownMenu"]["text_color"] = ["#111111", "#cccccc"]

    def _bidi_safe_add_menu_commands(self):
        self.delete(0, "end")
        for value in self._values:
            safe_label = f"\u200F{value}\u200F"
            self.add_command(label=safe_label, command=lambda v=value: self._button_callback(v))
    DropdownMenu._add_menu_commands = _bidi_safe_add_menu_commands

    def _bidi_safe_configure_menu(self):
        super(DropdownMenu, self).configure(
            tearoff=False,
            relief="flat",
            activebackground=self._apply_appearance_mode(self._hover_color),
            borderwidth=self._apply_widget_scaling(1),
            activeborderwidth=self._apply_widget_scaling(1),
            bg=self._apply_appearance_mode(self._fg_color),
            fg=self._apply_appearance_mode(self._text_color),
            activeforeground=self._apply_appearance_mode(self._text_color),
            font=self._apply_font_scaling(self._font),
            cursor="hand2"
        )
    DropdownMenu._configure_menu_for_platforms = _bidi_safe_configure_menu
except Exception:
    pass


# =============================================================================
# PROFESSIONAL ENTERPRISE DESIGN SYSTEM (VS Code / WinUI 3 Style)
# =============================================================================
GLASS_BG_MAIN = ("#F3F3F3", "#1E1E1E")       # Main App Background
GLASS_BG_SIDEBAR = ("#F9F9F9", "#252526")    # Sidebar Background
GLASS_CARD = ("#FFFFFF", "#2D2D30")          # Item Card Background
GLASS_CARD_BORDER = ("#E5E5E5", "#3E3E42")   # Card Border
GLASS_CARD_HOVER = ("#F0F0F0", "#3E3E42")    # Card Hover
GLASS_INPUT = ("#FFFFFF", "#3C3C3C")         # Input Box Background
GLASS_INPUT_BORDER = ("#CCCCCC", "#555555")  # Input Box Border
GLASS_HEADER_BG = ("#FFFFFF", "#2D2D30")     # Header
GLASS_HEADER_BORDER = ("#E5E5E5", "#3E3E42") # Header Border
GLASS_DIVIDER = ("#E5E5E5", "#3E3E42")       # Divider

# Text Colors
TEXT_PRIMARY = ("#111111", "#CCCCCC")        # Primary Text
TEXT_SECONDARY = ("#444444", "#999999")      # Secondary Text
TEXT_MUTED = ("#777777", "#808080")          # Muted Text

# Single Unified Accent (Windows/VS Code Blue)
ACCENT_COLOR = ("#007ACC", "#007ACC")
ACCENT_HOVER = ("#005999", "#005999")


def apply_windows_glass(window):
    """Enables Windows 11 Immersive Dark/Light Mode and Mica/Acrylic backdrop."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        is_dark = ctk.get_appearance_mode().lower() == "dark"
        dark = ctypes.c_int(2 if is_dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        # 3 = Mica backdrop
        backdrop = ctypes.c_int(3)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    except Exception:
        pass


# =============================================================================
# DIRECTIVE PAGE SPECS (טבלת הגדרות עמודי ההנחיות)
#
# Facts, Commands, Constraints, Styles and Instructions are the same page with
# different fields and wording. Everything that differs between them is declared
# here; build_crud_page/refresh_crud_page/on_add_crud_item/on_gemini_optimize in
# AIMemoryHubApp render all five from this table.
#
# Field "key" values MUST match the keys memory_hub writes (see add_info /
# add_command / add_constraint / add_style / add_instruction) and the order must
# match those functions' positional parameters - the generic add handler passes
# the field values positionally.
# =============================================================================
# How long a directive stays in force. A rule with an expiry stops being injected into every
# rule file the moment it lapses (see memory_hub.item_is_expired) - "כללים עם תאריך תפוגה".
EXPIRY_OPTIONS = {
    "קבוע": None,
    "ללא הגבלה": None,
    "שבוע": 7,
    "חודש": 30,
    "3 חודשים": 90,
    "שנה": 365,
}
EXPIRY_DEFAULT = "קבוע"


CRUD_PAGE_SPECS = {
    "facts": {
        "title": "עובדות ונתונים קבועים",
        "subtitle": "עובדות קבועות הנשמרות תמיד בזיכרון המערכת: אתר, פרטי קשר ונתונים קבועים",
        "search_placeholder": "חיפוש בעובדות",
        "search_fields": ["name", "value"],
        "count_text": "עובדות: {active} פעילות (מתוך {total})",
        "empty_text": "אין עובדות להצגה.",
        "fields": [
            {"key": "name", "label": "שם המידע / מפתח", "placeholder": "האתר שלי, טלפון או כתובת", "gemini_label": "שם"},
            {"key": "value", "label": "ערך / תוכן", "placeholder": "https://example.com או נתון קבוע", "gemini_label": "ערך"},
        ],
        "required": ["name", "value"],
        "missing_title": "שדות חסרים",
        "missing_msg": "נא להזין שם וערך לעובדה.",
        "add_fn": "add_info",
        "added_status": "נוספה עובדה: {first}",
        "optimize_fn": "optimize_info",
        "gemini_min_fields": ["name", "value"],
        "gemini_empty_title": "הזן מידע",
        "gemini_empty_msg": "נא להקליד לפחות שם או ערך.",
        "gemini_status": "Gemini מנתח ומחדד את המידע...",
        "gemini_done_status": "השדות עודכנו בהצלחה!",
        "card": {"variant": "detailed", "title_field": "name", "body_field": "value"},
    },

    "commands": {
        "title": "⚡ פקודות ביצוע וכללי התנהגות",
        "subtitle": "פקודות המופעלות אוטומטית במקרים מוגדרים: חתימה בסיום, תבניות מענה ועוד",
        "search_placeholder": "חיפוש בפקודות",
        "search_fields": ["name", "details"],
        "count_text": "פקודות: {active} פעילות (מתוך {total})",
        "empty_text": "אין פקודות להצגה.",
        "fields": [
            {"key": "name", "label": "שם פקודה", "placeholder": "חתימה אישית בסיום", "gemini_label": "שם"},
            {"key": "details", "label": "פירוט הפעולה / תוכן", "placeholder": "לצרף בסיום מענה בברכה ושם", "gemini_label": "פירוט"},
            {"key": "trigger_case", "label": "באיזה מקרה לבצע", "placeholder": "בסיום מענה למיילים או פונקציות", "gemini_label": "מקרה"},
        ],
        "required": ["name", "details"],
        "missing_title": "שדות חסרים",
        "missing_msg": "נא להזין לפחות שם פקודה ופירוט.",
        "add_fn": "add_command",
        "added_status": "נוספה פקודה: {first}",
        "optimize_fn": "optimize_command",
        "gemini_min_fields": ["name", "details"],
        "gemini_empty_title": "הזן פקודה",
        "gemini_empty_msg": "נא להקליד פרטים.",
        "gemini_status": "Gemini מנסח פקודה אימפרטיבית...",
        "gemini_done_status": "שדות הפקודה עודכנו!",
        "card": {
            "variant": "compact",
            "title_field": "name",
            "accent": "amber",
            "type_badge": "פקודת ביצוע",
            "lines": [
                {"field": "name", "prefix": "⚡ ", "size": 13, "weight": "bold", "color": "primary", "always": True},
                {"field": "details", "prefix": "פעולה: ", "size": 12, "color": "secondary", "wrap": 500, "always": True},
                {"field": "trigger_case", "prefix": "מקרה: ", "size": 11, "color": "primary", "wrap": 500, "always": True},
            ],
        },
    },

    "constraints": {
        "title": "מגבלות ואיסורים",
        "subtitle": "איסורים מחמירים: מה שאסור לעשות בשום מקרה (הגנת קוד קיים, מניעת מחיקת הערות)",
        "search_placeholder": "חיפוש באיסורים",
        "search_fields": ["constraint"],
        "count_text": "איסורים: {active} פעילים (מתוך {total})",
        "empty_text": "אין איסורים להצגה.",
        "fields": [
            {"key": "constraint", "label": "האיסור המחייב", "placeholder": "לעולם אל תמחק הערות קוד או תיעוד", "gemini_label": "איסור"},
            {"key": "alternative_or_why", "label": "הנחיה חלופית או נימוק", "placeholder": "שמור על כל התיעוד הקיים והוסף עליו", "gemini_label": "חלופה"},
        ],
        "required": ["constraint"],
        "missing_title": "שדה חסר",
        "missing_msg": "נא להזין את תוכן האיסור.",
        "add_fn": "add_constraint",
        "added_status": "מגבלה חדשה נוספה והושתלה",
        "optimize_fn": "optimize_constraint",
        "gemini_min_fields": ["constraint"],
        "gemini_empty_title": "הזן איסור",
        "gemini_empty_msg": "נא להקליד פרטים.",
        "gemini_status": "Gemini מנסח איסור מחמיר...",
        "gemini_done_status": "שדות האיסור עודכנו!",
        "card": {
            "variant": "compact",
            "title_field": "constraint",
            "accent": "rose",
            "type_badge": "איסור מחייב",
            "lines": [
                {"field": "constraint", "size": 13, "weight": "bold", "color": "secondary", "wrap": 500, "always": True},
                {"field": "alternative_or_why", "prefix": "חלופה: ", "size": 11, "color": "secondary", "wrap": 500},
            ],
        },
    },

    "styles": {
        "title": "סגנון מענה ושפה",
        "subtitle": "הגדרות אופי הדיאלוג: עברית רהוטה וברורה, רמת תמצות, ישירות ומקצועיות",
        "search_placeholder": "חיפוש בסגנון",
        "search_fields": ["aspect", "instruction"],
        "count_text": "כללי סגנון: {active} פעילים (מתוך {total})",
        "empty_text": "אין כללי סגנון להצגה.",
        "fields": [
            {"key": "aspect", "label": "היבט הסגנון", "placeholder": "שפה וסגנון מענה", "gemini_label": "היבט"},
            {"key": "instruction", "label": "הנחיית הסגנון", "placeholder": "עברית רהוטה ונקייה ללא תרגום מכונה", "gemini_label": "הנחיה"},
        ],
        "required": ["aspect", "instruction"],
        "missing_title": "שדות חסרים",
        "missing_msg": "נא להזין היבט סגנון והנחיה.",
        "add_fn": "add_style",
        "added_status": "כלל סגנון נוסף: {first}",
        "optimize_fn": "optimize_style",
        "gemini_min_fields": ["aspect", "instruction"],
        "gemini_empty_title": "הזן פרטים",
        "gemini_empty_msg": "נא להקליד פרטים.",
        "gemini_status": "Gemini מנסח כלל סגנון מדויק...",
        "gemini_done_status": "שדות הסגנון עודכנו!",
        "card": {"variant": "detailed", "title_field": "aspect", "body_field": "instruction"},
    },

    "instructions": {
        "title": " הוראות מותנות והנחיות פרטיות",
        "subtitle": "הנחיות הפועלות רק במצבים מוגדרים: הוראה ספציפית ומתי בדיוק ליישם אותה",
        "search_placeholder": "חיפוש בהוראות",
        "search_fields": ["instruction"],
        "count_text": "הוראות: {active} פעילים (מתוך {total})",
        "empty_text": "אין הוראות להצגה.",
        "fields": [
            {"key": "instruction", "label": "הוראה / הנחיה", "placeholder": "הסבר כל צעד בצורה מסודרת", "gemini_label": "הוראה"},
            {"key": "when_to_apply", "label": "מתי ליישם (אופציונלי)", "placeholder": "בכל שיחה ומענה", "gemini_label": "מתי"},
        ],
        "required": ["instruction"],
        "missing_title": "שדה חסר",
        "missing_msg": "נא להזין את תוכן ההוראה.",
        "add_fn": "add_instruction",
        "added_status": "הוראה מותנית נוספה והושתלה",
        "optimize_fn": "optimize_instruction",
        "gemini_min_fields": ["instruction"],
        "gemini_empty_title": "הזן הוראה",
        "gemini_empty_msg": "נא להקליד פרטים.",
        "gemini_status": "Gemini מנסח הוראה מחייבת...",
        "gemini_done_status": "שדות ההוראה עודכנו!",
        "card": {
            "variant": "compact",
            "title_field": "instruction",
            "accent": "emerald",
            "type_badge": "הנחיה מותנית",
            "lines": [
                {"field": "instruction", "prefix": " ", "size": 13, "weight": "bold", "color": "primary", "wrap": 500, "always": True},
                {"field": "when_to_apply", "prefix": "מתי: ", "size": 11, "color": "secondary", "wrap": 500, "default": "תמיד", "always": True},
            ],
        },
    },
}


class AIMemoryHubApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.configure(fg_color=GLASS_BG_MAIN)
        apply_windows_glass(self)

        self.title("Universal AI Memory Hub v1.0.1 Enterprise - ניהול זיכרון אוטומטי למודלים")
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
        ico_file = os.path.join(base_dir, "app_icon.ico")
        if os.path.exists(ico_file):
            try:
                self.iconbitmap(ico_file)
            except Exception:
                pass
        self.geometry("1200x820")
        self.minsize(1060, 720)

        # Main Layout: Right Sidebar (Nav) + Left Main Content
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)  # Main Content (Left)
        self.grid_columnconfigure(1, weight=0)  # Sidebar (Right)

        self.current_page = "facts"
        self.pages = {}
        # Per-category widget registry for the directive pages built from CRUD_PAGE_SPECS
        # (entries / scope / ai / search / count / scroll / gemini_btn).
        self.crud_widgets = {}
        self.tray_icon = None

        # Build UI
        self.create_sidebar()
        self.create_main_content()
        self.create_statusbar()

        # Window Close Event (Minimize to Tray)
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # Show initial page
        self.show_page("chat_memory")
        self.refresh_all_views()

        # Start Services: Tray, Hotkey, and Folder Watcher
        self.init_system_tray()
        self.init_global_hotkey()
        self.init_folder_watcher()
        self.init_web_dashboard()
        self.after(300, self.prune_invalid_paths_on_startup)
        self.after(900, self.sweep_expired_rules)
        self.after(1500, self.schedule_auto_profile_checks)
        self.after(600, self.warn_if_database_unreadable)
        self.after(1200, self.check_startup_updates)

    # =========================================================================
    # SIDEBAR NAVIGATION (Right Column)
    # =========================================================================
    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=270, corner_radius=0, fg_color=GLASS_BG_SIDEBAR, border_width=1, border_color=GLASS_CARD_BORDER)
        self.sidebar.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_propagate(False)

        # App Brand Header Card (Clean Minimalist Professional)
        brand = ctk.CTkFrame(self.sidebar, corner_radius=12, fg_color=GLASS_CARD, border_width=1, border_color=GLASS_CARD_BORDER)
        brand.pack(fill="x", padx=12, pady=(14, 10))

        ctk.CTkLabel(
            brand,
            text="Universal AI Memory Hub",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="e", padx=14, pady=(10, 0))

        ctk.CTkLabel(
            brand,
            text="מערכת ניהול זיכרון מרכזית (v1.0.1)",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_MUTED
        ).pack(anchor="e", padx=14, pady=(2, 10))

        # Workspace / Profile Switcher Box (Frosted Glass)
        profile_box = ctk.CTkFrame(self.sidebar, corner_radius=12, fg_color=GLASS_CARD, border_width=1, border_color=GLASS_CARD_BORDER)
        profile_box.pack(fill="x", padx=12, pady=(0, 10))

        p_header = ctk.CTkFrame(profile_box, fg_color="transparent")
        p_header.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            p_header,
            text="סביבת עבודה",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="right")

        btn_new_prof = ctk.CTkButton(
            p_header,
            text="+ חדש",
            width=50,
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=("#111c30", "#1e3a8a"),
            border_width=1,
            border_color=("#1e3052", "#3b82f6"),
            text_color="#ffffff",
            hover_color=("#1e3a8a", "#2563eb"),
            corner_radius=6,
            command=self.on_create_profile_dialog
        )
        btn_new_prof.pack(side="left")

        profiles = memory_hub.get_profiles()
        profile_names = [v["name"] for v in profiles.values()]
        cur_id = memory_hub.get_current_profile_id()
        cur_name = profiles.get(cur_id, {}).get("name", "ראשי (כללי)")

        self.combo_profile = ctk.CTkComboBox(
            profile_box,
            values=profile_names if profile_names else ["ראשי (כללי)"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=30,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            command=self.on_profile_selected
        )
        self.combo_profile.set(cur_name)
        self.combo_profile.pack(fill="x", padx=10, pady=(0, 6))

        btn_triggers = ctk.CTkButton(
            profile_box,
            text="מילות הפעלה למצב זה",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            height=24,
            corner_radius=6,
            fg_color="transparent",
            border_width=1,
            border_color=GLASS_CARD_BORDER,
            text_color=TEXT_SECONDARY,
            hover_color=GLASS_CARD_HOVER,
            command=self.open_profile_triggers_dialog
        )
        btn_triggers.pack(fill="x", padx=10, pady=(0, 8))

        self.btn_web_dashboard = ctk.CTkButton(
            self.sidebar,
            text="פתח לוח בקרה מודרני בדפדפן 🌐",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=34,
            corner_radius=8,
            fg_color="#0284c7",
            border_width=1,
            border_color="#0369a1",
            text_color="#ffffff",
            hover_color="#0369a1",
            command=self.open_web_dashboard
        )
        self.btn_web_dashboard.pack(fill="x", padx=12, pady=(0, 6))

        # Prominent GitHub Auto-Update Button in Sidebar
        self.btn_sidebar_update = ctk.CTkButton(
            self.sidebar,
            text="סנכרון ועדכון גרסה מהענן",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=32,
            corner_radius=8,
            fg_color=ACCENT_COLOR,
            border_width=1,
            border_color=("#3b82f6", "#2563eb"),
            text_color="#ffffff",
            hover_color=ACCENT_HOVER,
            command=self.on_check_updates_manual
        )
        self.btn_sidebar_update.pack(fill="x", padx=12, pady=(0, 10))

        # Nav Buttons Container
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=8, pady=2)

        self.nav_buttons = {}
        nav_items = [
            ("chat_memory", "שיחה וניהול חופשי", "#2563eb"),
            ("facts", "עובדות ונתונים", "#2563eb"),
            ("commands", "פקודות ופעולות", "#2563eb"),
            ("constraints", "מגבלות ואיסורים", "#2563eb"),
            ("styles", "סגנון וטון מענה", "#2563eb"),
            ("instructions", "הנחיות מותנות", "#2563eb"),
            ("context_files", "מסמכים והקשר", "#2563eb"),
            ("chat_miner", "כריית שיחות ותובנות", "#2563eb"),
            ("simulator", "סימולטור מענה חי", "#2563eb"),
            ("paths", "נתיבי פרויקטים", "#2563eb"),
            ("preview", "תצוגה מקדימה", "#2563eb"),
            ("settings", "הגדרות מערכת", "#2563eb")
        ]

        for page_key, label_text, color in nav_items:
            btn = ctk.CTkButton(
                self.nav_frame,
                text=label_text,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                anchor="e",
                height=32,
                corner_radius=8,
                fg_color="transparent",
                text_color=TEXT_MUTED,
                hover_color=GLASS_CARD_HOVER,
                command=lambda pk=page_key: self.show_page(pk)
            )
            btn.pack(fill="x", pady=1)
            self.nav_buttons[page_key] = btn

        # Bottom Sidebar: AI Sanity Check + Spotlight + Stats + Sync Now
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=12, pady=8)

        # Professional Action Buttons
        btn_sanity = ctk.CTkButton(
            bottom,
            text="בדיקת תקינות וסתירות",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            border_width=1,
            border_color=GLASS_CARD_BORDER,
            text_color=TEXT_PRIMARY,
            hover_color=GLASS_CARD_HOVER,
            height=30,
            corner_radius=8,
            command=self.open_sanity_check_dialog
        )
        btn_sanity.pack(fill="x", pady=(0, 4))

        btn_spotlight = ctk.CTkButton(
            bottom,
            text="הוספה מהירה - מקש קיצור",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="transparent",
            border_width=1,
            border_color=GLASS_CARD_BORDER,
            text_color=TEXT_PRIMARY,
            hover_color=GLASS_CARD_HOVER,
            height=30,
            corner_radius=8,
            command=self.open_spotlight
        )
        btn_spotlight.pack(fill="x", pady=(0, 4))

        self.lbl_sidebar_stats = ctk.CTkLabel(
            bottom,
            text="טוען...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED
        )
        self.lbl_sidebar_stats.pack(anchor="e", pady=(0, 4))

        self.btn_sidebar_sync = ctk.CTkButton(
            bottom,
            text="סנכרן את כל הפרויקטים",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            height=34,
            corner_radius=8,
            command=self.on_sync_all_click
        )
        self.btn_sidebar_sync.pack(fill="x")

    def on_profile_selected(self, selected_name):
        profiles = memory_hub.get_profiles()
        for p_id, p_info in profiles.items():
            if p_info.get("name") == selected_name:
                memory_hub.set_current_profile(p_id)
                self.refresh_all_views()
                self.set_status(f"הוחלף פרופיל פעיל ל: {selected_name}")
                break

    def on_create_profile_dialog(self):
        dialog = ctk.CTkInputDialog(text="הזן שם עבור סביבת העבודה החדשה", title="יצירת פרופיל חדש")
        name = dialog.get_input()
        if name and name.strip():
            p_id = f"prof_{int(os.times().system*1000)}_{name.strip()[:6]}"
            ok, p_info = memory_hub.add_profile(p_id, name.strip())
            if ok:
                memory_hub.set_current_profile(p_id)
                self.update_profiles_combo()
                self.refresh_all_views()
                self.set_status(f"נוצר פרופיל חדש: {name}")

    def update_profiles_combo(self):
        profiles = memory_hub.get_profiles()
        names = [v["name"] for v in profiles.values()]
        cur_id = memory_hub.get_current_profile_id()
        cur_name = profiles.get(cur_id, {}).get("name", "ראשי (כללי)")
        self.combo_profile.configure(values=names)
        self.combo_profile.set(cur_name)

    def open_profile_triggers_dialog(self):
        cur_id = memory_hub.get_current_profile_id()
        profiles = memory_hub.get_profiles()
        p_info = profiles.get(cur_id, {})
        cur_name = p_info.get("name", "ראשי (כללי)")
        triggers, desc, inject_mode = memory_hub.get_profile_triggers(cur_id)

        diag = ctk.CTkToplevel(self)
        diag.title(f"הגדרת מצב שיחה וטריגרים: {cur_name}")
        diag.geometry("480x400")
        diag.attributes("-topmost", True)

        ctk.CTkLabel(
            diag,
            text=f"הגדרת מילות הפעלה למצב: {cur_name}",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            diag,
            text="כאשר נאמרת אחת ממילות ההפעלה (למשל 'זה לעסקים'), המערכת תפעיל אוטומטית את כללי המצב הזה:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED,
            wraplength=420,
            justify="right"
        ).pack(pady=(0, 14), padx=20)

        f_inputs = ctk.CTkFrame(diag, fg_color="transparent")
        f_inputs.pack(fill="x", padx=24)

        ctk.CTkLabel(f_inputs, text="מילות הפעלה מופרדות בפסיקים", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e")
        ent_triggers = ctk.CTkEntry(f_inputs, height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
        ent_triggers.pack(fill="x", pady=(2, 10))
        ent_triggers.insert(0, ", ".join(triggers) if triggers else "")

        ctk.CTkLabel(f_inputs, text="תיאור המצב מתי להפעיל פרופיל זה", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e")
        ent_desc = ctk.CTkEntry(f_inputs, height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
        ent_desc.pack(fill="x", pady=(2, 12))
        ent_desc.insert(0, desc if desc else "")

        chk_var = ctk.BooleanVar(value=inject_mode)
        chk_inject = ctk.CTkCheckBox(
            f_inputs,
            text="החל כמצב שיחה דינמי אוטומטי לתוך הנחיות הזיכרון (מומלץ)",
            variable=chk_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_PRIMARY
        )
        chk_inject.pack(anchor="e", pady=(0, 16))

        def on_save():
            new_triggers = [t.strip() for t in ent_triggers.get().split(",") if t.strip()]
            new_desc = ent_desc.get().strip()
            new_inject = chk_var.get()
            memory_hub.set_profile_triggers(cur_id, new_triggers, new_desc, new_inject)
            diag.destroy()
            self.refresh_all_views()
            self.set_status(f"עודכנו מילות הפעלה למצב: {cur_name}")

        btn_row = ctk.CTkFrame(diag, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(10, 16))

        ctk.CTkButton(btn_row, text="שמור וסנכרן לכל המודלים", width=140, height=34, corner_radius=8, fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), command=on_save).pack(side="right")
        ctk.CTkButton(btn_row, text="ביטול", width=90, height=34, corner_radius=8, fg_color="#475569", hover_color="#334155", text_color="#ffffff", command=diag.destroy).pack(side="left")

    # =========================================================================
    # MAIN CONTENT CONTAINER (Left Column)
    # =========================================================================
    def create_main_content(self):
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color=GLASS_BG_MAIN)
        self.main_container.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.build_page_chat_memory()
        self.build_page_facts()
        self.build_page_commands()
        self.build_page_constraints()
        self.build_page_styles()
        self.build_page_instructions()
        self.build_page_context_files()
        self.build_page_chat_miner()
        self.build_page_simulator()
        self.build_page_paths()
        self.build_page_preview()
        self.build_page_settings()

    # =========================================================================
    # 0. PAGE: CHAT MEMORY (שיחה חופשית וניהול זיכרון אינטליגנטי)
    # =========================================================================
    def build_page_chat_memory(self):
        p = self.pages["chat_memory"] = ctk.CTkFrame(self.main_container, fg_color="transparent")

        self.create_page_header(
            p,
            "שיחה חופשית וניהול זיכרון",
            "שיחה ישירה בעברית חופשית: המערכת מסווגת אוטומטית לקטגוריה, בודקת סתירות ומעדכנת את הזיכרון."
        )

        # Conflict alert container (packed dynamically only when active conflicts exist)
        self.chat_conflict_container = ctk.CTkFrame(p, fg_color="transparent", height=0)

        # Chat Input Box (The Conversational Brain)
        input_card = self.create_glass_card(p, corner_radius=8)
        self.chat_input_card = input_card
        input_card.pack(fill="x", pady=(0, 10))

        lbl_hint = ctk.CTkLabel(
            input_card,
            text="הקלד כאן כל עובדה, איסור, חתימה או סגנון לזיכרון הקבוע",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        lbl_hint.pack(anchor="e", padx=16, pady=(10, 6))

        input_row = ctk.CTkFrame(input_card, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(0, 10))

        self.chat_input_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="למשל: האתר שלי הוא example.com, או: בסיום מענה חתום תמיד בברכה",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=38,
            corner_radius=6,
            border_color=GLASS_INPUT_BORDER,
            justify="right"
        )
        self.chat_input_entry.pack(side="right", fill="x", expand=True, padx=(8, 0))
        self.chat_input_entry.bind("<Return>", lambda e: self.on_chat_memory_submit())

        btn_submit = ctk.CTkButton(
            input_row,
            text="שמור בזיכרון",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=38,
            width=150,
            corner_radius=6,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#ffffff",
            command=self.on_chat_memory_submit
        )
        btn_submit.pack(side="left")

        # Quick Example Chips
        chips_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        chips_frame.pack(fill="x", padx=16, pady=(0, 10))

        examples = [
            ("עובדה", "האתר שלי הוא https://example.com"),
            ("איסור", "לעולם אל תמחק הערות קוד או תיעוד קיים"),
            ("מצב עסקי", "זה לעסקים: תצרף תמיד בסיום מענה 'בברכה, הצוות'"),
            ("מצב קוד", "הקפד על פונקציות נקיות וטיפוסים מדויקים")
        ]

        for tag, ex_text in reversed(examples):
            b_chip = ctk.CTkButton(
                chips_frame,
                text=f"[{tag}] {ex_text[:28]}...",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                height=22,
                corner_radius=4,
                fg_color="transparent",
                border_width=1,
                border_color=GLASS_CARD_BORDER,
                text_color=TEXT_MUTED,
                hover_color=GLASS_CARD_HOVER,
                command=lambda t=ex_text: self.set_chat_input_text(t)
            )
            b_chip.pack(side="right", padx=(0, 6))

        # Recent entries / memory logs
        header_row = ctk.CTkFrame(p, fg_color="transparent")
        header_row.pack(fill="x", pady=(4, 4))
        ctk.CTkLabel(
            header_row,
            text="זיכרונות, כללים ופעולות שנלמדו משיחות קודמות",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="right")

        self.chat_history_scroll = ctk.CTkScrollableFrame(p, corner_radius=8, fg_color=GLASS_BG_MAIN)
        self.chat_history_scroll.pack(fill="both", expand=True, pady=(0, 4))

    def set_chat_input_text(self, text):
        self.chat_input_entry.delete(0, "end")
        self.chat_input_entry.insert(0, text)

    def on_chat_memory_submit(self):
        text = self.chat_input_entry.get().strip()
        if not text:
            return

        ok, parsed, conflicts, msg = memory_hub.add_conversational_memory(text)
        self.chat_input_entry.delete(0, "end")
        self.refresh_all_views()

        if ok:
            cat_hebrew = {
                "facts": "עובדה ומידע קבוע",
                "constraints": "מגבלה ואיסור חמור",
                "styles": "סגנון וטון מענה",
                "commands": "פקודת ביצוע / חתימה",
                "instructions": "הנחיה מותנית"
            }.get(parsed["category"], parsed["category"])
            prof = parsed.get("target_profile") or "default"
            status_text = f"נלמד בהצלחה! סווג כ-{cat_hebrew} בפרופיל '{prof}'"
            if conflicts:
                status_text += f" | שים לב: זוהו {len(conflicts)} סתירות!"
            self.set_status(status_text)
        else:
            self.set_status(f"שגיאה בניתוח: {msg}")

    def refresh_page_chat_memory(self):
        if not hasattr(self, "chat_history_scroll"):
            return

        # 1. Update Conflict Banner
        for w in self.chat_conflict_container.winfo_children():
            w.destroy()

        conflicts = memory_hub.detect_conflicts()
        if conflicts:
            if hasattr(self, "chat_input_card"):
                self.chat_conflict_container.pack(fill="x", pady=(0, 6), before=self.chat_input_card)
            else:
                self.chat_conflict_container.pack(fill="x", pady=(0, 6))
            is_light = ctk.get_appearance_mode().lower() == "light"
            bg = "#FEF2F2" if is_light else "#450A0A"
            border = "#EF4444"
            ban = ctk.CTkFrame(self.chat_conflict_container, fg_color=bg, border_width=1, border_color=border, corner_radius=6)
            ban.pack(fill="x", pady=(0, 4))

            c_info = conflicts[0]
            ctk.CTkLabel(ban, text=f"⚠️ {c_info.get('title')}: {c_info.get('description')}", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#DC2626", justify="right").pack(side="right", padx=12, pady=6)
            btn_res = ctk.CTkButton(ban, text="בדוק ופתור סתירות", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), height=24, width=120, corner_radius=4, fg_color="#DC2626", hover_color="#B91C1C", text_color="#FFFFFF", command=self.open_sanity_check_dialog)
            btn_res.pack(side="left", padx=10, pady=6)
        else:
            self.chat_conflict_container.pack_forget()

        # 2. Populate scroll with recent items from all categories
        for w in self.chat_history_scroll.winfo_children():
            w.destroy()

        db = memory_hub.load_db()
        cur_id = db.get("currentProfile", "default")
        p_data = db.get("profiles", {}).get(cur_id, {}).get("data", {})

        all_items = []
        cat_labels = {
            "facts": ("עובדה", "#007ACC"),
            "constraints": ("איסור", "#DC2626"),
            "styles": ("סגנון", "#10B981"),
            "commands": ("פקודה", "#F59E0B"),
            "instructions": ("הנחיה", "#6366F1")
        }

        for cat, (lbl, color) in cat_labels.items():
            for it in p_data.get(cat, []):
                all_items.append((cat, lbl, color, it))

        if not all_items:
            ctk.CTkLabel(self.chat_history_scroll, text="אין עדיין זיכרונות בפרופיל זה. נסה להקליד משהו למעלה!", font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_MUTED).pack(pady=30)
            return

        for cat, lbl, color, item in all_items[:25]:
            row = self.create_glass_card(self.chat_history_scroll, corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)

            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.pack(side="left", padx=8, pady=6)

            btn_del = self.create_card_action_button(actions, "מחק", lambda c=cat, i_id=item.get("id"): self.on_del_item(c, i_id, "פריט"), "del", 40, 24)
            btn_del.pack(side="left", padx=2)

            btn_edit = self.create_card_action_button(actions, "ערוך", lambda c=cat, it=item: self.open_edit_dialog(c, it), "edit", 40, 24)
            btn_edit.pack(side="left", padx=2)

            badge = self.create_glass_badge(actions, lbl, "default")
            badge.pack(side="left", padx=(4, 0))

            content_f = ctk.CTkFrame(row, fg_color="transparent")
            content_f.pack(side="right", fill="both", expand=True, padx=8, pady=6)

            main_text = item.get("name") or item.get("constraint") or item.get("aspect") or item.get("instruction") or ""
            sub_text = item.get("value") or item.get("alternative_or_why") or item.get("details") or item.get("when_to_apply") or ""

            ctk.CTkLabel(content_f, text=main_text, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e")
            if sub_text and sub_text != main_text:
                ctk.CTkLabel(content_f, text=sub_text, font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY).pack(anchor="e")

    def on_reorder_item(self, category, item_id, direction):
        ok, msg = memory_hub.reorder_item(category, item_id, direction)
        if ok:
            self.refresh_all_views()
            self.set_status(f"סדר החוקים שונה בהצלחה ({direction})")
        else:
            self.set_status(msg)

    def show_page(self, page_key):
        self.current_page = page_key
        for k, page in self.pages.items():
            if k == page_key:
                page.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
            else:
                page.grid_forget()

        is_light = ctk.get_appearance_mode().lower() == "light"
        for k, btn in self.nav_buttons.items():
            if k == page_key:
                if is_light:
                    btn.configure(fg_color="#eff6ff", border_width=1, border_color=ACCENT_COLOR, text_color=TEXT_PRIMARY)
                else:
                    btn.configure(fg_color="#121e38", border_width=1, border_color="#2563eb", text_color=TEXT_PRIMARY)
            else:
                btn.configure(fg_color="transparent", border_width=0, text_color=("#475569" if is_light else "#94a3b8"))

    # Scope Dropdown Helper
    def get_scope_options(self):
        return ["גלובלי"] + [p.get("name") for p in memory_hub.get_paths()]

    # AI Target Options Helpers
    def get_ai_target_options(self):
        return [
            "כל המודלים",
            "Google Antigravity",
            "Claude Desktop",
            "Cursor",
            "Windsurf",
            "GitHub Copilot",
            "התאמה אישית..."
        ]

    def parse_ai_target_option(self, opt_str, fallback=None):
        if not opt_str or "כל המודלים" in opt_str or "לכולם" in opt_str or "כל מודלי" in opt_str:
            return ["all"]
        elif "Antigravity" in opt_str:
            return ["antigravity"]
        elif "Claude" in opt_str:
            return ["claude"]
        elif "Cursor" in opt_str:
            return ["cursor"]
        elif "Windsurf" in opt_str:
            return ["windsurf"]
        elif "Copilot" in opt_str:
            return ["copilot"]
        elif isinstance(opt_str, list):
            return opt_str
        return fallback or ["all"]

    def format_ai_target_badge(self, item):
        target_ais = item.get("target_ais", ["all"])
        if not target_ais or target_ais == ["all"] or target_ais == "all":
            return "לכל המודלים"
        if isinstance(target_ais, str):
            target_ais = [target_ais]
        mapping = {
            "antigravity": "Antigravity",
            "claude": "Claude",
            "cursor": "Cursor",
            "windsurf": "Windsurf",
            "copilot": "Copilot",
            "cline": "Cline"
        }
        names = [mapping[a] for a in target_ais if a in mapping]
        return f"{', '.join(names)}" if names else "לכל המודלים"

    def run_async(self, work_fn, on_error=None):
        """
        Runs work_fn on a daemon thread with uniform error handling.

        Replaces the hand-copied `self.run_async(worker)`
        pattern: previously an exception inside a worker vanished silently and left the
        triggering button disabled forever, with no trace anywhere.
        """
        def runner():
            try:
                work_fn()
            except Exception as e:
                print(f"[run_async] background task failed: {e}")
                try:
                    if on_error:
                        self.after(0, lambda err=e: on_error(err))
                    else:
                        self.after(0, lambda err=e: self.set_status(f"הפעולה ברקע נכשלה: {err}"))
                except Exception:
                    pass

        threading.Thread(target=runner, daemon=True).start()

    def format_expiry_badge(self, item):
        """
        (text, color) for a rule that carries an expiry, else None.
        An expired rule stays visible in the list - it just stops being injected - so the
        badge is what tells the user why an AI no longer sees it.
        """
        raw = item.get("expiresAt")
        if not raw:
            return None
        try:
            expires = datetime.fromisoformat(str(raw))
        except Exception:
            return None

        days_left = (expires - datetime.now()).days
        if expires <= datetime.now():
            return (f"פג בתאריך {expires.strftime('%d.%m.%y')}", "rose")
        if days_left <= 7:
            return (f"פג בעוד {max(days_left, 0)} ימים", "amber")
        return (f"בתוקף עד {expires.strftime('%d.%m.%y')}", "default")

    def resolve_expiry(self, combo_widget):
        """Turns the expiry selection into an ISO timestamp, or None for 'no limit'."""
        if combo_widget is None:
            return None
        days = EXPIRY_OPTIONS.get(combo_widget.get())
        if not days:
            return None
        return (datetime.now() + timedelta(days=days)).isoformat()

    def resolve_target_ais(self, combo_widget, fallback=None):
        """
        Returns the AI targets chosen in a combo box: either the explicit multi-select
        stored by the custom-targets dialog, or the parsed single selection.
        """
        if hasattr(combo_widget, "_custom_selection"):
            return combo_widget._custom_selection
        return self.parse_ai_target_option(combo_widget.get(), fallback=fallback)

    def check_custom_ai_selection(self, selected_val, combo_widget):
        if "מותאמת" in selected_val or "התאמה" in selected_val:
            def on_confirm(custom_list):
                if custom_list == ["all"]:
                    combo_widget.set("כל המודלים")
                else:
                    mapping = {"antigravity": "Antigravity", "claude": "Claude", "cursor": "Cursor", "windsurf": "Windsurf", "copilot": "Copilot", "cline": "Cline"}
                    display_str = ", ".join([mapping.get(k, k) for k in custom_list])
                    combo_widget.set(f"מותאם: {display_str}")
                    combo_widget._custom_selection = custom_list

            self.open_custom_ai_targets_dialog(["all"], on_confirm)

    def open_custom_ai_targets_dialog(self, current_selection, on_confirm_callback):
        diag = ctk.CTkToplevel(self)
        diag.title("בחירת מודלי יעד מותאמים אישית")
        diag.geometry("420x390")
        diag.attributes("-topmost", True)
        diag.configure(fg_color=GLASS_BG_MAIN)

        ctk.CTkLabel(diag, text="בחר לאילו מודלים הכלל יוזרק", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color=TEXT_PRIMARY).pack(pady=(16, 12))

        ai_defs = [
            ("antigravity", "Google Antigravity (GEMINI.md)"),
            ("claude", "Claude Desktop / Code (CLAUDE.md)"),
            ("cursor", "Cursor AI (.cursorrules)"),
            ("windsurf", "Windsurf (.windsurfrules)"),
            ("copilot", "GitHub Copilot (copilot-instructions.md)"),
            ("cline", "Cline / Roo Code (.clinerules)")
        ]

        chk_vars = {}
        for key, title in ai_defs:
            is_checked = ("all" in current_selection) or (key in current_selection)
            v = ctk.BooleanVar(value=is_checked)
            chk_vars[key] = v
            chk = ctk.CTkCheckBox(diag, text=title, variable=v, font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_PRIMARY)
            chk.pack(anchor="e", padx=30, pady=4)

        def on_save():
            selected = [k for k, v in chk_vars.items() if v.get()]
            if len(selected) == len(ai_defs) or len(selected) == 0:
                final_res = ["all"]
            else:
                final_res = selected
            on_confirm_callback(final_res)
            diag.destroy()

        btn_row = ctk.CTkFrame(diag, fg_color="transparent")
        btn_row.pack(fill="x", padx=30, pady=(20, 10))

        ctk.CTkButton(btn_row, text="אישור", width=100, fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff", command=on_save).pack(side="right")
        ctk.CTkButton(btn_row, text="ביטול", width=80, fg_color=("#E5E5E5", "#334155"), hover_color=("#D5D5D5", "#475569"), text_color=TEXT_PRIMARY, command=diag.destroy).pack(side="left")

    # =========================================================================
    # GLASSMORPHISM UI HELPERS
    # =========================================================================
    def create_glass_card(self, parent, corner_radius=12, border_color=GLASS_CARD_BORDER, fg_color=GLASS_CARD):
        return ctk.CTkFrame(
            parent,
            corner_radius=corner_radius,
            fg_color=fg_color,
            border_width=1,
            border_color=border_color
        )

    def create_card_action_button(self, parent, text, cmd, btn_type="default", width=28, height=28):
        is_light = ctk.get_appearance_mode().lower() == "light"
        if btn_type == "del":
            fg = "#FFEDED" if is_light else "#4A1B1B"
            border = "#FFD6D6" if is_light else "#662222"
            hover = "#FFD6D6" if is_light else "#5A2020"
            tc = "#D32F2F" if is_light else "#FF6B6B"
        elif btn_type == "edit" or btn_type == "gemini":
            fg = "#F0F8FF" if is_light else "#1E3040"
            border = "#D0E8FF" if is_light else "#2A4050"
            hover = "#D0E8FF" if is_light else "#253A4D"
            tc = "#007ACC" if is_light else "#4DB8FF"
        else:
            fg = "#F9F9F9" if is_light else "#333333"
            border = "#E5E5E5" if is_light else "#444444"
            hover = "#F0F0F0" if is_light else "#3E3E3E"
            tc = "#111111" if is_light else "#CCCCCC"

        lbl_text = text
        btn_w = width
        if text in ["ערוך", "ערוך"]:
            lbl_text = "ערוך"
            btn_w = 45
        elif text in ["מחק", "מחק", "מחק"]:
            lbl_text = "מחק"
            btn_w = 45
        elif text in ["▲", "מעלה"]:
            lbl_text = "מעלה"
            btn_w = 40
        elif text in ["▼", "מטה"]:
            lbl_text = "מטה"
            btn_w = 40

        return ctk.CTkButton(
            parent,
            text=lbl_text,
            width=btn_w,
            height=height,
            corner_radius=6,
            fg_color=fg,
            border_width=1,
            border_color=border,
            hover_color=hover,
            text_color=tc,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=cmd
        )

    def create_glass_badge(self, parent, text, color_type="cyan"):
        is_light = ctk.get_appearance_mode().lower() == "light"
        
        # Unified clean badge look without pastel colors
        fg = "#F3F3F3" if is_light else "#333333"
        border = "#E5E5E5" if is_light else "#444444"
        tc = "#333333" if is_light else "#CCCCCC"

        b_frame = ctk.CTkFrame(parent, corner_radius=6, fg_color=fg, border_width=1, border_color=border)
        lbl = ctk.CTkLabel(b_frame, text=text, font=ctk.CTkFont(family="Segoe UI", size=11, weight="normal"), text_color=tc)
        lbl.pack(padx=8, pady=2)
        return b_frame

    # =========================================================================
    # DIRECTIVE PAGES (Facts / Commands / Constraints / Styles / Instructions)
    #
    # All five pages are built, refreshed and handled by the generic methods below,
    # driven by the CRUD_PAGE_SPECS table (defined above the class). They previously
    # existed as five hand-copied, near-identical implementations (~990 lines); the
    # drift between those copies is exactly what shipped a Styles page reading a
    # field name the data layer never writes, crashing the app on launch.
    #
    # To add or change a page, edit its entry in CRUD_PAGE_SPECS - not the code here.
    # =========================================================================
    def build_crud_page(self, category):
        spec = CRUD_PAGE_SPECS[category]

        p = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages[category] = p

        # The order of this list is the order the AI reads the rules in - state it, because
        # the arrows looked like a display preference and were being ignored.
        self.create_page_header(p, spec["title"],
                                spec["subtitle"] + "  •  סדר הרשימה קובע את עדיפות הקריאה: מה שלמעלה מקבל עדיפות עליונה")

        # Form Box (Frosted Glass Container)
        box = self.create_glass_card(p, corner_radius=14)
        box.pack(fill="x", pady=(0, 10))

        row_inputs = ctk.CTkFrame(box, fg_color="transparent")
        row_inputs.pack(fill="x", padx=14, pady=(12, 6))

        widgets = {"entries": {}}
        self.crud_widgets[category] = widgets

        # Text inputs - generous width, one per declared field
        for idx, field in enumerate(spec["fields"]):
            fr = ctk.CTkFrame(row_inputs, fg_color="transparent")
            if category == "commands" and idx == 0:
                fr.pack(side="right", padx=(6, 0))
                fr.configure(width=190)
            else:
                fr.pack(side="right", fill="x", expand=True, padx=((6, 0) if idx == 0 else (6, 6)))

            ctk.CTkLabel(fr, text=field["label"], font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
            if category == "commands" and idx == 0:
                ent = ctk.CTkEntry(fr, placeholder_text=field["placeholder"], width=190, height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
            else:
                ent = ctk.CTkEntry(fr, placeholder_text=field["placeholder"], height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
            ent.pack(fill="x", pady=(2, 0))
            widgets["entries"][field["key"]] = ent

        # Row 2: Selectors on right, Actions on left
        row_ctrls = ctk.CTkFrame(box, fg_color="transparent")
        row_ctrls.pack(fill="x", padx=14, pady=(4, 12))

        # Selectors container (aligned right)
        fr_selectors = ctk.CTkFrame(row_ctrls, fg_color="transparent")
        fr_selectors.pack(side="right")

        # Scope selector
        fr_scope = ctk.CTkFrame(fr_selectors, fg_color="transparent")
        fr_scope.pack(side="right", padx=(0, 10))
        ctk.CTkLabel(fr_scope, text="תחולה", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        combo_scope = ctk.CTkComboBox(fr_scope, values=self.get_scope_options(), width=145, height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY)
        try:
            combo_scope._entry.configure(justify="right")
        except Exception:
            pass
        combo_scope.pack(pady=(2, 0))
        widgets["scope"] = combo_scope

        # AI target selector
        fr_ai = ctk.CTkFrame(fr_selectors, fg_color="transparent")
        fr_ai.pack(side="right", padx=(0, 10))
        ctk.CTkLabel(fr_ai, text="מודל יעד", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        combo_ai = ctk.CTkComboBox(
            fr_ai,
            values=self.get_ai_target_options(),
            width=155,
            height=32,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            state="readonly",
            command=lambda v, cat=category: self.check_custom_ai_selection(v, self.crud_widgets[cat]["ai"])
        )
        combo_ai.set("כל המודלים")
        combo_ai.pack(pady=(2, 0))
        widgets["ai"] = combo_ai

        # Expiry selector - declared once here, so it appears on all five directive pages.
        # Deliberately NOT part of spec["fields"]: that list is a positional contract passed
        # straight into memory_hub.add_* and gemini_optimizer.optimize_*.
        fr_exp = ctk.CTkFrame(fr_selectors, fg_color="transparent")
        fr_exp.pack(side="right")
        ctk.CTkLabel(fr_exp, text="תוקף", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        combo_exp = ctk.CTkComboBox(fr_exp, values=list(EXPIRY_OPTIONS.keys()), width=120, height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY, state="readonly")
        combo_exp.set(EXPIRY_DEFAULT)
        combo_exp.pack(pady=(2, 0))
        widgets["expires"] = combo_exp

        # Action Buttons container (aligned left)
        fr_actions = ctk.CTkFrame(row_ctrls, fg_color="transparent")
        fr_actions.pack(side="left", pady=(16, 0))

        btn_add = ctk.CTkButton(
            fr_actions,
            text="שמור והשתל",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            border_width=1,
            border_color=("#3b82f6", "#0284c7"),
            text_color="#ffffff",
            width=120,
            height=32,
            corner_radius=8,
            command=lambda cat=category: self.on_add_crud_item(cat)
        )
        btn_add.pack(side="left", padx=(0, 8))

        default_crud_model = memory_hub.load_db().get("settings", {}).get("defaultGeminiModel", "פלאש לאסט")
        combo_crud_model = ctk.CTkComboBox(
            fr_actions,
            values=["פלאש לייט לאסט", "פלאש לאסט", "פרו לאסט"],
            width=135,
            height=32,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            state="readonly"
        )
        combo_crud_model.pack(side="left", padx=(0, 8))
        combo_crud_model.set(default_crud_model)
        widgets["gemini_model"] = combo_crud_model

        btn_gemini = ctk.CTkButton(
            fr_actions,
            text="שפר ניסוח עם Gemini",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            border_width=1,
            border_color=("#8b5cf6", "#7c3aed"),
            text_color="#ffffff",
            width=145,
            height=32,
            corner_radius=8,
            command=lambda cat=category: self.on_gemini_optimize(cat)
        )
        btn_gemini.pack(side="left")
        widgets["gemini_btn"] = btn_gemini

        # Search Bar & Count
        filter_bar = ctk.CTkFrame(p, fg_color="transparent")
        filter_bar.pack(fill="x", pady=(2, 6))

        entry_search = ctk.CTkEntry(
            filter_bar,
            placeholder_text=spec["search_placeholder"],
            height=30,
            width=240,
            corner_radius=15,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            text_color=TEXT_PRIMARY,
            justify="right"
        )
        entry_search.pack(side="left")
        entry_search.bind("<KeyRelease>", lambda e, cat=category: self.refresh_crud_page(cat))
        widgets["search"] = entry_search

        lbl_count = ctk.CTkLabel(filter_bar, text="", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY)
        lbl_count.pack(side="right")
        widgets["count"] = lbl_count

        scroll = ctk.CTkScrollableFrame(p, corner_radius=12, fg_color=GLASS_BG_MAIN)
        scroll.pack(fill="both", expand=True, pady=(0, 4))
        widgets["scroll"] = scroll

    def refresh_crud_page(self, category):
        widgets = self.crud_widgets.get(category)
        if not widgets:
            return  # page not built yet

        spec = CRUD_PAGE_SPECS[category]
        scroll = widgets["scroll"]

        for w in scroll.winfo_children():
            w.destroy()

        items = memory_hub.get_items(category)

        query = widgets["search"].get().strip().lower()
        if query:
            items = [x for x in items
                     if any(query in (x.get(f) or "").lower() for f in spec["search_fields"])]

        active = len([x for x in items if x.get("active", True)])
        widgets["count"].configure(text=spec["count_text"].format(active=active, total=len(items)))

        if not items:
            ctk.CTkLabel(scroll, text=spec["empty_text"], font=ctk.CTkFont(family="Segoe UI", size=13), text_color=TEXT_PRIMARY).pack(pady=30)
            return

        render = self.render_card_detailed if spec["card"]["variant"] == "detailed" else self.render_card_compact
        for item in items:
            render(scroll, category, item, spec)

    def render_card_detailed(self, parent, category, item, spec):
        """Card layout used by Facts and Styles: word-labelled action column, title + body."""
        card_spec = spec["card"]
        title_text = item.get(card_spec["title_field"], "")

        c = self.create_glass_card(parent, corner_radius=8)
        c.pack(fill="x", pady=4, padx=4)

        # Action frame (Left)
        actions = ctk.CTkFrame(c, fg_color="transparent")
        actions.pack(side="left", padx=12, pady=8)

        btn_up = self.create_card_action_button(actions, "▲ עדיפות", lambda i_id=item["id"]: self.on_reorder_item(category, i_id, "up"), "default", 62, 26)
        btn_up.pack(side="left", padx=2)

        btn_down = self.create_card_action_button(actions, "▼ הורד", lambda i_id=item["id"]: self.on_reorder_item(category, i_id, "down"), "default", 52, 26)
        btn_down.pack(side="left", padx=2)

        btn_edit = self.create_card_action_button(actions, "ערוך", lambda it=item: self.open_edit_dialog(category, it), "edit", 45, 26)
        btn_edit.pack(side="left", padx=2)

        btn_del = self.create_card_action_button(actions, "מחק", lambda i_id=item["id"], n=title_text or "Unknown": self.on_del_item(category, i_id, n), "del", 45, 26)
        btn_del.pack(side="left", padx=2)

        sw_var = ctk.BooleanVar(value=item.get("active", True))
        sw = ctk.CTkSwitch(actions, text="", variable=sw_var, width=30, command=lambda i_id=item["id"], v=sw_var: self.on_sw_item(category, i_id, v))
        sw.pack(side="left", padx=(10, 0))

        # Content frame (Right)
        content_f = ctk.CTkFrame(c, fg_color="transparent")
        content_f.pack(side="right", fill="both", expand=True, padx=12, pady=8)

        header_f = ctk.CTkFrame(content_f, fg_color="transparent")
        header_f.pack(anchor="e", fill="x")

        # Title
        ctk.CTkLabel(header_f, text=title_text, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color=TEXT_PRIMARY).pack(side="right")

        # Badges
        scope_str = item.get("scope", "global")
        badge_text = "כללי (גלובלי)" if scope_str == "global" else f"{scope_str}"
        self.create_glass_badge(header_f, badge_text).pack(side="right", padx=10)

        ai_badge_text = self.format_ai_target_badge(item)
        self.create_glass_badge(header_f, ai_badge_text).pack(side="right", padx=2)

        expiry_badge = self.format_expiry_badge(item)
        if expiry_badge:
            self.create_glass_badge(header_f, expiry_badge[0], expiry_badge[1]).pack(side="right", padx=2)

        val = item.get(card_spec["body_field"], "")
        if val:
            ctk.CTkLabel(content_f, text=val, font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_SECONDARY, wraplength=700, justify="right").pack(anchor="e", pady=(4, 0))

    def render_card_compact(self, parent, category, item, spec):
        """Card layout used by Commands, Constraints and Instructions: icon actions + stacked info lines."""
        card_spec = spec["card"]

        c = self.create_glass_card(parent, corner_radius=12)
        c.pack(fill="x", pady=3, padx=4)

        btn_up = self.create_card_action_button(c, "▲", lambda i_id=item["id"]: self.on_reorder_item(category, i_id, "up"), "default", 26, 28)
        btn_up.pack(side="left", padx=(8, 1), pady=6)

        btn_down = self.create_card_action_button(c, "▼", lambda i_id=item["id"]: self.on_reorder_item(category, i_id, "down"), "default", 26, 28)
        btn_down.pack(side="left", padx=(1, 4), pady=6)

        del_name = item.get(card_spec["title_field"], "") or "Unknown"
        btn_del = self.create_card_action_button(c, "מחק", lambda i_id=item["id"], n=del_name: self.on_del_item(category, i_id, n), "del", 28, 28)
        btn_del.pack(side="left", padx=(2, 2), pady=6)

        btn_edit = self.create_card_action_button(c, "ערוך", lambda it=item: self.open_edit_dialog(category, it), "edit", 28, 28)
        btn_edit.pack(side="left", padx=(2, 6), pady=6)

        sw_var = ctk.BooleanVar(value=item.get("active", True))
        sw = ctk.CTkSwitch(c, text="פעיל", variable=sw_var, command=lambda i_id=item["id"], v=sw_var: self.on_sw_item(category, i_id, v))
        sw.pack(side="left", padx=6)

        scope_str = item.get("scope", "global")
        badge_text = "כללי (גלובלי)" if scope_str == "global" else f"{scope_str}"
        self.create_glass_badge(c, badge_text, card_spec["accent"] if scope_str == "global" else "default").pack(side="left", padx=4)

        ai_badge_text = self.format_ai_target_badge(item)
        self.create_glass_badge(c, ai_badge_text, "purple").pack(side="left", padx=4)

        expiry_badge = self.format_expiry_badge(item)
        if expiry_badge:
            self.create_glass_badge(c, expiry_badge[0], expiry_badge[1]).pack(side="left", padx=4)

        # Type badge (right) + stacked info lines
        self.create_glass_badge(c, card_spec["type_badge"], card_spec["accent"]).pack(side="right", padx=(0, 10), pady=6)

        info = ctk.CTkFrame(c, fg_color="transparent")
        info.pack(side="right", fill="both", expand=True, padx=8, pady=6)

        for line in card_spec["lines"]:
            raw = item.get(line["field"], line.get("default", ""))
            if not raw and not line.get("always"):
                continue
            text = line.get("prefix", "") + str(raw)
            if not text.endswith("\u200f"):
                text += "\u200f"
            label_kwargs = {
                "text": text,
                "font": ctk.CTkFont(family="Segoe UI", size=line["size"], weight=line.get("weight", "normal")),
                "text_color": TEXT_PRIMARY if line.get("color", "primary") == "primary" else TEXT_SECONDARY,
                "justify": "right",
            }
            if line.get("wrap"):
                label_kwargs["wraplength"] = line["wrap"]
            ctk.CTkLabel(info, **label_kwargs).pack(anchor="e")

    def on_add_crud_item(self, category):
        spec = CRUD_PAGE_SPECS[category]
        widgets = self.crud_widgets[category]

        values = {key: ent.get().strip() for key, ent in widgets["entries"].items()}

        missing = [f for f in spec["required"] if not values.get(f)]
        if missing:
            messagebox.showwarning(spec["missing_title"], spec["missing_msg"])
            return

        scope = widgets["scope"].get()
        scope_clean = "global" if "גלובלי" in scope else scope
        target_ais = self.resolve_target_ais(widgets["ai"])

        # Warn before writing, not after: a contradicting rule that reaches the file is
        # exactly how the AI ends up doing "not what I meant".
        candidate = dict(values)
        candidate["scope"] = scope_clean
        candidate["target_ais"] = target_ais
        if not self.confirm_no_conflicts(category, candidate):
            return

        add_fn = getattr(memory_hub, spec["add_fn"])
        ordered = [values[f["key"]] for f in spec["fields"]]
        add_fn(*ordered, scope=scope_clean, active=True, target_ais=target_ais,
               expires_at=self.resolve_expiry(widgets.get("expires")))

        for ent in widgets["entries"].values():
            ent.delete(0, "end")

        self.refresh_all_views()
        first_value = values[spec["fields"][0]["key"]]
        self.set_status(spec["added_status"].format(first=first_value))

    def confirm_no_conflicts(self, category, candidate, exclude_id=None):
        """
        Checks a rule about to be saved against the existing memory (current profile AND
        the main profile) and, when it contradicts one, asks the user to decide.
        Returns True to proceed with the save, False to abort.
        """
        try:
            conflicts = memory_hub.detect_conflicts(proposed_item=candidate, category=category)
        except Exception as e:
            print(f"[conflict check] {e}")
            return True  # never block a save because the check itself failed

        # An edit compares against everything except the item being edited.
        conflicts = [
            c for c in conflicts
            if c.get("proposed_item") is not None
            and (exclude_id is None or (c.get("existing_item") or {}).get("id") != exclude_id)
        ]
        if not conflicts:
            return True

        lines = []
        for c in conflicts[:4]:
            where = "הפרופיל הראשי" if c.get("profile_id") == "default" else "הפרופיל הנוכחי"
            lines.append(f"• {c.get('title', '')}\n   ({where}) {c.get('description', '')}")
        if len(conflicts) > 4:
            lines.append(f"… ועוד {len(conflicts) - 4} סתירות.")

        msg = ("הכלל שאתה מוסיף סותר כלל שכבר קיים בזיכרון:\n\n"
               + "\n\n".join(lines)
               + "\n\nשני הכללים ייכתבו לקובץ החוקים, והמודלים יצטרכו להחליט בעצמם במי לבחור.\n\n"
                 "להוסיף בכל זאת?")

        return messagebox.askyesno("זוהתה סתירה", msg)

    def on_gemini_optimize(self, category):
        spec = CRUD_PAGE_SPECS[category]
        widgets = self.crud_widgets[category]

        values = {key: ent.get().strip() for key, ent in widgets["entries"].items()}
        if not any(values.get(f) for f in spec["gemini_min_fields"]):
            messagebox.showinfo(spec["gemini_empty_title"], spec["gemini_empty_msg"])
            return

        widgets["gemini_btn"].configure(state="disabled", text="מעבד...")
        self.set_status(spec["gemini_status"])

        optimize_fn = getattr(gemini_optimizer, spec["optimize_fn"])
        ordered = [values[f["key"]] for f in spec["fields"]]
        chosen_model = widgets["gemini_model"].get() if "gemini_model" in widgets else None

        def worker():
            ok, res = optimize_fn(*ordered, model=chosen_model)
            self.after(0, lambda: self.on_gemini_optimize_done(category, ok, res))

        self.run_async(worker, on_error=lambda e: self.on_gemini_optimize_done(category, False, e))

    def on_gemini_optimize_done(self, category, ok, res):
        spec = CRUD_PAGE_SPECS[category]
        widgets = self.crud_widgets[category]

        widgets["gemini_btn"].configure(state="normal", text="שפר ניסוח עם Gemini")

        if not (ok and isinstance(res, dict)):
            messagebox.showerror("שגיאה", str(res))
            return

        suggestion = "\n".join(f"{f['gemini_label']}: {res.get(f['key'])}" for f in spec["fields"])
        msg = f"Gemini מציע:\n\n{suggestion}\n\nהסבר: {res.get('explanation')}\n\nהאם להחיל?"

        if messagebox.askyesno("הצעת שיפור מ-Gemini", msg):
            for field in spec["fields"]:
                ent = widgets["entries"][field["key"]]
                ent.delete(0, "end")
                ent.insert(0, res.get(field["key"], ""))
            self.set_status(spec["gemini_done_status"])

    # --- Thin per-page wrappers -------------------------------------------------
    # Kept so create_main_content() and refresh_all_views() keep their explicit,
    # readable call sites (and any external caller keeps working).
    def build_page_facts(self): self.build_crud_page("facts")
    def refresh_page_facts(self): self.refresh_crud_page("facts")

    def build_page_commands(self): self.build_crud_page("commands")
    def refresh_page_commands(self): self.refresh_crud_page("commands")

    def build_page_constraints(self): self.build_crud_page("constraints")
    def refresh_page_constraints(self): self.refresh_crud_page("constraints")

    def build_page_styles(self): self.build_crud_page("styles")
    def refresh_page_styles(self): self.refresh_crud_page("styles")

    def build_page_instructions(self): self.build_crud_page("instructions")
    def refresh_page_instructions(self): self.refresh_crud_page("instructions")

    # =========================================================================
    # GENERIC EDIT DIALOG (Inline Edit Modal)
    # =========================================================================
    def open_edit_dialog(self, category, item):
        diag = ctk.CTkToplevel(self)
        diag.title("עריכת פריט בזיכרון")
        diag.geometry("560x520")
        diag.attributes("-topmost", True)
        diag.configure(fg_color=GLASS_BG_MAIN)

        box = ctk.CTkFrame(diag, corner_radius=12, fg_color=GLASS_CARD, border_width=1, border_color=GLASS_CARD_BORDER)
        box.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(box, text="עריכת פריט בזיכרון", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=16, pady=(12, 8))

        fields = {}
        if category == "facts":
            f_specs = [("name", "שם המידע"), ("value", "ערך / תוכן")]
        elif category == "commands":
            f_specs = [("name", "שם פקודה"), ("details", "פירוט הפעולה"), ("trigger_case", "באיזה מקרה")]
        elif category == "constraints":
            f_specs = [("constraint", "האיסור"), ("alternative_or_why", "הנחיה חלופית")]
        elif category == "styles":
            f_specs = [("aspect", "היבט הסגנון"), ("instruction", "הנחיית הסגנון")]
        elif category == "context_files":
            f_specs = [("name", "שם תצוגה"), ("path", "נתיב קובץ במחשב"), ("summary", "תקציר והנחיות מפתח")]
        else:
            f_specs = [("instruction", "הוראה"), ("when_to_apply", "מתי ליישם")]

        for key, lbl in f_specs:
            ctk.CTkLabel(box, text=lbl, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e", padx=16, pady=(4, 1))
            entry = ctk.CTkEntry(box, height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
            entry.insert(0, item.get(key, ""))
            entry.pack(fill="x", padx=16)
            fields[key] = entry

        # Scope
        ctk.CTkLabel(box, text="תחולה", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e", padx=16, pady=(4, 1))
        combo_sc = ctk.CTkComboBox(box, values=self.get_scope_options(), height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY)
        cur_sc = item.get("scope", "global")
        combo_sc.set("גלובלי" if cur_sc == "global" else cur_sc)
        try:
            combo_sc._entry.configure(justify="right")
        except Exception:
            pass
        combo_sc.pack(fill="x", padx=16)

        # Target AI
        ctk.CTkLabel(box, text="מודל יעד", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e", padx=16, pady=(4, 1))
        combo_ai = ctk.CTkComboBox(box, values=self.get_ai_target_options(), height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY, state="readonly", command=lambda v: self.check_custom_ai_selection(v, combo_ai))
        cur_ai = item.get("target_ais", ["all"])
        if not cur_ai or cur_ai == ["all"] or cur_ai == "all":
            combo_ai.set("כל המודלים")
        elif cur_ai == ["antigravity"]:
            combo_ai.set("Google Antigravity")
        elif cur_ai == ["claude"]:
            combo_ai.set("Claude Desktop")
        elif cur_ai == ["cursor"]:
            combo_ai.set("Cursor")
        elif cur_ai == ["windsurf"]:
            combo_ai.set("Windsurf")
        elif cur_ai == ["copilot"]:
            combo_ai.set("GitHub Copilot")
        else:
            combo_ai.set(f"מותאם ({len(cur_ai)} מודלים)")
            combo_ai._custom_selection = cur_ai if isinstance(cur_ai, list) else [cur_ai]
        combo_ai.pack(fill="x", padx=16)

        btn_row = ctk.CTkFrame(box, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(16, 10))

        def on_save_edit():
            updated = {}
            for k, ent in fields.items():
                updated[k] = ent.get().strip()
            sc_val = combo_sc.get()
            updated["scope"] = "global" if "גלובלי" in sc_val else sc_val

            updated["target_ais"] = self.resolve_target_ais(combo_ai, fallback=item.get("target_ais", ["all"]))

            # Same gate as adding: an edit that flips a rule's meaning is just as likely to
            # contradict an existing one, and used to be written with no check at all.
            if not self.confirm_no_conflicts(category, updated, exclude_id=item.get("id")):
                return

            memory_hub.update_item(category, item.get("id"), updated)
            diag.destroy()
            self.refresh_all_views()
            self.set_status("הפריט עודכן והושתל בהצלחה!")

        btn_save = ctk.CTkButton(btn_row, text="שמור שינויים", fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff", command=on_save_edit)
        btn_save.pack(side="right")

        btn_cancel = ctk.CTkButton(btn_row, text="ביטול", fg_color=("#E5E5E5", "#334155"), hover_color=("#D5D5D5", "#475569"), text_color=TEXT_PRIMARY, command=diag.destroy)
        btn_cancel.pack(side="left")

    def on_del_item(self, category, item_id, name):
        if messagebox.askyesno("אישור מחיקה", f"האם למחוק את '{name}'?"):
            memory_hub.remove_item(category, item_id)
            self.refresh_all_views()
            self.set_status("הפריט נמחק בהצלחה")

    def on_sw_item(self, category, item_id, var):
        memory_hub.toggle_item(category, item_id, var.get())
        self.refresh_page_preview()
        self.update_stats()
        self.set_status("סטטוס עודכן והושתל")

    # =========================================================================
    # 6. PAGE: CONTEXT FILES (קבצי הקשר ומסמכים)
    # =========================================================================
    def build_page_context_files(self):
        p = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["context_files"] = p

        self.create_page_header(p, "קבצי הקשר ומסמכי פרויקט", "צירוף מסמכי אפיון, קובצי הגדרות או קוד כחלק מהזיכרון הקבוע")

        # Form Box (Frosted Glass Container)
        box = self.create_glass_card(p, corner_radius=14)
        box.pack(fill="x", pady=(0, 10))

        row1 = ctk.CTkFrame(box, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(12, 4))

        f_pick = ctk.CTkFrame(row1, fg_color="transparent")
        f_pick.pack(side="right", fill="x", expand=True, padx=(4, 0))
        ctk.CTkLabel(f_pick, text="נתיב קובץ במחשב", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")

        path_row = ctk.CTkFrame(f_pick, fg_color="transparent")
        path_row.pack(fill="x", pady=(2, 0))
        self.entry_file_path = ctk.CTkEntry(path_row, placeholder_text="בחר קובץ (MD, TXT, JSON, PY)...", height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY)
        self.entry_file_path.pack(side="right", fill="x", expand=True, padx=(4, 0))
        btn_browse = ctk.CTkButton(path_row, text="סייר קבצים", width=100, height=34, corner_radius=8, fg_color=("#0b1526", "#1e3a8a"), border_width=1, border_color=("#1d4ed8", "#3b82f6"), hover_color=("#1e40af", "#2563eb"), text_color="#ffffff", command=self.on_browse_context_file)
        btn_browse.pack(side="left")

        f_name = ctk.CTkFrame(row1, fg_color="transparent")
        f_name.pack(side="right", padx=(4, 4))
        ctk.CTkLabel(f_name, text="שם תצוגה / כותרת", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.entry_file_name = ctk.CTkEntry(f_name, placeholder_text="למשל אפיון ארכיטקטורה", width=180, height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
        self.entry_file_name.pack(pady=(2, 0))

        f_scope = ctk.CTkFrame(row1, fg_color="transparent")
        f_scope.pack(side="right", padx=(0, 4))
        ctk.CTkLabel(f_scope, text="תחולה", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.combo_file_scope = ctk.CTkComboBox(f_scope, values=self.get_scope_options(), width=140, height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY)
        try:
            self.combo_file_scope._entry.configure(justify="right")
        except Exception:
            pass
        self.combo_file_scope.pack(pady=(2, 0))

        f_ai = ctk.CTkFrame(row1, fg_color="transparent")
        f_ai.pack(side="right", padx=(0, 4))
        ctk.CTkLabel(f_ai, text="מודל יעד", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.combo_file_ai = ctk.CTkComboBox(f_ai, values=self.get_ai_target_options(), width=150, height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY, state="readonly", command=lambda v: self.check_custom_ai_selection(v, self.combo_file_ai))
        self.combo_file_ai.set("כל המודלים")
        self.combo_file_ai.pack(pady=(2, 0))

        row2 = ctk.CTkFrame(box, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=(6, 12))

        f_sum = ctk.CTkFrame(row2, fg_color="transparent")
        f_sum.pack(side="right", fill="x", expand=True, padx=(4, 0))
        ctk.CTkLabel(f_sum, text="תקציר והנחיות מרכזיות למודלים (אופציונלי)", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.entry_file_summary = ctk.CTkEntry(f_sum, placeholder_text="דגשים קריטיים מתוך הקובץ, מטרות או כללים", height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
        self.entry_file_summary.pack(fill="x", pady=(2, 0))

        self.btn_gemini_summarize = ctk.CTkButton(
            row2,
            text="✨ תמצת עם Gemini",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            border_width=1,
            border_color=("#8b5cf6", "#7c3aed"),
            text_color="#ffffff",
            width=150,
            height=34,
            corner_radius=8,
            command=self.on_gemini_summarize_file
        )
        self.btn_gemini_summarize.pack(side="right", padx=(8, 8), pady=(18, 0))

        btn_add = ctk.CTkButton(
            row2,
            text="שמור והשתל",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            border_width=1,
            border_color=("#3b82f6", "#0284c7"),
            text_color="#ffffff",
            width=120,
            height=34,
            corner_radius=8,
            command=self.on_add_context_file
        )
        btn_add.pack(side="right", pady=(18, 0))

        # Search Bar & Count
        filter_bar = ctk.CTkFrame(p, fg_color="transparent")
        filter_bar.pack(fill="x", pady=(2, 6))

        self.entry_search_files = ctk.CTkEntry(
            filter_bar,
            placeholder_text="חיפוש בקבצים",
            height=30,
            width=240,
            corner_radius=15,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            text_color=TEXT_PRIMARY,
            justify="right"
        )
        self.entry_search_files.pack(side="left")
        self.entry_search_files.bind("<KeyRelease>", lambda e: self.refresh_page_context_files())

        self.lbl_files_count = ctk.CTkLabel(filter_bar, text="", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY)
        self.lbl_files_count.pack(side="right")

        self.scroll_files = ctk.CTkScrollableFrame(p, corner_radius=12, fg_color=GLASS_BG_MAIN)
        self.scroll_files.pack(fill="both", expand=True, pady=(0, 4))

    def on_browse_context_file(self):
        path = filedialog.askopenfilename(
            title="בחר מסמך או קובץ קוד",
            filetypes=[
                ("כל הקבצים הנתמכים", "*.md;*.txt;*.json;*.yaml;*.yml;*.py;*.js;*.ts;*.html;*.css;*.csv"),
                ("מסמכי טקסט ו-Markdown", "*.md;*.txt"),
                ("קובצי קוד ותצורה", "*.json;*.yaml;*.yml;*.py;*.js;*.ts;*.html;*.css"),
                ("כל הקבצים", "*.*")
            ]
        )
        if path:
            self.entry_file_path.delete(0, "end")
            self.entry_file_path.insert(0, path)
            if not self.entry_file_name.get().strip():
                self.entry_file_name.delete(0, "end")
                self.entry_file_name.insert(0, os.path.basename(path))

    def on_add_context_file(self):
        path = self.entry_file_path.get().strip()
        name = self.entry_file_name.get().strip()
        summary = self.entry_file_summary.get().strip()
        scope = self.combo_file_scope.get()
        scope_clean = "global" if "גלובלי" in scope else scope

        target_ais = self.resolve_target_ais(self.combo_file_ai)

        if not path:
            messagebox.showwarning("שדה חסר", "נא לבחור נתיב קובץ.")
            return

        memory_hub.add_context_file(name, path, summary, scope=scope_clean, active=True, target_ais=target_ais)
        self.entry_file_path.delete(0, "end")
        self.entry_file_name.delete(0, "end")
        self.entry_file_summary.delete(0, "end")
        self.refresh_all_views()
        self.set_status(f"קובץ הקשר נוסף והושתל: {name or os.path.basename(path)}")

    def on_gemini_summarize_file(self):
        fp = self.entry_file_path.get().strip()
        if not fp or not os.path.isfile(fp):
            messagebox.showwarning("קובץ לא קיים", "נא לבחור קובץ קיים במחשב תחילה.")
            return

        self.btn_gemini_summarize.configure(state="disabled", text="✨ קורא ומתמצת...")
        self.set_status("Gemini מנתח את תוכן הקובץ...")

        def worker():
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("שגיאת קריאה", f"לא ניתן לקרוא את הקובץ: {e}"))
                self.after(0, lambda: self.btn_gemini_summarize.configure(state="normal", text="✨ תמצת עם Gemini"))
                return

            ok, res = gemini_optimizer.summarize_context_file(content, os.path.basename(fp))
            self.after(0, lambda: self.on_gemini_summarize_done(ok, res))

        self.run_async(worker)

    def on_gemini_summarize_done(self, ok, res):
        self.btn_gemini_summarize.configure(state="normal", text="✨ תמצת עם Gemini")
        if ok and res:
            self.entry_file_summary.delete(0, "end")
            self.entry_file_summary.insert(0, res.strip().replace("\n", " | ")[:300])
            self.set_status('תקציר הקובץ הופק בהצלחה ע"י Gemini!')
            messagebox.showinfo("תקציר הופק", f"התקציר חולץ בהצלחה:\n\n{res}")
        else:
            messagebox.showerror("שגיאה", str(res))

    def refresh_page_context_files(self):
        for w in self.scroll_files.winfo_children(): w.destroy()
        items = memory_hub.get_context_files()
        query = self.entry_search_files.get().strip().lower() if hasattr(self, "entry_search_files") else ""
        if query:
            items = [x for x in items if query in x.get("name", "").lower() or query in x.get("path", "").lower() or query in x.get("summary", "").lower()]

        active = len([x for x in items if x.get("active", True)])
        self.lbl_files_count.configure(text=f"קבצים: {active} פעילים (מתוך {len(items)})")

        if not items:
            ctk.CTkLabel(self.scroll_files, text="אין קבצי הקשר מצורפים.", font=ctk.CTkFont(family="Segoe UI", size=13), text_color=TEXT_PRIMARY).pack(pady=30)
            return

        for item in items:
            c = self.create_glass_card(self.scroll_files, corner_radius=12)
            c.pack(fill="x", pady=3, padx=4)

            btn_up = self.create_card_action_button(c, "▲", lambda i_id=item["id"]: self.on_reorder_item("context_files", i_id, "up"), "default", 26, 28)
            btn_up.pack(side="left", padx=(8, 1), pady=6)

            btn_down = self.create_card_action_button(c, "▼", lambda i_id=item["id"]: self.on_reorder_item("context_files", i_id, "down"), "default", 26, 28)
            btn_down.pack(side="left", padx=(1, 4), pady=6)

            btn_del = self.create_card_action_button(c, "מחק", lambda i_id=item["id"], n=item.get("name", "Unknown"): self.on_del_item("context_files", i_id, n), "del", 28, 28)
            btn_del.pack(side="left", padx=(2, 2), pady=6)

            btn_edit = self.create_card_action_button(c, "ערוך", lambda it=item: self.open_edit_dialog("context_files", it), "edit", 28, 28)
            btn_edit.pack(side="left", padx=(2, 6), pady=6)

            sw_var = ctk.BooleanVar(value=item.get("active", True))
            sw = ctk.CTkSwitch(c, text="פעיל", variable=sw_var, command=lambda i_id=item["id"], v=sw_var: self.on_sw_item("context_files", i_id, v))
            sw.pack(side="left", padx=6)

            scope_str = item.get("scope", "global")
            badge_text = "כללי (גלובלי)" if scope_str == "global" else f"{scope_str}"
            self.create_glass_badge(c, badge_text, "cyan" if scope_str == "global" else "default").pack(side="left", padx=4)

            ai_badge_text = self.format_ai_target_badge(item)
            self.create_glass_badge(c, ai_badge_text, "purple").pack(side="left", padx=4)

            # Open file button
            p_exist = os.path.exists(item.get("path", ""))
            btn_open = self.create_card_action_button(c, "פתח", lambda fp=item.get("path"): os.startfile(fp) if os.path.exists(fp) else None, "edit", width=65, height=28)
            btn_open.configure(state="normal" if p_exist else "disabled")
            btn_open.pack(side="left", padx=4)

            # Glowing Teal Pip on Right
            self.create_glass_badge(c, "מסמך הקשר", "cyan").pack(side="right", padx=(0, 10), pady=6)
            info = ctk.CTkFrame(c, fg_color="transparent")
            info.pack(side="right", fill="both", expand=True, padx=8, pady=6)
            ctk.CTkLabel(info, text=f"{item.get('name', '')}", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e")
            ctk.CTkLabel(info, text=f"נתיב: {item.get('path', '')}", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY, wraplength=480, justify="right").pack(anchor="e")
            if item.get("summary"):
                ctk.CTkLabel(info, text=f"הנחיות ודגשים: {item.get('summary', '')}", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY, wraplength=480, justify="right").pack(anchor="e")

    # =========================================================================
    # AI SANITY CHECK & CONFLICT DETECTION MODAL
    # =========================================================================

    def open_sanity_check_dialog(self):
        self.set_status("מבצע בדיקת תקינות חוקים עם Gemini...")

        dialog = ctk.CTkToplevel(self)
        dialog.title(" בדיקת תקינות חוקים וזיהוי סתירות (Gemini AI)")
        dialog.geometry("720x640")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=GLASS_BG_MAIN)

        lbl_loading = ctk.CTkLabel(dialog, text="⏳ מנתח את כל החוקים, ההנחיות והאיסורים באמצעות Gemini...\nנא להמתין מספר שניות.", font=ctk.CTkFont(family="Segoe UI", size=14), text_color=TEXT_PRIMARY)
        lbl_loading.pack(pady=80)

        def worker():
            p_data = memory_hub.get_current_profile_data()
            local_conflicts = memory_hub.detect_conflicts()
            ok, res = gemini_optimizer.analyze_conflicts_and_health(p_data)
            if not ok or not res:
                res = {
                    "health_score": 100 if not local_conflicts else max(50, 100 - len(local_conflicts)*20),
                    "summary": "בדיקת תקינות מקומית הסתיימה בהצלחה.",
                    "conflicts": [],
                    "recommendations": ["המערכת מוכנה לפעולה ולסנכרון מלא."]
                }
            for lc in local_conflicts:
                res.setdefault("conflicts", []).append({
                    "title": lc.get("title", "סתירה בזיכרון"),
                    "description": lc.get("description", ""),
                    "suggestion": "מומלץ לבחור אחד מהערכים או להסיר את הפריט הכפול.",
                    "item_id": lc.get("item_b", {}).get("id") or lc.get("existing_item", {}).get("id"),
                    "profile_id": lc.get("profile_id")
                })
            res["health_score"] = max(30, 100 - len(res.get("conflicts", []))*15)
            self.after(0, lambda: render_report(True, res))

        def resolve_item(item_id, profile_id=None):
            memory_hub.resolve_conflict("conf", "delete", target_item_id=item_id, profile_id=profile_id)
            self.refresh_all_views()
            dialog.destroy()
            self.set_status("הפריט הוסר והסתירה נפתרה בהצלחה!")

        def render_report(ok, res):
            lbl_loading.destroy()
            if not ok:
                ctk.CTkLabel(dialog, text=f"❌ שגיאה בבדיקה:\n{res}", text_color=TEXT_PRIMARY, font=ctk.CTkFont(family="Segoe UI", size=13), wraplength=600).pack(pady=30)
                ctk.CTkButton(dialog, text="סגור", width=110, corner_radius=8, fg_color="#1e293b", hover_color="#334155", command=dialog.destroy).pack(pady=10)
                return

            top_box = self.create_glass_card(dialog, corner_radius=14)
            top_box.pack(fill="x", padx=16, pady=12)

            score = res.get("health_score", 100)
            score_color = "#10b981" if score >= 85 else ("#f59e0b" if score >= 60 else "#f43f5e")

            score_frame = ctk.CTkFrame(top_box, fg_color="transparent")
            score_frame.pack(side="right", padx=16, pady=12)
            ctk.CTkLabel(score_frame, text=f"{score}", font=ctk.CTkFont(family="Segoe UI", size=34, weight="bold"), text_color=score_color).pack()
            ctk.CTkLabel(score_frame, text="ציון בריאות", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_PRIMARY).pack()

            summary_frame = ctk.CTkFrame(top_box, fg_color="transparent")
            summary_frame.pack(side="right", fill="both", expand=True, padx=12, pady=12)
            ctk.CTkLabel(summary_frame, text=" דוח תקינות מערכת הזיכרון", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e")
            ctk.CTkLabel(summary_frame, text=res.get("summary", ""), font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_SECONDARY, wraplength=450, justify="right").pack(anchor="e", pady=(4, 0))

            scroll = ctk.CTkScrollableFrame(dialog, corner_radius=12, fg_color=GLASS_BG_MAIN)
            scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

            conflicts = res.get("conflicts", [])
            if conflicts:
                ctk.CTkLabel(scroll, text="⚠️ סתירות ואזהרות שזוהו", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", pady=(6, 4))
                for c in conflicts:
                    cf_box = self.create_glass_card(scroll, corner_radius=10, border_color="#EF4444")
                    cf_box.pack(fill="x", pady=4, padx=4)
                    ctk.CTkLabel(cf_box, text=f"• {c.get('title', '')}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=12, pady=(6, 2))
                    ctk.CTkLabel(cf_box, text=c.get("description", ""), font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY, wraplength=580, justify="right").pack(anchor="e", padx=12)
                    if c.get("suggestion"):
                        ctk.CTkLabel(cf_box, text=f"הצעה לתיקון: {c.get('suggestion')}", font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"), text_color=TEXT_SECONDARY, wraplength=580, justify="right").pack(anchor="e", padx=12, pady=(2, 6))
                    if c.get("item_id"):
                        btn_fix = ctk.CTkButton(cf_box, text="מחק פריט זה לפתרון הסתירה", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), height=24, width=150, corner_radius=4, fg_color="#EF4444", hover_color="#DC2626", text_color="#FFFFFF", command=lambda i_id=c.get("item_id"), p_id=c.get("profile_id"): resolve_item(i_id, p_id))
                        btn_fix.pack(anchor="w", padx=12, pady=(0, 6))
            else:
                ctk.CTkLabel(scroll, text="✅ לא נמצאו סתירות בין החוקים, המערכת פועלת בהרמוניה מלאה", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", pady=10)

            recs = res.get("recommendations", [])
            if recs:
                ctk.CTkLabel(scroll, text="המלצות לחידוד הפרומפט", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", pady=(12, 4))
                for r in recs:
                    r_box = self.create_glass_card(scroll, corner_radius=8)
                    r_box.pack(fill="x", pady=2, padx=4)
                    ctk.CTkLabel(r_box, text=f"✓ {r}", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY, wraplength=580, justify="right").pack(anchor="e", padx=12, pady=5)

            btn_close = ctk.CTkButton(dialog, text="סגור דוח", width=130, height=32, corner_radius=8, fg_color=("#E5E5E5", "#1e293b"), border_width=1, border_color=GLASS_CARD_BORDER, hover_color=GLASS_CARD_HOVER, text_color=TEXT_PRIMARY, command=dialog.destroy)
            btn_close.pack(pady=8)
            self.set_status("בדיקת תקינות הושלמה.")

        # The analysis worker was defined but never launched, so this dialog used to sit on
        # "מנתח..." forever and the whole sanity check never ran.
        self.run_async(worker, on_error=lambda e: render_report(False, e))

    # =========================================================================
    # 7. PAGE: CHAT & EMAIL MEMORY MINER (כריית זיכרונות משיחות ומיילים)
    # =========================================================================
    def build_page_chat_miner(self):
        p = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["chat_miner"] = p

        self.create_page_header(
            p,
            "כריית וחילוץ זיכרונות משיחות ומיילים",
            "איתור וניתוח של שיחות מכל סביבות הפיתוח והשיחה, קבצים ומאגרי מיילים לזיכרון הקבוע"
        )

        self.current_miner_suggestions = []
        self.discovered_chats_data = []

        # Top Card: Source Selection (Frosted Glass Container)
        box_src = self.create_glass_card(p, corner_radius=14)
        box_src.pack(fill="x", pady=(0, 10))

        # Mode Selector
        mode_row = ctk.CTkFrame(box_src, fg_color="transparent")
        mode_row.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(
            mode_row,
            text="בחר מקור לניתוח",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=TEXT_SECONDARY
        ).pack(side="right", padx=(10, 0))

        self.seg_miner_mode = ctk.CTkSegmentedButton(
            mode_row,
            values=["תוכנות במחשב", "קובץ שיחה", "תיקייה שלמה", "מאגר מיילים", "הדבקה חופשית"],
            command=self.on_chat_miner_mode_change
        )
        self.seg_miner_mode.pack(side="right")
        self.seg_miner_mode.set("תוכנות במחשב")

        # Container for dynamic inputs
        self.miner_inputs_container = ctk.CTkFrame(box_src, fg_color="transparent")
        self.miner_inputs_container.pack(fill="x", padx=14, pady=(4, 6))

        # 1. Discovered Chats Frame (Multi-App Discovery)
        self.frame_mode_discovered = ctk.CTkFrame(self.miner_inputs_container, fg_color="transparent")
        self.frame_mode_discovered.pack(fill="x")

        self.combo_miner_app = ctk.CTkComboBox(
            self.frame_mode_discovered,
            values=[
                "Google Antigravity",
                "GitHub Copilot",
                "Cline & Roo",
                "Claude Code",
                "Cursor IDE",
                "Windsurf IDE",
                "ChatGPT Export",
                "סריקה מקיפה - כל התוכנות"
            ],
            width=170,
            height=34,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.on_change_miner_app
        )
        self.combo_miner_app.pack(side="right", padx=(0, 8))
        self.combo_miner_app.set("Google Antigravity")

        self.combo_discovered_chats = ctk.CTkComboBox(
            self.frame_mode_discovered,
            height=34,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.combo_discovered_chats.pack(side="right", fill="x", expand=True, padx=(8, 0))

        btn_rescan_chats = ctk.CTkButton(
            self.frame_mode_discovered,
            text="סרוק שיחות 🔄",
            width=120,
            height=34,
            corner_radius=8,
            fg_color="#0c1628",
            border_width=1,
            border_color="#1e3a8a",
            hover_color="#162544",
            text_color="#ffffff",
            command=self.on_refresh_discovered_chats
        )
        btn_rescan_chats.pack(side="left")

        # 2. File Pick Frame
        self.frame_mode_file = ctk.CTkFrame(self.miner_inputs_container, fg_color="transparent")
        self.entry_miner_file = ctk.CTkEntry(
            self.frame_mode_file,
            placeholder_text="בחר קובץ שיחה (JSONL, JSON, TXT, MD, EML)...",
            height=34,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            text_color=TEXT_PRIMARY
        )
        self.entry_miner_file.pack(side="right", fill="x", expand=True, padx=(8, 0))
        btn_browse_miner_file = ctk.CTkButton(
            self.frame_mode_file,
            text="סייר קבצים",
            width=110,
            height=34,
            corner_radius=8,
            fg_color="#0b1526",
            border_width=1,
            border_color="#1d4ed8",
            hover_color="#1e40af",
            text_color="#ffffff",
            command=self.on_browse_chat_file
        )
        btn_browse_miner_file.pack(side="left")

        # 3. Folder Pick Frame (Entire Folder Batch)
        self.frame_mode_folder = ctk.CTkFrame(self.miner_inputs_container, fg_color="transparent")
        self.entry_miner_folder = ctk.CTkEntry(
            self.frame_mode_folder,
            placeholder_text="בחר תיקייה לסריקה של כל קובצי השיחות והמיילים שבה...",
            height=34,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            text_color=TEXT_PRIMARY
        )
        self.entry_miner_folder.pack(side="right", fill="x", expand=True, padx=(8, 0))
        btn_browse_miner_folder = ctk.CTkButton(
            self.frame_mode_folder,
            text="סייר תיקיות",
            width=110,
            height=34,
            corner_radius=8,
            fg_color="#0b1526",
            border_width=1,
            border_color="#1d4ed8",
            hover_color="#1e40af",
            text_color="#ffffff",
            command=self.on_browse_chat_folder
        )
        btn_browse_miner_folder.pack(side="left")

        # 4. Email Archive & Threads Frame
        self.frame_mode_email = ctk.CTkFrame(self.miner_inputs_container, fg_color="transparent")

        em_top_row = ctk.CTkFrame(self.frame_mode_email, fg_color="transparent")
        em_top_row.pack(fill="x", pady=(0, 4))
        self.entry_miner_email = ctk.CTkEntry(
            em_top_row,
            placeholder_text="בחר קובץ מייל (.eml)...",
            height=34,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            text_color=TEXT_PRIMARY
        )
        self.entry_miner_email.pack(side="right", fill="x", expand=True, padx=(8, 0))
        btn_browse_miner_email = ctk.CTkButton(
            em_top_row,
            text="סייר קבצים (.eml)",
            width=140,
            height=34,
            corner_radius=8,
            fg_color="#0b1526",
            border_width=1,
            border_color="#1d4ed8",
            hover_color="#1e40af",
            text_color="#ffffff",
            command=self.on_browse_email_file
        )
        btn_browse_miner_email.pack(side="left")

        ctk.CTkLabel(
            self.frame_mode_email,
            text="או הדבק כאן תוכן התכתבות או שרשור מיילים",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=TEXT_SECONDARY
        ).pack(anchor="e", pady=(4, 2))

        self.txt_miner_email = ctk.CTkTextbox(
            self.frame_mode_email,
            height=75,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.txt_miner_email.pack(fill="x")

        # 5. Paste Text Frame
        self.frame_mode_paste = ctk.CTkFrame(self.miner_inputs_container, fg_color="transparent")
        self.txt_miner_paste = ctk.CTkTextbox(
            self.frame_mode_paste,
            height=85,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.txt_miner_paste.pack(fill="x")

        # Action Button Row
        act_row = ctk.CTkFrame(box_src, fg_color="transparent")
        act_row.pack(fill="x", padx=14, pady=(6, 12))

        self.btn_run_miner = ctk.CTkButton(
            act_row,
            text="חלץ תובנות וזיכרונות ✨",
            fg_color="#831843",
            hover_color="#9f1239",
            border_width=1,
            border_color="#f43f5e",
            text_color="#ffffff",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.on_run_chat_miner
        )
        self.btn_run_miner.pack(side="right")

        self.lbl_miner_status = ctk.CTkLabel(
            act_row,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_PRIMARY
        )
        self.lbl_miner_status.pack(side="right", padx=12)

        # Target Profile for Extracted Memories
        profile_names = list(memory_hub.get_profiles().keys())
        ctk.CTkLabel(
            act_row,
            text="פרופיל יעד",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY
        ).pack(side="left", padx=(0, 6))

        self.combo_miner_profile = ctk.CTkComboBox(
            act_row,
            values=profile_names,
            width=130,
            height=32,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        try:
            self.combo_miner_profile._entry.configure(justify="right")
        except Exception:
            pass
        self.combo_miner_profile.pack(side="left")
        self.combo_miner_profile.set(memory_hub.load_db().get("currentProfile", "default"))

        # Gemini Model Selector for Chat/Email Mining
        default_miner_model = memory_hub.load_db().get("settings", {}).get("defaultGeminiModel", "פלאש לאסט")
        ctk.CTkLabel(
            act_row,
            text="מודל עבודה",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY
        ).pack(side="left", padx=(10, 4))

        self.combo_miner_model = ctk.CTkComboBox(
            act_row,
            values=["פלאש לייט לאסט", "פלאש לאסט", "פרו לאסט"],
            width=130,
            height=32,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        try:
            self.combo_miner_model._entry.configure(justify="right")
        except Exception:
            pass
        self.combo_miner_model.pack(side="left")
        self.combo_miner_model.set(default_miner_model)

        # Results Bar
        res_bar = ctk.CTkFrame(p, fg_color="transparent")
        res_bar.pack(fill="x", pady=(4, 6))

        self.lbl_miner_results_title = ctk.CTkLabel(
            res_bar,
            text="הצעות לזיכרון הקבוע",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=TEXT_PRIMARY
        )
        self.lbl_miner_results_title.pack(side="right")

        self.btn_miner_batch_add = ctk.CTkButton(
            res_bar,
            text="אשר והוסף את כל ההצעות",
            fg_color="#062e24",
            hover_color="#064e3b",
            border_width=1,
            border_color="#059669",
            text_color="#ffffff",
            height=30,
            corner_radius=8,
            state="disabled",
            command=self.on_batch_add_miner_suggestions
        )
        self.btn_miner_batch_add.pack(side="left")

        # Suggestions Scrollable Frame
        self.scroll_miner_results = ctk.CTkScrollableFrame(p, corner_radius=12, fg_color=GLASS_BG_MAIN)
        self.scroll_miner_results.pack(fill="both", expand=True, pady=(0, 4))

        # Initial load of discovered chats
        self.on_refresh_discovered_chats()
        self.render_miner_suggestions()

    def on_chat_miner_mode_change(self, mode):
        self.frame_mode_discovered.pack_forget()
        self.frame_mode_file.pack_forget()
        self.frame_mode_folder.pack_forget()
        self.frame_mode_email.pack_forget()
        self.frame_mode_paste.pack_forget()

        if "תוכנות" in mode:
            self.frame_mode_discovered.pack(fill="x")
        elif "קובץ" in mode:
            self.frame_mode_file.pack(fill="x")
        elif "תיקייה" in mode:
            self.frame_mode_folder.pack(fill="x")
        elif "מיילים" in mode:
            self.frame_mode_email.pack(fill="x")
        else:
            self.frame_mode_paste.pack(fill="x")

    def on_change_miner_app(self, app_name):
        self.on_refresh_discovered_chats()

    def on_refresh_discovered_chats(self):
        app_name = self.combo_miner_app.get() if hasattr(self, "combo_miner_app") else "Google Antigravity"
        self.discovered_chats_data = chat_miner.discover_chats(app_name=app_name, max_results=30)
        if self.discovered_chats_data:
            opts = [f"[{c['time_str']}] {c['title']} ({c['size_kb']} KB)" for c in self.discovered_chats_data]
            self.combo_discovered_chats.configure(values=opts)
            self.combo_discovered_chats.set(opts[0])
            self.lbl_miner_status.configure(text=f"אותרו {len(self.discovered_chats_data)} שיחות במחשב עבור {app_name}")
        else:
            self.combo_discovered_chats.configure(values=["לא אותרו שיחות במחשב עבור תוכנה זו"])
            self.combo_discovered_chats.set("לא אותרו שיחות במחשב עבור תוכנה זו")
            self.lbl_miner_status.configure(text=f"לא אותרו שיחות במחשב עבור {app_name}")

    def on_browse_chat_file(self):
        fp = filedialog.askopenfilename(
            title="בחר קובץ תמליל שיחה",
            filetypes=[
                ("קובצי שיחה ומיילים", "*.jsonl;*.json;*.txt;*.md;*.eml"),
                ("כל הקבצים", "*.*")
            ]
        )
        if fp:
            self.entry_miner_file.delete(0, "end")
            self.entry_miner_file.insert(0, fp)

    def on_browse_chat_folder(self):
        folder = filedialog.askdirectory(title="בחר תיקיית שיחות או מיילים לסריקה")
        if folder:
            self.entry_miner_folder.delete(0, "end")
            self.entry_miner_folder.insert(0, folder)

    def on_browse_email_file(self):
        fp = filedialog.askopenfilename(
            title="בחר קובץ מייל (.eml)",
            filetypes=[
                ("קובצי אימייל", "*.eml;*.msg;*.txt"),
                ("כל הקבצים", "*.*")
            ]
        )
        if fp:
            self.entry_miner_email.delete(0, "end")
            self.entry_miner_email.insert(0, fp)

    def on_run_chat_miner(self):
        mode = self.seg_miner_mode.get()
        chat_text = ""
        source_type = "chat"

        if "תוכנות" in mode:
            if not self.discovered_chats_data:
                messagebox.showwarning("אין שיחות", "לא אותרו שיחות במחשב עבור התוכנה שנבחרה.")
                return
            sel_str = self.combo_discovered_chats.get()
            idx = 0
            opts = [f"[{c['time_str']}] {c['title']} ({c['size_kb']} KB)" for c in self.discovered_chats_data]
            if sel_str in opts:
                idx = opts.index(sel_str)
            target_path = self.discovered_chats_data[idx]["path"]
            chat_text = chat_miner.parse_raw_or_file_chat(target_path)

        elif "קובץ" in mode:
            fp = self.entry_miner_file.get().strip()
            if not fp or not os.path.isfile(fp):
                messagebox.showwarning("קובץ לא קיים", "נא לבחור קובץ קיים.")
                return
            chat_text = chat_miner.parse_raw_or_file_chat(fp)

        elif "תיקייה" in mode:
            folder = self.entry_miner_folder.get().strip()
            if not folder or not os.path.isdir(folder):
                messagebox.showwarning("תיקייה לא קיימת", "נא לבחור תיקייה קיימת לסריקה.")
                return
            chat_text = chat_miner.parse_folder_chats(folder)

        elif "מיילים" in mode:
            source_type = "email"
            fp = self.entry_miner_email.get().strip()
            if fp and os.path.isfile(fp):
                chat_text = chat_miner.parse_email_file(fp)
            else:
                pasted_em = self.txt_miner_email.get("1.0", "end").strip()
                if pasted_em:
                    chat_text = chat_miner.parse_raw_email(pasted_em)
                else:
                    messagebox.showwarning("מייל חסר", "נא לבחור קובץ .eml או להדביק תוכן מייל בתיבה.")
                    return

        else:
            chat_text = self.txt_miner_paste.get("1.0", "end").strip()
            if not chat_text:
                messagebox.showwarning("טקסט חסר", "נא להדביק תוכן שיחה בתיבה.")
                return

        if not chat_text or len(chat_text.strip()) < 15:
            messagebox.showwarning("תוכן קצר מדי", "תוכן השיחה או המייל קצר מדי להפקת זיכרונות.")
            return

        self.btn_run_miner.configure(state="disabled", text="מנתח תוכן... ⏳")
        self.lbl_miner_status.configure(text="מחלץ תובנות וחוקים מהתוכן...")
        self.set_status("מנתח את תוכן השיחה/המייל להפקת זיכרונות...")

        chosen_model = self.combo_miner_model.get() if hasattr(self, "combo_miner_model") else None

        def worker():
            ok, res = gemini_optimizer.extract_memories_from_chat(chat_text, source_type=source_type, model=chosen_model)
            self.after(0, lambda: self.on_chat_miner_done(ok, res))

        self.run_async(worker)

    def on_chat_miner_done(self, ok, res):
        self.btn_run_miner.configure(state="normal", text="חלץ תובנות וזיכרונות ✨")
        if not ok:
            messagebox.showerror("שגיאת ניתוח", f"לא ניתן היה לחלץ זיכרונות:\n{res}")
            self.lbl_miner_status.configure(text="שגיאה בניתוח התוכן")
            return

        self.current_miner_suggestions = res if isinstance(res, list) else []
        count = len(self.current_miner_suggestions)
        self.lbl_miner_status.configure(text=f"נמצאו {count} הצעות חדשות!")
        self.set_status(f"ניתוח התוכן הושלם. אותרו {count} הצעות לזיכרון.")
        self.render_miner_suggestions()

    def render_miner_suggestions(self):
        for w in self.scroll_miner_results.winfo_children():
            w.destroy()

        count = len(self.current_miner_suggestions)
        self.lbl_miner_results_title.configure(text=f"הצעות לזיכרון הקבוע ({count}):")
        self.btn_miner_batch_add.configure(state="normal" if count > 0 else "disabled")

        if count == 0:
            empty_box = ctk.CTkFrame(self.scroll_miner_results, fg_color="transparent")
            empty_box.pack(pady=40)
            ctk.CTkLabel(
                empty_box,
                text="טרם נותחה שיחה או שלא אותרו כללים חדשים.\nבחר מקור לניתוח (תוכנת AI, קובץ, תיקייה או מייל) ולחץ על 'חלץ תובנות וזיכרונות ✨'.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=TEXT_PRIMARY,
                justify="center"
            ).pack()
            return

        cat_names = {
            "facts": ("עובדה קבועה 📌", "#38bdf8"),
            "commands": ("פקודת ביצוע ⚡", "#f59e0b"),
            "constraints": ("איסור מחייב ⛔", "#f43f5e"),
            "styles": ("סגנון מענה 🎨", "#a855f7"),
            "instructions": ("הוראה מותנית 🛡️", "#10b981")
        }

        cat_pip_colors = {
            "facts": "#38bdf8",
            "commands": "#f59e0b",
            "constraints": "#f43f5e",
            "styles": "#a855f7",
            "instructions": "#10b981"
        }

        for idx, sug in enumerate(self.current_miner_suggestions):
            cat = sug.get("category", "facts")
            badge_title, badge_color = cat_names.get(cat, ("כלל", "#38bdf8"))
            confidence = int(sug.get("confidence", 0.9) * 100)
            data = sug.get("data", {})

            card = self.create_glass_card(self.scroll_miner_results, corner_radius=14)
            card.pack(fill="x", pady=4, padx=4)

            # Glowing Category Pip on Right
            pip_color = cat_pip_colors.get(cat, "#38bdf8")
            pip = ctk.CTkFrame(card, width=4, height=48, corner_radius=2, fg_color=pip_color)
            pip.pack(side="right", padx=(0, 10), pady=8)

            main_c = ctk.CTkFrame(card, fg_color="transparent")
            main_c.pack(side="right", fill="both", expand=True, padx=(8, 4), pady=6)

            # Top Header Row in Card
            c_header = ctk.CTkFrame(main_c, fg_color="transparent")
            c_header.pack(fill="x", pady=(2, 4))

            self.create_glass_badge(c_header, badge_title, "cyan" if cat=="facts" else ("emerald" if cat=="instructions" else ("purple" if cat=="styles" else "default"))).pack(side="right", padx=(6, 0))

            title_lbl = ctk.CTkLabel(
                c_header,
                text=sug.get("title", "הצעה"),
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=TEXT_PRIMARY
            )
            title_lbl.pack(side="right", padx=(4, 0))

            conf_lbl = ctk.CTkLabel(
                c_header,
                text=f"{confidence}% ביטחון",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=TEXT_PRIMARY
            )
            conf_lbl.pack(side="left")

            # Data Fields Display (Frosted Inset)
            content_frame = ctk.CTkFrame(main_c, fg_color=GLASS_INPUT, corner_radius=8, border_width=1, border_color=GLASS_INPUT_BORDER)
            content_frame.pack(fill="x", pady=4)

            content_text = ""
            if cat == "facts":
                content_text = f"שם המידע: {data.get('name', '')}\nערך / תוכן: {data.get('value', '')}"
            elif cat == "commands":
                content_text = f"שם פקודה: {data.get('name', '')}\nפירוט: {data.get('details', '')}\nבאיזה מקרה לבצע: {data.get('trigger_case', '')}"
            elif cat == "constraints":
                content_text = f"איסור מחייב: {data.get('constraint', '')}\nהנחיה חלופית או נימוק: {data.get('alternative_or_why', '')}"
            elif cat == "styles":
                content_text = f"היבט הסגנון: {data.get('aspect', '')}\nהנחיית הסגנון: {data.get('instruction', '')}"
            elif cat == "instructions":
                content_text = f"הוראה: {data.get('instruction', '')}\nמתי ליישם: {data.get('when_to_apply', '')}"

            ctk.CTkLabel(
                content_frame,
                text=content_text,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=TEXT_SECONDARY,
                justify="right",
                anchor="e",
                wraplength=580
            ).pack(fill="x", padx=10, pady=8)

            # Reason & Quote from Chat
            if sug.get("quote") or sug.get("reason"):
                rq_frame = ctk.CTkFrame(main_c, fg_color="transparent")
                rq_frame.pack(fill="x", pady=2)
                if sug.get("quote"):
                    ctk.CTkLabel(
                        rq_frame,
                        text=f"מתוך השיחה: \"{sug.get('quote')}\"",
                        font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
                        text_color=TEXT_PRIMARY,
                        anchor="e",
                        justify="right",
                        wraplength=580
                    ).pack(anchor="e")
                if sug.get("reason"):
                    ctk.CTkLabel(
                        rq_frame,
                        text=f"נימוק: {sug.get('reason')}",
                        font=ctk.CTkFont(family="Segoe UI", size=11),
                        text_color=TEXT_PRIMARY,
                        anchor="e",
                        justify="right",
                        wraplength=580
                    ).pack(anchor="e", pady=(2, 0))

            # Bottom Actions Row: Scope + Add Button + Dismiss Button
            act_box = ctk.CTkFrame(main_c, fg_color="transparent")
            act_box.pack(fill="x", pady=(6, 4))

            combo_sc = ctk.CTkComboBox(act_box, values=self.get_scope_options(), width=140, height=30, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY, font=ctk.CTkFont(family="Segoe UI", size=10))
            try:
                combo_sc._entry.configure(justify="right")
            except Exception:
                pass
            combo_sc.pack(side="right", padx=(0, 6))

            combo_ai = ctk.CTkComboBox(act_box, values=self.get_ai_target_options(), width=150, height=30, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY, font=ctk.CTkFont(family="Segoe UI", size=10), state="readonly", command=lambda v, c=None: None)
            combo_ai.configure(command=lambda v, c=combo_ai: self.check_custom_ai_selection(v, c))
            combo_ai.set("כל המודלים")
            combo_ai.pack(side="right", padx=(0, 8))

            btn_add = ctk.CTkButton(
                act_box,
                text="אשר והוסף לזיכרון ➕",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color="#062e24",
                hover_color="#064e3b",
                border_width=1,
                border_color="#059669",
                text_color="#ffffff",
                height=30,
                corner_radius=8,
                command=lambda s=sug, c_sc=combo_sc, c_ai=combo_ai, cf=card: self.on_add_single_miner_suggestion(s, c_sc, c_ai, cf)
            )
            btn_add.pack(side="right", padx=(0, 6))

            btn_dismiss = self.create_card_action_button(act_box, "התעלם ✖", lambda s=sug, cf=card: self.on_dismiss_miner_suggestion(s, cf), "del", width=70, height=30)
            btn_dismiss.pack(side="left")

    def on_add_single_miner_suggestion(self, sug, combo_sc, combo_ai, card_frame):
        if hasattr(self, "combo_miner_profile"):
            target_p = self.combo_miner_profile.get()
            if target_p and target_p in memory_hub.get_profiles():
                memory_hub.set_current_profile(target_p)

        cat = sug.get("category", "facts")
        data = sug.get("data", {})
        sc_val = combo_sc.get()
        scope = "global" if "גלובלי" in sc_val else sc_val

        target_ais = self.resolve_target_ais(combo_ai)

        if cat == "facts":
            memory_hub.add_fact(data.get("name", "מידע"), data.get("value", ""), scope=scope, target_ais=target_ais)
        elif cat == "commands":
            memory_hub.add_command(data.get("name", "פקודה"), data.get("details", ""), data.get("trigger_case", ""), scope=scope, target_ais=target_ais)
        elif cat == "constraints":
            memory_hub.add_constraint(data.get("constraint", "איסור"), data.get("alternative_or_why", ""), scope=scope, target_ais=target_ais)
        elif cat == "styles":
            memory_hub.add_style(data.get("aspect", "סגנון"), data.get("instruction", ""), scope=scope, target_ais=target_ais)
        elif cat == "instructions":
            memory_hub.add_instruction(data.get("instruction", "הוראה"), data.get("when_to_apply", ""), scope=scope, target_ais=target_ais)

        if sug in self.current_miner_suggestions:
            self.current_miner_suggestions.remove(sug)

        card_frame.destroy()
        count = len(self.current_miner_suggestions)
        self.lbl_miner_results_title.configure(text=f"הצעות לזיכרון הקבוע ({count}):")
        self.btn_miner_batch_add.configure(state="normal" if count > 0 else "disabled")

        self.refresh_all_views()
        self.set_status(f"הפריט '{sug.get('title')}' נוסף בהצלחה לזיכרון הקבוע והושתל!")

    def on_dismiss_miner_suggestion(self, sug, card_frame):
        if sug in self.current_miner_suggestions:
            self.current_miner_suggestions.remove(sug)
        card_frame.destroy()
        count = len(self.current_miner_suggestions)
        self.lbl_miner_results_title.configure(text=f"הצעות לזיכרון הקבוע ({count}):")
        self.btn_miner_batch_add.configure(state="normal" if count > 0 else "disabled")

    def on_batch_add_miner_suggestions(self):
        if not self.current_miner_suggestions:
            return

        if hasattr(self, "combo_miner_profile"):
            target_p = self.combo_miner_profile.get()
            if target_p and target_p in memory_hub.get_profiles():
                memory_hub.set_current_profile(target_p)

        added_count = 0
        for sug in list(self.current_miner_suggestions):
            cat = sug.get("category", "facts")
            data = sug.get("data", {})
            scope = "global"

            if cat == "facts":
                memory_hub.add_fact(data.get("name", "מידע"), data.get("value", ""), scope=scope)
            elif cat == "commands":
                memory_hub.add_command(data.get("name", "פקודה"), data.get("details", ""), data.get("trigger_case", ""), scope=scope)
            elif cat == "constraints":
                memory_hub.add_constraint(data.get("constraint", "איסור"), data.get("alternative_or_why", ""), scope=scope)
            elif cat == "styles":
                memory_hub.add_style(data.get("aspect", "סגנון"), data.get("instruction", ""), scope=scope)
            elif cat == "instructions":
                memory_hub.add_instruction(data.get("instruction", "הוראה"), data.get("when_to_apply", ""), scope=scope)

            added_count += 1

        self.current_miner_suggestions.clear()
        self.render_miner_suggestions()
        self.refresh_all_views()
        messagebox.showinfo("הוספה הושלמה", f"נוספו בהצלחה {added_count} פריטי זיכרון חדשים ונשתלו בכל הפרויקטים!")
        self.set_status(f"נוספו {added_count} פריטי זיכרון חדשים בהצלחה")


    # =========================================================================
    # 8. PAGE: PROJECTS PATH MANAGER
    # =========================================================================
    # =========================================================================
    # SMART AI LIVE SIMULATOR & TESTER (סימולטור חכם לבדיקת מענה AI)
    # =========================================================================
    def build_page_simulator(self):
        p = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["simulator"] = p

        self.create_page_header(p, "סימולטור ובדיקת מענה בזמן אמת", "בדוק באופן מיידי כיצד המודלים מגיבים לשאלותיך על בסיס הזיכרון והכללים שהוגדרו")

        # Query Box
        box = self.create_glass_card(p, corner_radius=14)
        box.pack(fill="x", pady=(0, 12))

        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=(14, 6))

        f_ai = ctk.CTkFrame(r1, fg_color="transparent")
        f_ai.pack(side="right", padx=(10, 0))
        ctk.CTkLabel(f_ai, text="מודל לבדיקה", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.combo_sim_ai = ctk.CTkComboBox(f_ai, values=["Google Antigravity", "Claude Desktop", "Cursor", "Windsurf", "GitHub Copilot"], width=170, height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY)
        try:
            self.combo_sim_ai._entry.configure(justify="right")
        except Exception:
            pass
        self.combo_sim_ai.pack(pady=(2, 0))

        f_scope = ctk.CTkFrame(r1, fg_color="transparent")
        f_scope.pack(side="right", padx=(10, 0))
        ctk.CTkLabel(f_scope, text="סביבת עבודה (פרויקט)", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.combo_sim_scope = ctk.CTkComboBox(f_scope, values=self.get_scope_options(), width=170, height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY)
        try:
            self.combo_sim_scope._entry.configure(justify="right")
        except Exception:
            pass
        self.combo_sim_scope.pack(pady=(2, 0))

        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(6, 10))

        ctk.CTkLabel(r2, text="שאל שאלה לבדיקת הזיכרון", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e")

        q_row = ctk.CTkFrame(r2, fg_color="transparent")
        q_row.pack(fill="x", pady=(2, 0))

        self.entry_sim_query = ctk.CTkEntry(q_row, placeholder_text="למשל: מה הכתובת של האתר שלי? או: איך לחתום בסוף מייל?", height=36, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
        self.entry_sim_query.pack(side="right", fill="x", expand=True, padx=(8, 0))
        self.entry_sim_query.bind("<Return>", lambda e: self.on_run_simulation())

        btn_run_sim = ctk.CTkButton(q_row, text="בדוק מענה", width=120, height=36, corner_radius=8, fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), command=self.on_run_simulation)
        btn_run_sim.pack(side="left")

        # Quick Preset Buttons
        p_row = ctk.CTkFrame(box, fg_color="transparent")
        p_row.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(p_row, text="שאלות מהירות", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_MUTED).pack(side="right", padx=(8, 0))
        for q_text in ["מה הכתובת של האתר שלי?", "זה לעסקים, תנסח לי מייל", "מצב קוד: כתוב פונקציה", "איך לחתום בסוף מייל?"]:
            ctk.CTkButton(p_row, text=q_text, height=24, font=ctk.CTkFont(family="Segoe UI", size=10), fg_color=("#eff6ff", "#1e293b"), text_color=TEXT_PRIMARY, border_width=1, border_color=("#bfdbfe", "#334155"), hover_color=("#dbeafe", "#2d3748"), corner_radius=6, command=lambda qt=q_text: [self.entry_sim_query.delete(0, 'end'), self.entry_sim_query.insert(0, qt), self.on_run_simulation()]).pack(side="right", padx=3)

        # Simulation Results Card
        res_card = self.create_glass_card(p, corner_radius=14)
        res_card.pack(fill="both", expand=True, pady=(0, 8))

        # Result Header with Stats
        rh = ctk.CTkFrame(res_card, fg_color="transparent")
        rh.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(rh, text="מענה המודל המדויק", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(side="right")

        self.lbl_sim_status = ctk.CTkLabel(rh, text="ממתין לבדיקה", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_MUTED)
        self.lbl_sim_status.pack(side="left")

        self.txt_sim_result = ctk.CTkTextbox(res_card, height=130, font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_PRIMARY, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, wrap="word")
        self.txt_sim_result.pack(fill="x", padx=16, pady=(0, 10))

        # Diagnostic Badges Container
        self.f_diag = ctk.CTkFrame(res_card, fg_color="transparent")
        self.f_diag.pack(fill="x", padx=16, pady=(0, 10))

        # Live Gemini Test Button Row
        btn_live_row = ctk.CTkFrame(res_card, fg_color="transparent")
        btn_live_row.pack(fill="x", padx=16, pady=(0, 12))

        self.btn_live_gemini = ctk.CTkButton(
            btn_live_row,
            text="בדיקה ישירה מול מודל ענן (Gemini)",
            height=32,
            corner_radius=8,
            fg_color="#4f46e5",
            hover_color="#4338ca",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.on_run_live_gemini_test
        )
        self.btn_live_gemini.pack(side="right")

        default_sim_model = memory_hub.load_db().get("settings", {}).get("defaultGeminiModel", "פלאש לאסט")
        ctk.CTkLabel(
            btn_live_row,
            text="מודל נבחר",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY
        ).pack(side="right", padx=(10, 4))

        self.combo_sim_model = ctk.CTkComboBox(
            btn_live_row,
            values=["פלאש לייט לאסט", "פלאש לאסט", "פרו לאסט"],
            width=130,
            height=32,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        try:
            self.combo_sim_model._entry.configure(justify="right")
        except Exception:
            pass
        self.combo_sim_model.pack(side="right")
        self.combo_sim_model.set(default_sim_model)

    def on_run_simulation(self):
        query = self.entry_sim_query.get().strip()
        if not query:
            return

        self.txt_sim_result.configure(state="normal")
        self.txt_sim_result.delete("1.0", "end")

        for w in self.f_diag.winfo_children():
            w.destroy()

        # 1. Check Dynamic Modes (Triggers)
        profiles = memory_hub.get_profiles()
        matched_mode = None
        matched_trigger = None
        for pid, pinfo in profiles.items():
            triggers = pinfo.get("trigger_keywords", [])
            for trig in triggers:
                if trig.lower() in query.lower():
                    matched_mode = (pid, pinfo)
                    matched_trigger = trig
                    break
            if matched_mode:
                break

        if matched_mode:
            pid, pinfo = matched_mode
            pname = pinfo.get("name", pid)
            pdata = pinfo.get("data", {})
            lines = [f"🎯 זוהה מצב שיחה דינמי: {pname} (מילת הפעלה: '{matched_trigger}')\n"]
            lines.append("מעבר מיידי להחלת חוקי המצב בשיחה:")
            for st in pdata.get("styles", []):
                if st.get("active", True):
                    lines.append(f"• טון וסגנון: {st.get('aspect')}: {st.get('instruction')}")
            for cmd in pdata.get("commands", []):
                if cmd.get("active", True):
                    lines.append(f"• פקודה/חתימה: {cmd.get('name')}: {cmd.get('details')}")
            for f in pdata.get("facts", []):
                if f.get("active", True):
                    lines.append(f"• עובדה ייעודית: {f.get('name')}: {f.get('value')}")
            for c in pdata.get("constraints", []):
                if c.get("active", True):
                    lines.append(f"• מגבלה: {c.get('constraint')}")
            for inst in pdata.get("instructions", []):
                if inst.get("active", True):
                    lines.append(f"• הוראה: {inst.get('instruction')}")

            self.txt_sim_result.insert("1.0", "\n".join(lines))
            self.lbl_sim_status.configure(text=f"מצב '{pname}' הופעל אוטומטית לפי מילת מפתח")
            self.create_glass_badge(self.f_diag, f"מצב פעיל: {pname}", "emerald").pack(side="right", padx=(0, 6))
            self.create_glass_badge(self.f_diag, f"טריגר: {matched_trigger}", "cyan").pack(side="right", padx=(0, 6))
            self.create_glass_badge(self.f_diag, "החלפת פרסונה חכמה בזמן אמת", "purple").pack(side="right")
            self.txt_sim_result.configure(state="disabled")
            return

        p_data = memory_hub.get_current_profile_data()
        facts = p_data.get("facts", [])
        commands = p_data.get("commands", [])

        matched_fact = None
        for f in facts:
            if not f.get("active", True): continue
            name = f.get("name", "").lower()
            if name in query.lower() or any(w in query.lower() for w in name.split() if len(w) > 2):
                matched_fact = f
                break

        matched_cmd = None
        for c in commands:
            if not c.get("active", True): continue
            if "חתום" in query or "חתימה" in query or "בסוף" in query:
                matched_cmd = c
                break

        if matched_fact:
            val = matched_fact.get('value')
            if "אתר" in matched_fact.get("name", ""):
                ans = f"כתובת האתר שלך היא:\n{val}"
            else:
                ans = f"לפי הזיכרון הקבוע שלי, התשובה היא:\n{val}"
            self.txt_sim_result.insert("1.0", ans)
            self.lbl_sim_status.configure(text="מענה מיידי מתוך הזיכרון (0.01 שניות)")

            self.create_glass_badge(self.f_diag, "קריאות לכלים (Tool Calls): 0 (סריקות קבצים נחסמו)", "emerald").pack(side="right", padx=(0, 6))
            self.create_glass_badge(self.f_diag, f"עובדה פעילה: {matched_fact.get('name')}", "cyan").pack(side="right", padx=(0, 6))
            self.create_glass_badge(self.f_diag, "איסור שלילי: מענה ישיר ללא כלי סריקה", "rose").pack(side="right")
        elif matched_cmd:
            ans = f"הנחיית ביצוע מופעלת: {matched_cmd.get('name')}\nפעולה: {matched_cmd.get('details')}"
            self.txt_sim_result.insert("1.0", ans)
            self.lbl_sim_status.configure(text="פקודת ביצוע זוהתה והופעלה")
            self.create_glass_badge(self.f_diag, f"פקודה: {matched_cmd.get('name')}", "amber").pack(side="right", padx=(0, 6))
            self.create_glass_badge(self.f_diag, "קריאות לכלים: 0", "emerald").pack(side="right")
        else:
            self.txt_sim_result.insert("1.0", f"השאלה '{query}' אינה תואמת עובדה קבועה קיימת בזיכרון.\nכדי שהמודל יידע לענות עליה מיידית ללא חיפוש במחשב, מומלץ להוסיף אותה בעמוד 'עובדות ונתונים'.")
            self.lbl_sim_status.configure(text="לא זוהתה עובדה תואמת בזיכרון")
            self.create_glass_badge(self.f_diag, "נדרשת הוספת עובדה בזיכרון", "rose").pack(side="right")

        self.txt_sim_result.configure(state="disabled")

    def on_run_live_gemini_test(self):
        query = self.entry_sim_query.get().strip()
        if not query:
            messagebox.showwarning("שאלה ריקה", "אנא הזן שאלה לבדיקה.")
            return

        db = memory_hub.load_db()
        api_key = db.get("settings", {}).get("geminiApiKey", "")
        if not api_key:
            messagebox.showinfo("נדרש מפתח Gemini", "כדי לבדוק מול Google Gemini Live בענן, אנא הזן מפתח API במסך 'הגדרות מערכת'.")
            return

        self.btn_live_gemini.configure(state="disabled", text="⏳ שואל את Gemini Live...")
        self.lbl_sim_status.configure(text="שולח שאילתה אל Gemini API...")

        chosen_model = self.combo_sim_model.get() if hasattr(self, "combo_sim_model") else None

        def worker():
            sys_prompt = memory_hub.generate_prompt_markdown()
            full_prompt = f"{sys_prompt}\n\nUser question: {query}\nAnswer directly based on your persistent memory:"
            ok, res = gemini_optimizer.call_gemini(full_prompt, api_key=api_key, model=chosen_model)

            def update_ui():
                self.btn_live_gemini.configure(state="normal", text="שאל מודל חי (Google Gemini Live API)")
                self.txt_sim_result.configure(state="normal")
                self.txt_sim_result.delete("1.0", "end")
                if ok:
                    self.txt_sim_result.insert("1.0", res)
                    self.lbl_sim_status.configure(text="מענה חי התקבל בהצלחה מ-Gemini API!")
                    for w in self.f_diag.winfo_children(): w.destroy()
                    self.create_glass_badge(self.f_diag, f"מענה חי: {chosen_model or 'מודל חי'}", "purple").pack(side="right", padx=(0, 6))
                    self.create_glass_badge(self.f_diag, "קריאות לכלים: 0", "emerald").pack(side="right")
                else:
                    self.txt_sim_result.insert("1.0", f"שגיאת תקשורת עם Gemini: {res}")
                    self.lbl_sim_status.configure(text="שגיאה במענה חי")
                self.txt_sim_result.configure(state="disabled")

            self.after(0, update_ui)

        self.run_async(worker)

    def build_page_paths(self):
        p = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["paths"] = p

        self.create_page_header(p, "ניהול נתיבי פרויקטים לסנכרון", "סריקה וסנכרון של קובצי הכללים בכל סביבות הפיתוח והתיקיות במחשב")

        bar = self.create_glass_card(p, corner_radius=14)
        bar.pack(fill="x", pady=(0, 10))

        btn_row = ctk.CTkFrame(bar, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=12)

        btn_browse = ctk.CTkButton(
            btn_row,
            text="➕ בחר תיקייה נוספת...",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#062e24",
            hover_color="#064e3b",
            border_width=1,
            border_color="#059669",
            text_color="#ffffff",
            height=34,
            corner_radius=8,
            command=self.on_browse_folder
        )
        btn_browse.pack(side="right", padx=6)

        btn_rescan = ctk.CTkButton(
            btn_row,
            text="🔄 סרוק פרויקטים חדשים במחשב",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0c1628",
            hover_color="#162544",
            border_width=1,
            border_color="#1e3a8a",
            text_color="#ffffff",
            height=34,
            corner_radius=8,
            command=self.on_rescan_projects
        )
        btn_rescan.pack(side="right", padx=6)

        filter_bar = ctk.CTkFrame(p, fg_color="transparent")
        filter_bar.pack(fill="x", pady=(2, 6))

        self.lbl_paths_count = ctk.CTkLabel(filter_bar, text="", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY)
        self.lbl_paths_count.pack(side="right")

        self.scroll_paths = ctk.CTkScrollableFrame(p, corner_radius=12, fg_color=GLASS_BG_MAIN)
        self.scroll_paths.pack(fill="both", expand=True, pady=(0, 4))

    def render_global_targets(self, parent):
        """
        The user-level rule files, shown above the project list because they are what makes
        a directive apply everywhere - a project folder is the exception, not the rule.
        """
        try:
            targets = memory_hub.get_global_targets()
        except Exception as e:
            print(f"[global targets] {e}")
            return

        installed = [t for t in targets if t["installed"]]

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(2, 4), padx=4)
        ctk.CTkLabel(header, text="יעדים גלובליים (חלים על כל הפרויקטים)",
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="right")
        ctk.CTkLabel(header, text=f"{len(installed)} כלים מותקנים",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=TEXT_SECONDARY).pack(side="left")

        db_settings = memory_hub.load_db().get("settings", {})
        disabled_keys = set(db_settings.get("disabledGlobalTargets", []))

        for t in targets:
            row = self.create_glass_card(parent, corner_radius=12)
            row.pack(fill="x", pady=3, padx=4)

            if t["installed"]:
                sw_var = ctk.BooleanVar(value=t["key"] not in disabled_keys)
                sw = ctk.CTkSwitch(row, text="פעיל", variable=sw_var,
                                   command=lambda k=t["key"], v=sw_var: self.on_sw_global_target(k, v))
                sw.pack(side="left", padx=(10, 6), pady=6)
                status_text, status_color = ("מסונכרן", "emerald") if t["written"] else ("ממתין לסנכרון", "amber")
            else:
                ctk.CTkLabel(row, text="לא מותקן", font=ctk.CTkFont(family="Segoe UI", size=11),
                             text_color=TEXT_MUTED).pack(side="left", padx=(12, 6), pady=6)
                status_text, status_color = ("לא רלוונטי", "default")

            self.create_glass_badge(row, status_text, status_color).pack(side="left", padx=4)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="right", fill="both", expand=True, padx=10, pady=6)
            ctk.CTkLabel(info, text=t["name"], font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                         text_color=TEXT_PRIMARY).pack(anchor="e")
            ctk.CTkLabel(info, text=t["path"], font=ctk.CTkFont(family="Segoe UI", size=10),
                         text_color=TEXT_MUTED, wraplength=520, justify="right").pack(anchor="e")
            ctk.CTkLabel(info, text=t["note"], font=ctk.CTkFont(family="Segoe UI", size=10),
                         text_color=TEXT_SECONDARY, wraplength=520, justify="right").pack(anchor="e")

        ctk.CTkLabel(parent, text="נתיבי פרויקטים (לכלים שאין להם קובץ גלובלי, או לחוקים ייעודיים לפרויקט)",
                     font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="e", pady=(14, 4), padx=8)

    def on_sw_global_target(self, key, var):
        """Enables/disables one global rules file and cleans up if it was turned off."""
        db = memory_hub.load_db()
        settings = db.setdefault("settings", {})
        disabled = set(settings.get("disabledGlobalTargets", []))

        if var.get():
            disabled.discard(key)
        else:
            disabled.add(key)

        settings["disabledGlobalTargets"] = sorted(disabled)
        memory_hub.save_db(db)

        self.set_status("מעדכן יעדים גלובליים...")

        def worker():
            res = memory_hub.inject_global_targets()
            self.after(0, lambda: self.set_status(
                f"עודכנו {len(res['written'])} קבצי חוקים גלובליים" if res["written"]
                else "היעדים הגלובליים עודכנו"))
            self.after(0, self.refresh_page_paths)

        self.run_async(worker)

    def refresh_page_paths(self):
        for w in self.scroll_paths.winfo_children(): w.destroy()
        paths = memory_hub.get_paths()
        active = len([x for x in paths if x.get("active", True)])
        self.lbl_paths_count.configure(text=f"פרויקטים: {active} פעילים להשתלה (מתוך {len(paths)})")

        self.render_global_targets(self.scroll_paths)

        for p_item in paths:
            p_path = p_item.get("path")
            p_name = p_item.get("name", os.path.basename(p_path))
            p_active = p_item.get("active", True)

            row = self.create_glass_card(self.scroll_paths, corner_radius=12)
            row.pack(fill="x", pady=3, padx=4)

            btn_del = self.create_card_action_button(row, "מחק", lambda path=p_path, name=p_name: self.on_del_path(path, name), "del", 28, 28)
            btn_del.pack(side="left", padx=(8, 4), pady=6)

            sw_var = ctk.BooleanVar(value=p_active)
            sw = ctk.CTkSwitch(row, text="פעיל", variable=sw_var, command=lambda path=p_path, v=sw_var: self.on_sw_path(path, v))
            sw.pack(side="left", padx=6)

            status_text = "פעיל להשתלה" if p_active else "⚪ מושהה"
            self.create_glass_badge(row, status_text, "emerald" if p_active else "default").pack(side="left", padx=4)

            btn_open = self.create_card_action_button(row, "פתח תיקייה", lambda pt=p_path: os.startfile(pt) if os.path.isdir(pt) else None, "edit", width=95, height=28)
            btn_open.pack(side="left", padx=4)

            # Glowing Pip on Right side
            pip = ctk.CTkFrame(row, width=4, height=44, corner_radius=2, fg_color="#10b981" if p_active else "#475569")
            pip.pack(side="right", padx=(0, 10), pady=6)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="right", fill="both", expand=True, padx=8, pady=6)
            ctk.CTkLabel(info, text=f"{p_name}", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e")
            ctk.CTkLabel(info, text=p_path, font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY).pack(anchor="e")

    def on_browse_folder(self):
        chosen = filedialog.askdirectory(title="בחר תיקיית פרויקט להשתלת זיכרון")
        if chosen:
            ok, msg = memory_hub.add_path(chosen, active=True)
            if ok:
                self.refresh_page_paths()
                self.update_stats()
                self.set_status(f"נתיב נוסף והושתל: {chosen}")
            else:
                messagebox.showinfo("הודעה", msg)

    def on_rescan_projects(self):
        newly, total = memory_hub.rescan_projects()
        self.refresh_page_paths()
        self.update_stats()
        self.set_status(f"אותרו {newly} פרויקטים חדשים. סה\"כ: {total}")
        messagebox.showinfo("סריקה הושלמה", f"אותרו ונוספו {newly} פרויקטים חדשים.\nסה\"כ נתיבים מנוהלים: {total}")

    def on_sw_path(self, path, var):
        memory_hub.toggle_path(path, var.get())
        self.update_stats()
        st = "פעיל" if var.get() else "מושהה"
        self.set_status(f"נתיב עודכן ל-{st}: {os.path.basename(path)}")

    def on_del_path(self, path, name):
        if messagebox.askyesno("הסרת נתיב", f"האם להסיר את '{name}' מרשימת ההשתלה ולנקות קובצי זיכרון?"):
            memory_hub.remove_path(path, clean_files=True)
            self.refresh_page_paths()
            self.update_stats()
            self.set_status(f"הנתיב {name} הוסר ונוקה")

    # =========================================================================
    # 7. PAGE: LIVE PREVIEW (תצוגה מקדימה מעוצבת וקוד מקור)
    # =========================================================================
    def build_page_preview(self):
        p = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.pages["preview"] = p

        self.create_page_header(
            p,
            "👁️ תצוגה מקדימה של פרומפט הזיכרון",
            "צפייה מפורטת בכל הכללים והקוד שמוזרקים בזמן אמת למודלים השונים"
        )

        top_bar = ctk.CTkFrame(p, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 10))

        # View Mode Switcher (Segmented button)
        self.seg_preview_mode = ctk.CTkSegmentedButton(
            top_bar,
            values=["תצוגה מעוצבת", "קוד Markdown מקורי"],
            command=self.on_preview_mode_change,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            selected_color="#2563eb",
            selected_hover_color=ACCENT_HOVER,
            unselected_color="#1e293b",
            unselected_hover_color="#334155",
            height=32
        )
        self.seg_preview_mode.set("תצוגה מעוצבת")
        self.seg_preview_mode.pack(side="left", padx=(0, 10))

        self.btn_copy_preview = ctk.CTkButton(
            top_bar,
            text="העתק טקסט ללוח",
            width=135,
            height=32,
            fg_color="#334155",
            hover_color="#475569",
            command=self.on_copy_preview
        )
        self.btn_copy_preview.pack(side="left")

        # Preview Target AI selector (No parentheses to prevent Tkinter BiDi reversal!)
        f_prev_ai = ctk.CTkFrame(top_bar, fg_color="transparent")
        f_prev_ai.pack(side="right", padx=0)
        ctk.CTkLabel(f_prev_ai, text="סינון לפי מודל יעד", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_PRIMARY).pack(side="right", padx=(8, 0))
        self.combo_preview_ai = ctk.CTkComboBox(
            f_prev_ai,
            values=[
                "🌐 כל המודלים",
                "✨ Google Antigravity",
                "Claude Desktop",
                "⚡ Cursor AI",
                "Windsurf",
                "GitHub Copilot",
                "Cline & Roo"
            ],
            width=210,
            height=32,
            state="readonly",
            command=lambda v: self.refresh_page_preview()
        )
        self.combo_preview_ai.set("🌐 כל המודלים")
        self.combo_preview_ai.pack(side="right")

        # Container for preview views
        self.preview_container = ctk.CTkFrame(p, fg_color="transparent")
        self.preview_container.pack(fill="both", expand=True)

        # 1. Visual Card-Based View
        self.scroll_preview_visual = ctk.CTkScrollableFrame(self.preview_container, corner_radius=10, fg_color=GLASS_BG_MAIN)

        # 2. Raw Markdown Code View (Clean GitHub Dark Palette - not radioactive green)
        self.txt_preview = ctk.CTkTextbox(
            self.preview_container,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            corner_radius=10,
            fg_color=GLASS_INPUT,
            text_color=TEXT_PRIMARY,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            wrap="word"
        )

        # Default to visual view
        self.scroll_preview_visual.pack(fill="both", expand=True)

    def on_preview_mode_change(self, mode):
        if "מעוצבת" in mode:
            self.txt_preview.pack_forget()
            self.scroll_preview_visual.pack(fill="both", expand=True)
        else:
            self.scroll_preview_visual.pack_forget()
            self.txt_preview.pack(fill="both", expand=True)
        self.refresh_page_preview()

    def get_selected_preview_ai_key(self):
        sel = self.combo_preview_ai.get() if hasattr(self, "combo_preview_ai") else "כל המודלים"
        if "Antigravity" in sel: return "antigravity"
        elif "Claude" in sel: return "claude"
        elif "Cursor" in sel: return "cursor"
        elif "Windsurf" in sel: return "windsurf"
        elif "Copilot" in sel: return "copilot"
        elif "Cline" in sel: return "cline"
        return "all"

    def refresh_page_preview(self):
        ai_key = self.get_selected_preview_ai_key()
        prompt = memory_hub.generate_prompt_markdown(target_ai=ai_key)

        # Update RAW text
        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("1.0", prompt)

        # Update Visual View
        for w in self.scroll_preview_visual.winfo_children():
            w.destroy()

        p_data = memory_hub.get_current_profile_data()

        # Model Banner Info (Frosted Glass Container)
        banner = self.create_glass_card(self.scroll_preview_visual, corner_radius=14)
        banner.pack(fill="x", pady=(4, 10), padx=4)

        ai_names = {
            "all": "כל המודלים המותקנים",
            "antigravity": "Google Antigravity (GEMINI.md)",
            "claude": "Claude Desktop / Claude Code (CLAUDE.md)",
            "cursor": "Cursor AI (.cursorrules)",
            "windsurf": "Windsurf / Codeium (.windsurfrules)",
            "copilot": "GitHub Copilot (copilot-instructions.md)",
            "cline": "Cline / Roo Code (.clinerules)"
        }
        b_box = ctk.CTkFrame(banner, fg_color="transparent")
        b_box.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(b_box, text=f"יעד תצוגה נוכחי: {ai_names.get(ai_key, ai_key)}", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e")
        ctk.CTkLabel(b_box, text="להלן כל החוקים, המידע וההנחיות שמוזרקים למודל זה בזמן אמת. כללים המיועדים למודלים אחרים מסוננים אוטומטית.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY).pack(anchor="e", pady=(2, 0))

        # Categories list to render
        sections = [
            ("facts", "עובדות ונתונים קבועים", "#38bdf8"),
            ("commands", "פקודות וכללי התנהגות", "#f59e0b"),
            ("constraints", "מגבלות ואיסורים", "#f43f5e"),
            ("styles", "סגנון מענה ושפה", "#a855f7"),
            ("instructions", " הוראות מותנות והנחיות פרטיות", "#10b981"),
            ("context_files", "קבצי הקשר ומסמכים", "#eab308")
        ]

        total_matching = 0
        for cat_key, cat_title, cat_color in sections:
            all_items = p_data.get(cat_key, [])
            matched = [x for x in all_items if x.get("active", True) and memory_hub.item_matches_ai(x, ai_key)]
            total_matching += len(matched)

            sec_frame = self.create_glass_card(self.scroll_preview_visual, corner_radius=14)
            sec_frame.pack(fill="x", pady=5, padx=4)

            # Section Header
            sec_head = ctk.CTkFrame(sec_frame, fg_color="transparent")
            sec_head.pack(fill="x", padx=12, pady=(10, 6))

            ctk.CTkLabel(sec_head, text=f"{len(matched)} פעילים", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY).pack(side="left")
            ctk.CTkLabel(sec_head, text=cat_title, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=cat_color).pack(side="right")

            if not matched:
                ctk.CTkLabel(sec_frame, text="אין חוקים פעילים בקטגוריה זו עבור מודל זה.", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY).pack(pady=(2, 10), padx=12, anchor="e")
                continue

            for it in matched:
                card = ctk.CTkFrame(sec_frame, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER)
                card.pack(fill="x", pady=3, padx=10)

                # Badges on left
                b_row = ctk.CTkFrame(card, fg_color="transparent")
                b_row.pack(side="left", padx=8, pady=8)

                # Scope badge
                sc_txt = "כללי (גלובלי)" if it.get("scope", "global") == "global" else f"{it.get('scope')}"
                self.create_glass_badge(b_row, sc_txt, "cyan" if "גלובלי" in sc_txt else "default").pack(side="left", padx=3)

                # AI Badge
                ai_b_txt = self.format_ai_target_badge(it)
                self.create_glass_badge(b_row, ai_b_txt, "purple").pack(side="left", padx=3)

                # Info on right
                c_info = ctk.CTkFrame(card, fg_color="transparent")
                c_info.pack(side="right", fill="x", expand=True, padx=8, pady=8)

                if cat_key == "facts":
                    ctk.CTkLabel(c_info, text=f"• {it.get('name', '')}: {it.get('value', '')}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY, justify="right", wraplength=480).pack(anchor="e")
                elif cat_key == "commands":
                    ctk.CTkLabel(c_info, text=f" {it.get('name', '')}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY, justify="right").pack(anchor="e")
                    ctk.CTkLabel(c_info, text=f"פעולה: {it.get('details', '')}", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY, justify="right", wraplength=480).pack(anchor="e")
                    if it.get("trigger_case"):
                        ctk.CTkLabel(c_info, text=f"מתי לבצע: {it.get('trigger_case', '')}", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_PRIMARY, justify="right").pack(anchor="e")
                elif cat_key == "constraints":
                    ctk.CTkLabel(c_info, text=f" איסור: {it.get('constraint', '')}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY, justify="right", wraplength=480).pack(anchor="e")
                    if it.get("alternative_or_why"):
                        ctk.CTkLabel(c_info, text=f"הנחיה חלופית: {it.get('alternative_or_why', '')}", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY, justify="right", wraplength=480).pack(anchor="e")
                elif cat_key == "styles":
                    ctk.CTkLabel(c_info, text=f"{it.get('aspect', '')}: {it.get('instruction', '')}", font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_PRIMARY, justify="right", wraplength=480).pack(anchor="e")
                elif cat_key == "instructions":
                    ctk.CTkLabel(c_info, text=f" {it.get('instruction', '')}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY, justify="right", wraplength=480).pack(anchor="e")
                    if it.get("when_to_apply"):
                        ctk.CTkLabel(c_info, text=f"מתי ליישם: {it.get('when_to_apply', '')}", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY, justify="right").pack(anchor="e")
                elif cat_key == "context_files":
                    ctk.CTkLabel(c_info, text=f"{it.get('name', '')}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY, justify="right").pack(anchor="e")
                    ctk.CTkLabel(c_info, text=f"נתיב: {it.get('path', '')}", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_PRIMARY, justify="right", wraplength=480).pack(anchor="e")
                    if it.get("summary"):
                        ctk.CTkLabel(c_info, text=f"דגשים: {it.get('summary', '')}", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY, justify="right", wraplength=480).pack(anchor="e")

            # Padding bottom
            ctk.CTkFrame(sec_frame, height=6, fg_color="transparent").pack()

    def on_copy_preview(self):
        ai_key = self.get_selected_preview_ai_key()
        content = memory_hub.generate_prompt_markdown(target_ai=ai_key)
        self.clipboard_clear()
        self.clipboard_append(content)
        self.btn_copy_preview.configure(text="✓ הועתק בהצלחה!", fg_color="#059669")
        self.after(1600, lambda: self.btn_copy_preview.configure(text="העתק טקסט ללוח", fg_color="#334155"))
        self.set_status("הפרומפט המלא הועתק ללוח בהצלחה!")

    # =========================================================================
    # 8. PAGE: SETTINGS, BACKUP & GEMINI API
    # =========================================================================
    WEEKDAY_LABELS = [("ב'", 0), ("ג'", 1), ("ד'", 2), ("ה'", 3), ("ו'", 4), ("ש'", 5), ("א'", 6)]

    def build_auto_profile_settings(self, parent):
        """
        Configures how the active profile is chosen automatically. Three strategies, each
        with its own switch, because they answer different questions:
          • לוח זמנים - "בשעות העבודה תחשוב עסקי"
          • תיקיית פרויקט - "בתיקייה הזו תחשוב קוד"
          • מילות הפעלה - "כשאני שואל על המייל העסקי שלי, תחשוב עסקי" (ה-AI מחליט בעצמו)
        """
        conf = memory_hub.get_auto_switch_settings()

        box = self.create_glass_card(parent, corner_radius=14)
        box.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box, text="מעבר פרופיל אוטומטי",
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(8, 2))
        ctk.CTkLabel(box, text="בחירת אופן ההחלפה האוטומטית של הפרופיל ללא צורך בהחלפה ידנית",
                     font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_SECONDARY,
                     wraplength=640, justify="right").pack(anchor="e", padx=14, pady=(0, 6))

        self.sw_auto_profile = ctk.CTkSwitch(box, text="הפעל מעבר פרופיל אוטומטי",
                                             command=self.on_save_auto_profile)
        self.sw_auto_profile.pack(anchor="e", padx=18, pady=(2, 6))
        if conf.get("enabled"): self.sw_auto_profile.select()
        else: self.sw_auto_profile.deselect()

        strategies = ctk.CTkFrame(box, fg_color="transparent")
        strategies.pack(fill="x", padx=18, pady=(0, 8))

        self.sw_auto_schedule = ctk.CTkSwitch(strategies, text="לפי שעות פעילות ולוח זמנים",
                                              command=self.on_save_auto_profile)
        self.sw_auto_schedule.pack(anchor="e", pady=2)
        if conf.get("useSchedule"): self.sw_auto_schedule.select()
        else: self.sw_auto_schedule.deselect()

        self.sw_auto_folder = ctk.CTkSwitch(strategies, text="לפי תיקיית הפרויקט שבה אתה עובד",
                                            command=self.on_save_auto_profile)
        self.sw_auto_folder.pack(anchor="e", pady=2)
        if conf.get("useFolder"): self.sw_auto_folder.select()
        else: self.sw_auto_folder.deselect()

        self.sw_auto_keywords = ctk.CTkSwitch(
            strategies, text="לפי מילות הפעלה וזיהוי הקשר",
            command=self.on_save_auto_profile)
        self.sw_auto_keywords.pack(anchor="e", pady=2)
        if conf.get("useKeywords"): self.sw_auto_keywords.select()
        else: self.sw_auto_keywords.deselect()

        ctk.CTkLabel(box, text="הגדרות לכל פרופיל",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(6, 2))

        self.profile_rule_widgets = {}
        for pid, pinfo in memory_hub.get_profiles().items():
            self.build_profile_rule_row(box, pid, pinfo)

        ctk.CTkButton(box, text="שמור כללי מעבר", width=150, height=30, corner_radius=8,
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff",
                      command=self.on_save_profile_rules).pack(anchor="e", padx=18, pady=(4, 12))

    def build_profile_rule_row(self, parent, pid, pinfo):
        sched = memory_hub.get_profile_schedule(pid)
        keywords, _desc, _mode = memory_hub.get_profile_triggers(pid)
        patterns = pinfo.get("folder_patterns") or []

        card = self.create_glass_card(parent, corner_radius=10)
        card.pack(fill="x", padx=14, pady=3)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(head, text=pinfo.get("name", pid),
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="right")

        sw_sched = ctk.CTkSwitch(head, text="פעיל בשעות", width=40)
        sw_sched.pack(side="left")
        if sched.get("enabled"): sw_sched.select()
        else: sw_sched.deselect()

        time_row = ctk.CTkFrame(card, fg_color="transparent")
        time_row.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(time_row, text="מ־", font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=TEXT_SECONDARY).pack(side="right")
        e_start = ctk.CTkEntry(time_row, width=60, height=26, corner_radius=6, fg_color=GLASS_INPUT,
                               border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY)
        e_start.insert(0, sched.get("start", "09:00"))
        e_start.pack(side="right", padx=(2, 6))

        ctk.CTkLabel(time_row, text="עד", font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=TEXT_SECONDARY).pack(side="right")
        e_end = ctk.CTkEntry(time_row, width=60, height=26, corner_radius=6, fg_color=GLASS_INPUT,
                             border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY)
        e_end.insert(0, sched.get("end", "18:00"))
        e_end.pack(side="right", padx=(2, 10))

        day_vars = {}
        active_days = set(sched.get("days") or [])
        for label, idx in self.WEEKDAY_LABELS:
            var = ctk.BooleanVar(value=idx in active_days)
            cb = ctk.CTkCheckBox(time_row, text=label, variable=var, width=20, checkbox_width=16,
                                 checkbox_height=16, font=ctk.CTkFont(family="Segoe UI", size=10),
                                 text_color=TEXT_SECONDARY)
            cb.pack(side="right", padx=1)
            day_vars[idx] = var

        e_keywords = ctk.CTkEntry(card, height=28, corner_radius=6, fg_color=GLASS_INPUT,
                                  border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY,
                                  placeholder_text="מילות הפעלה מופרדות בפסיק, למשל: עסקי, לקוח", justify="right")
        e_keywords.insert(0, ", ".join(keywords))
        e_keywords.pack(fill="x", padx=10, pady=2)

        e_folders = ctk.CTkEntry(card, height=28, corner_radius=6, fg_color=GLASS_INPUT,
                                 border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY,
                                 placeholder_text="שמות תיקיות מופרדים בפסיק, למשל: work, code", justify="right")
        e_folders.insert(0, ", ".join(patterns))
        e_folders.pack(fill="x", padx=10, pady=(2, 8))

        self.profile_rule_widgets[pid] = {
            "schedule_on": sw_sched, "start": e_start, "end": e_end,
            "days": day_vars, "keywords": e_keywords, "folders": e_folders,
        }

    def on_save_auto_profile(self):
        memory_hub.set_auto_switch_settings(
            enabled=bool(self.sw_auto_profile.get()),
            useSchedule=bool(self.sw_auto_schedule.get()),
            useFolder=bool(self.sw_auto_folder.get()),
            useKeywords=bool(self.sw_auto_keywords.get()),
        )
        self.set_status("הגדרות מעבר הפרופיל נשמרו")
        self.apply_auto_profile_now()

    def on_save_profile_rules(self):
        for pid, w in getattr(self, "profile_rule_widgets", {}).items():
            memory_hub.set_profile_schedule(
                pid,
                enabled=bool(w["schedule_on"].get()),
                start=w["start"].get().strip() or "09:00",
                end=w["end"].get().strip() or "18:00",
                days=[idx for idx, var in w["days"].items() if var.get()],
            )
            memory_hub.set_profile_triggers(pid, w["keywords"].get())
            memory_hub.set_profile_folder_patterns(pid, w["folders"].get())

        self.set_status("כללי המעבר נשמרו והושתלו")
        self.apply_auto_profile_now()
        self.refresh_all_views()

    def apply_auto_profile_now(self):
        """
        Applies the schedule/folder strategies. Keyword switching is not decided here -
        the AI does that itself from the trigger words written into the rules block.
        Re-checked every 10 minutes so a schedule boundary is picked up while the app runs.
        """
        try:
            changed, pid, reason = memory_hub.apply_auto_profile()
        except Exception as e:
            print(f"[auto profile] {e}")
            return

        if changed:
            name = memory_hub.get_profiles().get(pid, {}).get("name", pid)
            self.set_status(f"הוחלף פרופיל אוטומטית ל'{name}' ({reason})")
            self.update_profiles_combo()
            self.refresh_all_views()

    def schedule_auto_profile_checks(self):
        self.apply_auto_profile_now()
        self.after(10 * 60 * 1000, self.schedule_auto_profile_checks)

    def build_page_settings(self):
        p = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.pages["settings"] = p

        self.create_page_header(p, " הגדרות מערכת וסנכרון ענן", "ניהול מפתח גישה, שחזור וייצוא גיבויים, סנכרון ענן ואפשרויות מערכת")

        db = memory_hub.load_db()
        settings = db.get("settings", {})

        # Scope Mode Box (Macro vs Micro vs Both) (Frosted Glass Container) - AT TOP
        box_scope = self.create_glass_card(p, corner_radius=14)
        box_scope.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box_scope, text="היקף סנכרון חוקים - מאקרו ומיקרו", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(8, 2))
        ctk.CTkLabel(box_scope, text="קביעת אופן הפצת הכללים: שמירה גלובלית לכל הפרויקטים, שמירה מקומית בכל תיקייה, או שילוב של שניהם", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(0, 6))

        scope_mode_map = {
            "מאקרו בלבד": "macro",
            "לפי פרויקטים": "micro",
            "מצב משולב": "both"
        }
        scope_mode_rev = {v: k for k, v in scope_mode_map.items()}
        cur_scope_mode = settings.get("syncScopeMode", "macro")

        scope_row = ctk.CTkFrame(box_scope, fg_color="transparent")
        scope_row.pack(fill="x", padx=14, pady=(2, 6))

        self.seg_sync_scope = ctk.CTkSegmentedButton(
            scope_row,
            values=list(scope_mode_map.keys()),
            command=self.on_change_sync_scope
        )
        self.seg_sync_scope.set(scope_mode_rev.get(cur_scope_mode, "מאקרו בלבד"))
        self.seg_sync_scope.pack(fill="x")

        self.lbl_scope_desc = ctk.CTkLabel(box_scope, text="", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_SECONDARY, justify="right", wraplength=900)
        self.lbl_scope_desc.pack(anchor="e", padx=16, pady=(2, 6))
        self.update_scope_desc_label(cur_scope_mode)

        scope_action_row = ctk.CTkFrame(box_scope, fg_color="transparent")
        scope_action_row.pack(fill="x", padx=14, pady=(2, 10))

        self.sw_clean_on_macro = ctk.CTkSwitch(scope_action_row, text="ניקוי אוטומטי מתיקיות פרויקטים במצב מאקרו", command=self.on_save_settings)
        self.sw_clean_on_macro.pack(side="right")
        if settings.get("cleanProjectsOnMacro", False): self.sw_clean_on_macro.select()
        else: self.sw_clean_on_macro.deselect()

        btn_clean_now = ctk.CTkButton(
            scope_action_row,
            text="ניקוי תיקיות פרויקטים",
            width=160,
            height=30,
            corner_radius=8,
            fg_color="#374151",
            hover_color="#4b5563",
            text_color="#ffffff",
            command=self.on_clean_all_projects_gui
        )
        btn_clean_now.pack(side="left")

        # API Key Box (Frosted Glass Container)
        box1 = self.create_glass_card(p, corner_radius=14)
        box1.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box1, text="מפתח גישה למודל Gemini", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(10, 2))

        api_row = ctk.CTkFrame(box1, fg_color="transparent")
        api_row.pack(fill="x", padx=14, pady=(2, 10))

        cur_key = settings.get("geminiApiKey") or os.environ.get("GEMINI_API_KEY", "")
        self.entry_settings_api = ctk.CTkEntry(api_row, placeholder_text="הזן מפתח גישה...", height=34, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, show="•", justify="right")
        self.entry_settings_api.pack(side="right", fill="x", expand=True, padx=(8, 0))
        if cur_key: self.entry_settings_api.insert(0, cur_key)

        btn_test = ctk.CTkButton(api_row, text="בדיקת חיבור", width=120, height=34, corner_radius=8, fg_color="#062e24", hover_color="#064e3b", border_width=1, border_color="#059669", text_color="#ffffff", command=self.on_test_gemini)
        btn_test.pack(side="left")

        # Global Default Model Selector
        model_row = ctk.CTkFrame(box1, fg_color="transparent")
        model_row.pack(fill="x", padx=14, pady=(2, 10))

        ctk.CTkLabel(model_row, text="מודל עבודה ראשי", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(side="right", padx=(8, 0))

        self.combo_settings_gemini_model = ctk.CTkComboBox(
            model_row,
            values=["פלאש לייט לאסט", "פלאש לאסט", "פרו לאסט"],
            width=180,
            height=32,
            corner_radius=8,
            fg_color=GLASS_INPUT,
            border_width=1,
            border_color=GLASS_INPUT_BORDER,
            button_color=("#f1f5f9", "#131d31"),
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda v: self.on_save_settings()
        )
        self.combo_settings_gemini_model._entry.configure(justify="right")
        self.combo_settings_gemini_model.pack(side="right")
        cur_model = settings.get("defaultGeminiModel", "פלאש לאסט")
        if cur_model not in ["פלאש לייט לאסט", "פלאש לאסט", "פרו לאסט"]:
            cur_model = "פלאש לאסט"
        self.combo_settings_gemini_model.set(cur_model)

        # Backup & Restore Box (Frosted Glass Container)
        box2 = self.create_glass_card(p, corner_radius=14)
        box2.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box2, text="גיבוי ושחזור נתונים מקומי", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(10, 4))

        backup_row = ctk.CTkFrame(box2, fg_color="transparent")
        backup_row.pack(fill="x", padx=14, pady=(0, 12))

        btn_export = ctk.CTkButton(backup_row, text="ייצוא גיבוי", width=130, height=34, corner_radius=8, fg_color="#0c1628", hover_color="#162544", border_width=1, border_color="#1e3a8a", text_color="#ffffff", command=self.on_export_backup)
        btn_export.pack(side="right", padx=(0, 8))

        btn_import = ctk.CTkButton(backup_row, text="שחזור גיבוי", width=130, height=34, corner_radius=8, fg_color="#0c1628", hover_color="#162544", border_width=1, border_color="#1e3a8a", text_color="#ffffff", command=self.on_import_backup)
        btn_import.pack(side="right")

        # Cloud Sync Box (GitHub Gist) (Frosted Glass Container)
        box_cloud = self.create_glass_card(p, corner_radius=14)
        box_cloud.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box_cloud, text="סנכרון וגיבוי ענן מאובטח", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(8, 2))
        ctk.CTkLabel(box_cloud, text="גיבוי וסנכרון מיידי בין מחשבים שונים באמצעות ענן מאובטח", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(0, 4))

        t_row = ctk.CTkFrame(box_cloud, fg_color="transparent")
        t_row.pack(fill="x", padx=14, pady=2)
        ctk.CTkLabel(t_row, text="טוקן גישה לענן", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY).pack(side="right", padx=(8, 0))
        self.entry_gist_token = ctk.CTkEntry(t_row, placeholder_text="הזן טוקן GitHub Gist...", height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, show="•", justify="right")
        self.entry_gist_token.pack(side="right", fill="x", expand=True)
        if settings.get("githubGistToken"): self.entry_gist_token.insert(0, settings.get("githubGistToken"))

        g_row = ctk.CTkFrame(box_cloud, fg_color="transparent")
        g_row.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(g_row, text="מזהה גיבוי בענן", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY).pack(side="right", padx=(8, 0))
        self.entry_gist_id = ctk.CTkEntry(g_row, placeholder_text="מזהה גיבוי בענן (אופציונלי)...", height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, text_color=TEXT_PRIMARY, justify="right")
        self.entry_gist_id.pack(side="right", fill="x", expand=True)
        if settings.get("githubGistId"): self.entry_gist_id.insert(0, settings.get("githubGistId"))

        cloud_btn_row = ctk.CTkFrame(box_cloud, fg_color="transparent")
        cloud_btn_row.pack(fill="x", padx=14, pady=(6, 6))

        self.btn_push_cloud = ctk.CTkButton(cloud_btn_row, text="העלאה לענן", width=140, height=34, corner_radius=8, fg_color="#1e1b4b", hover_color="#2e1065", border_width=1, border_color="#6366f1", text_color="#ffffff", command=self.on_cloud_push)
        self.btn_push_cloud.pack(side="right", padx=(0, 8))

        self.btn_pull_cloud = ctk.CTkButton(cloud_btn_row, text="הורדה מענן", width=140, height=34, corner_radius=8, fg_color="#082f49", hover_color="#075985", border_width=1, border_color="#0284c7", text_color="#ffffff", command=self.on_cloud_pull)
        self.btn_pull_cloud.pack(side="right")

        self.sw_auto_cloud = ctk.CTkSwitch(box_cloud, text="סנכרן לענן אוטומטית בכל שמירת שינוי", command=self.on_save_settings)
        self.sw_auto_cloud.pack(anchor="e", padx=18, pady=(4, 10))
        if settings.get("autoCloudSync", False): self.sw_auto_cloud.select()
        else: self.sw_auto_cloud.deselect()

        self.build_auto_profile_settings(p)

        # GitHub Auto-Update Box (Frosted Glass Container)
        box_update = self.create_glass_card(p, corner_radius=14)
        box_update.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box_update, text="בדיקת עדכוני תוכנה", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(8, 2))
        ctk.CTkLabel(box_update, text=f"גרסה נוכחית v{updater.CURRENT_VERSION}  •  מאגר {updater.REPO_OWNER}/{updater.REPO_NAME}", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(0, 4))

        up_btn_row = ctk.CTkFrame(box_update, fg_color="transparent")
        up_btn_row.pack(fill="x", padx=14, pady=(4, 6))

        self.btn_check_update = ctk.CTkButton(
            up_btn_row,
            text="בדיקת עדכונים",
            width=150,
            height=34,
            corner_radius=8,
            fg_color="#082f49",
            hover_color="#075985",
            border_width=1,
            border_color="#0284c7",
            text_color="#ffffff",
            command=self.on_check_updates_manual
        )
        self.btn_check_update.pack(side="right", padx=(0, 8))

        btn_open_repo = ctk.CTkButton(
            up_btn_row,
            text="פתיחת דף הפרויקט",
            width=160,
            height=34,
            corner_radius=8,
            fg_color="#0c1628",
            hover_color="#162544",
            border_width=1,
            border_color="#1e3a8a",
            text_color="#ffffff",
            command=lambda: webbrowser.open(updater.GITHUB_REPO_URL)
        )
        btn_open_repo.pack(side="right")

        self.sw_auto_update_check = ctk.CTkSwitch(box_update, text="בדוק עדכונים אוטומטית בעת הפעלת התוכנה", command=self.on_save_settings)
        self.sw_auto_update_check.pack(anchor="e", padx=18, pady=(4, 4))
        if settings.get("checkUpdatesOnStartup", True): self.sw_auto_update_check.select()
        else: self.sw_auto_update_check.deselect()

        self.sw_auto_install = ctk.CTkSwitch(box_update, text="התקנת עדכונים אוטומטית בעת סגירת התוכנה", command=self.on_save_settings)
        self.sw_auto_install.pack(anchor="e", padx=18, pady=(0, 4))
        if settings.get("autoInstallUpdates", False): self.sw_auto_install.select()
        else: self.sw_auto_install.deselect()

        self.sw_global_targets = ctk.CTkSwitch(box_update, text="השתלה גם לקבצי חוקים גלובליים בכל הפרויקטים", command=self.on_save_settings)
        self.sw_global_targets.pack(anchor="e", padx=18, pady=(0, 4))
        if settings.get("injectGlobalTargets", True): self.sw_global_targets.select()
        else: self.sw_global_targets.deselect()

        self.sw_mcp_mode_switch = ctk.CTkSwitch(box_update, text="אפשר החלפת פרופיל פעיל דרך שרת זיכרון MCP", command=self.on_save_settings)
        self.sw_mcp_mode_switch.pack(anchor="e", padx=18, pady=(0, 10))
        if settings.get("allowMcpModeSwitch", False): self.sw_mcp_mode_switch.select()
        else: self.sw_mcp_mode_switch.deselect()

        # Appearance & Themes Box (Frosted Glass Container)
        box_theme = self.create_glass_card(p, corner_radius=14)
        box_theme.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box_theme, text="התאמה אישית של עיצוב ומראה", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(8, 4))

        theme_row = ctk.CTkFrame(box_theme, fg_color="transparent")
        theme_row.pack(fill="x", padx=14, pady=(0, 10))

        THEME_MAP = {"כחול": "blue", "ירוק": "green", "כחול כהה": "dark-blue"}
        THEME_REV = {v: k for k, v in THEME_MAP.items()}
        MODE_MAP = {"בהיר": "light", "כהה": "dark", "מערכת": "system"}
        MODE_REV = {v: k for k, v in MODE_MAP.items()}

        f_thm = ctk.CTkFrame(theme_row, fg_color="transparent")
        f_thm.pack(side="right", padx=(14, 0))
        ctk.CTkLabel(f_thm, text="צבע הדגשה", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.combo_color_theme = ctk.CTkComboBox(f_thm, values=["כחול", "ירוק", "כחול כהה"], width=130, height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY, command=self.on_change_color_theme)
        self.combo_color_theme._entry.configure(justify="right")
        self.combo_color_theme.set(THEME_REV.get(settings.get("colorTheme", "blue"), "כחול"))
        self.combo_color_theme.pack()

        f_mode = ctk.CTkFrame(theme_row, fg_color="transparent")
        f_mode.pack(side="right")
        ctk.CTkLabel(f_mode, text="מצב תצוגה", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY).pack(anchor="e")
        self.combo_app_mode = ctk.CTkComboBox(f_mode, values=["בהיר", "כהה", "מערכת"], width=130, height=32, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, button_color=("#f1f5f9", "#131d31"), text_color=TEXT_PRIMARY, command=self.on_change_appearance_mode)
        self.combo_app_mode._entry.configure(justify="right")
        self.combo_app_mode.set(MODE_REV.get(settings.get("appearanceMode", "light"), "בהיר"))
        self.combo_app_mode.pack()

        # System Switches (Frosted Glass Container)
        box3 = self.create_glass_card(p, corner_radius=14)
        box3.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(box3, text="אפשרויות סנכרון ואוטומציה", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", padx=14, pady=(8, 4))

        self.sw_claude = ctk.CTkSwitch(box3, text="סנכרון שרת זיכרון עם Claude Desktop", command=self.on_save_settings)
        self.sw_claude.pack(anchor="e", padx=18, pady=2)
        if settings.get("injectClaudeMcp", True): self.sw_claude.select()
        else: self.sw_claude.deselect()

        self.sw_anti = ctk.CTkSwitch(box3, text="סנכרון ידע קבוע עם Google Antigravity", command=self.on_save_settings)
        self.sw_anti.pack(anchor="e", padx=18, pady=2)
        if settings.get("injectAntigravityKnowledge", True): self.sw_anti.select()
        else: self.sw_anti.deselect()

        self.sw_watcher = ctk.CTkSwitch(box3, text="ניטור אוטומטי של תיקיות פרויקטים חדשות בשולחן העבודה", command=self.on_save_settings)
        self.sw_watcher.pack(anchor="e", padx=18, pady=2)
        if settings.get("folderWatcherActive", True): self.sw_watcher.select()
        else: self.sw_watcher.deselect()

        self.sw_tray = ctk.CTkSwitch(box3, text="מזעור למגש המערכת בסגירת החלון במקום יציאה", command=self.on_save_settings)
        self.sw_tray.pack(anchor="e", padx=18, pady=2)
        if settings.get("minimizeToTray", False): self.sw_tray.select()
        else: self.sw_tray.deselect()

        self.sw_autosync = ctk.CTkSwitch(box3, text="סנכרון והשתלה אוטומטית מידית בכל שינוי פריט או נתיב", command=self.on_save_settings)
        self.sw_autosync.pack(anchor="e", padx=18, pady=(2, 10))
        if settings.get("autoSyncOnChange", True): self.sw_autosync.select()
        else: self.sw_autosync.deselect()

        # Activity Logs
        ctk.CTkLabel(p, text="יומן פעולות", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=TEXT_PRIMARY).pack(anchor="e", pady=(2, 2))
        self.txt_logs = ctk.CTkTextbox(p, font=ctk.CTkFont(family="Consolas", size=11), corner_radius=10, text_color=TEXT_SECONDARY)
        self.txt_logs.pack(fill="both", expand=True, pady=(0, 4))

    def on_change_appearance_mode(self, new_mode):
        mode_map = {"בהיר": "light", "כהה": "dark", "מערכת": "system"}
        real_mode = mode_map.get(new_mode, new_mode)
        ctk.set_appearance_mode(real_mode)
        apply_windows_glass(self)
        self.on_save_settings()
        self.refresh_all_views()

    def on_change_color_theme(self, new_theme):
        theme_map = {"כחול": "blue", "ירוק": "green", "כחול כהה": "dark-blue"}
        real_theme = theme_map.get(new_theme, new_theme)
        ctk.set_default_color_theme(real_theme)
        self.on_save_settings()
        messagebox.showinfo("שינוי ערכת נושא", "ערכת הנושא נשמרה. כדי להחיל את צבעי הכפתורים במלואם מומלץ להפעיל את התוכנה מחדש.")

    def on_cloud_push(self):
        tok = self.entry_gist_token.get().strip()
        gid = self.entry_gist_id.get().strip()
        if not tok:
            messagebox.showwarning("טוקן חסר", "נא להזין GitHub Personal Access Token.")
            return

        self.btn_push_cloud.configure(state="disabled", text="⏳ מעלה...")
        self.set_status("מעלה גיבוי אל שרת הענן...")

        def worker():
            ok, msg, new_gid = memory_hub.push_to_cloud(token=tok, gist_id=gid)
            self.after(0, lambda: self.on_cloud_push_done(ok, msg, new_gid))
        self.run_async(worker)

    def on_cloud_push_done(self, ok, msg, new_gid):
        self.btn_push_cloud.configure(state="normal", text="העלאה לענן")
        if ok:
            if new_gid and not self.entry_gist_id.get().strip():
                self.entry_gist_id.delete(0, "end")
                self.entry_gist_id.insert(0, new_gid)
            self.on_save_settings()
            messagebox.showinfo("סנכרון ענן", f"✅ {msg}")
            self.set_status("הגיבוי עלה בהצלחה לענן!")
        else:
            messagebox.showerror("שגיאת סנכרון", f"❌ {msg}")
            self.set_status("סנכרון לענן נכשל")

    def on_cloud_pull(self):
        tok = self.entry_gist_token.get().strip()
        gid = self.entry_gist_id.get().strip()
        if not tok or not gid:
            messagebox.showwarning("פרטים חסרים", "נא להזין גם GitHub Token וגם Gist ID לשחזור.")
            return

        if not messagebox.askyesno("אישור שחזור", "האם להוריד את הנתונים מהענן ולשחזר אותם? פעולה זו תחליף את הנתונים המקומיים."):
            return

        self.btn_pull_cloud.configure(state="disabled", text="⏳ מוריד...")
        self.set_status("מוריד נתונים משרת הענן...")

        def worker():
            ok, msg = memory_hub.pull_from_cloud(token=tok, gist_id=gid)
            self.after(0, lambda: self.on_cloud_pull_done(ok, msg))
        self.run_async(worker)

    def on_cloud_pull_done(self, ok, msg):
        self.btn_pull_cloud.configure(state="normal", text="הורדה מענן")
        if ok:
            self.update_profiles_combo()
            self.refresh_all_views()
            messagebox.showinfo("שחזור הושלם", f"✅ {msg}")
            self.set_status("הנתונים שוחזרו בהצלחה מהענן!")
        else:
            messagebox.showerror("שגיאת שחזור", f"❌ {msg}")
            self.set_status("שחזור מהענן נכשל")

    def on_test_gemini(self):
        key = self.entry_settings_api.get().strip()
        if not key:
            messagebox.showwarning("מפתח חסר", "נא להזין מפתח API לבדיקה.")
            return
        model = self.combo_settings_gemini_model.get() if hasattr(self, "combo_settings_gemini_model") else None
        self.set_status(f"בודק תקשורת עם Gemini API ({model or 'ברירת מחדל'})...")
        ok, res = gemini_optimizer.call_gemini("ענה במילה אחת בלבד: תקין", api_key=key, model=model)
        if ok:
            messagebox.showinfo("חיבור תקין", f"✅ החיבור אל Gemini API תקין ופעיל!\nמודל נבחר: {model or 'ברירת מחדל'}")
            self.set_status("החיבור אל Gemini API תקין!")
            self.on_save_settings()
        else:
            messagebox.showerror("שגיאה", f"❌ החיבור נכשל:\n{res}")
            self.set_status("החיבור אל Gemini API נכשל")

    def update_scope_desc_label(self, mode):
        if mode == "macro":
            txt = "מצב מאקרו: חיסכון מרבי במשאבים, הכללים נשמרים בהגדרות הראשיות ומוחלים על כל סביבות הפיתוח"
        elif mode == "micro":
            txt = "מצב מיקרו: יצירת קובצי הגדרה ייעודיים בתוך כל תיקיית פרויקט מקומית בנפרד"
        else:
            txt = "מצב משולב: סנכרון כפול מלא הן ברמת המערכת הגלובלית והן בתיקיות הפרויקטים"
        if hasattr(self, "lbl_scope_desc"):
            self.lbl_scope_desc.configure(text=txt)

    def on_change_sync_scope(self, val):
        scope_mode_map = {
            "מאקרו בלבד": "macro",
            "לפי פרויקטים": "micro",
            "מצב משולב": "both",
            "מאקרו (גלובלי בלבד)": "macro",
            "מיקרו (לפי פרויקטים)": "micro",
            "היברידי (שניהם)": "both"
        }
        mode = scope_mode_map.get(val, "macro")
        self.update_scope_desc_label(mode)
        self.on_save_settings()
        if hasattr(self, "sw_autosync") and self.sw_autosync.get():
            self.on_sync_all()

    def on_clean_all_projects_gui(self):
        if not messagebox.askyesno("ניקוי תיקיות פרויקטים", "האם להסיר את כל קבצי ובלוקי החוקים מכל תיקיות הפרויקטים המוגדרות?\n(קבצי המאקרו הגלובליים יישארו פעילים)"):
            return
        res = memory_hub.clean_all_project_folders()
        self.refresh_all_views()
        messagebox.showinfo("ניקוי הושלם", f"נוקו בהצלחה קבצי חוקים מ-{res.get('cleaned_count', 0)} תיקיות פרויקטים.")

    def on_save_settings(self):
        db = memory_hub.load_db()
        db.setdefault("settings", {})
        db["settings"]["geminiApiKey"] = self.entry_settings_api.get().strip()
        db["settings"]["githubGistToken"] = self.entry_gist_token.get().strip()
        db["settings"]["githubGistId"] = self.entry_gist_id.get().strip()
        db["settings"]["autoCloudSync"] = self.sw_auto_cloud.get()
        mode_map = {"בהיר": "light", "כהה": "dark", "מערכת": "system"}
        theme_map = {"כחול": "blue", "ירוק": "green", "כחול כהה": "dark-blue"}
        db["settings"]["appearanceMode"] = mode_map.get(self.combo_app_mode.get(), self.combo_app_mode.get())
        db["settings"]["colorTheme"] = theme_map.get(self.combo_color_theme.get(), self.combo_color_theme.get())
        db["settings"]["injectClaudeMcp"] = self.sw_claude.get()
        db["settings"]["injectAntigravityKnowledge"] = self.sw_anti.get()
        db["settings"]["folderWatcherActive"] = self.sw_watcher.get()
        db["settings"]["minimizeToTray"] = self.sw_tray.get()
        db["settings"]["autoSyncOnChange"] = self.sw_autosync.get()
        if hasattr(self, "combo_settings_gemini_model"):
            db["settings"]["defaultGeminiModel"] = self.combo_settings_gemini_model.get()

        scope_mode_map = {
            "מאקרו בלבד": "macro",
            "לפי פרויקטים": "micro",
            "מצב משולב": "both",
            "מאקרו (גלובלי בלבד)": "macro",
            "מיקרו (לפי פרויקטים)": "micro",
            "היברידי (שניהם)": "both",
            "מאקרו (גלובלי בלבד - מומלץ)": "macro",
            "מיקרו (פר פרויקט בלבד)": "micro",
            "שניהם (היברידי: מאקרו + מיקרו)": "both"
        }
        if hasattr(self, "seg_sync_scope"):
            db["settings"]["syncScopeMode"] = scope_mode_map.get(self.seg_sync_scope.get(), "macro")
        if hasattr(self, "sw_clean_on_macro"):
            db["settings"]["cleanProjectsOnMacro"] = self.sw_clean_on_macro.get()

        if hasattr(self, "sw_auto_update_check"):
            db["settings"]["checkUpdatesOnStartup"] = self.sw_auto_update_check.get()
        if hasattr(self, "sw_auto_install"):
            db["settings"]["autoInstallUpdates"] = bool(self.sw_auto_install.get())
        if hasattr(self, "sw_global_targets"):
            db["settings"]["injectGlobalTargets"] = bool(self.sw_global_targets.get())
        if hasattr(self, "sw_mcp_mode_switch"):
            db["settings"]["allowMcpModeSwitch"] = bool(self.sw_mcp_mode_switch.get())
        memory_hub.save_db(db)
        if db.get("settings", {}).get("autoSyncOnChange", True):
            memory_hub.inject_all()
        self.set_status("הגדרות נשמרו")

    # =========================================================================
    # GITHUB AUTO-UPDATE SYSTEM
    # =========================================================================
    def sweep_expired_rules(self):
        """
        Injection is event-driven, so without this a rule that lapsed overnight would stay
        in every project's rule file until the next edit. Re-checked hourly.
        """
        def worker():
            expired = memory_hub.sweep_expired_items()
            if expired:
                names = ", ".join(
                    (e["item"].get("name") or e["item"].get("constraint")
                     or e["item"].get("aspect") or e["item"].get("instruction") or "?")
                    for e in expired[:3]
                )
                self.after(0, lambda: self.set_status(
                    f"{len(expired)} כללים פגו והוסרו מקובצי החוקים: {names}"))
                self.after(0, self.refresh_all_views)

        self.run_async(worker)
        self.after(60 * 60 * 1000, self.sweep_expired_rules)

    def prune_invalid_paths_on_startup(self):
        """
        Drops sync targets that no longer exist or were never real projects (PyInstaller
        temp folders auto-registered by older builds), so syncs don't waste work writing
        rule files into throwaway directories.
        """
        try:
            removed = memory_hub.prune_invalid_paths()
        except Exception as e:
            print(f"[prune paths] {e}")
            return

        if removed:
            self.refresh_page_paths()
            self.update_stats()
            self.set_status(f"נוקו {len(removed)} נתיבי סנכרון לא תקינים")

    def warn_if_database_unreadable(self):
        """
        If memory.json could not be read at startup the app silently continues on an empty
        default database - and the next save would overwrite the real file. Tell the user,
        and point them at the preserved copy so nothing is lost without their knowledge.
        """
        err_info = getattr(memory_hub, "LAST_LOAD_ERROR", {}) or {}
        if not err_info.get("error"):
            return

        preserved = err_info.get("preserved_path")
        msg = (
            "לא ניתן היה לקרוא את קובץ הזיכרון (memory.json) והאפליקציה נטענה עם נתוני ברירת מחדל.\n\n"
            f"פירוט השגיאה: {err_info.get('error')}\n\n"
        )
        if preserved:
            msg += (f"עותק של הקובץ המקורי נשמר עבורך כאן:\n{preserved}\n\n"
                    "מומלץ לשחזר ממנו (או מהגיבוי memory.json.bak) לפני ביצוע שינויים נוספים.")
        else:
            msg += "לא ניתן היה לשמור עותק של הקובץ המקורי. מומלץ לבדוק את תיקיית הנתונים ידנית."

        self.set_status("אזהרה: קובץ הזיכרון לא נקרא - נטענו נתוני ברירת מחדל")
        messagebox.showwarning("שגיאה בטעינת קובץ הזיכרון", msg)

        # Only warn once per launch.
        err_info["error"] = None

    def prepare_silent_update(self, release_info):
        """
        Downloads and verifies a new version in the background and parks it. Nothing is
        installed mid-session: the installer runs on exit, once the .exe it replaces is no
        longer running and the database has been closed cleanly.
        """
        import tempfile

        use_setup = bool(release_info.get("setup_download_url"))
        dl_url = release_info.get("setup_download_url") or release_info.get("portable_download_url")
        expected_sha = release_info.get("setup_sha256") if use_setup else release_info.get("portable_sha256")
        new_v = release_info.get("latest_version", "")

        if not dl_url:
            return

        dest_dir = tempfile.mkdtemp(prefix="AIMemoryHubUpdate_")
        dest = os.path.join(dest_dir, f"AIMemoryHub_Setup_v{new_v}.exe")

        ok, res = updater.download_update(dl_url, dest, expected_sha256=expected_sha)
        if not ok:
            print(f"[silent update] {res}")
            self.after(0, lambda: self.set_status(f"הורדת העדכון נכשלה: {res}"))
            return

        self._pending_update = {"path": dest, "sha256": expected_sha, "version": new_v}
        self.after(0, lambda: self.set_status(
            f"גרסה {new_v} הורדה ואומתה — תותקן אוטומטית בסגירת התוכנה"))

    def install_pending_update(self):
        """Runs on the way out, after the tray icon is stopped and before the process ends."""
        pending = getattr(self, "_pending_update", None)
        if not pending:
            return
        try:
            ok, msg = updater.launch_installer_silent(pending["path"], pending.get("sha256"))
            if not ok:
                print(f"[silent update] {msg}")
        except Exception as e:
            print(f"[silent update] {e}")

    def check_startup_updates(self):
        db = memory_hub.load_db()
        if not db.get("settings", {}).get("checkUpdatesOnStartup", True):
            return

        auto_install = db.get("settings", {}).get("autoInstallUpdates", False)

        def worker():
            try:
                avail, info, msg = updater.check_for_updates()
                if avail and info:
                    if auto_install and not getattr(self, "_pending_update", None):
                        self.prepare_silent_update(info)
                    else:
                        self.after(0, lambda: self.open_update_dialog(info))
            except Exception as e:
                # Runs every 20 minutes in the background: record the failure instead of
                # swallowing it, otherwise a permanently broken update check is invisible.
                print(f"[startup update check] {e}")
                try:
                    self.after(0, lambda err=e: self.set_status(f"בדיקת עדכונים ברקע נכשלה: {err}"))
                except Exception:
                    pass

        self.run_async(worker)
        # Schedule next periodic background check every 20 minutes
        self.after(20 * 60 * 1000, self.check_startup_updates)

    def on_check_updates_manual(self):
        if hasattr(self, "btn_check_update"):
            self.btn_check_update.configure(state="disabled", text="בודק עדכונים... ⏳")
        if hasattr(self, "btn_sidebar_update"):
            self.btn_sidebar_update.configure(state="disabled", text="בודק עדכונים... ⏳")
        self.set_status("בודק עדכונים מול GitHub Releases...")

        def worker():
            avail, info, msg = updater.check_for_updates()
            self.after(0, lambda: self.on_check_updates_done(avail, info, msg))

        self.run_async(worker)

    def on_check_updates_done(self, avail, info, msg):
        if hasattr(self, "btn_check_update"):
            self.btn_check_update.configure(state="normal", text="בדוק עדכונים עכשיו 🔄")
        if hasattr(self, "btn_sidebar_update"):
            self.btn_sidebar_update.configure(state="normal", text="בדיקת עדכוני תוכנה")
        self.set_status(msg)
        if info:
            self.open_update_dialog(info, is_newer=avail)
        else:
            messagebox.showinfo("בדיקת עדכונים", f"{msg}")

    def open_update_dialog(self, release_info, is_newer=True):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        cur_v = release_info.get("current_version", updater.CURRENT_VERSION)
        new_v = release_info.get("latest_version", "")

        diag = ctk.CTkToplevel(self)
        title_str = "התראת עדכון: גרסה חדשה זמינה בענן!" if is_newer else "✓ המערכת מעודכנת לגרסה העדכנית ביותר"
        diag.title(title_str)
        diag.geometry("580x520")
        diag.attributes("-topmost", True)
        diag.lift()
        diag.focus_force()

        box = ctk.CTkFrame(diag, corner_radius=14, fg_color=GLASS_CARD, border_width=1, border_color=GLASS_CARD_BORDER)
        box.pack(fill="both", expand=True, padx=12, pady=12)

        hdr_color = ("#0284c7", "#38bdf8") if is_newer else ("#059669", "#34d399")
        hdr_txt = f"גרסה חדשה זמינה בענן: v{new_v}" if is_newer else f"✓ אתה משתמש בגרסה העדכנית ביותר (v{cur_v})"
        ctk.CTkLabel(box, text=hdr_txt, font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color=hdr_color).pack(anchor="e", padx=16, pady=(14, 2))

        sub_txt = f"גרסה נוכחית מותקנת: v{cur_v}  ➜  גרסה חדשה בענן: v{new_v}" if is_newer else f"הגרסה שבידך (v{cur_v}) תואמת לשחרור העדכני ביותר בענן."
        ctk.CTkLabel(box, text=sub_txt, font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_PRIMARY).pack(anchor="e", padx=16, pady=(0, 6))

        ctk.CTkLabel(box, text="חידושים ושינויים בגרסה זו", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=TEXT_SECONDARY).pack(anchor="e", padx=16, pady=(4, 2))
        txt_body = ctk.CTkTextbox(box, height=150, font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_PRIMARY, corner_radius=8, fg_color=GLASS_INPUT, border_width=1, border_color=GLASS_INPUT_BORDER, wrap="word")
        txt_body.pack(fill="x", padx=16, pady=(0, 8))
        txt_body.insert("1.0", release_info.get("body", ""))
        txt_body.configure(state="disabled")

        # Progress bar and status (hidden until download starts)
        f_progress = ctk.CTkFrame(box, fg_color="transparent")
        f_progress.pack(fill="x", padx=16, pady=(2, 2))

        prog_bar = ctk.CTkProgressBar(f_progress, height=12, corner_radius=6)
        prog_bar.set(0)
        lbl_prog = ctk.CTkLabel(f_progress, text="", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=TEXT_SECONDARY)

        btn_row = ctk.CTkFrame(box, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(10, 10))

        dl_btn_txt = "הורדה והתקנה של העדכון" if is_newer else "התקנה מחדש / רענון גרסה"
        btn_download = ctk.CTkButton(btn_row, text=dl_btn_txt, fg_color="#059669", hover_color="#047857", text_color="#ffffff", height=34, corner_radius=8)
        btn_download.pack(side="right", padx=(6, 0))

        btn_web = ctk.CTkButton(btn_row, text="פתיחת דף הפרויקט", fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff", height=34, corner_radius=8,
                                command=lambda: webbrowser.open(release_info.get("html_url", updater.GITHUB_RELEASES_URL)))
        btn_web.pack(side="right", padx=(6, 0))

        btn_close = ctk.CTkButton(btn_row, text="הזכר לי מאוחר יותר", fg_color=("#E5E5E5", "#334155"), hover_color=("#D5D5D5", "#475569"), text_color=TEXT_PRIMARY, height=34, corner_radius=8, command=diag.destroy)
        btn_close.pack(side="left")

        def start_download():
            use_setup = bool(release_info.get("setup_download_url"))
            dl_url = release_info.get("setup_download_url") or release_info.get("portable_download_url")
            expected_sha = release_info.get("setup_sha256") if use_setup else release_info.get("portable_sha256")
            if not dl_url:
                messagebox.showerror("שגיאה", "לא נמצא קובץ התקנה ישיר להורדה עבור שחרור זה ב-GitHub.")
                return

            btn_download.configure(state="disabled", text="⏳ מוריד...")
            prog_bar.pack(fill="x", pady=(2, 2))
            lbl_prog.pack(anchor="e")

            import tempfile
            # Private, randomly-named directory so another local process can't predict the
            # installer path and swap the file before it is executed.
            dest_dir = tempfile.mkdtemp(prefix="AIMemoryHubUpdate_")
            dest = os.path.join(dest_dir, f"AIMemoryHub_Setup_v{new_v}.exe")

            def on_prog(percent, dl_bytes, total_bytes):
                p_val = percent / 100.0
                dl_mb = dl_bytes / (1024 * 1024)
                tot_mb = total_bytes / (1024 * 1024)
                diag.after(0, lambda: prog_bar.set(p_val))
                diag.after(0, lambda: lbl_prog.configure(text=f"הורדה: {percent:.1f}% ({dl_mb:.1f} מתוך {tot_mb:.1f} MB)"))

            def launch_installer():
                try:
                    updater.launch_installer_and_exit(dest, expected_sha256=expected_sha)
                except Exception as e:
                    messagebox.showerror("שגיאת התקנה", f"לא ניתן להפעיל את קובץ ההתקנה:\n{e}")
                    btn_download.configure(state="normal", text="⬇️ נסה שוב")

            def worker():
                ok, res = updater.download_update(dl_url, dest, progress_callback=on_prog, expected_sha256=expected_sha)
                if ok:
                    diag.after(0, lambda: lbl_prog.configure(text="ההורדה הושלמה! מפעיל את תוכנית ההתקנה..."))
                    diag.after(800, launch_installer)
                else:
                    diag.after(0, lambda: messagebox.showerror("שגיאת הורדה", res))
                    diag.after(0, lambda: btn_download.configure(state="normal", text="⬇️ נסה שוב"))

            self.run_async(worker)

        btn_download.configure(command=start_download)

    def on_export_backup(self):
        default_name = f"ai_memory_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=default_name, filetypes=[("JSON files", "*.json")])
        if path:
            memory_hub.export_backup(path)
            messagebox.showinfo("גיבוי הושלם", f"הגיבוי נשמר בהצלחה ב:\n{path}")
            self.set_status("קובץ גיבוי יוצא בהצלחה")

    def on_import_backup(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if path:
            if messagebox.askyesno("שחזור גיבוי", "האם לשחזר את הנתונים מקובץ הגיבוי? פעולה זו תחליף את הנתונים הנוכחיים."):
                ok, msg = memory_hub.import_backup(path)
                if ok:
                    self.update_profiles_combo()
                    self.refresh_all_views()
                    messagebox.showinfo("שחזור הושלם", msg)
                else:
                    messagebox.showerror("שגיאת שחזור", msg)

    def refresh_page_settings(self):
        db = memory_hub.load_db()
        logs = db.get("logs", [])
        self.txt_logs.delete("1.0", "end")
        for log in logs:
            time_str = log.get("timestamp", "")[:19].replace("T", " ")
            msg = log.get("message", "")
            self.txt_logs.insert("end", f"[{time_str}] {msg}\n")

    # =========================================================================
    # SYSTEM TRAY INTEGRATION (pystray)
    # =========================================================================
    def create_tray_image(self):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
        icon_path = os.path.join(base_dir, "app_icon.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path).convert("RGBA")
                return img.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass
        # Fallback neon brain icon
        img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=(79, 70, 229, 255))
        draw.ellipse([18, 18, 46, 46], fill=(129, 140, 248, 255))
        draw.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 255))
        return img

    def init_web_dashboard(self):
        try:
            web_server.start_server(port=3456, background=True)
        except Exception as e:
            print(f"[init_web_dashboard] Error: {e}")

    def open_web_dashboard(self):
        webbrowser.open("http://localhost:3456")
        self.set_status("נפתח לוח הבקרה המודרני בדפדפן (http://localhost:3456)")

    def init_system_tray(self):
        if not pystray:
            return

        def tray_worker():
            menu = pystray.Menu(
                pystray.MenuItem("הצג חלון ראשי", lambda: self.restore_from_tray()),
                pystray.MenuItem("פתח Web Dashboard בדפדפן 🌐", lambda: self.open_web_dashboard()),
                pystray.MenuItem("הוספה מהירה (Ctrl+Alt+M)", lambda: self.open_spotlight()),
                pystray.MenuItem("סנכרן עכשיו לכל הנתיבים", lambda: self.on_sync_all_click()),
                pystray.MenuItem("יציאה מלאה", lambda: self.quit_application())
            )
            self.tray_icon = pystray.Icon("AIMemoryHub", self.create_tray_image(), "Universal AI Memory Hub", menu)
            self.tray_icon.run()

        threading.Thread(target=tray_worker, daemon=True).start()

    def restore_from_tray(self):
        self.after(0, lambda: (self.deiconify(), self.lift(), self.focus_force()))

    def on_window_close(self):
        db = memory_hub.load_db()
        if db.get("settings", {}).get("minimizeToTray", False) and pystray:
            self.withdraw()
            self.set_status("המערכת ממוזערת למגש המערכת (Ctrl+Alt+M להוספה מהירה)")
        else:
            self.quit_application()

    def quit_application(self):
        if self.tray_icon:
            try: self.tray_icon.stop()
            except Exception: pass
        # Install a downloaded update here, not mid-session: the executable being replaced
        # is about to stop running and the database is already saved.
        self.install_pending_update()
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    # =========================================================================
    # GLOBAL HOTKEY & SPOTLIGHT (Ctrl+Alt+M)
    # =========================================================================
    def init_global_hotkey(self):
        if not keyboard:
            return

        def on_hotkey():
            self.after(0, self.open_spotlight)

        try:
            keyboard.add_hotkey("ctrl+alt+m", on_hotkey)
        except Exception as e:
            print(f"Could not register global hotkey: {e}")

    def open_spotlight(self):
        spotlight.show_spotlight(master=self, on_saved_callback=self.on_spotlight_saved)

    def on_spotlight_saved(self):
        self.refresh_all_views()
        self.set_status("נוספה עובדה חדשה דרך Spotlight והושתלה בהצלחה!")

    # =========================================================================
    # FOLDER WATCHER (ניטור תיקיות בזמן אמת)
    # =========================================================================
    def init_folder_watcher(self):
        def on_new_folder(path, name):
            self.after(0, lambda: self.notify_new_folder(path, name))

        memory_hub.start_folder_watcher(on_new_project_callback=on_new_folder)

    def notify_new_folder(self, path, name):
        self.refresh_page_paths()
        self.update_stats()
        self.set_status(f"זוהה פרויקט חדש: {name} והושתלו בו קובצי הזיכרון!")

    # =========================================================================
    # HELPERS & SYNC
    # =========================================================================
    def create_page_header(self, parent, title, subtitle):
        glass_hdr = ctk.CTkFrame(
            parent,
            corner_radius=14,
            fg_color=GLASS_HEADER_BG,
            border_width=1,
            border_color=GLASS_HEADER_BORDER
        )
        glass_hdr.pack(fill="x", pady=(0, 10))

        content = ctk.CTkFrame(glass_hdr, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=10)

        # Right side: Title & Subtitle
        r_box = ctk.CTkFrame(content, fg_color="transparent")
        r_box.pack(side="right", fill="x", expand=True)

        ctk.CTkLabel(
            r_box,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(anchor="e")

        ctk.CTkLabel(
            r_box,
            text=subtitle,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_MUTED
        ).pack(anchor="e", pady=(2, 0))

        # Left side: Software Update Button + Luminous Pill Badge
        btn_hdr_update = ctk.CTkButton(
            content,
            text="בדיקת עדכוני תוכנה",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=30,
            width=160,
            corner_radius=8,
            fg_color=ACCENT_COLOR,
            border_width=1,
            border_color=("#bfdbfe", "#2563eb"),
            text_color="#ffffff",
            hover_color=ACCENT_HOVER,
            command=self.on_check_updates_manual
        )
        btn_hdr_update.pack(side="left", padx=(0, 8))

        badge = ctk.CTkFrame(
            content,
            corner_radius=20,
            fg_color=("#ecfdf5", "#064e3b"),
            border_width=1,
            border_color=("#a7f3d0", "#059669")
        )
        badge.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(
            badge,
            text="מנוע פעיל ●",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=("#047857", "#34d399")
        ).pack(padx=10, pady=3)

    def create_statusbar(self):
        self.statusbar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=GLASS_BG_SIDEBAR, border_width=1, border_color=GLASS_DIVIDER)
        self.statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")

        f_st = ctk.CTkFrame(self.statusbar, fg_color="transparent")
        f_st.pack(side="right", padx=16)

        ctk.CTkLabel(f_st, text="🟢", font=ctk.CTkFont(size=9)).pack(side="right", padx=(4, 0))
        self.lbl_status = ctk.CTkLabel(
            f_st,
            text="מוכן לפעולה. Ctrl+Alt+M להוספה מהירה מכל מקום.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY
        )
        self.lbl_status.pack(side="right")

    def set_status(self, text):
        self.lbl_status.configure(text=text)

    def update_stats(self):
        p_data = memory_hub.get_current_profile_data()
        f_act = len([x for x in p_data.get("facts", []) if x.get("active", True)])
        c_act = len([x for x in p_data.get("commands", []) if x.get("active", True)])
        k_act = len([x for x in p_data.get("constraints", []) if x.get("active", True)])
        s_act = len([x for x in p_data.get("styles", []) if x.get("active", True)])
        i_act = len([x for x in p_data.get("instructions", []) if x.get("active", True)])
        files_act = len([x for x in p_data.get("context_files", []) if x.get("active", True)])
        p_act = len([x for x in memory_hub.get_paths() if x.get("active", True)])

        total = f_act + c_act + k_act + s_act + i_act + files_act
        stats_text = f"סה\"כ {total} כללים וקבצים פעילים\nבתוך {p_act} נתיבי פרויקטים"

        # Proposals from the MCP server are never written to memory on their own - if the
        # queue isn't visible, an AI suggestion just sits there unseen.
        try:
            pending = memory_hub.count_pending_proposals()
        except Exception:
            pending = 0
        if pending:
            stats_text += f"\n🔔 {pending} הצעות ממתינות לאישורך"

        self.lbl_sidebar_stats.configure(text=stats_text)
        self.update_proposals_button(pending)

    def update_proposals_button(self, pending):
        """Shows a review button in the sidebar only while proposals are waiting."""
        if not hasattr(self, "btn_proposals"):
            self.btn_proposals = ctk.CTkButton(
                self.lbl_sidebar_stats.master,
                text="",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                fg_color=("#fef3c7", "#78350f"),
                hover_color=("#fde68a", "#92400e"),
                text_color=TEXT_PRIMARY,
                height=28,
                corner_radius=8,
                command=self.open_proposals_dialog,
            )

        if pending:
            self.btn_proposals.configure(text=f"אשר או דחה {pending} הצעות")
            self.btn_proposals.pack(fill="x", pady=(0, 6))
        else:
            self.btn_proposals.pack_forget()

    def open_proposals_dialog(self):
        """Review queue for memory an AI proposed through the MCP server."""
        proposals = memory_hub.get_proposals("pending")

        diag = ctk.CTkToplevel(self)
        diag.title("הצעות הממתינות לאישור")
        diag.geometry("720x560")
        diag.attributes("-topmost", True)
        diag.configure(fg_color=GLASS_BG_MAIN)

        ctk.CTkLabel(
            diag,
            text="זיכרון שנלמד אוטומטית — ממתין לאישורך",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="e", padx=16, pady=(14, 2))

        ctk.CTkLabel(
            diag,
            text="כל פריט כאן הגיע דרך שרת הזיכרון (MCP). אישור יוסיף אותו לפרופיל שצוין; דחייה תסיר אותו.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=TEXT_SECONDARY,
            wraplength=650,
            justify="right",
        ).pack(anchor="e", padx=16, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(diag, corner_radius=12, fg_color=GLASS_BG_MAIN)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        def close_and_refresh():
            diag.destroy()
            self.refresh_all_views()

        if not proposals:
            ctk.CTkLabel(
                scroll,
                text="אין כרגע הצעות ממתינות.",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=TEXT_PRIMARY,
            ).pack(pady=30)

        for prop in proposals:
            card = self.create_glass_card(scroll, corner_radius=10)
            card.pack(fill="x", pady=5, padx=4)

            item = prop.get("item", {})
            label = (item.get("name") or item.get("constraint") or item.get("aspect")
                     or item.get("instruction") or "(ללא כותרת)")
            body = (item.get("value") or item.get("details") or item.get("alternative_or_why")
                    or item.get("when_to_apply") or "")

            head = ctk.CTkFrame(card, fg_color="transparent")
            head.pack(fill="x", padx=12, pady=(8, 2))
            ctk.CTkLabel(head, text=label, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                         text_color=TEXT_PRIMARY, wraplength=430, justify="right").pack(side="right")
            self.create_glass_badge(head, prop.get("category", ""), "cyan").pack(side="left", padx=3)
            self.create_glass_badge(head, prop.get("target_profile", "default"), "purple").pack(side="left", padx=3)

            if body:
                ctk.CTkLabel(card, text=body, font=ctk.CTkFont(family="Segoe UI", size=11),
                             text_color=TEXT_SECONDARY, wraplength=620, justify="right").pack(anchor="e", padx=12)

            if prop.get("raw_text"):
                ctk.CTkLabel(card, text=f"מקור: \"{prop['raw_text'][:160]}\"",
                             font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
                             text_color=TEXT_MUTED, wraplength=620, justify="right").pack(anchor="e", padx=12, pady=(2, 0))

            if prop.get("conflicts"):
                ctk.CTkLabel(card, text=f"⚠️ זוהו {len(prop['conflicts'])} סתירות מול הזיכרון הקיים",
                             font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                             text_color=("#b91c1c", "#fb7185"),
                             wraplength=620, justify="right").pack(anchor="e", padx=12, pady=(2, 0))

            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(fill="x", padx=12, pady=(6, 8))

            def on_approve(pid=prop["id"]):
                ok, res = memory_hub.approve_proposal(pid)
                if ok:
                    self.set_status("ההצעה אושרה ונוספה לזיכרון")
                else:
                    messagebox.showerror("שגיאה", str(res))
                close_and_refresh()

            def on_reject(pid=prop["id"]):
                memory_hub.reject_proposal(pid)
                self.set_status("ההצעה נדחתה")
                close_and_refresh()

            ctk.CTkButton(btns, text="אשר והוסף", width=110, height=28, corner_radius=6,
                          font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                          fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff",
                          command=on_approve).pack(side="right", padx=(0, 6))

            ctk.CTkButton(btns, text="דחה", width=80, height=28, corner_radius=6,
                          font=ctk.CTkFont(family="Segoe UI", size=11),
                          fg_color="transparent", border_width=1, border_color=GLASS_INPUT_BORDER,
                          text_color=TEXT_SECONDARY, command=on_reject).pack(side="right")

        ctk.CTkButton(diag, text="סגור", width=120, height=32, corner_radius=8,
                      fg_color="transparent", border_width=1, border_color=GLASS_INPUT_BORDER,
                      text_color=TEXT_PRIMARY, command=close_and_refresh).pack(pady=(0, 12))

    def refresh_all_views(self):
        self.refresh_page_chat_memory()
        self.refresh_page_facts()
        self.refresh_page_commands()
        self.refresh_page_constraints()
        self.refresh_page_styles()
        self.refresh_page_instructions()
        self.refresh_page_context_files()
        self.refresh_page_paths()
        self.refresh_page_preview()
        self.refresh_page_settings()
        self.update_stats()

    def on_sync_all_click(self):
        self.btn_sidebar_sync.configure(state="disabled", text="⏳ משתיל...")
        self.set_status("מבצע השתלה לכל הנתיבים...")

        def worker():
            res = memory_hub.inject_all()
            self.after(0, lambda: self.on_sync_finished(res))
        self.run_async(worker)

    def open_drift_dialog(self, drifted):
        """
        Shown when a rule file's injected block was edited outside the app. The edit is
        still on disk - nothing was overwritten - and the user decides what happens to it.
        """
        total_files = sum(len(d.get("files", [])) for d in drifted)

        diag = ctk.CTkToplevel(self)
        diag.title("קבצי חוקים ששונו מחוץ לאפליקציה")
        diag.geometry("700x520")
        diag.attributes("-topmost", True)
        diag.configure(fg_color=GLASS_BG_MAIN)

        ctk.CTkLabel(diag, text=f"⚠️ {total_files} קבצים שונו ידנית — לא נדרסו",
                     font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="e", padx=16, pady=(14, 2))

        ctk.CTkLabel(diag,
                     text="הבלוק בקבצים האלה שונה מאז הסנכרון האחרון, ולכן הסנכרון דילג עליהם "
                          "והשאיר את העריכה שלך. בחר מה לעשות עם כל אחד.",
                     font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY,
                     wraplength=640, justify="right").pack(anchor="e", padx=16, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(diag, corner_radius=12, fg_color=GLASS_BG_MAIN)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        for folder_entry in drifted:
            folder = folder_entry.get("folder", "")
            for f in folder_entry.get("files", []):
                card = self.create_glass_card(scroll, corner_radius=10)
                card.pack(fill="x", pady=4, padx=4)

                ctk.CTkLabel(card, text=f.get("file", ""),
                             font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                             text_color=TEXT_PRIMARY).pack(anchor="e", padx=12, pady=(8, 0))
                ctk.CTkLabel(card, text=folder, font=ctk.CTkFont(family="Segoe UI", size=10),
                             text_color=TEXT_MUTED, wraplength=600,
                             justify="right").pack(anchor="e", padx=12)

                btns = ctk.CTkFrame(card, fg_color="transparent")
                btns.pack(fill="x", padx=12, pady=(6, 8))

                def on_open(path=f.get("path")):
                    try:
                        os.startfile(path)
                    except Exception as e:
                        messagebox.showerror("שגיאה", f"לא ניתן לפתוח את הקובץ:\n{e}")

                def on_overwrite(fold=folder):
                    if not messagebox.askyesno(
                            "לדרוס את השינוי?",
                            "העריכה הידנית בקובץ תוחלף בתוכן מהזיכרון. להמשיך?"):
                        return
                    memory_hub.force_resync_folder(fold)
                    diag.destroy()
                    self.refresh_all_views()
                    self.set_status("הקובץ נדרס בהתאם לזיכרון")

                ctk.CTkButton(btns, text="שמור את העריכה שלי", width=140, height=28, corner_radius=6,
                              font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                              fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#ffffff",
                              command=diag.destroy).pack(side="right", padx=(0, 6))

                ctk.CTkButton(btns, text="פתח את הקובץ", width=110, height=28, corner_radius=6,
                              font=ctk.CTkFont(family="Segoe UI", size=11),
                              fg_color="transparent", border_width=1, border_color=GLASS_INPUT_BORDER,
                              text_color=TEXT_SECONDARY, command=on_open).pack(side="right", padx=(0, 6))

                ctk.CTkButton(btns, text="דרוס מהזיכרון", width=110, height=28, corner_radius=6,
                              font=ctk.CTkFont(family="Segoe UI", size=11),
                              fg_color="transparent", border_width=1, border_color=("#b91c1c", "#fb7185"),
                              text_color=("#b91c1c", "#fb7185"),
                              command=on_overwrite).pack(side="right")

        ctk.CTkButton(diag, text="סגור", width=120, height=32, corner_radius=8,
                      fg_color="transparent", border_width=1, border_color=GLASS_INPUT_BORDER,
                      text_color=TEXT_PRIMARY, command=diag.destroy).pack(pady=(0, 12))

    def on_sync_finished(self, res):
        self.btn_sidebar_sync.configure(state="normal", text="השתל לכל הנתיבים")
        self.refresh_all_views()

        global_written = res.get("global_written") or []
        global_failed = res.get("global_failed") or []
        global_line = ""
        if global_written:
            global_line = f"\nקבצי חוקים גלובליים שעודכנו: {', '.join(global_written)}"
        if global_failed:
            names = ", ".join(g.get("name", "?") for g in global_failed)
            global_line += f"\n⚠️ נכשלה כתיבה גלובלית: {names}"

        # A file whose block was edited by hand is skipped rather than overwritten - tell
        # the user, or "protected your edit" becomes just as silent as destroying it was.
        drifted = res.get("drifted_files") or []
        if drifted:
            self.after(200, lambda d=drifted: self.open_drift_dialog(d))

        failed = res.get("failed_folders") or []
        if failed:
            # Report the real outcome: some folders could not be written (read-only,
            # locked by a sync client, disk full) - never claim a full success.
            details = "\n".join(
                f"• {f.get('folder')}: {'; '.join(f.get('errors', []))[:160]}" for f in failed[:5]
            )
            if len(failed) > 5:
                details += f"\n… ועוד {len(failed) - 5} נתיבים נוספים."
            msg = (f"הסנכרון הושלם חלקית.\n\n"
                   f"עודכנו {res['folders_synced']} מתוך {res.get('total_active_folders', 0)} נתיבים.\n"
                   f"{len(failed)} נתיבים נכשלו:\n\n{details}{global_line}")
            self.set_status(f"סנכרון חלקי: {len(failed)} נתיבים נכשלו")
            messagebox.showwarning("השתלה הושלמה חלקית", msg)
            return

        msg = (f"סנכרון מלא הושלם בהצלחה!\n"
               f"עודכנו {res['folders_synced']} נתיבי פרויקטים + Claude Desktop + Antigravity."
               f"{global_line}")
        self.set_status("סנכרון מלא הושלם!")
        messagebox.showinfo("השתלה הושלמה", msg)


if __name__ == "__main__":
    # A frozen build has no mcp_server.py on disk for an AI client to launch, so the .exe
    # itself doubles as the MCP server when started with --mcp (see get_mcp_launch_command).
    if "--mcp" in sys.argv[1:]:
        import mcp_server
        mcp_server.main()
    else:
        app = AIMemoryHubApp()
        app.mainloop()
