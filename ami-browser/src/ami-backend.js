'use strict';

const path = require('path');
const playwrightMcpDir = path.dirname(require.resolve('playwright/lib/mcp/program'));
const { BrowserServerBackend } = require(path.join(playwrightMcpDir, 'browser', 'browserServerBackend'));
const { toMcpTool } = require(path.join(playwrightMcpDir, 'sdk', 'tool'));
const { z } = require('playwright-core/lib/mcpBundle');
const { ActionStore, extractDomain } = require('./action-store');
const { translateAction } = require('./action-translator');
const {
  amiExecuteSchema,
  browserFallbackSchema,
  amiMemorySearchSchema,
  addCreateConfigSchema,
  addToolSchema,
  addUpdateToolSchema,
  addDeleteToolSchema,
} = require('./action-tools');

// Tools that are "read-only" and should NOT trigger save nudges
const READ_ONLY_FALLBACK_TOOLS = new Set([
  'browser_snapshot',
  'browser_console_messages',
  'browser_network_requests',
  'browser_tabs',
  'browser_take_screenshot',
]);

class AmiBackend {
  constructor(config, browserContextFactory) {
    this._inner = new BrowserServerBackend(config, browserContextFactory, { allTools: true });
    this._store = new ActionStore();
    this._currentDomain = null;
    this._currentUrl = null;
    this._currentTools = [];       // Tools for current page
    this._currentConfigs = [];     // Configs for current domain
    this._lastLookedUpUrl = null;

    // Nudge state
    this._fallbackNudgePending = false;
    this._fallbackEverUsed = false;
    this._extractionHintShown = false;
    this._fallbackToolsUsed = [];
    this._fallbackActionLog = [];
    this._savedToolCategories = new Set();
  }

  async initialize(clientInfo) {
    await this._inner.initialize(clientInfo);
  }

  _resetPageState() {
    this._fallbackNudgePending = false;
    this._fallbackEverUsed = false;
    this._extractionHintShown = false;
    this._fallbackToolsUsed = [];
    this._fallbackActionLog = [];
    this._lastLookedUpUrl = null;
    this._savedToolCategories = new Set();
  }

  async _lookupToolsForUrl(url) {
    const domain = extractDomain(url);
    this._currentDomain = domain;
    this._currentUrl = url;
    this._lastLookedUpUrl = url;

    if (domain) {
      this._currentConfigs = await this._store.getConfigsForDomain(domain);
      this._currentTools = await this._store.findToolsForUrl(domain, url);
    } else {
      this._currentConfigs = [];
      this._currentTools = [];
    }
  }

  async listTools() {
    const navigateSchema = {
      name: 'browser_navigate',
      title: 'Navigate to a URL',
      description: 'Navigate to a URL in the browser. After navigation, available saved tools for the site will be shown.',
      inputSchema: z.object({
        url: z.string().describe('The URL to navigate to'),
      }),
      type: 'action',
    };

    const snapshotSchema = {
      name: 'browser_snapshot',
      title: 'Page snapshot',
      description: 'Capture accessibility snapshot of the current page, this is better than screenshot',
      inputSchema: z.object({
        filename: z.string().optional().describe('Save snapshot to markdown file instead of returning it in the response.'),
      }),
      type: 'readOnly',
    };

    return [
      navigateSchema,
      snapshotSchema,
      browserFallbackSchema,
      amiExecuteSchema,
      amiMemorySearchSchema,
      addCreateConfigSchema,
      addToolSchema,
      addUpdateToolSchema,
      addDeleteToolSchema,
    ].map(schema => toMcpTool(schema));
  }

  async callTool(name, rawArguments, progress) {
    switch (name) {
      case 'browser_navigate':
        return this._handleNavigate(rawArguments, progress);
      case 'browser_snapshot':
        return this._handleSnapshot(rawArguments, progress);
      case 'browser_fallback':
        return this._handleFallback(rawArguments, progress);
      case 'ami_execute':
        return this._handleExecute(rawArguments, progress);
      case 'ami_memory':
        return this._handleMemorySearch(rawArguments);
      case 'add_create-config':
        return this._handleCreateConfig(rawArguments);
      case 'add_tool':
        return this._handleAddTool(rawArguments);
      case 'add_update-tool':
        return this._handleUpdateTool(rawArguments);
      case 'add_delete-tool':
        return this._handleDeleteTool(rawArguments);
      default:
        return {
          content: [{ type: 'text', text: `### Error\nTool "${name}" not found. Use browser_fallback to access raw Playwright tools.` }],
          isError: true,
        };
    }
  }

  // ─── Navigate with multi-stage URL resolution ───

  async _handleNavigate(args, progress) {
    this._resetPageState();

    // Stage 1: Navigate
    let result = await this._inner.callTool('browser_navigate', args, progress);
    result = truncateResult(result);
    const requestedUrl = args.url;

    await this._lookupToolsForUrl(requestedUrl);

    // Stage 2: Server-side redirect detection
    if (this._currentTools.length === 0) {
      const finalUrl = extractFinalUrl(result);
      if (finalUrl && finalUrl !== requestedUrl) {
        await this._lookupToolsForUrl(finalUrl);
      }
    }

    // Stage 3: SPA client-side redirect detection
    if (this._currentTools.length === 0 && this._currentDomain) {
      try {
        const spaResult = await this._inner.callTool('browser_run_code', {
          code: [
            'async (page) => {',
            '  const startUrl = page.url();',
            '  try {',
            '    await page.waitForURL(url => url.toString() !== startUrl, { timeout: 2000 });',
            '  } catch {}',
            '  return { url: page.url() };',
            '}',
          ].join('\n'),
        });
        const spaUrl = extractFinalUrl(spaResult);
        if (spaUrl && spaUrl !== this._currentUrl) {
          await this._lookupToolsForUrl(spaUrl);
        }
      } catch {}
    }

    // Prepend available tools info
    const domain = this._currentDomain;
    if (this._currentTools.length > 0) {
      const toolList = this._currentTools.map(t => {
        const params = (t.input_schema || []).map(p => p.name).join(', ');
        return `  <tool name="${t.name}" params="${params}">${t.description}</tool>`;
      }).join('\n');

      const extra = `<available-tools domain="${domain}">
${toolList}
</available-tools>
<navigation-reminder>
You have saved tools for ${domain}. Use ami_execute to run them.
If you need browser_fallback for something not yet saved, you MUST save a complete tool with add_tool before you are done. This includes resultSelector for data extraction.
</navigation-reminder>\n\n`;
      return prependTextToResult(result, extra);
    } else if (domain) {
      const extra = `<navigation-reminder>
No saved tools for ${domain}. Use browser_fallback to interact with the page.
</navigation-reminder>\n\n`;
      return prependTextToResult(result, extra);
    }

    return result;
  }

  // ─── Snapshot with SPA detection + nudges ───

  async _handleSnapshot(args, progress) {
    let result = await this._inner.callTool('browser_snapshot', args, progress);
    result = truncateResult(result);

    let nudgePrefix = '';

    // Late SPA detection
    const snapshotUrl = extractFinalUrl(result);
    if (snapshotUrl && snapshotUrl !== this._lastLookedUpUrl) {
      await this._lookupToolsForUrl(snapshotUrl);

      if (this._currentTools.length > 0) {
        const toolList = this._currentTools.map(t => {
          const params = (t.input_schema || []).map(p => p.name).join(', ');
          return `  <tool name="${t.name}" params="${params}">${t.description}</tool>`;
        }).join('\n');
        nudgePrefix += `<tools-discovered domain="${this._currentDomain}">
<context>SPA navigation detected — saved tools are available for this page.</context>
${toolList}
<instruction>Use ami_execute for these tools instead of browser_fallback.</instruction>
</tools-discovered>\n\n`;
      }
    }

    // Save nudge after fallback action
    if (this._fallbackNudgePending) {
      this._fallbackNudgePending = false;
      nudgePrefix += this._buildSaveNudge() + '\n\n';
    }

    // Extraction reminder
    if (!this._extractionHintShown
        && this._fallbackEverUsed
        && !this._savedToolCategories.has('extraction')
        && !this._fallbackNudgePending) {
      this._extractionHintShown = true;

      const hasIncomplete = this._currentTools.some(t =>
        (t.execution?.fields?.length > 0 || t.execution?.submit) && !t.execution?.resultSelector);

      if (hasIncomplete) {
        const incomplete = this._currentTools.find(t =>
          (t.execution?.fields?.length > 0 || t.execution?.submit) && !t.execution?.resultSelector);
        nudgePrefix += `<tool-incomplete>
<observation>Your saved tool "${incomplete.name}" has NO resultSelector — it won't return data.</observation>
<instruction>Use add_update-tool to add "resultSelector" and "resultType" to the execution.</instruction>
</tool-incomplete>\n\n`;
      } else {
        nudgePrefix += `<extraction-reminder>
<observation>You took a snapshot to read page data but your saved tools don't extract anything.</observation>
<instruction>Update your tool or save a new one with "resultSelector" and "resultType" in the execution.</instruction>
</extraction-reminder>\n\n`;
      }
    }

    if (nudgePrefix) {
      result = prependTextToResult(result, nudgePrefix);
    }

    return result;
  }

  // ─── Fallback with reminders ───

  async _getUpstreamTools() {
    if (!this._upstreamToolsCache) {
      this._upstreamToolsCache = await this._inner.listTools();
    }
    return this._upstreamToolsCache;
  }

  async _handleFallback(args, progress) {
    const toolName = args.tool;
    const toolArgs = args.arguments || {};

    if (!toolName) {
      const tools = await this._getUpstreamTools();
      const toolList = tools.map(t => {
        const desc = (t.description || '').replace(/\n/g, ' ').slice(0, 120);
        return `- **${t.name}**: ${desc}${desc.length >= 120 ? '...' : ''}`;
      }).join('\n');
      const reminder = this._buildFallbackListReminder();
      return {
        content: [{ type: 'text', text: `### Available Playwright Tools\n${toolList}\n\nUse \`peek: true\` to inspect a tool's full input schema before calling it.\nExample: \`browser_fallback({ tool: "browser_click", peek: true })\`${reminder}` }],
      };
    }

    if (args.peek === true) {
      const tools = await this._getUpstreamTools();
      const match = tools.find(t => t.name === toolName);
      if (!match) {
        return {
          content: [{ type: 'text', text: `Unknown tool: "${toolName}". Call browser_fallback without a tool argument to list available tools.` }],
          isError: true,
        };
      }
      return {
        content: [{ type: 'text', text: `### Schema for ${toolName}\n\`\`\`json\n${JSON.stringify(match.inputSchema, null, 2)}\n\`\`\`\n\n**Description**: ${match.description || '(none)'}` }],
      };
    }

    // State tracking
    if (!READ_ONLY_FALLBACK_TOOLS.has(toolName)) {
      this._fallbackNudgePending = true;
      this._fallbackEverUsed = true;
      if (!this._fallbackToolsUsed.includes(toolName)) {
        this._fallbackToolsUsed.push(toolName);
      }
      this._fallbackActionLog.push({ tool: toolName, args: summarizeArgs(toolName, toolArgs) });
    }

    let result = await this._inner.callTool(toolName, toolArgs, progress);
    result = truncateResult(result);

    // Auto-peek on validation failure
    if (result.isError) {
      const errText = result.content?.[0]?.text || '';
      if (errText.includes('invalid_type') || errText.includes('invalid_union') || errText.includes('unrecognized_keys')) {
        const tools = await this._getUpstreamTools();
        const match = tools.find(t => t.name === toolName);
        if (match) {
          const schemaHint = `\n\n### Correct schema for ${toolName}\n\`\`\`json\n${JSON.stringify(match.inputSchema, null, 2)}\n\`\`\`\n\n**Description**: ${match.description || '(none)'}`;
          result = appendTextToResult(result, schemaHint);
        }
      }
    }

    // Save reminder after fallback action
    if (!READ_ONLY_FALLBACK_TOOLS.has(toolName)) {
      const reminder = `\n\n<save-reminder>
You used browser_fallback (${toolName}). You are NOT done yet.
Before saying you are done, you MUST save a complete tool:
  1. add_create-config (if no config exists yet)
  2. add_tool with fields + submit + resultSelector + input_schema params
An tool without resultSelector is INCOMPLETE.
</save-reminder>`;
      result = appendTextToResult(result, reminder);
    }

    return result;
  }

  // ─── Nudge builders ───

  _buildSaveNudge() {
    const domain = this._currentDomain;
    const hasExistingTools = this._currentTools.length > 0;

    let nudge = `<save-reminder>\n`;
    nudge += `You have used browser_fallback to interact with this page.\n`;
    nudge += `You are NOT done yet. Before finishing, complete this checklist:\n\n`;

    if (this._fallbackActionLog.length > 0) {
      nudge += `Steps you performed:\n`;
      for (let i = 0; i < this._fallbackActionLog.length; i++) {
        const entry = this._fallbackActionLog[i];
        nudge += `  ${i + 1}. ${entry.tool}(${entry.args})\n`;
      }
      nudge += `\n`;
    }

    if (hasExistingTools) {
      const existingNames = this._currentTools.map(t => t.name).join(', ');
      nudge += `Existing tools for ${domain}: ${existingNames}\n`;
      nudge += `→ If these don't cover what you just did, save a new tool. Do NOT duplicate existing ones.\n\n`;
    }

    const hasConfigs = this._currentConfigs.length > 0;
    nudge += `Checklist — complete ALL before saying you are done:\n`;
    if (!hasConfigs) {
      nudge += `  [ ] Call add_create-config for "${domain}"\n`;
    }
    nudge += `  [ ] Call add_tool with a COMPLETE tool covering the steps above\n`;
    nudge += `  [ ] Include "fields" for form inputs (parameterize all user-changeable values in input_schema)\n`;
    nudge += `  [ ] Include "submit" for form submission\n`;
    nudge += `  [ ] Include "waitFor" to wait for results to load\n`;
    nudge += `  [ ] Include "resultSelector" + "resultType" for data extraction\n`;
    nudge += `  [ ] Use kebab-case verb-noun name (e.g., "search-google")\n`;
    nudge += `\n`;
    nudge += `Only then is your task complete.\n`;
    nudge += `</save-reminder>`;

    return nudge;
  }

  _buildFallbackListReminder() {
    const domain = this._currentDomain;
    const hasExistingTools = this._currentTools.length > 0;

    if (hasExistingTools) {
      const toolList = this._currentTools.map(t => t.name).join(', ');
      return `\n\n<reminder>Saved tools exist for ${domain}: ${toolList}
Use ami_execute instead of browser_fallback when possible.
Any use of browser_fallback requires saving a complete tool before you are done.</reminder>`;
    } else if (domain) {
      return `\n\n<reminder>No saved tools for ${domain}. Use browser_fallback to complete the task first.</reminder>`;
    }
    return '';
  }

  // ─── ami_execute (run a saved tool) ───

  async _handleExecute(args, progress) {
    const { toolName, args: toolArgs = {} } = args;

    if (!toolName) {
      return {
        content: [{ type: 'text', text: '### Error\nMissing "toolName" parameter.' }],
        isError: true,
      };
    }

    // Look up tool — first in current page tools, then domain-wide, then globally
    let tool = this._currentTools.find(t => t.name === toolName);
    if (!tool && this._currentDomain) {
      tool = await this._store.findToolByNameForDomain(this._currentDomain, toolName);
    }
    if (!tool) {
      tool = await this._store.findToolByName(toolName);
    }

    if (!tool) {
      return {
        content: [{ type: 'text', text: `### Error\nTool "${toolName}" not found. Navigate to a site to see available tools.` }],
        isError: true,
      };
    }

    // Parse input_schema (params) from DB
    const params = Array.isArray(tool.input_schema) ? tool.input_schema : [];
    const execution = tool.execution || {};

    // Validate required params
    const missingParams = params
      .filter(p => p.required && toolArgs[p.name] === undefined)
      .map(p => p.name);

    if (missingParams.length > 0) {
      return {
        content: [{ type: 'text', text: `### Error\nMissing required parameters: ${missingParams.join(', ')}` }],
        isError: true,
      };
    }

    // Apply defaults
    const resolvedArgs = { ...toolArgs };
    for (const param of params) {
      if (resolvedArgs[param.name] === undefined && param.default !== undefined) {
        resolvedArgs[param.name] = param.default;
      }
    }

    // Translate to Playwright code — translateAction expects { execution, params }
    let code;
    try {
      code = translateAction({ execution, params }, resolvedArgs);
    } catch (e) {
      return {
        content: [{ type: 'text', text: `### Error translating tool\n${String(e)}` }],
        isError: true,
      };
    }

    // Execute
    const result = await this._inner.callTool('browser_run_code', { code }, progress);
    const header = `### Executed: ${tool.name}\n`;
    return prependTextToResult(result, header);
  }

  // ─── ami_memory (semantic search) ───

  async _handleMemorySearch(args) {
    const { query } = args;

    if (!query) {
      return {
        content: [{ type: 'text', text: '### Error\nMissing "query" parameter.' }],
        isError: true,
      };
    }

    try {
      const configs = await this._store.searchConfigsByQuery(query);

      if (configs.length === 0) {
        return {
          content: [{ type: 'text', text: `### No results\nNo saved sites match "${query}". Try navigating to a site manually with browser_navigate.` }],
        };
      }

      let text = `### Memory search results for "${query}"\n\n`;
      for (const config of configs) {
        text += `**${config.title}** — \`${config.domain}\`\n`;
        if (config.description) {
          text += `  ${config.description}\n`;
        }
        if (config.tools.length > 0) {
          text += `  Tools: ${config.tools.map(t => `\`${t.name}\``).join(', ')}\n`;
        } else {
          text += `  No saved tools yet.\n`;
        }
        text += '\n';
      }

      text += `Use \`browser_navigate\` to go to the relevant site, then use \`ami_execute\` to run its saved tools.`;

      return {
        content: [{ type: 'text', text }],
      };
    } catch (e) {
      return {
        content: [{ type: 'text', text: `### Error searching memory\n${e.message || String(e)}` }],
        isError: true,
      };
    }
  }

  // ─── add_create-config ───

  async _handleCreateConfig(args) {
    const { domain, urlPattern, title, description, tags } = args;

    if (!domain) {
      return {
        content: [{ type: 'text', text: '### Error\nMissing "domain" parameter.' }],
        isError: true,
      };
    }

    // Auto-fix domain with protocol
    let bareDomain = domain;
    if (/^https?:\/\//.test(domain)) {
      bareDomain = extractDomain(domain);
    }

    // Check if config already exists for this domain + pattern
    const pattern = urlPattern || '/*';
    const existing = await this._store.getConfigForDomainAndPattern(bareDomain, pattern);
    if (existing) {
      return {
        content: [{ type: 'text', text: `### Config Already Exists\n- **ID**: ${existing.id}\n- **Domain**: ${existing.domain}\n- **URL Pattern**: ${existing.url_pattern}\n- **Title**: ${existing.title}\n\nUse this configId with add_tool to add tools.` }],
      };
    }

    try {
      const config = await this._store.createConfig({
        domain: bareDomain,
        urlPattern: pattern,
        title: title || bareDomain,
        description: description || '',
        tags: tags || null,
      });

      // Refresh current configs
      if (bareDomain === this._currentDomain) {
        this._currentConfigs = await this._store.getConfigsForDomain(this._currentDomain);
      }

      return {
        content: [{ type: 'text', text: `### Config Created\n- **configId**: ${config.id}\n- **Domain**: ${config.domain}\n- **URL Pattern**: ${config.url_pattern}\n- **Title**: ${config.title}\n\nNow use \`add_tool({ configId: "${config.id}", ... })\` to add tools to this config.` }],
      };
    } catch (e) {
      return {
        content: [{ type: 'text', text: `### Error creating config\n${String(e.message || e)}` }],
        isError: true,
      };
    }
  }

  // ─── add_tool ───

  async _handleAddTool(args) {
    const { configId, name, description, inputSchema: inputSchemaJson, execution: executionJson } = args;

    if (!configId || !name) {
      return {
        content: [{ type: 'text', text: '### Error\nBoth "configId" and "name" are required.' }],
        isError: true,
      };
    }

    // Verify config exists
    const config = await this._store.getConfigById(configId);
    if (!config) {
      return {
        content: [{ type: 'text', text: `### Error\nConfig "${configId}" not found. Use add_create-config first.` }],
        isError: true,
      };
    }

    // Parse JSON inputs
    let inputSchema = [];
    let execution = {};
    try {
      if (inputSchemaJson) inputSchema = JSON.parse(inputSchemaJson);
    } catch (e) {
      return {
        content: [{ type: 'text', text: `### Error parsing inputSchema JSON\n${String(e)}` }],
        isError: true,
      };
    }
    try {
      if (executionJson) execution = JSON.parse(executionJson);
    } catch (e) {
      return {
        content: [{ type: 'text', text: `### Error parsing execution JSON\n${String(e)}` }],
        isError: true,
      };
    }

    // Validate name format
    const warnings = [];
    if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(name)) {
      warnings.push(`**Name format**: "${name}" should be kebab-case verb-noun, e.g., "search-products", "fill-login".`);
    }

    // Check parameterization
    if (execution.fields && execution.fields.length > 0 && (!inputSchema || inputSchema.length === 0)) {
      warnings.push(`**Parameterization**: Tool has ${execution.fields.length} field(s) but no params in inputSchema.`);
    }

    let warningText = '';
    if (warnings.length > 0) {
      warningText = `\n\n### Suggestions\n${warnings.map(w => `- ${w}`).join('\n')}`;
    }

    try {
      const tool = await this._store.addTool({
        configId,
        name,
        description: description || '',
        inputSchema,
        execution,
      });

      // Refresh current tools if same domain
      if (config.domain === this._currentDomain) {
        this._currentTools = await this._store.findToolsForUrl(this._currentDomain, this._currentUrl);
      }

      // Track saved categories
      const isFormTool = (execution.fields?.length > 0) || !!execution.submit;
      const isExtractionTool = !!execution.resultSelector;
      if (isFormTool) this._savedToolCategories.add('form');
      if (isExtractionTool) this._savedToolCategories.add('extraction');

      let followUp = '';
      if (isFormTool && !isExtractionTool && this._fallbackEverUsed) {
        followUp = `\n\n**Tool is INCOMPLETE** — no resultSelector. Use add_update-tool({ toolName: "${tool.name}" }) to add resultSelector and resultType.`;
      }

      return {
        content: [{ type: 'text', text: `### Tool Added\n- **toolId**: ${tool.id}\n- **Name**: ${tool.name}\n- **Config**: ${config.title} (${config.domain})\n- **Has extraction**: ${isExtractionTool ? 'yes' : '**NO — incomplete**'}\n- **Params**: ${(inputSchema || []).map(p => p.name).join(', ') || 'none'}\n\nThis tool is now available via \`ami_execute({ toolName: "${tool.name}", args: {...} })\` on ${config.domain}.${followUp}${warningText}` }],
      };
    } catch (e) {
      const errMsg = e.message || String(e);
      if (errMsg.includes('uq_tools_config_name')) {
        return {
          content: [{ type: 'text', text: `### Error\nA tool named "${name}" already exists in this config. Use add_update-tool to modify it, or choose a different name.` }],
          isError: true,
        };
      }
      return {
        content: [{ type: 'text', text: `### Error adding tool\n${errMsg}${warningText}` }],
        isError: true,
      };
    }
  }

  // ─── add_update-tool ───

  async _handleUpdateTool(args) {
    const { toolName, domain, newName, description, inputSchema: inputSchemaJson, execution: executionJson } = args;

    if (!toolName) {
      return {
        content: [{ type: 'text', text: '### Error\nMissing "toolName" parameter.' }],
        isError: true,
      };
    }

    // Resolve tool by name — try current domain first, then provided domain, then global
    const searchDomain = domain || this._currentDomain;
    let existing = null;
    if (searchDomain) {
      existing = await this._store.findToolByNameForDomain(searchDomain, toolName);
    }
    if (!existing) {
      existing = await this._store.findToolByName(toolName);
    }
    if (!existing) {
      return {
        content: [{ type: 'text', text: `### Error\nTool "${toolName}" not found${searchDomain ? ` for domain "${searchDomain}"` : ''}. Navigate to the site first or specify the domain.` }],
        isError: true,
      };
    }

    const updates = {};
    if (newName !== undefined) updates.name = newName;
    if (description !== undefined) updates.description = description;

    if (inputSchemaJson !== undefined) {
      try {
        updates.inputSchema = JSON.parse(inputSchemaJson);
      } catch (e) {
        return {
          content: [{ type: 'text', text: `### Error parsing inputSchema JSON\n${String(e)}` }],
          isError: true,
        };
      }
    }

    if (executionJson !== undefined) {
      try {
        updates.execution = JSON.parse(executionJson);
      } catch (e) {
        return {
          content: [{ type: 'text', text: `### Error parsing execution JSON\n${String(e)}` }],
          isError: true,
        };
      }
    }

    try {
      const updated = await this._store.updateTool(existing.id, updates);

      // Refresh current tools
      if (this._currentDomain) {
        this._currentTools = await this._store.findToolsForUrl(this._currentDomain, this._currentUrl);
      }

      return {
        content: [{ type: 'text', text: `### Tool Updated\n- **Name**: ${updated.name}\n- **Domain**: ${existing.domain}\n\nChanges saved successfully.` }],
      };
    } catch (e) {
      return {
        content: [{ type: 'text', text: `### Error updating tool\n${e.message || String(e)}` }],
        isError: true,
      };
    }
  }

  // ─── add_delete-tool ───

  async _handleDeleteTool(args) {
    const { toolName, domain } = args;

    if (!toolName) {
      return {
        content: [{ type: 'text', text: '### Error\nMissing "toolName" parameter.' }],
        isError: true,
      };
    }

    // Resolve tool by name — try current domain first, then provided domain, then global
    const searchDomain = domain || this._currentDomain;
    let tool = null;
    if (searchDomain) {
      tool = await this._store.findToolByNameForDomain(searchDomain, toolName);
    }
    if (!tool) {
      tool = await this._store.findToolByName(toolName);
    }
    if (!tool) {
      return {
        content: [{ type: 'text', text: `### Error\nTool "${toolName}" not found${searchDomain ? ` for domain "${searchDomain}"` : ''}. Navigate to the site first or specify the domain.` }],
        isError: true,
      };
    }

    const deleted = await this._store.deleteTool(tool.id);
    if (!deleted) {
      return {
        content: [{ type: 'text', text: `### Error\nFailed to delete tool "${toolName}".` }],
        isError: true,
      };
    }

    // Refresh current tools
    if (this._currentDomain) {
      this._currentTools = await this._store.findToolsForUrl(this._currentDomain, this._currentUrl);
    }

    return {
      content: [{ type: 'text', text: `### Deleted\nTool "${toolName}" removed from ${tool.domain}.` }],
    };
  }

  serverClosed(server) {
    this._inner.serverClosed(server);
  }
}

// ─── Constants ───

const MAX_RESULT_CHARS = 40000;

// ─── Helpers ───

function appendTextToResult(result, text) {
  const content = [...(result.content || [])];
  const lastIdx = content.length - 1;
  if (lastIdx >= 0 && content[lastIdx].type === 'text') {
    content[lastIdx] = { ...content[lastIdx], text: content[lastIdx].text + text };
  } else {
    content.push({ type: 'text', text });
  }
  return { ...result, content };
}

function prependTextToResult(result, text) {
  const content = [...(result.content || [])];
  if (content.length > 0 && content[0].type === 'text') {
    content[0] = { ...content[0], text: text + content[0].text };
  } else {
    content.unshift({ type: 'text', text });
  }
  return { ...result, content };
}

function summarizeArgs(toolName, args) {
  if (!args || Object.keys(args).length === 0) return '';
  switch (toolName) {
    case 'browser_click':
      return `ref: "${args.ref}"${args.element ? `, element: "${args.element}"` : ''}`;
    case 'browser_type':
      return `ref: "${args.ref}", text: "${args.text}"${args.submit ? ', submit: true' : ''}`;
    case 'browser_fill_form':
      if (args.fields) {
        const fields = args.fields.map(f => `${f.name || '?'}="${f.value}"`).join(', ');
        return `fields: [${fields}]`;
      }
      return JSON.stringify(args);
    case 'browser_select_option':
      return `ref: "${args.ref}", values: ${JSON.stringify(args.values)}`;
    case 'browser_press_key':
      return `key: "${args.key}"`;
    case 'browser_hover':
      return `ref: "${args.ref}"`;
    default: {
      const json = JSON.stringify(args);
      return json.length > 100 ? json.slice(0, 97) + '...' : json;
    }
  }
}

function extractFinalUrl(result) {
  if (!result?.content) return null;
  for (const item of result.content) {
    if (item.type !== 'text') continue;
    const match = item.text.match(/- Page URL:\s*(https?:\/\/\S+)/);
    if (match) return match[1];
  }
  return null;
}

function truncateResult(result) {
  if (!result?.content) return result;

  let totalSize = 0;
  for (const item of result.content) {
    if (item.type === 'text') {
      totalSize += item.text.length;
    } else {
      totalSize += JSON.stringify(item).length;
    }
  }

  if (totalSize <= MAX_RESULT_CHARS) return result;

  const content = [];
  let budget = MAX_RESULT_CHARS;

  for (const item of result.content) {
    if (item.type === 'image') continue;

    if (item.type !== 'text') {
      const itemSize = JSON.stringify(item).length;
      if (budget - itemSize < 0) continue;
      content.push(item);
      budget -= itemSize;
      continue;
    }

    if (item.text.length <= budget) {
      content.push(item);
      budget -= item.text.length;
    } else if (budget > 500) {
      const truncPoint = item.text.lastIndexOf('\n', budget);
      const cutAt = truncPoint > budget * 0.5 ? truncPoint : budget;
      const truncated = item.text.slice(0, cutAt);
      const droppedChars = item.text.length - cutAt;

      content.push({
        ...item,
        text: truncated + `\n\n--- Content truncated (${Math.round(droppedChars / 1024)}KB omitted). Take another snapshot or use resultSelector in saved tools to extract specific data. ---`,
      });
      budget = 0;
    }
  }

  return { ...result, content };
}

module.exports = { AmiBackend };
