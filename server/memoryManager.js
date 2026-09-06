const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const MEMORY_FILE = path.join(DATA_DIR, 'memory.json');

const DEFAULT_CATEGORIES = [
  'אתרים וקישורים',
  'פרטים אישיים ועסקיים',
  'העדפות פיתוח וקוד',
  'הנחיות כלליות ומענה',
  'הערות נוספות'
];

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function getInitialData() {
  return {
    version: '1.0',
    lastUpdated: new Date().toISOString(),
    settings: {
      autoSync: false,
      targetProjectFolders: [
        // Default to current user's workspace
        process.cwd()
      ],
      injectClaudeMcp: true,
      injectAntigravityKnowledge: true,
      injectProjectRules: true
    },
    facts: [
      {
        id: 'fact_default_website',
        category: 'אתרים וקישורים',
        key: 'האתר שלי',
        value: 'example.com',
        active: true,
        createdAt: new Date().toISOString()
      },
      {
        id: 'fact_default_lang',
        category: 'הנחיות כלליות ומענה',
        key: 'שפת מענה ראשית',
        value: 'עברית רהוטה וברורה',
        active: true,
        createdAt: new Date().toISOString()
      }
    ],
    logs: [
      {
        id: 'log_init',
        timestamp: new Date().toISOString(),
        action: 'initialization',
        message: 'מאגר הזיכרון אותחל בהצלחה'
      }
    ]
  };
}

function loadDatabase() {
  ensureDataDir();
  if (!fs.existsSync(MEMORY_FILE)) {
    const initial = getInitialData();
    fs.writeFileSync(MEMORY_FILE, JSON.stringify(initial, null, 2), 'utf-8');
    return initial;
  }
  try {
    const content = fs.readFileSync(MEMORY_FILE, 'utf-8');
    return JSON.parse(content);
  } catch (err) {
    console.error('Error parsing memory.json, creating fallback:', err);
    return getInitialData();
  }
}

function saveDatabase(data) {
  ensureDataDir();
  data.lastUpdated = new Date().toISOString();
  fs.writeFileSync(MEMORY_FILE, JSON.stringify(data, null, 2), 'utf-8');
}

function getMemories() {
  const db = loadDatabase();
  return {
    facts: db.facts || [],
    categories: DEFAULT_CATEGORIES,
    settings: db.settings || {},
    lastUpdated: db.lastUpdated,
    logs: (db.logs || []).slice(-30) // last 30 logs
  };
}

function addMemory({ category, key, value, active = true }) {
  if (!key || !value) {
    throw new Error('Key and Value are required');
  }
  const db = loadDatabase();
  const newFact = {
    id: 'fact_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7),
    category: category || 'הערות נוספות',
    key: key.trim(),
    value: value.trim(),
    active: Boolean(active),
    createdAt: new Date().toISOString()
  };
  db.facts = db.facts || [];
  db.facts.unshift(newFact);

  db.logs = db.logs || [];
  db.logs.unshift({
    id: 'log_' + Date.now(),
    timestamp: new Date().toISOString(),
    action: 'add_fact',
    message: `נוספה עובדה חדשה: "${newFact.key}" (${newFact.category})`
  });

  saveDatabase(db);
  return newFact;
}

function updateMemory(id, { category, key, value, active }) {
  const db = loadDatabase();
  const index = (db.facts || []).findIndex((f) => f.id === id);
  if (index === -1) {
    throw new Error('Fact not found');
  }

  if (category !== undefined) db.facts[index].category = category;
  if (key !== undefined) db.facts[index].key = key.trim();
  if (value !== undefined) db.facts[index].value = value.trim();
  if (active !== undefined) db.facts[index].active = Boolean(active);
  db.facts[index].updatedAt = new Date().toISOString();

  db.logs = db.logs || [];
  db.logs.unshift({
    id: 'log_' + Date.now(),
    timestamp: new Date().toISOString(),
    action: 'update_fact',
    message: `עודכנה עובדה: "${db.facts[index].key}"`
  });

  saveDatabase(db);
  return db.facts[index];
}

function deleteMemory(id) {
  const db = loadDatabase();
  const factToDelete = (db.facts || []).find((f) => f.id === id);
  db.facts = (db.facts || []).filter((f) => f.id !== id);

  if (factToDelete) {
    db.logs = db.logs || [];
    db.logs.unshift({
      id: 'log_' + Date.now(),
      timestamp: new Date().toISOString(),
      action: 'delete_fact',
      message: `נמחקה עובדה: "${factToDelete.key}"`
    });
  }

  saveDatabase(db);
  return { success: true, id };
}

function quickAdd(naturalText) {
  if (!naturalText || typeof naturalText !== 'string') {
    throw new Error('Text is required');
  }

  const text = naturalText.trim();
  let category = 'הערות נוספות';
  let key = 'מידע קבוע';
  let value = text;

  // Simple heuristic parsing for Hebrew / English
  // Example: "האתר שלי זה example.com" or "תוסיף למטה את האתר שלי: example.com"
  const cleaned = text
    .replace(/^תוסיף\s+(למטה\s+)?(את\s+)?/i, '')
    .replace(/^תזכור\s+(ש)?/i, '')
    .trim();

  if (cleaned.includes(':')) {
    const parts = cleaned.split(':');
    key = parts[0].trim();
    value = parts.slice(1).join(':').trim();
  } else if (cleaned.includes(' זה ') || cleaned.includes(' הוא ')) {
    const splitter = cleaned.includes(' זה ') ? ' זה ' : ' הוא ';
    const parts = cleaned.split(splitter);
    key = parts[0].trim();
    value = parts.slice(1).join(splitter).trim();
  } else if (cleaned.includes('=')) {
    const parts = cleaned.split('=');
    key = parts[0].trim();
    value = parts.slice(1).join('=').trim();
  }

  // Detect category based on key or value
  const lower = (key + ' ' + value).toLowerCase();
  if (lower.includes('אתר') || lower.includes('site') || lower.includes('web') || lower.includes('http') || lower.includes('.com') || lower.includes('.co.il')) {
    category = 'אתרים וקישורים';
  } else if (lower.includes('שם') || lower.includes('מייל') || lower.includes('טלפון') || lower.includes('חברה') || lower.includes('עסק') || lower.includes('כתובת')) {
    category = 'פרטים אישיים ועסקיים';
  } else if (lower.includes('שפה') || lower.includes('קוד') || lower.includes('react') || lower.includes('python') || lower.includes('node') || lower.includes('style') || lower.includes('git')) {
    category = 'העדפות פיתוח וקוד';
  } else if (lower.includes('הנחיה') || lower.includes('סגנון') || lower.includes('עברית') || lower.includes('קצר') || lower.includes('תשובה')) {
    category = 'הנחיות כלליות ומענה';
  }

  return addMemory({ category, key, value, active: true });
}

function updateSettings(newSettings) {
  const db = loadDatabase();
  db.settings = { ...(db.settings || {}), ...newSettings };
  saveDatabase(db);
  return db.settings;
}

function addLog(action, message) {
  const db = loadDatabase();
  db.logs = db.logs || [];
  db.logs.unshift({
    id: 'log_' + Date.now(),
    timestamp: new Date().toISOString(),
    action,
    message
  });
  saveDatabase(db);
}

function generateMemoryPromptText() {
  const db = loadDatabase();
  const activeFacts = (db.facts || []).filter((f) => f.active);

  if (activeFacts.length === 0) {
    return `<!-- AI_MEMORY_HUB_START -->\n<!-- AI Memory Hub: אין כרגע עובדות פעילות בזיכרון -->\n<!-- AI_MEMORY_HUB_END -->`;
  }

  // Group by category
  const groups = {};
  for (const fact of activeFacts) {
    const cat = fact.category || 'כללי';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(fact);
  }

  let lines = [];
  lines.push('<!-- AI_MEMORY_HUB_START -->');
  lines.push('# 🧠 AI Persistent Memory & User Facts');
  lines.push('> עובדות קבועות והנחיות זיכרון שנשמרות עבור המשתמש בכל השיחות:');
  lines.push('');

  for (const [category, items] of Object.entries(groups)) {
    lines.push(`### 📌 ${category}`);
    for (const item of items) {
      lines.push(`- **${item.key}**: ${item.value}`);
    }
    lines.push('');
  }

  lines.push(`_סונכרן אוטומטית באמצעות Universal AI Memory Hub | עודכן: ${new Date().toLocaleString('he-IL')}_`);
  lines.push('<!-- AI_MEMORY_HUB_END -->');

  return lines.join('\n');
}

module.exports = {
  getMemories,
  addMemory,
  updateMemory,
  deleteMemory,
  quickAdd,
  updateSettings,
  addLog,
  generateMemoryPromptText
};
