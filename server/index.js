const express = require('express');
const cors = require('cors');
const path = require('path');
const { scanAITools } = require('./scanner');
const {
  getMemories,
  addMemory,
  updateMemory,
  deleteMemory,
  quickAdd,
  updateSettings,
  generateMemoryPromptText
} = require('./memoryManager');
const { performFullInjection } = require('./injector');

const app = express();
const PORT = process.env.PORT || 3456;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

// Helper to check and run auto-sync if enabled
function triggerAutoSyncIfEnabled() {
  try {
    const data = getMemories();
    if (data.settings && data.settings.autoSync) {
      console.log('🔄 Auto-sync triggered...');
      performFullInjection({
        injectClaudeMcp: data.settings.injectClaudeMcp,
        injectAntigravity: data.settings.injectAntigravityKnowledge,
        targetFolders: data.settings.targetProjectFolders
      });
    }
  } catch (err) {
    console.error('Auto-sync error:', err);
  }
}

// 1. Scan AI Tools
app.get('/api/tools', (req, res) => {
  try {
    const tools = scanAITools();
    res.json({ success: true, tools });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 2. Get all memories & settings
app.get('/api/memories', (req, res) => {
  try {
    const data = getMemories();
    res.json({ success: true, ...data });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 3. Add memory
app.post('/api/memories', (req, res) => {
  try {
    const { category, key, value, active } = req.body;
    const newFact = addMemory({ category, key, value, active });
    triggerAutoSyncIfEnabled();
    res.json({ success: true, fact: newFact });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// 4. Quick Add (Natural language)
app.post('/api/quick-add', (req, res) => {
  try {
    const { text } = req.body;
    const newFact = quickAdd(text);
    triggerAutoSyncIfEnabled();
    res.json({ success: true, fact: newFact });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// 5. Update memory
app.put('/api/memories/:id', (req, res) => {
  try {
    const updated = updateMemory(req.params.id, req.body);
    triggerAutoSyncIfEnabled();
    res.json({ success: true, fact: updated });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// 6. Delete memory
app.delete('/api/memories/:id', (req, res) => {
  try {
    const result = deleteMemory(req.params.id);
    triggerAutoSyncIfEnabled();
    res.json(result);
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// 7. Preview generated prompt
app.get('/api/preview', (req, res) => {
  try {
    const promptText = generateMemoryPromptText();
    res.json({ success: true, promptText });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// 8. Update Settings
app.post('/api/settings', (req, res) => {
  try {
    const newSettings = updateSettings(req.body);
    res.json({ success: true, settings: newSettings });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// 9. Execute Injection / Sync
app.post('/api/inject', (req, res) => {
  try {
    const data = getMemories();
    const options = {
      injectClaudeMcp: req.body.injectClaudeMcp !== undefined ? req.body.injectClaudeMcp : data.settings.injectClaudeMcp,
      injectAntigravity: req.body.injectAntigravity !== undefined ? req.body.injectAntigravity : data.settings.injectAntigravityKnowledge,
      targetFolders: req.body.targetFolders || data.settings.targetProjectFolders
    };

    const injectionResults = performFullInjection(options);
    res.json({ success: true, results: injectionResults });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// Fallback to index.html for frontend routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`=======================================================`);
  console.log(`🧠 AI Memory Hub Server running at http://localhost:${PORT}`);
  console.log(`=======================================================`);
});
