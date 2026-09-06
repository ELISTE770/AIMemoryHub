const fs = require('fs');
const path = require('path');
const os = require('os');
const { scanAITools } = require('./scanner');
const { generateMemoryPromptText, addLog } = require('./memoryManager');

// Helper to replace or append content between markers
function injectBetweenMarkers(existingContent, newBlock) {
  const startMarker = '<!-- AI_MEMORY_HUB_START -->';
  const endMarker = '<!-- AI_MEMORY_HUB_END -->';

  const startIndex = existingContent.indexOf(startMarker);
  const endIndex = existingContent.indexOf(endMarker);

  if (startIndex !== -1 && endIndex !== -1 && endIndex >= startIndex) {
    const before = existingContent.substring(0, startIndex);
    const after = existingContent.substring(endIndex + endMarker.length);
    return before + newBlock + after;
  }

  // If markers not found, append to the end
  if (existingContent.trim().length > 0) {
    return existingContent.trim() + '\n\n' + newBlock + '\n';
  }
  return newBlock + '\n';
}

function backupFile(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      const backupPath = filePath + '.bak';
      fs.copyFileSync(filePath, backupPath);
      return backupPath;
    }
  } catch (err) {
    console.error(`Failed to backup ${filePath}:`, err);
  }
  return null;
}

/**
 * Injects MCP server config into Claude Desktop config
 */
function injectClaudeDesktopMcp(toolsList) {
  const claudeTool = toolsList.find((t) => t.id === 'claude_desktop');
  if (!claudeTool || !claudeTool.installed || !claudeTool.configPath) {
    return { success: false, reason: 'Claude Desktop not installed or config path not found' };
  }

  const configPath = claudeTool.configPath;
  const configDir = path.dirname(configPath);
  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
  }

  backupFile(configPath);

  let config = {};
  if (fs.existsSync(configPath)) {
    try {
      const content = fs.readFileSync(configPath, 'utf-8');
      config = JSON.parse(content);
    } catch (e) {
      console.warn('Could not parse existing claude config, creating fresh structure');
    }
  }

  config.mcpServers = config.mcpServers || {};

  const mcpServerScript = path.resolve(__dirname, 'mcpServer.js');

  config.mcpServers['ai-memory'] = {
    command: 'node',
    args: [mcpServerScript]
  };

  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
  addLog('claude_mcp_injected', `הושתל שרת MCP ב-Claude Desktop (${configPath})`);
  return { success: true, path: configPath };
}

/**
 * Injects into Antigravity knowledge base
 */
function injectAntigravityKnowledge(promptText) {
  const userProfile = process.env.USERPROFILE || os.homedir();
  const knowledgeDir = path.join(userProfile, '.gemini', 'antigravity', 'knowledge');

  if (!fs.existsSync(knowledgeDir)) {
    fs.mkdirSync(knowledgeDir, { recursive: true });
  }

  const targetFile = path.join(knowledgeDir, 'ai_persistent_memory.md');
  backupFile(targetFile);

  let content = '';
  if (fs.existsSync(targetFile)) {
    content = fs.readFileSync(targetFile, 'utf-8');
  }

  const updatedContent = injectBetweenMarkers(content, promptText);
  fs.writeFileSync(targetFile, updatedContent, 'utf-8');

  addLog('antigravity_knowledge_injected', `הושתל קובץ ידע ב-Antigravity (${targetFile})`);
  return { success: true, path: targetFile };
}

/**
 * Injects rule files (CLAUDE.md, GEMINI.md, .cursorrules, etc.) into target folders
 */
function injectProjectRules(targetFolder, promptText) {
  if (!targetFolder || !fs.existsSync(targetFolder)) {
    return { success: false, reason: 'Target folder does not exist' };
  }

  const results = [];
  const ruleFiles = [
    'CLAUDE.md',
    'GEMINI.md',
    '.cursorrules',
    '.windsurfrules'
  ];

  for (const filename of ruleFiles) {
    const filePath = path.join(targetFolder, filename);
    let content = '';
    if (fs.existsSync(filePath)) {
      backupFile(filePath);
      content = fs.readFileSync(filePath, 'utf-8');
    }
    const newContent = injectBetweenMarkers(content, promptText);
    fs.writeFileSync(filePath, newContent, 'utf-8');
    results.push({ file: filename, path: filePath, updated: true });
  }

  // Also handle .github/copilot-instructions.md for VS Code / Copilot
  const githubDir = path.join(targetFolder, '.github');
  if (!fs.existsSync(githubDir)) {
    fs.mkdirSync(githubDir, { recursive: true });
  }
  const copilotFile = path.join(githubDir, 'copilot-instructions.md');
  let copilotContent = '';
  if (fs.existsSync(copilotFile)) {
    backupFile(copilotFile);
    copilotContent = fs.readFileSync(copilotFile, 'utf-8');
  }
  fs.writeFileSync(copilotFile, injectBetweenMarkers(copilotContent, promptText), 'utf-8');
  results.push({ file: '.github/copilot-instructions.md', path: copilotFile, updated: true });

  addLog('project_rules_injected', `הושתלו קבצי הוראות בתיקייה: ${targetFolder}`);
  return { success: true, details: results };
}

/**
 * Main function to perform comprehensive injection
 */
function performFullInjection(options = {}) {
  const tools = scanAITools();
  const promptText = generateMemoryPromptText();
  const results = {
    timestamp: new Date().toISOString(),
    injectedTools: [],
    errors: []
  };

  // 1. Claude Desktop MCP
  if (options.injectClaudeMcp !== false) {
    const claudeRes = injectClaudeDesktopMcp(tools);
    if (claudeRes.success) {
      results.injectedTools.push({ tool: 'Claude Desktop (MCP)', path: claudeRes.path });
    } else {
      results.errors.push({ tool: 'Claude Desktop', error: claudeRes.reason });
    }
  }

  // 2. Antigravity Knowledge Base
  if (options.injectAntigravity !== false) {
    try {
      const antiRes = injectAntigravityKnowledge(promptText);
      results.injectedTools.push({ tool: 'Antigravity (Knowledge)', path: antiRes.path });
    } catch (err) {
      results.errors.push({ tool: 'Antigravity', error: err.message });
    }
  }

  // 3. Project folders rules injection
  const folders = options.targetFolders || [process.cwd()];
  for (const folder of folders) {
    try {
      const projRes = injectProjectRules(folder, promptText);
      if (projRes.success) {
        results.injectedTools.push({ tool: `כללי פרויקט (${path.basename(folder)})`, path: folder });
      }
    } catch (err) {
      results.errors.push({ tool: `תיקיית פרויקט ${folder}`, error: err.message });
    }
  }

  return results;
}

module.exports = {
  performFullInjection,
  injectClaudeDesktopMcp,
  injectAntigravityKnowledge,
  injectProjectRules,
  injectBetweenMarkers
};
