#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spotlight Quick-Add Overlay for Universal AI Memory Hub.
A sleek, floating modal triggered globally by Ctrl+Alt+M from anywhere on Windows.
"""

import sys
import re
import tkinter as tk
import customtkinter as ctk

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import memory_hub


class SpotlightOverlay(ctk.CTkToplevel):
    def __init__(self, master=None, on_saved_callback=None):
        super().__init__(master)

        self.on_saved_callback = on_saved_callback
        self.title("AI Memory Hub - הוספה מהירה")

        # Window styling
        self.overrideredirect(True)  # Borderless floating window
        self.attributes("-topmost", True)
        self.configure(fg_color="#0f172a")

        # Center on screen (near top)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w = 680
        h = 160
        x = (screen_w - w) // 2
        y = int(screen_h * 0.2)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Border outline frame
        outer = ctk.CTkFrame(self, corner_radius=14, border_width=2, border_color="#6366f1", fg_color="#0f172a")
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        # Header Row
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        title = ctk.CTkLabel(
            header,
            text="🧠 הוספה מהירה לזיכרון ה-AI (Spotlight)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#f8fafc"
        )
        title.pack(side="right")

        hint = ctk.CTkLabel(
            header,
            text="לחץ Enter לשמירה | Esc לסגירה",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748b"
        )
        hint.pack(side="left")

        # Main Input Row
        input_frame = ctk.CTkFrame(outer, fg_color="transparent")
        input_frame.pack(fill="x", padx=16, pady=(4, 8))

        self.entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="הקלד כאן... (למשל: 'האתר שלי: example.com' או 'איסור: אל תמחק הערות' או 'חתימה: בברכה, [שמך]')...",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=42,
            fg_color="#1e293b",
            text_color="#f8fafc",
            placeholder_text_color="#64748b",
            border_color="#334155"
        )
        self.entry.pack(fill="x")
        self.entry.focus_set()

        # Options Row: Type & Scope
        opt_frame = ctk.CTkFrame(outer, fg_color="transparent")
        opt_frame.pack(fill="x", padx=16, pady=(0, 10))

        # Scope selector
        self.combo_scope = ctk.CTkComboBox(
            opt_frame,
            values=["גלובלי (לכל הפרויקטים)"] + [p.get("name") for p in memory_hub.get_paths()],
            width=200,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#1e293b",
            text_color="#f8fafc",
            border_color="#334155",
            button_color="#334155",
            dropdown_fg_color="#1e293b",
            dropdown_text_color="#f8fafc"
        )
        self.combo_scope.pack(side="right")

        ctk.CTkLabel(opt_frame, text="תחולה:", font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94a3b8").pack(side="right", padx=(0, 6))

        # Status Label
        self.lbl_status = ctk.CTkLabel(
            opt_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#4ade80"
        )
        self.lbl_status.pack(side="left")

        # Key Bindings
        self.bind("<Escape>", lambda e: self.close_spotlight())
        self.entry.bind("<Return>", lambda e: self.on_save())

        # Grab focus
        self.after(100, self.force_focus)

    def force_focus(self):
        self.lift()
        self.focus_force()
        self.entry.focus_set()

    def close_spotlight(self):
        self.destroy()

    def on_save(self):
        raw = self.entry.get().strip()
        if not raw:
            return

        scope_val = self.combo_scope.get()
        scope = "global" if "גלובלי" in scope_val else scope_val

        try:
            msg = self.classify_and_store(raw, scope)
        except Exception as e:
            # A failed save (disk full, file locked by OneDrive, permission error) must not
            # leave the always-on-top overlay frozen with no feedback and no auto-close.
            self.lbl_status.configure(text=f"❌ השמירה נכשלה: {e}")
            self.entry.configure(state="normal")
            return

        self.lbl_status.configure(text=f"✅ {msg} והושתל בהצלחה!")
        self.entry.configure(state="disabled")

        if self.on_saved_callback:
            try:
                self.on_saved_callback()
            except Exception as e:
                print(f"[Spotlight] on_saved_callback failed: {e}")

        self.after(600, self.close_spotlight)

    def classify_and_store(self, raw, scope):
        """
        Detects the directive category from the free-text input and stores it.
        Returns the status message; raises on storage failure so on_save can report it.
        """
        # Smart Parsing: Detect Category
        # 1. Negative Constraint
        if any(k in raw.lower() for k in ["איסור:", "אסור:", "לעולם אל", "אל תעשה", "never"]):
            cleaned = re.sub(r'^(איסור:|אסור:)\s*', '', raw, flags=re.IGNORECASE).strip()
            memory_hub.add_constraint(cleaned, "הימנע מכך לחלוטין", scope=scope)
            msg = "⛔ נשמר איסור מחייב"

        # 2. Command
        elif any(k in raw.lower() for k in ["חתימה", "פקודה:", "בסוף כל", "תמיד לשים"]):
            cleaned = re.sub(r'^(פקודה:)\s*', '', raw, flags=re.IGNORECASE).strip()
            name = "פקודה אוטומטית"
            details = cleaned
            trigger = "בכל מקרה רלוונטי"
            if ":" in cleaned:
                parts = cleaned.split(":", 1)
                name = parts[0].strip()
                details = parts[1].strip()
            memory_hub.add_command(name, details, trigger, scope=scope)
            msg = f"⚡ נשמרה פקודה: {name}"

        # 3. Tone / Style
        elif any(k in raw.lower() for k in ["סגנון:", "טון:", "עברית", "תמציתי", "בלי הקדמות"]):
            cleaned = re.sub(r'^(סגנון:|טון:)\s*', '', raw, flags=re.IGNORECASE).strip()
            aspect = "סגנון וטון מענה"
            instruction = cleaned
            if ":" in cleaned:
                parts = cleaned.split(":", 1)
                aspect = parts[0].strip()
                instruction = parts[1].strip()
            memory_hub.add_style(aspect, instruction, scope=scope)
            msg = f"🎨 נשמר סגנון: {aspect}"

        # 4. Instruction
        elif any(k in raw.lower() for k in ["הוראה:", "הנחיה:"]):
            cleaned = re.sub(r'^(הוראה:|הנחיה:)\s*', '', raw, flags=re.IGNORECASE).strip()
            memory_hub.add_instruction(cleaned, "בכל שיחה ומענה", scope=scope)
            msg = "🛡️ נשמרה הוראה פרטית"

        # 5. Fact / Information (Default)
        else:
            name = "מידע כללי"
            val = raw
            if ":" in raw:
                parts = raw.split(":", 1)
                name = parts[0].strip()
                val = parts[1].strip()
            elif " זה " in raw:
                parts = raw.split(" זה ", 1)
                name = parts[0].strip()
                val = parts[1].strip()
            elif " הוא " in raw:
                parts = raw.split(" הוא ", 1)
                name = parts[0].strip()
                val = parts[1].strip()
            memory_hub.add_info(name, val, scope=scope)
            msg = f"📌 נשמר מידע: {name}"

        return msg


def show_spotlight(master=None, on_saved_callback=None):
    overlay = SpotlightOverlay(master=master, on_saved_callback=on_saved_callback)
    return overlay


if __name__ == "__main__":
    app = ctk.CTk()
    app.withdraw()
    show_spotlight()
    app.mainloop()
