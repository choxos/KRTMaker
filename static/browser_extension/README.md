# KRT Maker Browser Extension

Real-time RRID suggestions and KRT assistance while writing manuscripts.

## 🚀 Features

- **Real-time RRID suggestions** as you type resource names
- **Cross-database validation** to ensure RRID accuracy
- **One-click insertion** of validated RRIDs
- **Support for major platforms**: Overleaf, Google Docs, Notion, Editorial Manager
- **Context-aware detection** of research resources

## 📦 Installation

### Chrome/Edge
1. Download or clone this repository
2. Open `chrome://extensions/` in your browser
3. Enable "Developer mode" (toggle in top-right)
4. Click "Load unpacked" and select this folder
5. The extension will appear in your browser toolbar

### Firefox
1. Download or clone this repository  
2. Open `about:debugging` in Firefox
3. Click "This Firefox"
4. Click "Load Temporary Add-on"
5. Select the `manifest.json` file

## 🎯 How It Works

The extension integrates with the KRT Maker API to provide:

1. **Resource Detection**: Automatically identifies research resources as you type
2. **RRID Suggestions**: Queries the KRT Maker database for appropriate RRIDs
3. **Validation**: Cross-references suggestions with multiple scientific databases
4. **Insertion**: Provides one-click insertion of validated RRIDs

## 🔧 Development

This extension is built using:
- **Manifest V3** for modern browser compatibility
- **Content Scripts** for page interaction
- **Background Service Worker** for API communication
- **Popup Interface** for user controls

### API Endpoints Used

- `POST /api/browser/suggest-rrid/` - Get RRID suggestions
- `POST /api/browser/validate-rrid/` - Validate existing RRIDs

### Supported Platforms

✅ **Overleaf** - LaTeX manuscript writing  
✅ **Google Docs** - Document editing  
✅ **Notion** - Note-taking and writing  
✅ **Editorial Manager** - Journal submission system  
✅ **PubMed Central** - Manuscript preparation  

## 📝 Usage

1. **Install the extension** using the instructions above
2. **Navigate to a supported platform** (Overleaf, Google Docs, etc.)
3. **Start typing resource names** like "anti-beta-tubulin antibody"
4. **Click the KRT Assistant icon** when it appears
5. **Select an RRID suggestion** to insert it automatically

## 🛠️ Configuration

Click the extension icon in your browser toolbar to:
- Enable/disable the assistant
- Configure which platforms to monitor
- View recent suggestions
- Access help and documentation

## 🔒 Privacy

This extension:
- Only activates on manuscript writing platforms
- Sends resource names to the KRT Maker API for suggestions
- Does not store or transmit document content
- Operates with minimal permissions

## 🐛 Troubleshooting

**Extension not working?**
- Ensure you're on a supported platform
- Check that the extension is enabled
- Verify the KRT Maker API is accessible
- Try refreshing the page

**No suggestions appearing?**
- Check your internet connection
- Ensure resource names are recognized patterns
- Try typing more specific resource names
- Check the extension popup for error messages

## 🤝 Contributing

This is part of the open-source KRT Maker project. To contribute:

1. Visit the [GitHub repository](https://github.com/choxos/KRTMaker)
2. Fork the project
3. Create a feature branch
4. Submit a pull request

## 📄 License

Part of the KRT Maker project - enhancing reproducibility in biomedical research.

---

**Need help?** Visit the [KRT Maker documentation](http://localhost:8001/api-docs/) or try the [web interface](http://localhost:8001/ai/).