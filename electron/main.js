/**
 * main.js — Jarvis Electron shell
 *
 * Multi-display layout:
 *   Display 0 (primary)  → Screen 1: JARVIS HUD        (http://localhost:8765/)
 *   Display 1            → Screen 2: Media Dashboard    (http://localhost:8765/screen2)
 *   Display 2            → Screen 3: Home Dashboard     (http://localhost:8765/screen3)
 *
 * Single-monitor fallback: only Screen 1 is opened.
 *
 * The focus server (port 8766) lets Python bring the window to front
 * on every wake word by calling http://127.0.0.1:8766/focus.
 */

const { app, BrowserWindow, Tray, Menu, nativeImage, screen } = require('electron');
const path = require('path');
const http = require('http');

const SCREENS = [
  { url: 'http://localhost:8765/',        label: 'JARVIS HUD'        },
  { url: 'http://localhost:8765/screen2', label: 'Media Dashboard'   },
  { url: 'http://localhost:8765/screen3', label: 'Home Dashboard'    },
];

let windows = [];   // one BrowserWindow per display
let tray    = null;
let mainWindow = null;  // alias for windows[0] — used by focus server

// ── Single-instance lock ───────────────────────────────────────────────────────
// If a second instance is launched, focus the existing window instead.
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


// ── Window factory ────────────────────────────────────────────────────────────

function createWindow(displayBounds, url, label) {
  const win = new BrowserWindow({
    x:               displayBounds.x,
    y:               displayBounds.y,
    width:           displayBounds.width,
    height:          displayBounds.height,
    fullscreen:      true,
    backgroundColor: '#030d12',
    icon:            path.join(__dirname, 'icon.png'),
    title:           `J.A.R.V.I.S. — ${label}`,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  });

  win.loadURL(url);

  win.once('ready-to-show', () => {
    win.show();
    win.focus();
  });

  // Retry if Jarvis server isn't up yet
  win.webContents.on('did-fail-load', () => {
    setTimeout(() => win && win.loadURL(url), 2000);
  });

  // Hide to tray instead of quitting
  win.on('close', (e) => {
    if (!app.isQuiting) {
      e.preventDefault();
      win.hide();
    }
  });

  return win;
}


// ── App startup ───────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  const displays = screen.getAllDisplays();
  console.log(`[Jarvis] Detected ${displays.length} display(s).`);

  // Open one screen per display, up to 3
  const count = Math.min(displays.length, SCREENS.length);
  for (let i = 0; i < count; i++) {
    const win = createWindow(displays[i].bounds, SCREENS[i].url, SCREENS[i].label);
    windows.push(win);
    console.log(`[Jarvis] Screen ${i + 1} → ${displays[i].bounds.width}x${displays[i].bounds.height} @ (${displays[i].bounds.x},${displays[i].bounds.y}) — ${SCREENS[i].label}`);
  }

  mainWindow = windows[0];
  createTray();
});


// ── Tray ──────────────────────────────────────────────────────────────────────

function createTray() {
  const img = nativeImage.createEmpty();
  tray = new Tray(img);
  tray.setToolTip('J.A.R.V.I.S.');

  const menuItems = windows.map((win, i) => ({
    label: `Show ${SCREENS[i].label}`,
    click: () => { win.show(); win.focus(); },
  }));

  const menu = Menu.buildFromTemplate([
    ...menuItems,
    { type: 'separator' },
    { label: 'Quit', click: () => { app.isQuiting = true; app.quit(); } },
  ]);

  tray.setContextMenu(menu);
  tray.on('double-click', () => {
    windows.forEach(w => { w.show(); w.focus(); });
  });
}


app.on('window-all-closed', (e) => {
  e.preventDefault(); // keep running in tray
});


// ── Focus server (port 8766) ───────────────────────────────────────────────────
// Python calls GET /focus on every wake word to bring the HUD window forward.

const focusServer = http.createServer((req, res) => {
  res.writeHead(200);
  res.end('ok');
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

focusServer.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    // Another Electron instance already holds 8766 — single-instance lock handles this
    console.log('[Jarvis] Focus server port 8766 already in use — skipping.');
  } else {
    console.error('[Jarvis] Focus server error:', err);
  }
});

focusServer.listen(8766, '127.0.0.1');
