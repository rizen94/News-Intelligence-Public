# Development Setup Guide

## Problem: Browser Caching & Hot Module Replacement Issues

### Root Causes Identified:
1. **Browser aggressively caching bundle.js** - Returns 304 Not Modified
2. **HMR not working reliably** - Changes require hard refresh
3. **File watching using polling** - Slower and less reliable than native watching
4. **No cache-busting in development** - Same filenames = browser caches

## Solutions Implemented

### 1. Environment Configuration (`.env.development`)
- Disables caching headers
- Enables Fast Refresh
- Configures file watching
- Prevents service worker registration

### 2. Optimized Development Server Script
Use `scripts/dev-server-optimized.sh` instead of `npm start`:
```bash
cd web
./scripts/dev-server-optimized.sh
```

This script:
- Clears build cache before starting
- Sets optimal environment variables
- Ensures HMR is enabled
- Provides helpful tips

### 3. HTML Meta Tags (Development Only)
Added cache-control headers to `public/index.html` that prevent caching in development mode.

### 4. Optional: CRACO Configuration
For advanced webpack customization without ejecting, install CRACO:
```bash
npm install --save-dev @craco/craco
```

Then update `package.json` scripts:
```json
"start": "craco start",
"build": "craco build",
```

## Quick Fixes

### If HMR Still Doesn't Work:

1. **Check Browser Console:**
   - Look for `[HMR]` messages
   - Check for webpack errors
   - Verify WebSocket connection (`ws://localhost:3000/ws`)

2. **Check Network Tab:**
   - Look for `webpackHotUpdate` requests
   - Verify files are being requested (not 304)

3. **Browser DevTools Settings:**
   - Chrome: DevTools → Network → Disable cache (while DevTools open)
   - Firefox: DevTools → Network → Settings → Disable HTTP Cache

4. **Clear Browser Cache:**
   ```bash
   # Chrome/Edge
   chrome://settings/clearBrowserData
   
   # Firefox
   about:preferences#privacy → Clear Data
   ```

## Long-Term Solutions

### Option 1: Upgrade to React 18+ (Recommended)
React 18 has better HMR support:
```bash
npm install react@^18 react-dom@^18
```

### Option 2: Use Vite Instead of CRA
Vite has superior HMR and faster builds:
```bash
npm create vite@latest . -- --template react-ts
```

### Option 3: Eject and Customize Webpack
If you need full control:
```bash
npm run eject
# Then customize webpack.config.js directly
```

## Current Status

✅ Environment variables configured
✅ Development server script created
✅ HTML cache headers added
✅ Documentation created

⚠️ **Still need to:**
- Test HMR after restart
- Consider upgrading React or switching to Vite
- Monitor file watching performance

## Monitoring HMR

Watch for these in browser console:
- `[HMR] connected` - WebSocket connected
- `[HMR] bundle rebuilding` - File changed
- `[HMR] bundle rebuilt` - Ready to update
- `[HMR] Updated modules` - Changes applied

If you see `[HMR] Cannot apply update` - HMR failed, full reload needed.

