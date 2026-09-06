const fs = require('fs');
const path = require('path');
const os = require('os');

function scanAITools() {
  const userProfile = process.env.USERPROFILE || os.homedir();
  const appData = process.env.APPDATA || path.join(userProfile, 'AppData', 'Roaming');
  const localAppData = process.env.LOCALAPPDATA || path.join(userProfile, 'AppData', 'Local');

  const tools = [
    {
      id: 'claude_desktop',
      name: 'Claude Desktop',
      icon: '🧠',
      vendor: 'Anthropic',
      description: 'אפליקציית שולחן העבודה הרשמית של קלוד עם תמיכה מלאה ב-MCP והוראות קבועות',
      appPath: path.join(appData, 'Claude'),
      configPath: path.join(appData, 'Claude', 'claude_desktop_config.json'),
      injectionMethods: ['mcp', 'rules_file'],
      installed: false,
      details: ''
    },
    {
      id: 'antigravity',
      name: 'Google Antigravity',
      icon: '⚡',
      vendor: 'Google DeepMind',
      description: 'סביבת סוכני AI מתקדמת לפיתוח, תומכת בכללי GEMINI.md, הגדרות ידע ו-MCP',
      appPath: path.join(userProfile, '.gemini'),
      configPath: path.join(userProfile, '.gemini', 'antigravity'),
      knowledgePath: path.join(userProfile, '.gemini', 'antigravity', 'knowledge', 'ai_memory.md'),
      injectionMethods: ['rules_file', 'global_knowledge'],
      installed: false,
      details: ''
    },
    {
      id: 'vscode',
      name: 'Visual Studio Code',
      icon: '💻',
      vendor: 'Microsoft',
      description: 'עורך הקוד הפופולרי, תומך ב-GitHub Copilot, Cline, Roo Code והוראות זיכרון',
      appPath: path.join(appData, 'Code'),
      configPath: path.join(appData, 'Code', 'User'),
      injectionMethods: ['copilot_instructions'],
      installed: false,
      details: ''
    },
    {
      id: 'cursor',
      name: 'Cursor AI',
      icon: '🎯',
      vendor: 'Anysphere',
      description: 'עורך קוד ייעודי ל-AI, תומך בכללי .cursorrules ו-MDC memory',
      appPath: path.join(appData, 'Cursor'),
      configPath: path.join(appData, 'Cursor', 'User'),
      altAppPath: path.join(localAppData, 'Programs', 'cursor'),
      injectionMethods: ['cursorrules'],
      installed: false,
      details: ''
    },
    {
      id: 'windsurf',
      name: 'Windsurf (Codeium)',
      icon: '🏄',
      vendor: 'Codeium',
      description: 'סביבת פיתוח מבוססת סוכנים עם תמיכה בחוקי .windsurfrules ו-Global Memories',
      appPath: path.join(appData, 'Windsurf'),
      configPath: path.join(userProfile, '.codeium', 'windsurf', 'memories'),
      altAppPath: path.join(localAppData, 'Programs', 'windsurf'),
      injectionMethods: ['windsurfrules'],
      installed: false,
      details: ''
    },
    {
      id: 'chatgpt_desktop',
      name: 'ChatGPT Desktop',
      icon: '💬',
      vendor: 'OpenAI',
      description: 'אפליקציית שולחן העבודה של ChatGPT ל-Windows',
      appPath: path.join(appData, 'OpenAI', 'ChatGPT'),
      configPath: path.join(appData, 'OpenAI', 'ChatGPT'),
      injectionMethods: ['instruction_export'],
      installed: false,
      details: ''
    }
  ];

  const results = tools.map((tool) => {
    const existsPrimary = tool.appPath && fs.existsSync(tool.appPath);
    const existsAlt = tool.altAppPath && fs.existsSync(tool.altAppPath);
    const existsConfig = tool.configPath && fs.existsSync(tool.configPath);

    const installed = Boolean(existsPrimary || existsAlt || existsConfig);

    let details = 'לא אותר במחשב';
    if (installed) {
      if (tool.id === 'claude_desktop') {
        const configExists = fs.existsSync(tool.configPath);
        details = configExists 
          ? 'מותקן + קובץ קונפיגורציה claude_desktop_config.json אותר בהצלחה'
          : 'מותקן (ללא קובץ קונפיגורציה ראשוני)';
      } else if (tool.id === 'antigravity') {
        details = 'מותקן בספריית המשתמש (.gemini) ומוכן לסנכרון';
      } else if (tool.id === 'vscode') {
        details = 'מותקן (נתמך להשתלת copilot-instructions)';
      } else {
        details = 'מותקן ומזוהה במערכת';
      }
    }

    return {
      ...tool,
      installed,
      details
    };
  });

  return results;
}

module.exports = {
  scanAITools
};
