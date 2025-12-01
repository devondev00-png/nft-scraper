const { app, BrowserWindow, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let mainWindow = null;
let pythonProcess = null;
const PORT = 8080;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../static/anonscraper.png'),
    titleBarStyle: 'default',
    show: false
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Load the local server
  mainWindow.loadURL(`http://localhost:${PORT}`);

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startPythonServer() {
  const isDev = process.argv.includes('--dev');
  
  // In production, we'll need to bundle Python or use system Python
  // For now, use system Python and assume it's in PATH
  const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
  const serverPath = path.join(__dirname, '../web_server.py');
  
  // Check if server file exists
  if (!fs.existsSync(serverPath)) {
    console.error('web_server.py not found. Please ensure the file exists.');
    app.quit();
    return;
  }

  // Set environment variables
  const env = {
    ...process.env,
    PYTHONUNBUFFERED: '1'
  };

  // Load .env file if it exists
  const envPath = path.join(__dirname, '../.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    envContent.split('\n').forEach(line => {
      const [key, ...values] = line.split('=');
      if (key && values.length > 0) {
        env[key.trim()] = values.join('=').trim();
      }
    });
  }

  console.log('Starting Python server...');
  pythonProcess = spawn(pythonPath, [serverPath], {
    env: env,
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit'
  });

  pythonProcess.on('error', (error) => {
    console.error('Failed to start Python server:', error);
    app.quit();
  });

  pythonProcess.on('exit', (code) => {
    console.log(`Python server exited with code ${code}`);
    if (code !== 0 && code !== null) {
      app.quit();
    }
  });
}

function waitForServer(maxAttempts = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const checkServer = () => {
      const http = require('http');
      const req = http.get(`http://localhost:${PORT}`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          attempts++;
          if (attempts < maxAttempts) {
            setTimeout(checkServer, 1000);
          } else {
            reject(new Error('Server did not start in time'));
          }
        }
      });
      req.on('error', () => {
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(checkServer, 1000);
        } else {
          reject(new Error('Server did not start in time'));
        }
      });
    };
    checkServer();
  });
}

app.whenReady().then(async () => {
  startPythonServer();
  
  try {
    await waitForServer();
    createWindow();
  } catch (error) {
    console.error('Failed to start server:', error);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
});

