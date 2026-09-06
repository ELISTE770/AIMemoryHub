import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix 'commands' (used 'command' instead of 'name')
# In refresh_page_commands, it has:
# n=item["command"]: self.on_del_item("commands", i_id, n)
# ctk.CTkLabel(header_f, text=item.get("command", "")
content = re.sub(r'n=item\["command"\]:\s*self.on_del_item\("commands"', r'n=item["name"]: self.on_del_item("commands"', content)
content = re.sub(r'text=item.get\("command",\s*""\)', r'text=item.get("name", "")', content)

# 2. Fix 'styles' (used 'style' instead of 'aspect', and 'style' instead of 'instruction' for value)
# In refresh_page_styles:
# n=item["style"]: self.on_del_item("styles", i_id, n)
# text=item.get("style", "")
content = re.sub(r'n=item\["style"\]:\s*self.on_del_item\("styles"', r'n=item["aspect"]: self.on_del_item("styles"', content)

# Let's just fix the block inside refresh_page_styles
def fix_styles_block(m):
    block = m.group(0)
    block = block.replace('n=item["style"]', 'n=item["aspect"]')
    block = block.replace('text=item.get("style", "")', 'text=item.get("aspect", "")')
    block = block.replace('val = item.get("style", "")', 'val = item.get("instruction", "")')
    return block

content = re.sub(r'(def refresh_page_styles.*?)(?=def refresh_page_instructions)', fix_styles_block, content, flags=re.DOTALL)

# 3. Fix 'instructions' (used 'name' instead of 'instruction' for title, and 'instruction' instead of 'when_to_apply' for value)
def fix_instructions_block(m):
    block = m.group(0)
    block = block.replace('n=item["name"]', 'n=item["instruction"]')
    block = block.replace('text=item.get("name", "")', 'text=item.get("instruction", "")')
    block = block.replace('val = item.get("instruction", "")', 'val = item.get("when_to_apply", "")')
    block = block.replace('when = item.get("condition", "")', 'when = item.get("when_to_apply", "")')
    return block

content = re.sub(r'(def refresh_page_instructions.*?)(?=def refresh_page_context_files)', fix_instructions_block, content, flags=re.DOTALL)

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Keys fixed.")
