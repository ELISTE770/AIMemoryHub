/**
 * Universal AI Memory - Model Context Protocol (MCP) Server
 * Runs via stdio for Claude Desktop, Antigravity, Cursor, etc.
 */

const readline = require('readline');
const path = require('path');
const { getMemories, addMemory, quickAdd } = require('./memoryManager');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

function sendResponse(response) {
  process.stdout.write(JSON.stringify(response) + '\n');
}

function handleRequest(request) {
  const { id, method, params } = request;

  if (method === 'initialize') {
    return sendResponse({
      jsonrpc: '2.0',
      id,
      result: {
        protocolVersion: '2024-11-05',
        capabilities: {
          tools: {}
        },
        serverInfo: {
          name: 'ai-memory-hub',
          version: '1.0.0'
        }
      }
    });
  }

  if (method === 'notifications/initialized') {
    // No response needed for notification
    return;
  }

  if (method === 'tools/list') {
    return sendResponse({
      jsonrpc: '2.0',
      id,
      result: {
        tools: [
          {
            name: 'get_user_memories',
            description: 'שליפת כל הזיכרונות והעובדות הקבועות של המשתמש (כגון אתרי אינטרנט, פרטים אישיים, הנחיות קבועות והעדפות קוד)',
            inputSchema: {
              type: 'object',
              properties: {
                category: {
                  type: 'string',
                  description: 'סינון אופציונלי לפי קטגוריה (למשל: "אתרים וקישורים", "פרטים אישיים ועסקיים", "העדפות פיתוח וקוד")'
                }
              }
            }
          },
          {
            name: 'save_user_memory',
            description: 'שמירת עובדה או זיכרון חדש לזיכרון הקבוע של המשתמש כך שיישמר בכל השיחות העתידיות (למשל: אתר חדש, העדפת שפה, כתובת וכו\')',
            inputSchema: {
              type: 'object',
              required: ['key', 'value'],
              properties: {
                key: {
                  type: 'string',
                  description: 'כותרת או שם העובדה (למשל: "האתר שלי", "שפת תכנות מועדפת")'
                },
                value: {
                  type: 'string',
                  description: 'ערך או תוכן העובדה (למשל: "example.com", "TypeScript ו-React")'
                },
                category: {
                  type: 'string',
                  description: 'קטגוריה מתאימה'
                }
              }
            }
          },
          {
            name: 'search_user_memory',
            description: 'חיפוש עובדות ספציפיות בזיכרון המשתמש לפי מילת מפתח',
            inputSchema: {
              type: 'object',
              required: ['query'],
              properties: {
                query: {
                  type: 'string',
                  description: 'מילת חיפוש (למשל: "אתר", "מייל", "פרויקט")'
                }
              }
            }
          }
        ]
      }
    });
  }

  if (method === 'tools/call') {
    const toolName = params?.name;
    const args = params?.arguments || {};

    try {
      if (toolName === 'get_user_memories') {
        const data = getMemories();
        let facts = data.facts.filter((f) => f.active);
        if (args.category) {
          facts = facts.filter((f) => f.category === args.category);
        }
        return sendResponse({
          jsonrpc: '2.0',
          id,
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({ count: facts.length, facts }, null, 2)
              }
            ]
          }
        });
      }

      if (toolName === 'save_user_memory') {
        const newFact = addMemory({
          category: args.category || 'הערות נוספות',
          key: args.key,
          value: args.value,
          active: true
        });

        return sendResponse({
          jsonrpc: '2.0',
          id,
          result: {
            content: [
              {
                type: 'text',
                text: `✅ העובדה נשמרה בהצלחה בזיכרון הקבוע: "${newFact.key} = ${newFact.value}" (${newFact.category})`
              }
            ]
          }
        });
      }

      if (toolName === 'search_user_memory') {
        const query = (args.query || '').toLowerCase();
        const data = getMemories();
        const matches = data.facts.filter(
          (f) =>
            f.active &&
            (f.key.toLowerCase().includes(query) ||
              f.value.toLowerCase().includes(query) ||
              f.category.toLowerCase().includes(query))
        );

        return sendResponse({
          jsonrpc: '2.0',
          id,
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify({ query, foundCount: matches.length, matches }, null, 2)
              }
            ]
          }
        });
      }

      return sendResponse({
        jsonrpc: '2.0',
        id,
        error: {
          code: -32601,
          message: `Tool not found: ${toolName}`
        }
      });
    } catch (err) {
      return sendResponse({
        jsonrpc: '2.0',
        id,
        error: {
          code: -32000,
          message: err.message
        }
      });
    }
  }

  // Unknown method
  if (id !== undefined) {
    sendResponse({
      jsonrpc: '2.0',
      id,
      error: {
        code: -32601,
        message: `Method not found: ${method}`
      }
    });
  }
}

// Listen for JSON-RPC messages on stdin
rl.on('line', (line) => {
  if (!line.trim()) return;
  try {
    const request = JSON.parse(line);
    handleRequest(request);
  } catch (err) {
    // Ignore invalid json or non-json lines
  }
});
