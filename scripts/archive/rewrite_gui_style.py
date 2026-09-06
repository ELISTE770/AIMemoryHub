import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace the color palette with a professional one
old_palette = '''# =============================================================================
# MODERN LIGHT & DYNAMIC GLASSMORPHISM DESIGN SYSTEM (עיצוב מודרני בהיר ויוקרתי)
# =============================================================================
GLASS_BG_MAIN = ("#f1f5f9", "#060913")       # Modern Clean Slate Canvas
GLASS_BG_SIDEBAR = ("#ffffff", "#080d1a")    # Pure White Floating Sidebar
GLASS_CARD = ("#ffffff", "#0c1324")          # Crisp White Glass Card
GLASS_CARD_BORDER = ("#e2e8f0", "#1c2b45")   # Subtle 1px Border
GLASS_CARD_HOVER = ("#f1f5f9", "#131e36")    # Soft Hover Sheen
GLASS_INPUT = ("#ffffff", "#050812")         # Clean White Inset Input
GLASS_INPUT_BORDER = ("#cbd5e1", "#19263e")  # Input Border
GLASS_HEADER_BG = ("#ffffff", "#0b1426")     # Header Background
GLASS_HEADER_BORDER = ("#e2e8f0", "#1e3052") # Header Border
GLASS_DIVIDER = ("#e2e8f0", "#162035")       # Delicate Line

# Text Colors for perfect contrast
TEXT_PRIMARY = ("#0f172a", "#f8fafc")        # Deep Crisp Slate / White
TEXT_SECONDARY = ("#334155", "#cbd5e1")      # Slate-700 / Soft Slate
TEXT_MUTED = ("#64748b", "#94a3b8")          # Slate-500 / Muted Slate

# Accents
GLASS_ACCENT_CYAN = ("#0284c7", "#38bdf8")
GLASS_BORDER_CYAN = ("#7dd3fc", "#0284c7")
GLASS_ACCENT_PURPLE = ("#7c3aed", "#c084fc")
GLASS_BORDER_PURPLE = ("#c4b5fd", "#7c3aed")
GLASS_ACCENT_EMERALD = ("#059669", "#34d399")
GLASS_BORDER_EMERALD = ("#6ee7b7", "#059669")
GLASS_ACCENT_AMBER = ("#d97706", "#fbbf24")
GLASS_BORDER_AMBER = ("#fcd34d", "#d97706")
GLASS_ACCENT_ROSE = ("#e11d48", "#fb7185")
GLASS_BORDER_ROSE = ("#fda4af", "#e11d48")'''

new_palette = '''# =============================================================================
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
ACCENT_HOVER = ("#005999", "#005999")'''

content = content.replace(old_palette, new_palette)

# 2. Fix the Card Action Buttons to use unified colors
old_button_logic = '''        is_light = ctk.get_appearance_mode().lower() == "light"
        if is_light:
            if btn_type == "del":
                fg, border, hover, tc = "#fee2e2", "#fca5a5", "#fecaca", "#b91c1c"
            elif btn_type == "edit":
                fg, border, hover, tc = "#e0f2fe", "#7dd3fc", "#bae6fd", "#0284c7"
            elif btn_type == "gemini":
                fg, border, hover, tc = "#ede9fe", "#c4b5fd", "#ddd6fe", "#6d28d9"
            else:
                fg, border, hover, tc = "#f8fafc", "#cbd5e1", "#f1f5f9", "#334155"
        else:
            if btn_type == "del":
                fg, border, hover, tc = "#22080d", "#7f1d1d", "#991b1b", "#fca5a5"
            elif btn_type == "edit":
                fg, border, hover, tc = "#0b1526", "#1d4ed8", "#1e40af", "#93c5fd"
            elif btn_type == "gemini":
                fg, border, hover, tc = "#1e1035", "#7c3aed", "#6d28d9", "#d8b4fe"
            else:
                fg, border, hover, tc = "#0b1222", "#1c2b45", "#1e293b", "#cbd5e1"

        lbl_text = text
        btn_w = width
        if text == "✏️":
            lbl_text = "ערוך"
            btn_w = 42
        elif text == "🗑️":
            lbl_text = "מחק"
            btn_w = 42
        elif text == "▲":
            lbl_text = "↑"
        elif text == "▼":
            lbl_text = "↓"'''

new_button_logic = '''        is_light = ctk.get_appearance_mode().lower() == "light"
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
        if text in ["✏️", "ערוך"]:
            lbl_text = "ערוך"
            btn_w = 45
        elif text in ["🗑️", "מחק", "🗑"]:
            lbl_text = "מחק"
            btn_w = 45
        elif text in ["▲", "מעלה"]:
            lbl_text = "מעלה"
            btn_w = 40
        elif text in ["▼", "מטה"]:
            lbl_text = "מטה"
            btn_w = 40'''

content = content.replace(old_button_logic, new_button_logic)

# 3. Fix the badge creation
old_badge = '''    def create_glass_badge(self, parent, text, color_type="cyan"):
        is_light = ctk.get_appearance_mode().lower() == "light"
        if is_light:
            if color_type == "cyan":
                fg, border, tc = "#e0f2fe", "#7dd3fc", "#0369a1"
            elif color_type == "purple":
                fg, border, tc = "#ede9fe", "#c4b5fd", "#6d28d9"
            elif color_type == "emerald":
                fg, border, tc = "#d1fae5", "#6ee7b7", "#047857"
            elif color_type == "amber":
                fg, border, tc = "#fef3c7", "#fcd34d", "#b45309"
            elif color_type == "rose":
                fg, border, tc = "#ffe4e6", "#fda4af", "#be123c"
            else:
                fg, border, tc = "#f1f5f9", "#cbd5e1", "#334155"
        else:
            if color_type == "cyan":
                fg, border, tc = "#051329", "#0284c7", "#38bdf8"
            elif color_type == "purple":
                fg, border, tc = "#140c26", "#7c3aed", "#c084fc"
            elif color_type == "emerald":
                fg, border, tc = "#061a14", "#059669", "#34d399"
            elif color_type == "amber":
                fg, border, tc = "#1f1305", "#d97706", "#fbbf24"
            elif color_type == "rose":
                fg, border, tc = "#22080d", "#dc2626", "#f87171"
            else:
                fg, border, tc = "#070c18", "#1e293b", "#94a3b8"

        b_frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=fg, border_width=1, border_color=border)
        lbl = ctk.CTkLabel(b_frame, text=text, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=tc)
        lbl.pack(padx=8, pady=2)
        return b_frame'''

new_badge = '''    def create_glass_badge(self, parent, text, color_type="cyan"):
        is_light = ctk.get_appearance_mode().lower() == "light"
        
        # Unified clean badge look without pastel colors
        fg = "#F3F3F3" if is_light else "#333333"
        border = "#E5E5E5" if is_light else "#444444"
        tc = "#333333" if is_light else "#CCCCCC"

        b_frame = ctk.CTkFrame(parent, corner_radius=6, fg_color=fg, border_width=1, border_color=border)
        lbl = ctk.CTkLabel(b_frame, text=text, font=ctk.CTkFont(family="Segoe UI", size=11, weight="normal"), text_color=tc)
        lbl.pack(padx=8, pady=2)
        return b_frame'''

content = content.replace(old_badge, new_badge)

# 4. Global emoji stripping for known strings
replacements = {
    "👤 סביבת עבודה:": "סביבת עבודה:",
    "🔄 עדכון אוטומטי מ-GitHub": "עדכון אוטומטי מ-GitHub",
    "🤖 לכל ה-AI": "לכל המודלים",
    "🤖 מותאם:": "מותאם:",
    "🤖 מותאם": "מותאם",
    "🌐 גלובלי": "כללי (גלובלי)",
    "📁 ": "",
    "✏️": "ערוך",
    "🗑️": "מחק",
    "🗑": "מחק",
    "🤖 ": "",
    "✨ מעבד...": "מעבד...",
    "🔍 ": "",
    "🎨 ": "",
    "🛡 ": "",
    "💾 ": "",
    "📚 ": "",
    "📂 ": "",
    "📄 ": "",
    "💡 ": "",
    "💬 ": "",
    "📝 ": "",
    "🚀 ": "",
    "📌 ": "",
    "🟢 ": "",
    "👁 ": "",
    "📋 ": "",
    "🟣 ": "",
    "🌊 ": "",
    "🐙 ": "",
    "🎯 ": "",
    "🔑 ": "",
    "🔌 ": "",
    "📤 ": "",
    "📥 ": "",
}

for old, new in replacements.items():
    content = content.replace(old, new)
    
# Remove cyan pip glowing logic
content = content.replace('self.create_glass_badge(c, "עובדה קבועה", "cyan").pack(side="right", padx=(0, 10), pady=6)', '')
content = content.replace('self.create_glass_badge(c, "פקודה", "emerald").pack(side="right", padx=(0, 10), pady=6)', '')
content = content.replace('self.create_glass_badge(c, "איסור / חוק", "rose").pack(side="right", padx=(0, 10), pady=6)', '')
content = content.replace('self.create_glass_badge(c, "סגנון", "amber").pack(side="right", padx=(0, 10), pady=6)', '')
content = content.replace('self.create_glass_badge(c, "הוראה מותנית", "purple").pack(side="right", padx=(0, 10), pady=6)', '')

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Redesign complete.")
