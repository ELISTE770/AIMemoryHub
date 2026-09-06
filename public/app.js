// AI Memory Hub - Frontend Logic

let appState = {
  facts: [],
  categories: [],
  tools: [],
  settings: {},
  logs: [],
  selectedCategory: 'all',
  searchQuery: '',
  lastSyncTime: null
};

// Elements
const factsContainer = document.getElementById('facts-container');
const toolsContainer = document.getElementById('tools-container');
const previewContent = document.getElementById('preview-content');
const logsContainer = document.getElementById('logs-container');
const categoryChips = document.getElementById('category-chips');
const foldersList = document.getElementById('folders-list');

const statDetectedTools = document.getElementById('stat-detected-tools');
const statFactsCount = document.getElementById('stat-facts-count');
const statLastSync = document.getElementById('stat-last-sync');

const tabBadgeCount = document.getElementById('tab-badge-count');
const tabBadgeTools = document.getElementById('tab-badge-tools');

const autoSyncToggle = document.getElementById('auto-sync-toggle');
const btnSyncAll = document.getElementById('btn-sync-all');
const syncSpinner = document.getElementById('sync-spinner');
const syncIcon = document.getElementById('sync-icon');

const factModal = document.getElementById('fact-modal');
const factForm = document.getElementById('fact-form');
const modalTitle = document.getElementById('modal-title');
const modalFactId = document.getElementById('modal-fact-id');
const modalCategory = document.getElementById('modal-category');
const modalKey = document.getElementById('modal-key');
const modalValue = document.getElementById('modal-value');
const modalActive = document.getElementById('modal-active');
const btnCloseModal = document.getElementById('btn-close-modal');
const btnOpenAddModal = document.getElementById('btn-open-add-modal');

const quickAddForm = document.getElementById('quick-add-form');
const quickAddInput = document.getElementById('quick-add-input');
const searchInput = document.getElementById('search-input');
const btnCopyPreview = document.getElementById('btn-copy-preview');
const btnRescanTools = document.getElementById('btn-rescan-tools');
const addFolderForm = document.getElementById('add-folder-form');
const newFolderPathInput = document.getElementById('new-folder-path');

// Toast Notification
function showToast(message, icon = '✅') {
  const toast = document.getElementById('toast');
  const toastMessage = document.getElementById('toast-message');
  const toastIcon = document.getElementById('toast-icon');

  toastMessage.textContent = message;
  toastIcon.textContent = icon;
  toast.classList.add('toast-visible');

  setTimeout(() => {
    toast.classList.remove('toast-visible');
  }, 3500);
}

// Format Date
function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString('he-IL');
}

// Fetch All Data
async function loadAllData() {
  try {
    // 1. Fetch memories
    const memRes = await fetch('/api/memories');
    const memData = await memRes.json();
    if (memData.success) {
      appState.facts = memData.facts || [];
      appState.categories = memData.categories || [];
      appState.settings = memData.settings || {};
      appState.logs = memData.logs || [];
      autoSyncToggle.checked = Boolean(appState.settings.autoSync);
    }

    // 2. Fetch tools
    const toolsRes = await fetch('/api/tools');
    const toolsData = await toolsRes.json();
    if (toolsData.success) {
      appState.tools = toolsData.tools || [];
    }

    // 3. Fetch preview
    updatePreview();

    // Render components
    renderStats();
    renderCategories();
    renderFacts();
    renderTools();
    renderSettings();
    renderLogs();
  } catch (err) {
    console.error('Failed to load data:', err);
    showToast('שגיאה בטעינת נתונים מהשרת', '❌');
  }
}

// Render Stats
function renderStats() {
  const installedToolsCount = appState.tools.filter((t) => t.installed).length;
  const activeFactsCount = appState.facts.filter((f) => f.active).length;

  statDetectedTools.textContent = `${installedToolsCount} מתוך ${appState.tools.length}`;
  statFactsCount.textContent = `${activeFactsCount} (מתוך ${appState.facts.length})`;
  tabBadgeCount.textContent = activeFactsCount;
  tabBadgeTools.textContent = `${installedToolsCount} מזוהים`;

  if (appState.lastSyncTime) {
    statLastSync.textContent = formatDate(appState.lastSyncTime);
  }
}

// Render Categories Filter Chips
function renderCategories() {
  categoryChips.innerHTML = `
    <button class="cat-chip ${appState.selectedCategory === 'all' ? 'active bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300'} text-xs px-3 py-1.5 rounded-lg font-medium transition" data-category="all">
      הכל (${appState.facts.length})
    </button>
  `;

  appState.categories.forEach((cat) => {
    const count = appState.facts.filter((f) => f.category === cat).length;
    const isActive = appState.selectedCategory === cat;
    const btn = document.createElement('button');
    btn.className = `cat-chip ${isActive ? 'active bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300'} text-xs px-3 py-1.5 rounded-lg font-medium whitespace-nowrap transition`;
    btn.dataset.category = cat;
    btn.textContent = `${cat} (${count})`;
    btn.onclick = () => {
      appState.selectedCategory = cat;
      renderCategories();
      renderFacts();
    };
    categoryChips.appendChild(btn);
  });

  categoryChips.querySelector('[data-category="all"]').onclick = () => {
    appState.selectedCategory = 'all';
    renderCategories();
    renderFacts();
  };
}

// Render Facts
function renderFacts() {
  factsContainer.innerHTML = '';

  const filtered = appState.facts.filter((fact) => {
    const matchesCategory = appState.selectedCategory === 'all' || fact.category === appState.selectedCategory;
    const query = appState.searchQuery.toLowerCase();
    const matchesQuery = !query ||
      fact.key.toLowerCase().includes(query) ||
      fact.value.toLowerCase().includes(query) ||
      (fact.category && fact.category.toLowerCase().includes(query));
    return matchesCategory && matchesQuery;
  });

  if (filtered.length === 0) {
    factsContainer.innerHTML = `
      <div class="col-span-full text-center py-12 bg-slate-900/40 rounded-2xl border border-slate-800">
        <span class="text-3xl mb-2 block">🔍</span>
        <div class="text-sm font-medium text-slate-300">לא נמצאו עובדות בזיכרון</div>
        <div class="text-xs text-slate-500 mt-1">השתמש בתיבת ההוספה המהירה למעלה כדי להוסיף מידע קבוע ל-AI</div>
      </div>
    `;
    return;
  }

  filtered.forEach((fact) => {
    const card = document.createElement('div');
    card.className = `memory-card bg-slate-900/90 border ${fact.active ? 'border-slate-800/80' : 'border-slate-800/40 opacity-60'} rounded-2xl p-4 flex flex-col justify-between`;

    const isUrl = fact.value.startsWith('http://') || fact.value.startsWith('https://') || fact.value.includes('.com') || fact.value.includes('.co.il');

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between gap-2 mb-2">
          <span class="text-[11px] px-2.5 py-0.5 rounded-full bg-slate-800 text-indigo-300 font-medium border border-slate-700/50">
            ${escapeHtml(fact.category)}
          </span>
          <label class="flex items-center gap-1.5 cursor-pointer text-xs text-slate-400">
            <input type="checkbox" class="toggle-active rounded bg-slate-800 border-slate-700 text-indigo-600 focus:ring-indigo-500" ${fact.active ? 'checked' : ''}>
            <span class="text-[10px]">${fact.active ? 'פעיל' : 'מושהה'}</span>
          </label>
        </div>

        <div class="text-sm font-bold text-white mb-1">${escapeHtml(fact.key)}</div>
        <div class="text-xs text-slate-300 bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 font-mono break-all leading-relaxed">
          ${isUrl ? `<a href="${fact.value.startsWith('http') ? fact.value : 'https://' + fact.value}" target="_blank" class="text-indigo-400 underline hover:text-indigo-300">${escapeHtml(fact.value)} ↗</a>` : escapeHtml(fact.value)}
        </div>
      </div>

      <div class="flex items-center justify-between pt-3 mt-3 border-t border-slate-800/60 text-xs">
        <span class="text-[10px] text-slate-500">${formatDate(fact.createdAt)}</span>
        <div class="flex items-center gap-1">
          <button class="btn-edit-fact px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition">
            ✏️ ערוך
          </button>
          <button class="btn-delete-fact px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition">
            🗑️ מחק
          </button>
        </div>
      </div>
    `;

    // Active Toggle
    const toggle = card.querySelector('.toggle-active');
    toggle.onchange = async () => {
      try {
        await fetch(`/api/memories/${fact.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active: toggle.checked })
        });
        fact.active = toggle.checked;
        renderStats();
        renderFacts();
        updatePreview();
        showToast(toggle.checked ? 'העובדה הופעלה' : 'העובדה הושהתה');
      } catch (err) {
        showToast('שגיאה בעדכון עובדה', '❌');
      }
    };

    // Edit Button
    card.querySelector('.btn-edit-fact').onclick = () => {
      openEditModal(fact);
    };

    // Delete Button
    card.querySelector('.btn-delete-fact').onclick = async () => {
      if (confirm(`האם אתה בטוח שברצונך למחוק את "${fact.key}" מהזיכרון?`)) {
        try {
          await fetch(`/api/memories/${fact.id}`, { method: 'DELETE' });
          appState.facts = appState.facts.filter((f) => f.id !== fact.id);
          renderStats();
          renderCategories();
          renderFacts();
          updatePreview();
          showToast(`"${fact.key}" נמחק בהצלחה`);
        } catch (err) {
          showToast('שגיאה במחיקת עובדה', '❌');
        }
      }
    };

    factsContainer.appendChild(card);
  });
}

// Render Tools
function renderTools() {
  toolsContainer.innerHTML = '';

  appState.tools.forEach((tool) => {
    const card = document.createElement('div');
    const isInstalled = tool.installed;
    card.className = `bg-slate-900/90 border ${isInstalled ? 'border-emerald-500/30' : 'border-slate-800/60 opacity-60'} rounded-2xl p-5 flex flex-col justify-between`;

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between gap-3 mb-2">
          <div class="flex items-center gap-2.5">
            <span class="text-2xl">${tool.icon}</span>
            <div>
              <h3 class="text-sm font-bold text-white flex items-center gap-2">
                ${escapeHtml(tool.name)}
                <span class="text-[10px] text-slate-400 font-normal">(${escapeHtml(tool.vendor)})</span>
              </h3>
              <p class="text-xs text-slate-400 mt-0.5">${escapeHtml(tool.description)}</p>
            </div>
          </div>

          <span class="text-xs px-2.5 py-1 rounded-full font-medium ${isInstalled ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5' : 'bg-slate-800 text-slate-500'}">
            ${isInstalled ? '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse online-dot"></span> מותקן ומזוהה' : 'לא מותקן'}
          </span>
        </div>

        <div class="mt-3 space-y-1.5 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-[11px] font-mono">
          <div class="text-slate-400 flex items-center justify-between">
            <span>נתיב ראשי:</span>
            <span class="text-slate-300 truncate max-w-[280px]" title="${tool.appPath}">${escapeHtml(tool.appPath || 'לא מוגדר')}</span>
          </div>
          ${tool.configPath ? `
            <div class="text-slate-400 flex items-center justify-between">
              <span>קובץ הגדרות:</span>
              <span class="text-indigo-300 truncate max-w-[280px]" title="${tool.configPath}">${escapeHtml(tool.configPath)}</span>
            </div>
          ` : ''}
          <div class="text-emerald-400/90 pt-1 font-sans text-xs">
            ℹ️ ${escapeHtml(tool.details)}
          </div>
        </div>
      </div>

      <div class="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs">
        <div class="flex items-center gap-1.5">
          <span class="text-[10px] text-slate-400">ערוצי השתלה נתמכים:</span>
          ${(tool.injectionMethods || []).map((m) => `<span class="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">${m}</span>`).join(' ')}
        </div>
      </div>
    `;

    toolsContainer.appendChild(card);
  });
}

// Render Settings & Target Folders
function renderSettings() {
  foldersList.innerHTML = '';
  const folders = appState.settings.targetProjectFolders || [];

  if (folders.length === 0) {
    foldersList.innerHTML = `<div class="text-xs text-slate-500 italic">אין כרגע תיקיות פרויקטים מוגדרות</div>`;
  } else {
    folders.forEach((folder, idx) => {
      const item = document.createElement('div');
      item.className = 'flex items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono';
      item.innerHTML = `
        <span class="truncate text-slate-300" title="${folder}">${escapeHtml(folder)}</span>
        <button class="btn-remove-folder text-rose-400 hover:text-rose-300 p-1 text-sm font-sans" title="הסר תיקייה">✖</button>
      `;

      item.querySelector('.btn-remove-folder').onclick = async () => {
        const updated = folders.filter((_, i) => i !== idx);
        await saveSettings({ targetProjectFolders: updated });
        showToast('תיקייה הוסרה בהצלחה');
      };

      foldersList.appendChild(item);
    });
  }

  // Checkboxes
  document.getElementById('setting-claude-mcp').checked = appState.settings.injectClaudeMcp !== false;
  document.getElementById('setting-anti-knowledge').checked = appState.settings.injectAntigravityKnowledge !== false;
  document.getElementById('setting-project-rules').checked = appState.settings.injectProjectRules !== false;
}

// Save Settings helper
async function saveSettings(newSettings) {
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSettings)
    });
    const data = await res.json();
    if (data.success) {
      appState.settings = data.settings;
      renderSettings();
    }
  } catch (err) {
    showToast('שגיאה בשמירת הגדרות', '❌');
  }
}

// Render Logs
function renderLogs() {
  logsContainer.innerHTML = '';
  if (!appState.logs || appState.logs.length === 0) {
    logsContainer.innerHTML = `<div class="text-xs text-slate-500 italic p-2">אין עדיין רשומות ביומן</div>`;
    return;
  }

  appState.logs.forEach((log) => {
    const row = document.createElement('div');
    row.className = 'flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800/80';
    row.innerHTML = `
      <span class="text-slate-300">${escapeHtml(log.message)}</span>
      <span class="text-[10px] text-slate-500 whitespace-nowrap">${formatDate(log.timestamp)}</span>
    `;
    logsContainer.appendChild(row);
  });
}

// Update Preview
async function updatePreview() {
  try {
    const res = await fetch('/api/preview');
    const data = await res.json();
    if (data.success) {
      previewContent.textContent = data.promptText;
    }
  } catch (err) {
    console.error('Preview error:', err);
  }
}

// Perform Sync All
async function syncAll() {
  btnSyncAll.disabled = true;
  syncSpinner.classList.remove('hidden');
  syncIcon.classList.add('hidden');

  try {
    const res = await fetch('/api/inject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        injectClaudeMcp: document.getElementById('setting-claude-mcp').checked,
        injectAntigravity: document.getElementById('setting-anti-knowledge').checked
      })
    });
    const data = await res.json();
    if (data.success) {
      appState.lastSyncTime = new Date().toISOString();
      const count = (data.results.injectedTools || []).length;
      showToast(`סנכרון הושלם בהצלחה! הושתל ב-${count} מוקדים במחשב`, '🚀');
      loadAllData();
    } else {
      showToast('שגיאה בהשתלת זיכרון', '❌');
    }
  } catch (err) {
    showToast('שגיאה בתקשורת עם השרת', '❌');
  } finally {
    btnSyncAll.disabled = false;
    syncSpinner.classList.add('hidden');
    syncIcon.classList.remove('hidden');
  }
}

// Quick Add Handler
quickAddForm.onsubmit = async (e) => {
  e.preventDefault();
  const text = quickAddInput.value.trim();
  if (!text) return;

  try {
    const res = await fetch('/api/quick-add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`נוסף לזיכרון: "${data.fact.key}"`, '✨');
      quickAddInput.value = '';
      loadAllData();
    }
  } catch (err) {
    showToast('שגיאה בהוספה מהירה', '❌');
  }
};

// Search Filter
searchInput.oninput = (e) => {
  appState.searchQuery = e.target.value.trim();
  renderFacts();
};

// Modal Add / Edit
function openAddModal() {
  modalTitle.textContent = 'הוספת עובדה חדשה לזיכרון';
  modalFactId.value = '';
  modalKey.value = '';
  modalValue.value = '';
  modalActive.checked = true;
  factModal.classList.remove('hidden');
}

function openEditModal(fact) {
  modalTitle.textContent = 'עריכת עובדה בזיכרון';
  modalFactId.value = fact.id;
  modalCategory.value = fact.category || 'הערות נוספות';
  modalKey.value = fact.key;
  modalValue.value = fact.value;
  modalActive.checked = Boolean(fact.active);
  factModal.classList.remove('hidden');
}

btnOpenAddModal.onclick = openAddModal;
btnCloseModal.onclick = () => factModal.classList.add('hidden');

factForm.onsubmit = async (e) => {
  e.preventDefault();
  const id = modalFactId.value;
  const payload = {
    category: modalCategory.value,
    key: modalKey.value.trim(),
    value: modalValue.value.trim(),
    active: modalActive.checked
  };

  try {
    if (id) {
      // Update
      await fetch(`/api/memories/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showToast('עובדה עודכנה בהצלחה');
    } else {
      // Add
      await fetch('/api/memories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      showToast('עובדה חדשה נוספה בהצלחה');
    }
    factModal.classList.add('hidden');
    loadAllData();
  } catch (err) {
    showToast('שגיאה בשמירת עובדה', '❌');
  }
};

// Add Folder Form
addFolderForm.onsubmit = async (e) => {
  e.preventDefault();
  const pathVal = newFolderPathInput.value.trim();
  if (!pathVal) return;

  const current = appState.settings.targetProjectFolders || [];
  if (current.includes(pathVal)) {
    showToast('תיקייה זו כבר קיימת ברשימה', '⚠️');
    return;
  }

  current.push(pathVal);
  await saveSettings({ targetProjectFolders: current });
  newFolderPathInput.value = '';
  showToast('תיקיית פרויקט נוספה בהצלחה');
};

// Auto Sync Toggle
autoSyncToggle.onchange = async () => {
  await saveSettings({ autoSync: autoSyncToggle.checked });
  showToast(autoSyncToggle.checked ? 'סנכרון אוטומטי הופעל' : 'סנכרון אוטומטי בוטל');
};

// Copy Preview
btnCopyPreview.onclick = () => {
  navigator.clipboard.writeText(previewContent.textContent);
  showToast('הטקסט הועתק ללוח!');
};

// Rescan Tools
btnRescanTools.onclick = async () => {
  showToast('סורק כלי AI במחשב...');
  await loadAllData();
  showToast('סריקה הושלמה!');
};

btnSyncAll.onclick = syncAll;

// Tabs switcher
document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach((c) => c.classList.add('hidden'));

    btn.classList.add('active');
    const targetId = btn.dataset.tab;
    document.getElementById(targetId).classList.remove('hidden');
  };
});

// Escape HTML helper
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Initial load
loadAllData();
