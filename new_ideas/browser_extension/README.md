# KRT Helper Browser Extension

Real-time RRID suggestions and resource validation for scientific manuscript writing platforms.

## Features

- **Real-time RRID suggestions** as you type
- **RRID validation** against multiple databases
- **Resource detection** in manuscripts
- **Cross-platform support** (Overleaf, Google Docs, Notion, etc.)
- **Smart recommendations** based on context
- **Confidence scoring** for suggestions

## Installation

1. Clone or download the extension files
2. Open Chrome and go to `chrome://extensions/`
3. Enable "Developer mode" 
4. Click "Load unpacked" and select the extension folder

## Supported Platforms

- Overleaf
- Google Docs
- Notion
- Editorial Manager
- Generic text editors

## Usage

1. Navigate to a supported writing platform
2. Start writing your manuscript
3. The extension will automatically detect resource mentions
4. Click on highlighted resources for RRID suggestions
5. Use Ctrl+Shift+K to toggle the extension

## API Integration

The extension integrates with:
- KRT Maker API (local)
- SciCrunch API
- Antibody Registry API
- Vendor APIs (when available)

## Files

- `manifest.json` - Extension configuration
- `background.js` - Service worker for API calls
- `content.js` - Content script for page interaction  
- `popup.html/js` - Extension popup interface
- `styles.css` - Extension styling

## Development

To modify the extension:
1. Edit the relevant files
2. Reload the extension in Chrome
3. Test on supported platforms

## Privacy

The extension only processes text you're actively writing and doesn't store personal data permanently.
