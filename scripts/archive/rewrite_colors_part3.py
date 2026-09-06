import re
with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any bright fg_color="#something" with ACCENT_COLOR if it's a primary button.
# Let's just fix the sidebar sync button and add button
content = re.sub(r'fg_color="\#2563eb"', 'fg_color=ACCENT_COLOR', content)
content = re.sub(r'hover_color="\#1d4ed8"', 'hover_color=ACCENT_HOVER', content)
content = re.sub(r'border_color="\#3b82f6"', 'border_color=ACCENT_COLOR', content)

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Part 3 complete.")
