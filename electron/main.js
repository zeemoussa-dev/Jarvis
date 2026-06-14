const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const path = require('path');

const UI_URL = 'http://localhost:8765';
const WINDOW_WIDTH = 1400;
const WINDOW_HEIGHT = 860;

let mainWindow = null;
let tray = null;

// Single-instance lock — second launch focuses existing window instead of opening new one
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#030d12',
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#030d12',
      symbolColor: '#00d4ff',
      height: 32,
    },
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false, // show after ready-to-show to avoid flash
  });

  mainWindow.loadURL(UI_URL);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  // Retry connection if Jarvis server isn't up yet
  mainWindow.webContents.on('did-fail-load', () => {
    setTimeout(() => mainWindow && mainWindow.loadURL(UI_URL), 2000);
  });

  // Hide to tray instead of closing
  mainWindow.on('close', (e) => {
    if (!app.isQuiting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  // Use a blank image if no icon file — tray still works
  const img = nativeImage.createEmpty();
  tray = new Tray(img);
  tray.setToolTip('J.A.R.V.I.S.');

  const menu = Menu.buildFromTemplate([
    {
      label: 'Show JARVIS',
      click: () => {
        mainWindow.show();
        mainWindow.focus();
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuiting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(menu);
  tray.on('double-click', () => {
    mainWindow.show();
    mainWindow.focus();
  });
}

app.whenReady().then(() => {
  createWindow();
  createTray();
});

app.on('window-all-closed', (e) => {
  // Prevent quit — app lives in tray
  e.preventDefault();
});

// Focus endpoint — Python calls http://localhost:8766/focus to bring window forward
const http = require('http');
http.createServer((req, res) => {
  res.writeHead(200);
  res.end('ok');
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
}).listen(8766, '127.0.0.1');
