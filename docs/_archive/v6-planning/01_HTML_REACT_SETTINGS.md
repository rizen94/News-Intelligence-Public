# HTML and React Key Settings — v6 Planning

> **Purpose:** Provide a copy of HTML entry point and React key config for Claude when planning v6.

---

## 1. index.html (Entry Point)

**Path:** `web/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" href="/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#000000" />
    <meta
      name="description"
      content="News Intelligence System - Advanced News Analysis Platform"
    />
    <link rel="apple-touch-icon" href="/logo192.png" />
    <link rel="manifest" href="/manifest.json" />
    <title>News Intelligence System</title>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
    <script type="module" src="/src/index.tsx"></script>
  </body>
</html>
```

---

## 2. package.json (Dependencies & Scripts)

**Path:** `web/package.json`

```json
{
  "name": "news-intelligence-system-web",
  "version": "5.0.0",
  "description": "Web frontend for News Intelligence System v5.0 - Multi-Domain News Analysis Platform",
  "private": true,
  "dependencies": {
    "@emotion/react": "^11.10.5",
    "@emotion/styled": "^11.10.5",
    "@mui/icons-material": "^5.11.16",
    "@mui/lab": "^5.0.0-alpha.170",
    "@mui/material": "^5.11.16",
    "@mui/x-charts": "^6.0.0-alpha.0",
    "@mui/x-data-grid": "^6.0.2",
    "axios": "^1.3.4",
    "d3": "^7.8.5",
    "date-fns": "^2.29.3",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-markdown": "^8.0.7",
    "react-router-dom": "^6.8.1",
    "recharts": "^2.5.0",
    "remark-gfm": "^4.0.1",
    "zustand": "^4.3.8"
  },
  "devDependencies": {
    "@types/d3": "^7.4.0",
    "@types/node": "^20.0.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^5.1.4",
    "@vitejs/plugin-react-swc": "^4.2.3",
    "eslint": "^8.0.0",
    "eslint-config-prettier": "^8.0.0",
    "eslint-plugin-import": "^2.25.0",
    "eslint-plugin-react": "^7.25.0",
    "prettier": "^2.8.0",
    "typescript": "^5.2.0",
    "vite": "^7.3.1"
  },
  "scripts": {
    "dev": "vite",
    "start": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext .js,.jsx,.ts,.tsx",
    "lint:fix": "eslint src --ext .js,.jsx,.ts,.tsx --fix",
    "format": "prettier --write src/**/*.{js,jsx,ts,tsx,json,css,md}",
    "format:check": "prettier --check src/**/*.{js,jsx,ts,tsx,json,css,md}",
    "style:check": "npm run lint && npm run format:check",
    "style:fix": "npm run lint:fix && npm run format"
  },
  "browserslist": {
    "production": [">0.2%", "not dead", "not op_mini all"],
    "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
  },
  "homepage": "/"
}
```

---

## 3. vite.config.mts (Build & Dev Server)

**Path:** `web/vite.config.mts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

export default defineConfig({
  plugins: [react()],

  esbuild: {
    loader: 'tsx',
    include: /src\/.*\.(tsx?|jsx?)$/,
  },

  server: {
    port: 3000,
    host: true,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
    hmr: { overlay: true },
    watch: { usePolling: false, interval: 100 },
  },

  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          mui: ['@mui/material', '@mui/icons-material'],
        },
      },
    },
  },

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@services': path.resolve(__dirname, './src/services'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@types': path.resolve(__dirname, './src/types'),
    },
  },

  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', '@mui/material', '@mui/icons-material', 'axios'],
    esbuildOptions: { loader: { '.js': 'jsx' } },
  },
});
```

---

## 4. tsconfig.json (TypeScript Compiler)

**Path:** `web/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "types": ["node", "vite/client"],
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "strict": false,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "forceConsistentCasingInFileNames": true,
    "jsx": "react-jsx",
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@components/*": ["./src/components/*"],
      "@pages/*": ["./src/pages/*"],
      "@services/*": ["./src/services/*"],
      "@utils/*": ["./src/utils/*"],
      "@types/*": ["./src/types/*"],
      "@/hooks/*": ["./src/hooks/*"]
    },
    "allowJs": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "declaration": false,
    "declarationMap": false,
    "sourceMap": true
  },
  "include": ["src/**/*", "src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["node_modules", "build", "dist", "public"]
}
```

---

## 5. App.tsx Routing and Layout

**Path:** `web/src/App.tsx` (abbreviated)

### Theme (MUI)

```typescript
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1976d2' },
    secondary: { main: '#9c27b0' },
    error: { main: '#d32f2f' },
    warning: { main: '#ed6c02' },
    info: { main: '#0288d1' },
    success: { main: '#2e7d32' },
  },
});
```

### Route Structure

| Route | Component / Behavior |
|-------|----------------------|
| `/` | Redirect to `/politics/dashboard` |
| `/monitoring` | Monitoring (domain-agnostic) |
| `/settings` | Settings (domain-agnostic) |
| `/test-storyline-management` | StorylineManagementTest |
| `/dashboard` | LegacyRedirect → default domain dashboard |
| `/articles`, `/articles/duplicates`, `/articles/:id` | LegacyRedirect |
| `/storylines`, `/storylines/discover`, `/storylines/consolidation`, `/storylines/:id` | LegacyRedirect |
| `/topics`, `/topics/:topicName` | LegacyRedirect |
| `/rss-feeds`, `/rss-feeds/duplicates` | LegacyRedirect |
| `/intelligence`, `/intelligence/analysis`, `/intelligence/rag` | LegacyRedirect |
| `/:domain/*` | DomainLayout (handles all domain-specific sub-routes) |

### Domain-Specific Sub-Routes (via DomainLayout)

Typical pattern: `/:domain/dashboard`, `/:domain/articles`, `/:domain/storylines`, `/:domain/topics`, `/:domain/rss-feeds`, `/:domain/intelligence`, etc.

### Providers / Layout

- `ErrorBoundary` → `ThemeProvider` → `DomainProvider` → `Router`
- `Header`, `Navigation`, `main` (Routes), `Footer`

---

## 6. Path Aliases Summary

| Alias | Resolves to |
|-------|-------------|
| `@/*` | `./src/*` |
| `@components/*` | `./src/components/*` |
| `@pages/*` | `./src/pages/*` |
| `@services/*` | `./src/services/*` |
| `@utils/*` | `./src/utils/*` |
| `@types/*` | `./src/types/*` |
| `@/hooks/*` | `./src/hooks/*` |
