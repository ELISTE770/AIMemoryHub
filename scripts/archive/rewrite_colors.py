import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('text_color=("#0284c7", "#38bdf8")', 'text_color=TEXT_SECONDARY'),
    ('text_color=("#d97706", "#fbbf24")', 'text_color=TEXT_SECONDARY'),
    ('text_color=("#e11d48", "#f87171")', 'text_color=TEXT_SECONDARY'),
    ('text_color=("#059669", "#34d399")', 'text_color=TEXT_SECONDARY'),
    ('text_color=("#ffffff", "#c084fc")', 'text_color=TEXT_PRIMARY'),
    ('text_color=("#ffffff", "#38bdf8")', 'text_color=TEXT_PRIMARY'),
    ('text_color=("#1d4ed8", "#38bdf8")', 'text_color=ACCENT_COLOR'),
    ('text_color=("#334155", "#c084fc")', 'text_color=TEXT_PRIMARY'),
    ('text_color=("#334155", "#38bdf8")', 'text_color=TEXT_PRIMARY'),
    ('text_color=("#15803d", "#34d399")', 'text_color=TEXT_PRIMARY'),
    # Also strip the ⛔ emoji from constraints
    ('f"⛔ {item.get(\'constraint\', \'\')}"', 'item.get(\'constraint\', \'\')')
]

for old, new in replacements:
    content = content.replace(old, new)

# Also fix the button hover colors that are hardcoded like fg_color=("#2563eb", "#09182d")
content = re.sub(r'fg_color=\("\#[a-fA-F0-9]+", "\#[a-fA-F0-9]+"\)', 'fg_color=ACCENT_COLOR', content)
content = re.sub(r'hover_color=\("\#[a-fA-F0-9]+", "\#[a-fA-F0-9]+"\)', 'hover_color=ACCENT_HOVER', content)

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Color update complete.")
