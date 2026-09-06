import re

with open('gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the inner loop of refresh_page_*
def replace_loop(category, title_field, subtitle_field):
    pattern = r'(for item in items:\n\s+c = self\.create_glass_card\(self\.scroll_' + category + r'.*?)(?=def |$)'
    
    val_render = f'''val = item.get("{subtitle_field}", "")
            if val:
                ctk.CTkLabel(content_f, text=val, font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_SECONDARY, wraplength=700, justify="right").pack(anchor="e", pady=(4, 0))'''
    
    if category == 'commands':
        val_render = f'''val = item.get("details", "")
            if val:
                ctk.CTkLabel(content_f, text="פעולה: " + val, font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_SECONDARY, wraplength=700, justify="right").pack(anchor="e", pady=(4, 0))'''
    elif category == 'instructions':
        val_render = f'''val = item.get("instruction", "")
            when = item.get("condition", "")
            if val:
                ctk.CTkLabel(content_f, text=val, font=ctk.CTkFont(family="Segoe UI", size=12), text_color=TEXT_PRIMARY, wraplength=700, justify="right").pack(anchor="e", pady=(4, 0))
            if when:
                ctk.CTkLabel(content_f, text="מתי: " + when, font=ctk.CTkFont(family="Segoe UI", size=11), text_color=TEXT_SECONDARY, wraplength=700, justify="right").pack(anchor="e", pady=(2, 0))'''

    new_loop = f'''for item in items:
            c = self.create_glass_card(self.scroll_{category}, corner_radius=8)
            c.pack(fill="x", pady=4, padx=4)
            
            # Action frame (Left)
            actions = ctk.CTkFrame(c, fg_color="transparent")
            actions.pack(side="left", padx=12, pady=8)
            
            btn_up = self.create_card_action_button(actions, "מעלה", lambda i_id=item["id"]: self.on_reorder_item("{category}", i_id, "up"), "default", 40, 26)
            btn_up.pack(side="left", padx=2)
            
            btn_down = self.create_card_action_button(actions, "מטה", lambda i_id=item["id"]: self.on_reorder_item("{category}", i_id, "down"), "default", 40, 26)
            btn_down.pack(side="left", padx=2)
            
            btn_edit = self.create_card_action_button(actions, "ערוך", lambda it=item: self.open_edit_dialog("{category}", it), "edit", 45, 26)
            btn_edit.pack(side="left", padx=2)
            
            btn_del = self.create_card_action_button(actions, "מחק", lambda i_id=item["id"], n=item["{title_field}"]: self.on_del_item("{category}", i_id, n), "del", 45, 26)
            btn_del.pack(side="left", padx=2)
            
            sw_var = ctk.BooleanVar(value=item.get("active", True))
            sw = ctk.CTkSwitch(actions, text="", variable=sw_var, width=30, command=lambda i_id=item["id"], v=sw_var: self.on_sw_item("{category}", i_id, v))
            sw.pack(side="left", padx=(10, 0))

            # Content frame (Right)
            content_f = ctk.CTkFrame(c, fg_color="transparent")
            content_f.pack(side="right", fill="both", expand=True, padx=12, pady=8)
            
            header_f = ctk.CTkFrame(content_f, fg_color="transparent")
            header_f.pack(anchor="e", fill="x")
            
            # Title
            ctk.CTkLabel(header_f, text=item.get("{title_field}", ""), font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color=TEXT_PRIMARY).pack(side="right")
            
            # Badges
            scope_str = item.get("scope", "global")
            badge_text = "כללי (גלובלי)" if scope_str == "global" else f"{{scope_str}}"
            self.create_glass_badge(header_f, badge_text).pack(side="right", padx=10)
            
            ai_badge_text = self.format_ai_target_badge(item)
            self.create_glass_badge(header_f, ai_badge_text).pack(side="right", padx=2)
            
            {val_render}
\n    '''
    
    global content
    content = re.sub(pattern, new_loop, content, flags=re.DOTALL)

replace_loop('facts', 'name', 'value')
replace_loop('commands', 'command', 'details')
replace_loop('constraints', 'constraint', 'constraint')
replace_loop('styles', 'style', 'style')
replace_loop('instructions', 'name', 'instruction')

with open('gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("List rewrite complete.")
