import re
with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('v6.6 Modern Light', 'v6.6 Enterprise')
content = content.replace('v6.6 Enterprise Light', 'v6.6 Enterprise')

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Title update complete.")
