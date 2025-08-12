/**
 * Popup Script for KRT Helper Browser Extension
 */

// DOM elements
let statusIndicator, statusText, currentPage, resourceCount;
let toggleExtensionBtn, scanPageBtn, toggleText;
let autoSuggestionsToggle, rridValidationToggle, showConfidenceToggle, highlightToggle;

// Initialize popup
document.addEventListener('DOMContentLoaded', async () => {
  initializeElements();
  await loadCurrentStatus();
  await loadPreferences();
  setupEventListeners();
});

function initializeElements() {
  statusIndicator = document.getElementById('statusIndicator');
  statusText = document.getElementById('statusText');
  currentPage = document.getElementById('currentPage');
  resourceCount = document.getElementById('resourceCount');
  toggleExtensionBtn = document.getElementById('toggleExtensionBtn');
  scanPageBtn = document.getElementById('scanPageBtn');
  toggleText = document.getElementById('toggleText');
  
  autoSuggestionsToggle = document.getElementById('autoSuggestionsToggle');
  rridValidationToggle = document.getElementById('rridValidationToggle');
  showConfidenceToggle = document.getElementById('showConfidenceToggle');
  highlightToggle = document.getElementById('highlightToggle');
}

async function loadCurrentStatus() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // Update current page
    const hostname = new URL(tab.url).hostname;
    currentPage.textContent = hostname;
    
    // Check if extension is active on this page
    const isActive = await checkExtensionStatus(tab.id);
    updateStatusDisplay(isActive);
    
  } catch (error) {
    console.error('Failed to load status:', error);
    updateStatusDisplay(false);
  }
}

async function checkExtensionStatus(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { action: 'getStatus' });
    return response?.active || false;
  } catch {
    return false;
  }
}

function updateStatusDisplay(isActive) {
  if (isActive) {
    statusIndicator.className = 'status-indicator status-active';
    statusText.textContent = 'Active';
    toggleText.textContent = 'Disable';
  } else {
    statusIndicator.className = 'status-indicator status-inactive';
    statusText.textContent = 'Inactive';
    toggleText.textContent = 'Enable';
  }
}

async function loadPreferences() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getUserPreferences' });
    if (response.success) {
      const prefs = response.data;
      updateToggle(autoSuggestionsToggle, prefs.enableAutoSuggestions);
      updateToggle(rridValidationToggle, prefs.enableRRIDValidation);
      updateToggle(showConfidenceToggle, prefs.showConfidenceScores);
      updateToggle(highlightToggle, prefs.highlightLevel !== 'none');
    }
  } catch (error) {
    console.error('Failed to load preferences:', error);
  }
}

function updateToggle(toggle, isActive) {
  if (isActive) {
    toggle.classList.add('active');
  } else {
    toggle.classList.remove('active');
  }
}

function setupEventListeners() {
  scanPageBtn.addEventListener('click', handleScanPage);
  toggleExtensionBtn.addEventListener('click', handleToggleExtension);
  
  autoSuggestionsToggle.addEventListener('click', () => handleTogglePreference('enableAutoSuggestions', autoSuggestionsToggle));
  rridValidationToggle.addEventListener('click', () => handleTogglePreference('enableRRIDValidation', rridValidationToggle));
  showConfidenceToggle.addEventListener('click', () => handleTogglePreference('showConfidenceScores', showConfidenceToggle));
  highlightToggle.addEventListener('click', () => handleTogglePreference('highlightLevel', highlightToggle));
}

async function handleScanPage() {
  scanPageBtn.textContent = 'Scanning...';
  scanPageBtn.disabled = true;
  
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.tabs.sendMessage(tab.id, { action: 'scanDocument' });
    scanPageBtn.textContent = '✓ Scanned';
  } catch (error) {
    scanPageBtn.textContent = 'Error';
  } finally {
    setTimeout(() => {
      scanPageBtn.textContent = '🔍 Scan Current Page';
      scanPageBtn.disabled = false;
    }, 2000);
  }
}

async function handleToggleExtension() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.tabs.sendMessage(tab.id, { action: 'toggleExtension' });
    
    // Update status after toggle
    setTimeout(() => loadCurrentStatus(), 500);
  } catch (error) {
    console.error('Failed to toggle extension:', error);
  }
}

async function handleTogglePreference(prefKey, toggle) {
  const isActive = !toggle.classList.contains('active');
  updateToggle(toggle, isActive);
  
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getUserPreferences' });
    if (response.success) {
      const prefs = response.data;
      
      if (prefKey === 'highlightLevel') {
        prefs[prefKey] = isActive ? 'medium' : 'none';
      } else {
        prefs[prefKey] = isActive;
      }
      
      await chrome.runtime.sendMessage({ action: 'setUserPreferences', data: prefs });
    }
  } catch (error) {
    console.error('Failed to update preference:', error);
    // Revert toggle state
    updateToggle(toggle, !isActive);
  }
}

// Add help and about handlers
document.getElementById('helpLink').addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://github.com/your-repo/krt-maker#browser-extension' });
});

document.getElementById('aboutLink').addEventListener('click', () => {
  chrome.tabs.create({ url: 'https://github.com/your-repo/krt-maker' });
});
