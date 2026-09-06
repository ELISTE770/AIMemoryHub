import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all occurrences of n=item["xxx"] with n=item.get("xxx", "Unknown") inside lambdas for deletion
content = re.sub(r'n=item\["(.*?)"\]', r'n=item.get("\1", "Unknown")', content)

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Safe get fixed.")
