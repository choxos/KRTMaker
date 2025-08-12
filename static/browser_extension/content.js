/**
 * Content Script for KRT Helper Browser Extension
 * 
 * Provides real-time RRID suggestions and resource validation
 * on manuscript writing platforms like Overleaf, Google Docs, etc.
 */

// Global state
let isExtensionActive = false;
let userPreferences = {};
let currentSuggestionPopup = null;
let resourceHighlights = new Map();
let debounceTimer = null;

// Platform detection
const PLATFORM_CONFIGS = {
  overleaf: {
    textSelectors: ['.cm-editor', '.ace_editor', 'textarea'],
    insertMethod: 'ace_editor'
  },
  googledocs: {
    textSelectors: ['.kix-lineview-content', '[contenteditable="true"]'],
    insertMethod: 'contenteditable'
  },
  notion: {
    textSelectors: ['[data-block-id]', '[contenteditable="true"]'],
    insertMethod: 'contenteditable'
  },
  generic: {
    textSelectors: ['textarea', '[contenteditable="true"]', '.editor'],
    insertMethod: 'textarea'
  }
};

// Initialize extension
function initializeExtension() {
  console.log('KRT Helper: Initializing content script');
  
  // Load user preferences
  loadUserPreferences();
  
  // Detect platform
  const platform = detectPlatform();
  console.log('KRT Helper: Detected platform:', platform);
  
  // Set up event listeners
  setupEventListeners(platform);
  
  // Create UI elements
  createExtensionUI();
  
  // Start monitoring for text changes
  startTextMonitoring(platform);
  
  isExtensionActive = true;
  console.log('KRT Helper: Content script initialized');
}

function detectPlatform() {
  const hostname = window.location.hostname.toLowerCase();
  
  if (hostname.includes('overleaf') || hostname.includes('sharelatex')) {
    return 'overleaf';
  } else if (hostname.includes('docs.google.com')) {
    return 'googledocs';
  } else if (hostname.includes('notion.so')) {
    return 'notion';
  } else {
    return 'generic';
  }
}

async function loadUserPreferences() {
  try {
    const response = await sendMessageToBackground('getUserPreferences');
    if (response.success) {
      userPreferences = response.data;
    }
  } catch (error) {
    console.error('KRT Helper: Failed to load preferences:', error);
    userPreferences = getDefaultPreferences();
  }
}

function getDefaultPreferences() {
  return {
    enableAutoSuggestions: true,
    enableRRIDValidation: true,
    showConfidenceScores: true,
    maxSuggestions: 5,
    highlightLevel: 'medium'
  };
}

function setupEventListeners(platform) {
  const config = PLATFORM_CONFIGS[platform] || PLATFORM_CONFIGS.generic;
  
  // Listen for text selection and typing
  document.addEventListener('mouseup', handleTextSelection);
  document.addEventListener('keyup', handleTextChange);
  document.addEventListener('input', handleTextChange);
  
  // Listen for clicks to close popups
  document.addEventListener('click', handleDocumentClick);
  
  // Listen for keyboard shortcuts
  document.addEventListener('keydown', handleKeyboardShortcuts);
  
  // Platform-specific listeners
  if (platform === 'overleaf') {
    setupOverleafListeners();
  } else if (platform === 'googledocs') {
    setupGoogleDocsListeners();
  }
}

function setupOverleafListeners() {
  // Wait for Overleaf editor to load
  const waitForEditor = setInterval(() => {
    const editor = document.querySelector('.cm-editor, .ace_editor');
    if (editor) {
      clearInterval(waitForEditor);
      console.log('KRT Helper: Overleaf editor detected');
      
      // Add listeners for Overleaf-specific events
      editor.addEventListener('input', debounceTextChange);
      editor.addEventListener('paste', debounceTextChange);
    }
  }, 500);
}

function setupGoogleDocsListeners() {
  // Google Docs uses a different DOM structure
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList' || mutation.type === 'characterData') {
        debounceTextChange();
      }
    });
  });
  
  const docContent = document.querySelector('.kix-document-content');
  if (docContent) {
    observer.observe(docContent, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }
}

function createExtensionUI() {
  // Create floating action button
  const fab = document.createElement('div');
  fab.id = 'krt-helper-fab';
  fab.className = 'krt-helper-fab';
  fab.innerHTML = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M9 12l2 2 4-4"/>
      <path d="M21 12c-1 0-3-1-3-3s2-3 3-3 3 1 3 3-2 3-3 3"/>
      <path d="M3 12c1 0 3-1 3-3s-2-3-3-3-3 1-3 3 2 3 3 3"/>
      <path d="M12 3c0 1-1 3-3 3s-3-2-3-3 1-3 3-3 3 2 3 3"/>
      <path d="M12 21c0-1-1-3-3-3s-3 2-3 3 1 3 3 3 3-2 3-3"/>
    </svg>
  `;
  fab.title = 'KRT Helper - Click for options';
  fab.addEventListener('click', showMainMenu);
  
  document.body.appendChild(fab);
  
  // Create suggestion popup container
  const popupContainer = document.createElement('div');
  popupContainer.id = 'krt-helper-popup-container';
  document.body.appendChild(popupContainer);
}

function startTextMonitoring(platform) {
  if (!userPreferences.enableAutoSuggestions) return;
  
  // Set up text monitoring based on platform
  const config = PLATFORM_CONFIGS[platform] || PLATFORM_CONFIGS.generic;
  
  // Watch for text changes in relevant elements
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList' || mutation.type === 'characterData') {
        debounceTextChange();
      }
    });
  });
  
  config.textSelectors.forEach(selector => {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
      observer.observe(element, {
        childList: true,
        subtree: true,
        characterData: true
      });
    });
  });
}

function debounceTextChange() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    handleTextChange();
  }, 500); // Wait 500ms after user stops typing
}

async function handleTextChange() {
  if (!userPreferences.enableAutoSuggestions) return;
  
  try {
    // Get current text content
    const textContent = getCurrentTextContent();
    if (!textContent) return;
    
    // Extract resource mentions
    const response = await sendMessageToBackground('getResourceInfo', { text: textContent });
    
    if (response.success && response.data.resources.length > 0) {
      updateResourceHighlights(response.data.resources, textContent);
    }
    
  } catch (error) {
    console.error('KRT Helper: Text analysis error:', error);
  }
}

function getCurrentTextContent() {
  // Try different methods to get text content based on platform
  let textContent = '';
  
  // Try CodeMirror (Overleaf)
  const cmEditor = document.querySelector('.cm-editor .cm-content');
  if (cmEditor) {
    textContent = cmEditor.textContent;
  }
  
  // Try Ace Editor (Overleaf legacy)
  if (!textContent) {
    const aceEditor = document.querySelector('.ace_editor .ace_content');
    if (aceEditor) {
      textContent = aceEditor.textContent;
    }
  }
  
  // Try Google Docs
  if (!textContent) {
    const docsContent = document.querySelector('.kix-document-content');
    if (docsContent) {
      textContent = docsContent.textContent;
    }
  }
  
  // Try generic contenteditable
  if (!textContent) {
    const editableElement = document.querySelector('[contenteditable="true"]');
    if (editableElement) {
      textContent = editableElement.textContent;
    }
  }
  
  // Try textarea
  if (!textContent) {
    const textarea = document.querySelector('textarea');
    if (textarea) {
      textContent = textarea.value;
    }
  }
  
  return textContent;
}

function updateResourceHighlights(resources, fullText) {
  // Clear existing highlights
  clearResourceHighlights();
  
  if (userPreferences.highlightLevel === 'none') return;
  
  resources.forEach(resource => {
    if (resource.type === 'rrid') {
      highlightRRID(resource, fullText);
    } else if (resource.type === 'catalog') {
      highlightCatalogNumber(resource, fullText);
    } else if (resource.type === 'antibody') {
      highlightAntibody(resource, fullText);
    }
  });
}

function highlightRRID(resource, fullText) {
  if (userPreferences.enableRRIDValidation) {
    // Validate RRID and highlight accordingly
    sendMessageToBackground('validateRRID', { rrid: resource.value })
      .then(response => {
        if (response.success) {
          const isValid = response.data.is_valid;
          const status = response.data.status;
          
          addHighlight(resource, isValid ? 'valid-rrid' : 'invalid-rrid', {
            tooltip: `RRID: ${status}`,
            clickAction: () => showRRIDDetails(resource, response.data)
          });
        }
      })
      .catch(error => {
        console.error('RRID validation error:', error);
      });
  }
}

function highlightCatalogNumber(resource, fullText) {
  addHighlight(resource, 'catalog-number', {
    tooltip: 'Catalog number detected - click for RRID suggestions',
    clickAction: () => suggestRRIDForCatalog(resource)
  });
}

function highlightAntibody(resource, fullText) {
  addHighlight(resource, 'antibody-mention', {
    tooltip: 'Antibody detected - click for RRID suggestions',
    clickAction: () => suggestRRIDForAntibody(resource)
  });
}

function addHighlight(resource, className, options = {}) {
  // This is a simplified implementation
  // In a real implementation, you'd need to find the exact DOM elements
  // and add highlights without breaking the editor functionality
  
  const highlightId = `krt-highlight-${Date.now()}-${Math.random()}`;
  
  resourceHighlights.set(highlightId, {
    resource: resource,
    className: className,
    options: options
  });
  
  // For now, just store the highlight data
  // Real implementation would manipulate DOM elements carefully
}

function clearResourceHighlights() {
  resourceHighlights.forEach((highlight, id) => {
    // Remove highlight from DOM
    const element = document.getElementById(id);
    if (element) {
      element.remove();
    }
  });
  resourceHighlights.clear();
}

async function handleTextSelection() {
  const selection = window.getSelection();
  if (!selection.toString().trim()) return;
  
  const selectedText = selection.toString().trim();
  
  // Check if selection looks like a resource mention
  if (looksLikeResourceMention(selectedText)) {
    showQuickActionMenu(selectedText, selection);
  }
}

function looksLikeResourceMention(text) {
  // Simple heuristics for resource mentions
  const patterns = [
    /RRID:/i,
    /cat(?:alog)?\s*#/i,
    /anti-?\w+/i,
    /antibody/i,
    /version\s+\d+/i
  ];
  
  return patterns.some(pattern => pattern.test(text));
}

function showQuickActionMenu(selectedText, selection) {
  closeCurrentPopup();
  
  const popup = document.createElement('div');
  popup.className = 'krt-helper-quick-menu';
  popup.innerHTML = `
    <div class="krt-helper-menu-item" data-action="suggest-rrid">
      Suggest RRID
    </div>
    <div class="krt-helper-menu-item" data-action="validate-rrid">
      Validate RRID
    </div>
    <div class="krt-helper-menu-item" data-action="add-to-krt">
      Add to KRT
    </div>
  `;
  
  // Position popup near selection
  const rect = selection.getRangeAt(0).getBoundingClientRect();
  popup.style.position = 'fixed';
  popup.style.left = `${rect.left}px`;
  popup.style.top = `${rect.bottom + 5}px`;
  popup.style.zIndex = '10000';
  
  // Add event listeners
  popup.addEventListener('click', (e) => {
    const action = e.target.dataset.action;
    if (action) {
      handleQuickAction(action, selectedText);
      closeCurrentPopup();
    }
  });
  
  document.getElementById('krt-helper-popup-container').appendChild(popup);
  currentSuggestionPopup = popup;
}

async function handleQuickAction(action, text) {
  switch (action) {
    case 'suggest-rrid':
      await showRRIDSuggestions(text);
      break;
    case 'validate-rrid':
      await validateSelectedRRID(text);
      break;
    case 'add-to-krt':
      await addToKRTTable(text);
      break;
  }
}

async function showRRIDSuggestions(resourceText) {
  closeCurrentPopup();
  
  // Extract resource information
  const resourceInfo = parseResourceText(resourceText);
  
  try {
    const response = await sendMessageToBackground('suggestRRID', resourceInfo);
    
    if (response.success && response.data.suggestions.length > 0) {
      displaySuggestionPopup(response.data.suggestions, resourceText);
    } else {
      showNoSuggestionsMessage(resourceText);
    }
    
  } catch (error) {
    console.error('RRID suggestion error:', error);
    showErrorMessage('Failed to get RRID suggestions');
  }
}

function parseResourceText(text) {
  // Simple parsing logic
  const resourceInfo = {
    resourceName: text,
    resourceType: '',
    vendor: '',
    catalogNumber: ''
  };
  
  // Extract catalog number
  const catalogMatch = text.match(/cat(?:alog)?\s*#?\s*([A-Z0-9\-_]+)/i);
  if (catalogMatch) {
    resourceInfo.catalogNumber = catalogMatch[1];
  }
  
  // Determine resource type
  if (/antibody|anti-/i.test(text)) {
    resourceInfo.resourceType = 'antibody';
  } else if (/software|tool|package/i.test(text)) {
    resourceInfo.resourceType = 'software';
  }
  
  // Extract vendor (basic patterns)
  const vendorPatterns = {
    'Abcam': /abcam/i,
    'Sigma-Aldrich': /sigma|aldrich/i,
    'Invitrogen': /invitrogen|thermo\s*fisher/i
  };
  
  for (const [vendor, pattern] of Object.entries(vendorPatterns)) {
    if (pattern.test(text)) {
      resourceInfo.vendor = vendor;
      break;
    }
  }
  
  return resourceInfo;
}

function displaySuggestionPopup(suggestions, originalText) {
  const popup = document.createElement('div');
  popup.className = 'krt-helper-suggestion-popup';
  
  const header = document.createElement('div');
  header.className = 'krt-helper-popup-header';
  header.innerHTML = `
    <h3>RRID Suggestions for: "${originalText}"</h3>
    <button class="krt-helper-close-btn">&times;</button>
  `;
  
  const content = document.createElement('div');
  content.className = 'krt-helper-popup-content';
  
  suggestions.forEach(suggestion => {
    const item = document.createElement('div');
    item.className = 'krt-helper-suggestion-item';
    item.innerHTML = `
      <div class="suggestion-rrid">${suggestion.rrid}</div>
      <div class="suggestion-name">${suggestion.resource_name}</div>
      <div class="suggestion-meta">
        ${suggestion.vendor ? `Vendor: ${suggestion.vendor}` : ''}
        ${userPreferences.showConfidenceScores ? 
          `<span class="confidence">Confidence: ${(suggestion.confidence * 100).toFixed(0)}%</span>` : ''}
      </div>
      <div class="suggestion-actions">
        <button class="krt-helper-btn-primary" data-action="insert" data-rrid="${suggestion.rrid}">
          Insert RRID
        </button>
        <button class="krt-helper-btn-secondary" data-action="copy" data-rrid="${suggestion.rrid}">
          Copy
        </button>
      </div>
    `;
    content.appendChild(item);
  });
  
  popup.appendChild(header);
  popup.appendChild(content);
  
  // Add event listeners
  popup.addEventListener('click', handleSuggestionPopupClick);
  
  // Position and show popup
  positionPopup(popup);
  document.getElementById('krt-helper-popup-container').appendChild(popup);
  currentSuggestionPopup = popup;
}

function handleSuggestionPopupClick(e) {
  const action = e.target.dataset.action;
  const rrid = e.target.dataset.rrid;
  
  if (action === 'insert' && rrid) {
    insertRRIDIntoDocument(rrid);
    closeCurrentPopup();
  } else if (action === 'copy' && rrid) {
    copyToClipboard(rrid);
    showTemporaryMessage('RRID copied to clipboard');
  } else if (e.target.classList.contains('krt-helper-close-btn')) {
    closeCurrentPopup();
  }
}

function insertRRIDIntoDocument(rrid) {
  // Insert RRID at current cursor position
  // Implementation depends on the platform
  
  const platform = detectPlatform();
  
  if (platform === 'overleaf') {
    insertInOverleaf(`RRID:${rrid}`);
  } else if (platform === 'googledocs') {
    insertInGoogleDocs(`RRID:${rrid}`);
  } else {
    insertInGenericEditor(`RRID:${rrid}`);
  }
}

function insertInOverleaf(text) {
  // For Overleaf, we need to use their API or simulate typing
  // This is a simplified implementation
  const editor = document.querySelector('.cm-editor, .ace_editor');
  if (editor) {
    // Simulate typing the RRID
    simulateTyping(editor, text);
  }
}

function insertInGoogleDocs(text) {
  // Google Docs insertion is complex due to their custom editor
  // This would require using their API or simulating user actions
  copyToClipboard(text);
  showTemporaryMessage('RRID copied to clipboard - paste it manually');
}

function insertInGenericEditor(text) {
  const activeElement = document.activeElement;
  
  if (activeElement && (activeElement.tagName === 'TEXTAREA' || activeElement.contentEditable === 'true')) {
    if (activeElement.tagName === 'TEXTAREA') {
      const cursorPos = activeElement.selectionStart;
      const textBefore = activeElement.value.substring(0, cursorPos);
      const textAfter = activeElement.value.substring(activeElement.selectionEnd);
      activeElement.value = textBefore + text + textAfter;
      activeElement.selectionStart = activeElement.selectionEnd = cursorPos + text.length;
    } else {
      // ContentEditable
      const selection = window.getSelection();
      if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        range.deleteContents();
        range.insertNode(document.createTextNode(text));
        range.collapse(false);
      }
    }
  }
}

function simulateTyping(element, text) {
  // Simulate typing by dispatching keyboard events
  text.split('').forEach((char, index) => {
    setTimeout(() => {
      const event = new KeyboardEvent('keydown', {
        key: char,
        code: `Key${char.toUpperCase()}`,
        keyCode: char.charCodeAt(0),
        bubbles: true
      });
      element.dispatchEvent(event);
      
      const inputEvent = new InputEvent('input', {
        data: char,
        bubbles: true
      });
      element.dispatchEvent(inputEvent);
    }, index * 10);
  });
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).catch(err => {
    console.error('Failed to copy to clipboard:', err);
    // Fallback method
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  });
}

function showTemporaryMessage(message, duration = 3000) {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'krt-helper-temp-message';
  messageDiv.textContent = message;
  messageDiv.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #4CAF50;
    color: white;
    padding: 10px 20px;
    border-radius: 4px;
    z-index: 10001;
    font-size: 14px;
  `;
  
  document.body.appendChild(messageDiv);
  
  setTimeout(() => {
    if (messageDiv.parentNode) {
      messageDiv.parentNode.removeChild(messageDiv);
    }
  }, duration);
}

function positionPopup(popup) {
  popup.style.position = 'fixed';
  popup.style.top = '50%';
  popup.style.left = '50%';
  popup.style.transform = 'translate(-50%, -50%)';
  popup.style.zIndex = '10000';
  popup.style.maxWidth = '600px';
  popup.style.maxHeight = '500px';
}

function closeCurrentPopup() {
  if (currentSuggestionPopup) {
    currentSuggestionPopup.remove();
    currentSuggestionPopup = null;
  }
}

function handleDocumentClick(e) {
  if (currentSuggestionPopup && !currentSuggestionPopup.contains(e.target)) {
    closeCurrentPopup();
  }
}

function handleKeyboardShortcuts(e) {
  // Ctrl+Shift+K: Toggle KRT Helper
  if (e.ctrlKey && e.shiftKey && e.key === 'K') {
    e.preventDefault();
    toggleExtension();
  }
  
  // Escape: Close popups
  if (e.key === 'Escape') {
    closeCurrentPopup();
  }
}

function toggleExtension() {
  isExtensionActive = !isExtensionActive;
  
  const fab = document.getElementById('krt-helper-fab');
  if (fab) {
    fab.style.opacity = isExtensionActive ? '1' : '0.5';
  }
  
  if (!isExtensionActive) {
    clearResourceHighlights();
    closeCurrentPopup();
  }
  
  showTemporaryMessage(`KRT Helper ${isExtensionActive ? 'enabled' : 'disabled'}`);
}

function showMainMenu() {
  closeCurrentPopup();
  
  const menu = document.createElement('div');
  menu.className = 'krt-helper-main-menu';
  menu.innerHTML = `
    <div class="krt-helper-menu-header">
      <h3>KRT Helper</h3>
      <button class="krt-helper-close-btn">&times;</button>
    </div>
    <div class="krt-helper-menu-content">
      <div class="krt-helper-menu-item" data-action="scan-document">
        🔍 Scan Document for Resources
      </div>
      <div class="krt-helper-menu-item" data-action="toggle-highlights">
        💡 Toggle Highlights
      </div>
      <div class="krt-helper-menu-item" data-action="export-krt">
        📋 Export Current KRT
      </div>
      <div class="krt-helper-menu-item" data-action="settings">
        ⚙️ Settings
      </div>
      <div class="krt-helper-menu-item" data-action="help">
        ❓ Help
      </div>
    </div>
  `;
  
  menu.addEventListener('click', handleMainMenuClick);
  positionPopup(menu);
  document.getElementById('krt-helper-popup-container').appendChild(menu);
  currentSuggestionPopup = menu;
}

function handleMainMenuClick(e) {
  const action = e.target.dataset.action;
  
  switch (action) {
    case 'scan-document':
      scanDocumentForResources();
      break;
    case 'toggle-highlights':
      toggleHighlights();
      break;
    case 'export-krt':
      exportCurrentKRT();
      break;
    case 'settings':
      showSettings();
      break;
    case 'help':
      showHelp();
      break;
  }
  
  if (e.target.classList.contains('krt-helper-close-btn')) {
    closeCurrentPopup();
  }
}

async function scanDocumentForResources() {
  closeCurrentPopup();
  
  const textContent = getCurrentTextContent();
  if (!textContent) {
    showTemporaryMessage('No text content found');
    return;
  }
  
  try {
    const response = await sendMessageToBackground('getResourceInfo', { text: textContent });
    
    if (response.success) {
      showResourceScanResults(response.data.resources);
    } else {
      showTemporaryMessage('Failed to scan document');
    }
  } catch (error) {
    console.error('Document scan error:', error);
    showTemporaryMessage('Error scanning document');
  }
}

function showResourceScanResults(resources) {
  const popup = document.createElement('div');
  popup.className = 'krt-helper-scan-results';
  popup.innerHTML = `
    <div class="krt-helper-popup-header">
      <h3>Detected Resources (${resources.length})</h3>
      <button class="krt-helper-close-btn">&times;</button>
    </div>
    <div class="krt-helper-popup-content">
      ${resources.map(resource => `
        <div class="resource-item">
          <span class="resource-type">${resource.type}</span>
          <span class="resource-value">${resource.value}</span>
          <button class="krt-helper-btn-small" data-action="suggest" data-resource="${encodeURIComponent(JSON.stringify(resource))}">
            Get RRID
          </button>
        </div>
      `).join('')}
    </div>
  `;
  
  popup.addEventListener('click', (e) => {
    if (e.target.dataset.action === 'suggest') {
      const resource = JSON.parse(decodeURIComponent(e.target.dataset.resource));
      showRRIDSuggestions(resource.value);
    } else if (e.target.classList.contains('krt-helper-close-btn')) {
      closeCurrentPopup();
    }
  });
  
  positionPopup(popup);
  document.getElementById('krt-helper-popup-container').appendChild(popup);
  currentSuggestionPopup = popup;
}

function sendMessageToBackground(action, data = {}) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ action, data }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        resolve(response);
      }
    });
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
  initializeExtension();
}

console.log('KRT Helper content script loaded');
