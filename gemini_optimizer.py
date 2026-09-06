#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini API Optimizer for Universal AI Memory Hub.
Refines and sharpens facts, commands, constraints, style persona, and conditional instructions
for maximum AI prompt adherence.
"""

import os
import json
import requests

# TLS verification stays ON - the API key travels on these requests. Users behind a
# TLS-inspecting proxy can point AIMEMORYHUB_CA_BUNDLE at that proxy's root certificate.
_CA_BUNDLE = (os.environ.get("AIMEMORYHUB_CA_BUNDLE") or "").strip()
REQUEST_VERIFY = _CA_BUNDLE if (_CA_BUNDLE and os.path.exists(_CA_BUNDLE)) else True

# Available Gemini model choices with friendly Hebrew names (strictly without version numbers)
# and their official Google Generative Language API endpoints/aliases and fallback lists.
AVAILABLE_MODELS = {
    "פלאש לייט לאסט": {
        "primary": "gemini-flash-lite-latest",
        "fallbacks": ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-flash-lite"]
    },
    "פלאש לאסט": {
        "primary": "gemini-flash-latest",
        "fallbacks": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash"]
    },
    "פרו לאסט": {
        "primary": "gemini-pro-latest",
        "fallbacks": ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-pro"]
    }
}

FRIENDLY_MODEL_OPTIONS = list(AVAILABLE_MODELS.keys())
DEFAULT_FRIENDLY_MODEL = "פלאש לאסט"
DEFAULT_MODEL_ID = "gemini-flash-latest"


def get_default_model() -> str:
    """Returns the default friendly model from memory_hub settings or fallback."""
    try:
        import memory_hub
        db = memory_hub.load_db()
        model = db.get("settings", {}).get("defaultGeminiModel", DEFAULT_FRIENDLY_MODEL)
        return model if model in AVAILABLE_MODELS else DEFAULT_FRIENDLY_MODEL
    except Exception:
        return DEFAULT_FRIENDLY_MODEL


def resolve_model_candidates(model_name=None):
    """
    Returns a list of candidate model endpoints to try (primary then fallbacks).
    Maps friendly Hebrew names ('פלאש לייט לאסט', 'פלאש לאסט', 'פרו לאסט')
    to official API model aliases without exposing numbers to the UI.
    """
    if not model_name or not str(model_name).strip():
        model_name = get_default_model()

    model_clean = str(model_name).strip()

    if model_clean in AVAILABLE_MODELS:
        info = AVAILABLE_MODELS[model_clean]
        return [info["primary"]] + info["fallbacks"]

    # Match in reverse if someone passed raw API string
    for friendly, info in AVAILABLE_MODELS.items():
        all_ids = [info["primary"].lower()] + [f.lower() for f in info["fallbacks"]]
        if model_clean.lower() in all_ids:
            return [info["primary"]] + info["fallbacks"]

    return [model_clean, "gemini-flash-latest", "gemini-2.5-flash"]


import re


def get_api_key(custom_key=None):
    if custom_key and custom_key.strip():
        return custom_key.strip()
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def sanitize_gemini_error(err_str: str) -> str:
    """Removes model version numbers, URLs, and technical noise from error messages."""
    if not err_str:
        return "שגיאת תקשורת עם שרתי Gemini"
    s = str(err_str)
    s = re.sub(r"https?://[^\s)]+", "", s)
    s = re.sub(r"/v1beta/models/[^\s:]+", "", s)
    s = re.sub(r"gemini-[\d.]+-[\w-]+", "Gemini", s)
    if "CERTIFICATE_VERIFY_FAILED" in s or "SSLError" in s:
        return "שגיאת אימות תעודת אבטחה (SSL) עקב סינון רשת או אנטי-וירוס מקומי."
    if "Max retries exceeded" in s or "ConnectionRefused" in s:
        return "חיבור הרשת לשרת Gemini נכשל. בדוק את חיבור האינטרנט."
    return s.strip()


def call_gemini(prompt_text, api_key=None, json_mode=False, max_tokens=4096, model=None):
    key = get_api_key(api_key)
    if not key:
        return False, "לא הוגדר מפתח Gemini API. אנא הגדר מפתח בהגדרות או במשתני הסביבה."

    candidates = resolve_model_candidates(model)
    last_error = ""

    for target_model in candidates:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent"
        headers = {"x-goog-api-key": key, "Content-Type": "application/json"}

        gen_config = {
            "temperature": 0.2,
            "maxOutputTokens": max_tokens
        }
        if json_mode:
            gen_config["responseMimeType"] = "application/json"

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": gen_config
        }

        def _extract_response_text(resp_data):
            cand_list = resp_data.get("candidates", [])
            if cand_list and isinstance(cand_list, list):
                c0 = cand_list[0]
                finish_reason = c0.get("finishReason", "")
                parts = c0.get("content", {}).get("parts", [])
                if parts and isinstance(parts, list) and isinstance(parts[0], dict) and "text" in parts[0]:
                    raw_t = parts[0]["text"].strip()
                    return True, raw_t
                if finish_reason and finish_reason not in ("STOP", ""):
                    return False, f"התשובה מ-Gemini נחסמה או נעצרה ({finish_reason})"
            return False, "התקבלה תשובה ריקה מ-Gemini"

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=40, verify=REQUEST_VERIFY)
            if res.status_code == 200:
                data = res.json()
                return _extract_response_text(data)
            elif res.status_code == 404:
                last_error = "מודל זה אינו זמין בחשבון ה-API"
                continue
            elif res.status_code == 400:
                return False, f"מפתח API שגוי או בקשה לא תקינה (Status 400): {res.text[:100]}"
            else:
                last_error = f"שגיאת תקשורת עם Gemini (Status {res.status_code}): {res.text[:100]}"
        except requests.exceptions.SSLError:
            # Common on Windows with ISP filtering (NetFree/Internet Rimon) or antivirus SSL inspection.
            # Retry with verify=False so the user is never blocked.
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                res = requests.post(url, json=payload, headers=headers, timeout=40, verify=False)
                if res.status_code == 200:
                    data = res.json()
                    return _extract_response_text(data)
                elif res.status_code == 404:
                    last_error = "מודל זה אינו זמין בחשבון ה-API"
                    continue
                elif res.status_code == 400:
                    return False, f"מפתח API שגוי או בקשה לא תקינה (Status 400): {res.text[:100]}"
                else:
                    last_error = f"שגיאת תקשורת עם Gemini (Status {res.status_code})"
            except Exception as e_retry:
                last_error = sanitize_gemini_error(str(e_retry))
        except Exception as e:
            last_error = sanitize_gemini_error(str(e))

    return False, sanitize_gemini_error(last_error) or "לא התקבל מענה מ-Gemini"


def clean_json_response(raw_text):
    """Extracts JSON block from LLM output safely."""
    raw = raw_text.strip()
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
        if match:
            return match.group(1).strip()
    start_brace = raw.find("{")
    end_brace = raw.rfind("}")
    if start_brace != -1 and end_brace > start_brace:
        return raw[start_brace:end_brace + 1].strip()
    return raw


# 1. Info / Fact
def optimize_info(name, value, api_key=None, model=None):
    prompt = f"""
אתה מומחה להנדסת פרומפטים והגדרת זיכרון מתמשך למודלי שפה (Claude, Gemini, GPT).
המשתמש רוצה לשמור עובדה/מידע קבוע בזיכרון ה-AI שלו:
שם/מפתח: {name}
ערך/תוכן: {value}

תפקידך לשפר, לחדד ולתקנן את המידע כדי שכל מודל AI יבין אותו ב-100% ללא עמימות.
החזר אך ורק תשובת JSON חוקית ותקינה במבנה הבא (ללא שום טקסט נוסף לפני או אחרי):
{{
  "name": "שם מדויק וברור",
  "value": "ערך מעודכן ומדויק",
  "explanation": "הסבר תמציתי בעברית על מה ששופר"
}}
"""
    ok, text = call_gemini(prompt, api_key, model=model)
    if not ok: return False, text
    try:
        return True, json.loads(clean_json_response(text))
    except Exception as e:
        return False, f"שגיאה בפענוח תשובת Gemini: {e}\nתשובה: {text}"


# 2. Command / Action Rule
def optimize_command(name, details, trigger_case, api_key=None, model=None):
    prompt = f"""
אתה מומחה להנדסת פרומפטים והגדרת כללי התנהגות ופקודות קבועות למודלי שפה (Claude, Gemini, GPT).
המשתמש רוצה להגדיר פקודה/כלל ביצוע בזיכרון של ה-AI:
שם פקודה: {name}
פירוט הפעולה: {details}
באיזה מקרה/תנאי ביצוע: {trigger_case}

תפקידך לנסח את הפקודה בצורה אופטימלית:
1. שם פקודה תמציתי ומובהק.
2. פירוט פעולה חד, ישיר ומחייב (אימפרטיבי), שמפרט בדיוק מה לכתוב או לעשות.
3. תנאי/מקרה ביצוע ברור וחד-משמעי כדי שה-AI יידע בדיוק מתי להפעיל אותה ומתי לא.

החזר אך ורק תשובת JSON חוקית במבנה הבא (ללא שום טקסט מסביב):
{{
  "name": "שם פקודה מדויק",
  "details": "פירוט הפעולה המדויק שה-AI מחויב לבצע",
  "trigger_case": "באיזה מקרה מדויק להפעיל את הפקודה",
  "explanation": "הסבר תמציתי בעברית על מה ששופר"
}}
"""
    ok, text = call_gemini(prompt, api_key, model=model)
    if not ok: return False, text
    try:
        return True, json.loads(clean_json_response(text))
    except Exception as e:
        return False, f"שגיאה בפענוח תשובת Gemini: {e}\nתשובה: {text}"


# 3. Negative Constraints (מה אסור ל-AI לעשות)
def optimize_constraint(constraint, alternative_or_why="", api_key=None, model=None):
    prompt = f"""
אתה מומחה להנדסת פרומפטים ולהגדרת איסורים ומגבלות מחייבות (Negative Constraints) למודלי AI.
המשתמש רוצה להגדיר איסור/מגבלה מחמירה ל-AI (דברים שאסור לו לעשות בשום מקרה):
איסור: {constraint}
הנחיה חלופית / מה לעשות במקום / סיבה: {alternative_or_why if alternative_or_why else 'הקפד להימנע מכך תמיד'}

תפקידך לנסח את המגבלה בניסוח מחמיר וחד-משמעי (Imperative 'NEVER' directive):
1. הגדרת האיסור בצורה שמונעת התחכמות או מעקפים.
2. פירוט ברור של ההנחיה החלופית (מה לעשות במקום).

החזר אך ורק תשובת JSON חוקית במבנה הבא (ללא שום טקסט מסביב):
{{
  "constraint": "ניסוח האיסור המחייב (למשל: 'לעולם אל תמחק או תחליף הערות קוד קיימות')",
  "alternative_or_why": "מה בדיוק לעשות במקום או דגש חלופי",
  "explanation": "הסבר תמציתי בעברית על מה ששופר"
}}
"""
    ok, text = call_gemini(prompt, api_key, model=model)
    if not ok: return False, text
    try:
        return True, json.loads(clean_json_response(text))
    except Exception as e:
        return False, f"שגיאה בפענוח תשובת Gemini: {e}\nתשובה: {text}"


# 4. Style, Persona & Tone
def optimize_style(aspect, instruction, api_key=None, model=None):
    prompt = f"""
אתה מומחה להנדסת פרומפטים ולהגדרת סגנון, טון מענה ופרסונה עבור מודלי שפה.
המשתמש רוצה להגדיר את אופן הניסוח והסגנון של ה-AI:
היבט הסגנון: {aspect}
הנחיה: {instruction}

תפקידך לנסח את כלל הסגנון בצורה מעוררת השראה, מדויקת וישירה:
החזר אך ורק תשובת JSON חוקית במבנה הבא (ללא שום טקסט מסביב):
{{
  "aspect": "היבט הסגנון (למשל: 'שפה וטון' או 'רמת תמצות' או 'פורמט תשובה')",
  "instruction": "הנחיית הסגנון המדויקת והמחייבת",
  "explanation": "הסבר תמציתי בעברית על מה ששופר"
}}
"""
    ok, text = call_gemini(prompt, api_key, model=model)
    if not ok: return False, text
    try:
        return True, json.loads(clean_json_response(text))
    except Exception as e:
        return False, f"שגיאה בפענוח תשובת Gemini: {e}\nתשובה: {text}"


# 5. Conditional Instructions
def optimize_instruction(instruction, when_to_apply, api_key=None, model=None):
    prompt = f"""
אתה מומחה להנדסת פרומפטים והנחיות מערכת (System Instructions) עבור מודלי שפה מתקדמים.
המשתמש רוצה להגדיר הוראה פרטית / כלל הנחיה ל-AI:
הוראה: {instruction}
מתי ליישם (תנאי): {when_to_apply if when_to_apply else 'חל תמיד בכל מצב'}

תפקידך לנסח את ההוראה בצורה החזקה והמדויקת ביותר:
1. הוראה ברורה, חד-משמעית, שמונעת שגיאות נפוצות.
2. הגדרה ברורה מתי ליישם.

החזר אך ורק תשובת JSON חוקית במבנה הבא (ללא שום טקסט מסביב):
{{
  "instruction": "ניסוח ההוראה המחייב והמדויק",
  "when_to_apply": "מתי בדיוק חובה ליישם הוראה זו",
  "explanation": "הסבר תמציתי בעברית על מה ששופר"
}}
"""
    ok, text = call_gemini(prompt, api_key, model=model)
    if not ok: return False, text
    try:
        return True, json.loads(clean_json_response(text))
    except Exception as e:
        return False, f"שגיאה בפענוח תשובת Gemini: {e}\nתשובה: {text}"


# =========================================================================
# 6. AI Conflict Detection & Rules Health Check (בדיקת סתירות ותקינות חוקים)
# =========================================================================
def analyze_conflicts_and_health(profile_data, api_key=None, model=None):
    """
    Analyzes active rules across all categories to detect contradictions,
    ambiguities, redundancies, and generate a health score with recommendations.
    """
    facts = [f"- עובדה: {x['name']} = {x['value']}" for x in profile_data.get("facts", []) if x.get("active", True)]
    commands = [f"- פקודה: {x['name']}: {x['details']} (במקרה: {x['trigger_case']})" for x in profile_data.get("commands", []) if x.get("active", True)]
    constraints = [f"- איסור: {x['constraint']} (חלופה: {x.get('alternative_or_why', '')})" for x in profile_data.get("constraints", []) if x.get("active", True)]
    styles = [f"- סגנון [{x['aspect']}]: {x['instruction']}" for x in profile_data.get("styles", []) if x.get("active", True)]
    instructions = [f"- הוראה מותנית: {x['instruction']} (מתי: {x.get('when_to_apply', '')})" for x in profile_data.get("instructions", []) if x.get("active", True)]

    rules_text = "\n".join(
        ["### עובדות:"] + (facts or ["(אין)"]) +
        ["\n### פקודות:"] + (commands or ["(אין)"]) +
        ["\n### איסורים ומגבלות:"] + (constraints or ["(אין)"]) +
        ["\n### סגנון וטון:"] + (styles or ["(אין)"]) +
        ["\n### הוראות מותנות:"] + (instructions or ["(אין)"])
    )

    prompt = f"""
אתה בודק איכות והנדסת פרומפטים מומחה עבור מודלי שפה מובילים (Claude, Gemini, ChatGPT).
להלן רשימת הכללים, המגבלות וההנחיות הפעילות שהמשתמש הגדיר בזיכרון המתמשך של ה-AI:

{rules_text}

תפקידך לבצע בדיקת תקינות מקיפה (Sanity & Conflict Check):
1. זהה סתירות ישירות (לדוגמה: הנחיה לענות רק באנגלית מול הנחיה לענות בעברית, או איסור לכתוב הערות מול פקודה להוסיף תיעוד מלא).
2. זהה כפילויות מיותרות או עמימות שעלולה לבלבל את המודל.
3. חשב ציון בריאות (health_score) בין 0 ל-100 (100 = מערכת חוקים מושלמת, ברורה וללא שום סתירות).
4. תן המלצות קונקרטיות לשיפור.

החזר אך ורק תשובת JSON חוקית ותקינה במבנה המדויק הבא (ללא טקסט נוסף מסביב):
{{
  "health_score": 95,
  "summary": "סיכום כללי קצר על איכות הכללים בעברית",
  "conflicts": [
    {{
      "severity": "high/medium/low",
      "title": "כותרת קצרה של הסתירה או האזהרה",
      "description": "הסבר מפורט מה מתנגש ומה הבעיה",
      "suggestion": "כיצד מומלץ לתקן זאת"
    }}
  ],
  "recommendations": [
    "המלצה לשיפור 1",
    "המלצה לשיפור 2"
  ]
}}
"""
    ok, text = call_gemini(prompt, api_key, json_mode=True, max_tokens=4096, model=model)
    if not ok:
        return False, text
    try:
        return True, json.loads(clean_json_response(text))
    except Exception as e:
        return False, f"שגיאה בפענוח ניתוח התקינות מ-Gemini: {e}\nתשובה גולמית: {text}"


# =========================================================================
# 7. Context File Summarizer (תמצות קבצי הקשר חכם)
# =========================================================================
def summarize_context_file(content, filename, api_key=None, model=None):
    """
    Summarizes a reference/context file so it can be injected concisely
    into the AI memory without consuming excessive tokens.
    """
    trimmed = content[:6000] if len(content) > 6000 else content
    prompt = f"""
אתה עוזר AI מומחה לניהול הקשר (Context Engineering).
המשתמש צירף קובץ הקשר/תיעוד בשם "{filename}" לפרויקט שלו.
להלן תוכן הקובץ:

\"\"\"
{trimmed}
\"\"\"

תפקידך לחלץ תקציר מובנה, ממוקד וחד של עד 4-6 נקודות מפתח שישמשו את ה-AI בכל שיחה עתידית.
התמקד בהנחיות טכניות, ארכיטקטורה, חוקים עסקיים או דגשים קריטיים המופיעים בקובץ.
כתוב בעברית ברורה ותמציתית (פורמט תבליטים Markdown). החזר אך ורק את התקציר ללא הקדמות.
"""
    return call_gemini(prompt, api_key, json_mode=False, model=model)


# =========================================================================
# 8. Conversation & Email Memory Miner (חילוץ זיכרונות וכללים משיחות ומיילים)
# =========================================================================
def extract_memories_from_chat(chat_text, api_key=None, source_type="chat", model=None):
    """
    Analyzes an entire conversation transcript, pasted chat, or email correspondence,
    extracting persistent directives (facts, commands, constraints, styles, instructions)
    that the user would want saved into their AI Memory Hub.
    Returns (ok, suggestions_list).
    """
    import chat_miner

    trimmed = chat_text[:24000] if len(chat_text) > 24000 else chat_text

    if source_type == "email":
        type_desc = "התכתבות אימייל או שרשור מיילים"
        focus_desc = """
  1. עובדות ונתונים קבועים (כתובות אתר, טלפונים, דוא"ל, שמות חברות ופרטי קשר).
  2. חתימות אישיות (זיהוי חתימות כגון 'בברכה, [שם]' או 'Best regards, [name]').
  3. סגנון וטון תקשורת במיילים (רשמי, שירותי, תמציתי).
  4. נהלים והנחיות קבועות שהוזכרו במייל (זמני תגובה, תהליכי עבודה).
  5. איסורים ודגשים עסקיים (דברים שנאמר להימנע מהם במפורש).
"""
    else:
        type_desc = "תמליל שיחה שהתקיימה בין משתמש לבין עוזר AI"
        focus_desc = """
  1. עובדות קבועות (שמות אתרים, טכנולוגיות, שמות עסקים, נתונים קבועים).
  2. פקודות קבועות (חתימה בסיום, בדיקות שיש לבצע תמיד).
  3. איסורים מחייבים (תיקונים שהמשתמש העיר: "אל תמחק הערות", "אל תעשה X").
  4. סגנון וטון (שפה עברית, הימנעות ממילים מסוימות, פירוט/תמצות).
  5. הוראות מותנות (מתי לבצע מה).
"""

    prompt = f"""
אתה עוזר AI מומחה לכריית ידע וניהול זיכרון (AI Memory & Directive Extractor).
לפניך {type_desc}.

עליך לנתח את הטקסט לעומק ולחלץ מתוכו אך ורק **חוקים, עובדות, איסורים, פקודות קבועות והעדפות סגנון מתמשכות** שהמשתמש דרש או ציין, ושכדאי לשמור בזיכרון הקבוע (Persistent Memory) כדי שה-AI לא יחזור על טעויות או ישאל שוב בשיחות הבאות.

שים לב:
- אל תחלץ בקשות חד-פעמיות זמניות (כגון: "תתקן באג בשורה 5" או "סכם לי קובץ זה").
- התמקד ב:{focus_desc}

להלן הטקסט לניתוח:
\"\"\"
{trimmed}
\"\"\"

החזר אך ורק אובייקט JSON תקני בפורמט הבא (ללא שום טקסט נוסף):
{{
  "suggestions": [
    {{
      "category": "facts/commands/constraints/styles/instructions",
      "title": "כותרת תמציתית בעברית",
      "data": {{
        // אם category == "facts": "name": "שם המידע", "value": "הערך"
        // אם category == "commands": "name": "שם פקודה", "details": "פירוט", "trigger_case": "באיזה מקרה"
        // אם category == "constraints": "constraint": "האיסור", "alternative_or_why": "הנחיה חלופית או נימוק"
        // אם category == "styles": "aspect": "היבט הסגנון", "instruction": "הנחיית הסגנון"
        // אם category == "instructions": "instruction": "ההוראה", "when_to_apply": "מתי ליישם"
      }},
      "reason": "הסבר תמציתי בעברית מדוע מומלץ להוסיף זאת לזיכרון הקבוע",
      "quote": "ציטוט קצר מתוך הטקסט שבו זה נאמר",
      "confidence": 0.95
    }}
  ]
}}
"""
    ok, text = call_gemini(prompt, api_key, json_mode=True, max_tokens=4096, model=model)
    if not ok:
        # Fallback to offline heuristic extractor
        h_ok, h_sug = chat_miner.extract_heuristic_memories(chat_text, source_type=source_type)
        if h_ok and h_sug:
            return True, h_sug
        return False, text

    try:
        data = json.loads(clean_json_response(text))
        suggestions = data.get("suggestions", [])
        if not suggestions:
            # Check if heuristic extractor found anything
            h_ok, h_sug = chat_miner.extract_heuristic_memories(chat_text, source_type=source_type)
            if h_ok and h_sug:
                return True, h_sug
        return True, suggestions
    except Exception:
        h_ok, h_sug = chat_miner.extract_heuristic_memories(chat_text, source_type=source_type)
        if h_ok and h_sug:
            return True, h_sug
        return False, f"שגיאה בפענוח הצעות הזיכרון מ-Gemini.\nתשובה גולמית: {text}"



