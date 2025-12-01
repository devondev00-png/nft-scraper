// Preload script for Electron
// This runs in a context that has access to both DOM and Node.js APIs
// but with limited access for security

const { contextBridge } = require('electron');

// Expose protected methods that allow the renderer process to use
// the Node.js APIs in a safe way
contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron
  }
});



