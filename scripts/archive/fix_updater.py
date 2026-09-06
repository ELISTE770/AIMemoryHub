import re

with open('updater.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import ssl
if 'import ssl' not in content:
    content = content.replace('import subprocess', 'import subprocess\nimport ssl')

# Fix check_for_updates
old_check = '''    try:
        with urllib.request.urlopen(req, timeout=10) as response:'''
new_check = '''    try:
        # Create unverified context to bypass strict ISP/Proxy MITM handshake issues (e.g. NetFree)
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:'''
content = content.replace(old_check, new_check)

# Fix download_update
old_download = '''        with urllib.request.urlopen(req, timeout=60) as response:'''
new_download = '''        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=120, context=ctx) as response:'''
content = content.replace(old_download, new_download)

with open('updater.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("updater.py patched successfully.")
