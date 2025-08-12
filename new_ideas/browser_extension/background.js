/**
 * Browser Extension Background Service Worker for KRT Helper
 * 
 * Handles API communication, caching, and cross-tab coordination
 * for real-time RRID suggestions and resource validation.
 */

// API Configuration
const API_CONFIG = {
  KRT_MAKER_API: 'http://localhost:8000',  // Local development
  SCICRUNCH_API: 'https://scicrunch.org/api/1',
  ANTIBODY_REGISTRY_API: 'https://antibodyregistry.org/api',
  CACHE_DURATION: 24 * 60 * 60 * 1000, // 24 hours
  REQUEST_TIMEOUT: 10000, // 10 seconds
};

// Cache for RRID and resource data
let resourceCache = new Map();
let requestQueue = new Map();

// Initialize extension
chrome.runtime.onInstalled.addListener((details) => {
  console.log('KRT Helper extension installed:', details);
  initializeExtension();
});

async function initializeExtension() {
  // Load cached data
  try {
    const data = await chrome.storage.local.get(['resourceCache', 'userPreferences']);
    if (data.resourceCache) {
      resourceCache = new Map(Object.entries(data.resourceCache));
    }
    console.log('KRT Helper initialized with', resourceCache.size, 'cached resources');
  } catch (error) {
    console.error('Failed to initialize cache:', error);
  }
}

// Handle messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'suggestRRID':
      handleRRIDSuggestion(request.data, sendResponse);
      return true; // Indicates async response
      
    case 'validateRRID':
      handleRRIDValidation(request.data, sendResponse);
      return true;
      
    case 'getResourceInfo':
      handleResourceInfo(request.data, sendResponse);
      return true;
      
    case 'cacheResource':
      handleCacheResource(request.data, sendResponse);
      return true;
      
    case 'getUserPreferences':
      handleGetUserPreferences(sendResponse);
      return true;
      
    case 'setUserPreferences':
      handleSetUserPreferences(request.data, sendResponse);
      return true;
      
    default:
      sendResponse({ error: 'Unknown action' });
      return false;
  }
});

async function handleRRIDSuggestion(data, sendResponse) {
  try {
    const { resourceName, resourceType, vendor, catalogNumber } = data;
    
    // Check cache first
    const cacheKey = `suggest_${resourceName}_${resourceType}_${vendor}_${catalogNumber}`;
    const cached = getCachedResult(cacheKey);
    
    if (cached) {
      sendResponse({ success: true, data: cached, source: 'cache' });
      return;
    }
    
    // Avoid duplicate requests
    if (requestQueue.has(cacheKey)) {
      const existingRequest = requestQueue.get(cacheKey);
      existingRequest.then(result => sendResponse(result));
      return;
    }
    
    // Create new request
    const requestPromise = performRRIDSuggestion(resourceName, resourceType, vendor, catalogNumber);
    requestQueue.set(cacheKey, requestPromise);
    
    const result = await requestPromise;
    requestQueue.delete(cacheKey);
    
    // Cache successful results
    if (result.success) {
      setCachedResult(cacheKey, result.data);
    }
    
    sendResponse(result);
    
  } catch (error) {
    console.error('RRID suggestion error:', error);
    sendResponse({ 
      success: false, 
      error: error.message || 'Failed to get RRID suggestions' 
    });
  }
}

async function performRRIDSuggestion(resourceName, resourceType, vendor, catalogNumber) {
  const suggestions = [];
  
  try {
    // Try KRT Maker API first (if available)
    const krtMakerSuggestions = await fetchKRTMakerSuggestions(
      resourceName, resourceType, vendor, catalogNumber
    );
    suggestions.push(...krtMakerSuggestions);
  } catch (error) {
    console.warn('KRT Maker API unavailable:', error.message);
  }
  
  try {
    // Try SciCrunch API
    const sciCrunchSuggestions = await fetchSciCrunchSuggestions(
      resourceName, resourceType
    );
    suggestions.push(...sciCrunchSuggestions);
  } catch (error) {
    console.warn('SciCrunch API error:', error.message);
  }
  
  try {
    // Try Antibody Registry for antibodies
    if (resourceType && resourceType.toLowerCase().includes('antibody')) {
      const antibodySuggestions = await fetchAntibodySuggestions(
        resourceName, vendor, catalogNumber
      );
      suggestions.push(...antibodySuggestions);
    }
  } catch (error) {
    console.warn('Antibody Registry API error:', error.message);
  }
  
  // Remove duplicates and rank suggestions
  const uniqueSuggestions = removeDuplicateSuggestions(suggestions);
  const rankedSuggestions = rankSuggestions(uniqueSuggestions, resourceName);
  
  return {
    success: true,
    data: {
      suggestions: rankedSuggestions.slice(0, 5), // Top 5 suggestions
      total_found: suggestions.length,
      sources_searched: ['krt_maker', 'scicrunch', 'antibody_registry'].filter(
        source => suggestions.some(s => s.source === source)
      )
    }
  };
}

async function fetchKRTMakerSuggestions(resourceName, resourceType, vendor, catalogNumber) {
  const url = `${API_CONFIG.KRT_MAKER_API}/api/suggest-rrid/`;
  const params = new URLSearchParams({
    resource_name: resourceName,
    resource_type: resourceType || '',
    vendor: vendor || '',
    catalog_number: catalogNumber || ''
  });
  
  const response = await fetchWithTimeout(`${url}?${params}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    }
  });
  
  if (!response.ok) {
    throw new Error(`KRT Maker API error: ${response.status}`);
  }
  
  const data = await response.json();
  
  return data.suggestions.map(suggestion => ({
    rrid: suggestion.suggested_rrid,
    resource_name: suggestion.resource_name,
    confidence: suggestion.confidence_score,
    source: 'krt_maker',
    additional_info: suggestion.additional_info || {},
    vendor: suggestion.vendor || vendor,
    catalog_number: suggestion.catalog_number || catalogNumber
  }));
}

async function fetchSciCrunchSuggestions(resourceName, resourceType) {
  const url = `${API_CONFIG.SCICRUNCH_API}/resource-search`;
  const params = new URLSearchParams({
    q: resourceName,
    filter: resourceType || 'all'
  });
  
  const response = await fetchWithTimeout(`${url}?${params}`);
  
  if (!response.ok) {
    throw new Error(`SciCrunch API error: ${response.status}`);
  }
  
  const data = await response.json();
  
  return (data.results || []).map(result => ({
    rrid: result.rrid || '',
    resource_name: result.name || '',
    confidence: calculateSimilarity(resourceName, result.name || ''),
    source: 'scicrunch',
    additional_info: result,
    vendor: result.vendor || '',
    catalog_number: result.catalog || ''
  }));
}

async function fetchAntibodySuggestions(resourceName, vendor, catalogNumber) {
  const url = `${API_CONFIG.ANTIBODY_REGISTRY_API}/search`;
  const params = new URLSearchParams({
    q: resourceName
  });
  
  if (vendor) params.append('vendor', vendor);
  if (catalogNumber) params.append('catalog', catalogNumber);
  
  const response = await fetchWithTimeout(`${url}?${params}`);
  
  if (!response.ok) {
    throw new Error(`Antibody Registry API error: ${response.status}`);
  }
  
  const data = await response.json();
  
  return (data.results || []).map(result => ({
    rrid: result.rrid || '',
    resource_name: result.name || '',
    confidence: calculateSimilarity(resourceName, result.name || ''),
    source: 'antibody_registry',
    additional_info: result,
    vendor: result.vendor || vendor,
    catalog_number: result.catalog || catalogNumber
  }));
}

async function handleRRIDValidation(data, sendResponse) {
  try {
    const { rrid } = data;
    
    // Check cache
    const cacheKey = `validate_${rrid}`;
    const cached = getCachedResult(cacheKey);
    
    if (cached) {
      sendResponse({ success: true, data: cached, source: 'cache' });
      return;
    }
    
    // Validate RRID
    const validation = await validateRRID(rrid);
    
    // Cache result
    if (validation.success) {
      setCachedResult(cacheKey, validation.data);
    }
    
    sendResponse(validation);
    
  } catch (error) {
    console.error('RRID validation error:', error);
    sendResponse({ 
      success: false, 
      error: error.message || 'Failed to validate RRID' 
    });
  }
}

async function validateRRID(rrid) {
  try {
    // Clean RRID format
    const cleanRRID = rrid.replace('RRID:', '').trim();
    
    // Try SciCrunch validation
    const url = `${API_CONFIG.SCICRUNCH_API}/resource/${cleanRRID}`;
    const response = await fetchWithTimeout(url);
    
    if (response.ok) {
      const data = await response.json();
      return {
        success: true,
        data: {
          rrid: rrid,
          is_valid: true,
          status: data.deprecated ? 'deprecated' : 'active',
          resource_info: data,
          last_checked: new Date().toISOString()
        }
      };
    } else if (response.status === 404) {
      return {
        success: true,
        data: {
          rrid: rrid,
          is_valid: false,
          status: 'not_found',
          resource_info: {},
          last_checked: new Date().toISOString()
        }
      };
    } else {
      throw new Error(`Validation failed: ${response.status}`);
    }
    
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}

async function handleResourceInfo(data, sendResponse) {
  try {
    const { text } = data;
    
    // Extract potential resource mentions from text
    const resources = extractResourceMentions(text);
    
    sendResponse({ 
      success: true, 
      data: { 
        resources: resources,
        extracted_count: resources.length 
      } 
    });
    
  } catch (error) {
    console.error('Resource extraction error:', error);
    sendResponse({ 
      success: false, 
      error: error.message 
    });
  }
}

function extractResourceMentions(text) {
  const resources = [];
  
  // RRID pattern
  const rridPattern = /RRID:\s*([A-Z]+_\d+)/gi;
  let match;
  while ((match = rridPattern.exec(text)) !== null) {
    resources.push({
      type: 'rrid',
      value: match[0],
      identifier: match[1],
      position: match.index
    });
  }
  
  // Catalog number pattern
  const catalogPattern = /(?:cat(?:alog)?\s*#?\s*|catalog\s+number\s*:?\s*)([A-Z0-9\-_]+)/gi;
  while ((match = catalogPattern.exec(text)) !== null) {
    resources.push({
      type: 'catalog',
      value: match[0],
      identifier: match[1],
      position: match.index
    });
  }
  
  // Antibody mentions
  const antibodyPattern = /(?:anti-?|antibody\s+against\s+)(\w+)/gi;
  while ((match = antibodyPattern.exec(text)) !== null) {
    resources.push({
      type: 'antibody',
      value: match[0],
      target: match[1],
      position: match.index
    });
  }
  
  return resources;
}

async function handleCacheResource(data, sendResponse) {
  try {
    const { key, value, ttl } = data;
    setCachedResult(key, value, ttl);
    sendResponse({ success: true });
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}

async function handleGetUserPreferences(sendResponse) {
  try {
    const result = await chrome.storage.sync.get(['userPreferences']);
    const preferences = result.userPreferences || getDefaultPreferences();
    sendResponse({ success: true, data: preferences });
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}

async function handleSetUserPreferences(data, sendResponse) {
  try {
    await chrome.storage.sync.set({ userPreferences: data });
    sendResponse({ success: true });
  } catch (error) {
    sendResponse({ success: false, error: error.message });
  }
}

function getDefaultPreferences() {
  return {
    enableAutoSuggestions: true,
    enableRRIDValidation: true,
    showConfidenceScores: true,
    maxSuggestions: 5,
    cacheEnabled: true,
    preferredSources: ['krt_maker', 'scicrunch', 'antibody_registry'],
    highlightLevel: 'medium' // 'low', 'medium', 'high'
  };
}

// Utility functions
function getCachedResult(key) {
  const cached = resourceCache.get(key);
  if (cached && cached.expires > Date.now()) {
    return cached.data;
  }
  if (cached) {
    resourceCache.delete(key);
  }
  return null;
}

function setCachedResult(key, data, ttl = API_CONFIG.CACHE_DURATION) {
  resourceCache.set(key, {
    data: data,
    expires: Date.now() + ttl
  });
  
  // Persist cache to storage (debounced)
  debouncedPersistCache();
}

let persistCacheTimeout;
function debouncedPersistCache() {
  clearTimeout(persistCacheTimeout);
  persistCacheTimeout = setTimeout(() => {
    const cacheObject = Object.fromEntries(resourceCache);
    chrome.storage.local.set({ resourceCache: cacheObject });
  }, 1000);
}

async function fetchWithTimeout(url, options = {}, timeout = API_CONFIG.REQUEST_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);
  
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

function calculateSimilarity(str1, str2) {
  if (!str1 || !str2) return 0;
  
  const longer = str1.length > str2.length ? str1 : str2;
  const shorter = str1.length > str2.length ? str2 : str1;
  
  if (longer.length === 0) return 1.0;
  
  return (longer.length - editDistance(longer, shorter)) / longer.length;
}

function editDistance(str1, str2) {
  const matrix = [];
  
  for (let i = 0; i <= str2.length; i++) {
    matrix[i] = [i];
  }
  
  for (let j = 0; j <= str1.length; j++) {
    matrix[0][j] = j;
  }
  
  for (let i = 1; i <= str2.length; i++) {
    for (let j = 1; j <= str1.length; j++) {
      if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  
  return matrix[str2.length][str1.length];
}

function removeDuplicateSuggestions(suggestions) {
  const seen = new Set();
  return suggestions.filter(suggestion => {
    const key = `${suggestion.rrid}_${suggestion.resource_name}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function rankSuggestions(suggestions, query) {
  return suggestions.sort((a, b) => {
    // Primary sort by confidence
    if (b.confidence !== a.confidence) {
      return b.confidence - a.confidence;
    }
    
    // Secondary sort by source priority
    const sourcePriority = { 'krt_maker': 3, 'scicrunch': 2, 'antibody_registry': 1 };
    const aPriority = sourcePriority[a.source] || 0;
    const bPriority = sourcePriority[b.source] || 0;
    
    return bPriority - aPriority;
  });
}

// Cleanup old cache entries periodically
setInterval(() => {
  const now = Date.now();
  for (const [key, value] of resourceCache.entries()) {
    if (value.expires < now) {
      resourceCache.delete(key);
    }
  }
}, 60000); // Clean every minute

console.log('KRT Helper background service worker loaded');
