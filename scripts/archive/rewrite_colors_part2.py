import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Strip any remaining emojis
emoji_list = ['⚙️', '⛔', '🛡️', '☁️', '🤖', '📂', '📝']
for e in emoji_list:
    content = content.replace(e, '')

# General replacement for text_color in labels
content = re.sub(r'text_color="#[a-fA-F0-9]{6}"', 'text_color=TEXT_PRIMARY', content)

# A few specific fixes
content = content.replace('text_color=("#c7d2fe", "#c7d2fe")', 'text_color=TEXT_PRIMARY')
content = content.replace('text_color=("#0284c7", "#38bdf8")', 'text_color=TEXT_SECONDARY')
content = content.replace('text_color=("#d97706", "#fbbf24")', 'text_color=TEXT_SECONDARY')
content = content.replace('text_color=("#e11d48", "#f87171")', 'text_color=TEXT_SECONDARY')
content = content.replace('text_color=("#059669", "#34d399")', 'text_color=TEXT_SECONDARY')
content = content.replace('text_color=("#ffffff", "#c084fc")', 'text_color=TEXT_PRIMARY')
content = content.replace('text_color=("#ffffff", "#38bdf8")', 'text_color=TEXT_PRIMARY')
content = content.replace('text_color=("#334155", "#c084fc")', 'text_color=TEXT_PRIMARY')
content = content.replace('text_color=("#334155", "#38bdf8")', 'text_color=TEXT_PRIMARY')
content = content.replace('text_color=("#15803d", "#34d399")', 'text_color=TEXT_PRIMARY')

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Part 2 color and emoji update complete.")
