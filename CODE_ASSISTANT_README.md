# Code Assistant Setup

This directory contains scripts to run a local code assistant using Ollama and aider, with your News Intelligence project as context.

## Quick Start

### First Time Setup
```bash
./start-code-assistant.sh
```

This script will:
- Install Ollama and aider if not present
- Start Ollama service
- Pull the DeepSeek Coder 6.7B model
- Create aider configuration
- Generate a context file for your news app
- Start aider with your project as context

### Quick Start (after initial setup)
```bash
./quick-aider.sh
```

This script assumes everything is already installed and just starts aider quickly.

## What You Get

- **Local Ollama**: Runs on port 11434
- **Aider Integration**: Uses your news app as context
- **Model**: DeepSeek Coder 6.7B (good balance of performance and speed)
- **Context**: Comprehensive project context automatically loaded

## Usage

Once aider starts, you can:

1. **Ask questions** about your codebase
2. **Request code changes** - aider will make them directly
3. **Get explanations** of how your system works
4. **Debug issues** with context awareness
5. **Add new features** with full project understanding

## Example Commands in Aider

```
# Ask about the system
How does the RSS collection system work?

# Make changes
Add a new API endpoint for user preferences

# Debug issues
Why is the deduplication not working properly?

# Add features
Create a new ML model for sentiment analysis
```

## Configuration

- **Model**: DeepSeek Coder 6.7B (configurable in scripts)
- **Context File**: `.aider-context.md` (auto-generated)
- **Aider Config**: `~/.aider/aider.conf` (auto-generated)

## Stopping

- Press `Ctrl+C` to stop aider
- The script will automatically clean up Ollama if it started it

## Troubleshooting

### Ollama not starting
```bash
# Check if port 11434 is in use
lsof -i :11434

# Kill existing Ollama process
pkill ollama

# Restart
ollama serve
```

### Model not found
```bash
# List available models
ollama list

# Pull the model manually
ollama pull deepseek-coder:6.7b
```

### Aider not working
```bash
# Check aider installation
aider --version

# Reinstall if needed
pip install aider-chat
```

## Benefits Over Docker

- **Faster startup** - no container overhead
- **Direct file access** - no volume mounting issues
- **Simpler debugging** - direct process access
- **Resource efficient** - no Docker overhead
- **Easy customization** - modify scripts as needed

## Model Options

You can change the model in the scripts by editing the `OLLAMA_MODEL` variable:

- `deepseek-coder:6.7b` - Good balance (default)
- `deepseek-coder:33b` - More capable but slower
- `codellama:7b` - Alternative option
- `llama3.2:3b` - Faster but less capable

## Context File

The `.aider-context.md` file contains:
- Project overview
- Directory structure
- Key technologies
- Development guidelines
- Common tasks
- Important notes

This gives aider full context about your project without needing to analyze files each time.
