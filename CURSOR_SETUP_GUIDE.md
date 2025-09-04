# 🎯 Cursor + Local Ollama Setup Guide

## 🔍 **Finding the Right Settings**

### **Method 1: AI Settings (Most Common)**
1. **Open Cursor Settings** (Cmd/Ctrl + ,)
2. **Look for "AI" or "Code AI" section**
3. **Find "Custom Models" or "Local Models"**
4. **Add New Model with these details:**
   - **Name**: `DeepSeek Coder Local`
   - **API Base URL**: `http://localhost:11434/v1`
   - **API Key**: `dummy`
   - **Model Name**: `deepseek-coder:33b`

### **Method 2: Extensions/Integrations**
1. **Go to Extensions** (Cmd/Ctrl + Shift + X)
2. **Search for "Ollama" or "Local AI"**
3. **Install Ollama extension** if available
4. **Configure through extension settings**

### **Method 3: Settings.json (Manual)**
1. **Open Command Palette** (Cmd/Ctrl + Shift + P)
2. **Type "Preferences: Open Settings (JSON)"**
3. **Add this configuration:**

```json
{
  "cursor.ai.customModels": [
    {
      "name": "DeepSeek Coder Local",
      "apiBase": "http://localhost:11434/v1",
      "apiKey": "dummy",
      "model": "deepseek-coder:33b"
    }
  ]
}
```

### **Method 4: Environment Variables**
1. **Set environment variables:**
```bash
export CURSOR_AI_API_BASE="http://localhost:11434/v1"
export CURSOR_AI_API_KEY="dummy"
export CURSOR_AI_MODEL="deepseek-coder:33b"
```

## 🔧 **Alternative: Use Cursor's Built-in Local AI**

### **If Cursor has built-in local AI support:**
1. **Look for "Local AI" or "Offline AI" in settings**
2. **Enable local AI mode**
3. **Point to your Ollama installation**

## 🚀 **Quick Test**

### **Test if it's working:**
1. **Open a Python file**
2. **Try AI autocomplete** (Cmd/Ctrl + Space)
3. **Open AI chat** (Cmd/Ctrl + L)
4. **Ask**: "Write a simple Python function"

## 💡 **If You Can't Find the Settings**

### **Alternative Approach:**
1. **Use aider in terminal** for AI assistance
2. **Use Cursor for visual editing**
3. **Copy code between them**

### **Or try:**
1. **Update Cursor** to latest version
2. **Check Cursor documentation** for local AI setup
3. **Look for "Ollama" in the extensions marketplace**

## 🎯 **What to Look For**

The settings might be labeled as:
- "Custom Models"
- "Local Models" 
- "AI Providers"
- "Code AI Settings"
- "Extensions"
- "Integrations"

**Can you tell me what options you see in the AI/Models section?** This will help me guide you to the right place!
