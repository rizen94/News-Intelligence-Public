# 🔧 Cursor API Configuration Fix

## 🎯 **The Problem**
Cursor is trying to use your existing API keys (OpenAI/Anthropic) with the local model, but local Ollama doesn't need those keys.

## 🔍 **Solution: Configure Local API**

### **Method 1: Check for API Provider Settings**
1. **In Cursor Settings**, look for:
   - **"API Provider"** or **"AI Provider"**
   - **"Custom API"** or **"Local API"**
   - **"API Configuration"**

2. **Change the provider to:**
   - **"Custom"** or **"Local"**
   - **"Ollama"** (if available)
   - **"Self-hosted"**

### **Method 2: Look for API Base URL Setting**
1. **Find "API Base URL"** or **"Custom API Endpoint"**
2. **Set it to**: `http://localhost:11434/v1`
3. **Clear or ignore API Key fields**

### **Method 3: Check Model Configuration**
1. **When adding the model**, look for:
   - **"API Base"** field
   - **"Endpoint"** field
   - **"Provider"** dropdown

2. **Set:**
   - **API Base**: `http://localhost:11434/v1`
   - **API Key**: `dummy` or leave empty
   - **Provider**: `Ollama` or `Custom`

## 🔧 **Alternative: Manual Configuration**

### **Method 1: Settings JSON**
1. **Open Command Palette** (Cmd/Ctrl + Shift + P)
2. **Type "Preferences: Open Settings (JSON)"**
3. **Add this configuration:**

```json
{
  "cursor.ai.provider": "custom",
  "cursor.ai.apiBase": "http://localhost:11434/v1",
  "cursor.ai.apiKey": "dummy",
  "cursor.ai.model": "deepseek-coder:33b"
}
```

### **Method 2: Environment Variables**
```bash
# Set these before starting Cursor
export CURSOR_AI_PROVIDER="custom"
export CURSOR_AI_API_BASE="http://localhost:11434/v1"
export CURSOR_AI_API_KEY="dummy"
export CURSOR_AI_MODEL="deepseek-coder:33b"
```

## 🎯 **What to Look For**

In Cursor settings, look for these sections:
- **"AI Provider"** or **"Code AI Provider"**
- **"API Configuration"** or **"Custom API"**
- **"Local AI"** or **"Offline AI"**
- **"Model Settings"** or **"Advanced Settings"**

## 🧪 **Quick Test**

### **After making changes:**
1. **Restart Cursor**
2. **Try adding the model again**
3. **Test with a simple Python file**

## 💡 **If You Can't Find These Settings**

### **Alternative Approach:**
1. **Use aider in terminal** for AI assistance
2. **Use Cursor for visual editing**
3. **Copy code between them**

**Can you look for "API Provider" or "API Configuration" in your Cursor settings?** This will help us configure it to use your local Ollama instead of external APIs.
