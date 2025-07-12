# Dia TTS MCP Extension

A Model Context Protocol (MCP) extension that provides high-quality text-to-speech capabilities using the [Dia model from Nari Labs](https://github.com/nari-labs/dia).

## Overview

This extension integrates the Dia TTS model into the Ollama Stack, providing:

- **High-Quality Dialogue Generation**: Realistic multi-speaker conversations  
- **Voice Cloning**: Clone voices from reference audio (experimental)
- **Non-Verbal Audio**: Support for laughter, coughs, and other natural sounds
- **Seamless Integration**: Works with OpenWebUI through MCP protocol

## Features

### 🎙️ Text-to-Speech Tools
- `generate_speech` - Convert text to natural-sounding speech
- `generate_dialogue` - Create multi-speaker dialogues with `[S1]` and `[S2]` tags
- `voice_clone` - Clone voices from reference audio samples

### 📚 Resources  
- Model information and capabilities
- Dialogue script examples and best practices

### 🎯 Smart Prompts
- `create_dialogue_script` - Generate optimized dialogue scripts
- `optimize_text_for_tts` - Improve text for better speech synthesis

## Installation

### Prerequisites
- Docker and Docker Compose
- HuggingFace account and token (for model access)
- Ollama Stack running

### Quick Start

1. **Set up HuggingFace token**:
   ```bash
   export HF_TOKEN="your_huggingface_token_here"
   ```

2. **Enable the extension**:
   ```bash
   cd extensions
   ./manage.sh enable dia-tts-mcp
   ```

3. **Start the extension**:
   ```bash
   # Auto-detect platform
   ./manage.sh start dia-tts-mcp
   
   # Or specify platform
   ./manage.sh start dia-tts-mcp -p nvidia  # For NVIDIA GPU
   ./manage.sh start dia-tts-mcp -p apple   # For Apple Silicon
   ./manage.sh start dia-tts-mcp -p cpu     # For CPU-only
   ```

## Usage

### Basic Text-to-Speech
```python
# In OpenWebUI or any MCP client
result = await call_tool("generate_speech", {
    "text": "Hello, this is a test of the Dia TTS system.",
    "voice": "default",
    "seed": 42
})
```

### Multi-Speaker Dialogue
```python
result = await call_tool("generate_dialogue", {
    "script": "[S1] Good morning! How are you today? [S2] I'm doing great, thanks for asking! [S1] That's wonderful to hear.",
    "seed": 42
})
```

### Voice Cloning
```python
result = await call_tool("voice_clone", {
    "text": "This will be spoken in the cloned voice.",
    "reference_audio_path": "/path/to/reference.wav",
    "seed": 42
})
```

## Configuration

### Environment Variables
- `HF_TOKEN` - HuggingFace token (required)
- `PYTORCH_ENABLE_MPS_FALLBACK` - Enable MPS fallback on macOS
- `TORCH_COMPILE` - Enable/disable torch compilation
- `CUDA_VISIBLE_DEVICES` - GPU selection for NVIDIA

### Resource Requirements
- **Memory**: 16GB RAM recommended
- **GPU**: 10GB VRAM recommended for optimal performance
- **Storage**: ~5GB for model files

### Platform Support
| Platform | Support | Performance | Notes |
|----------|---------|-------------|-------|
| CPU | ✅ | Slow | Works but not recommended |
| NVIDIA GPU | ✅ | Optimal | Best performance |
| Apple Silicon | ✅ | Good | MPS acceleration |

## Management Commands

```bash
# List all extensions and their status
./manage.sh list

# Get detailed information about the extension
./manage.sh info dia-tts-mcp

# View logs
./manage.sh logs dia-tts-mcp -f

# Stop the extension
./manage.sh stop dia-tts-mcp

# Restart with different platform
./manage.sh restart dia-tts-mcp -p nvidia
```

## Integration with OpenWebUI

Once started, the extension automatically registers with OpenWebUI through the MCP proxy. You can:

1. **Use Tools**: Access TTS tools in chat conversations
2. **Browse Resources**: View model information and examples  
3. **Apply Prompts**: Use built-in prompts for script generation

## Troubleshooting

### Common Issues

**Model fails to load**:
- Ensure HF_TOKEN is set correctly
- Check that you have access to the Dia model repository
- Verify sufficient memory/GPU resources

**Audio generation fails**:
- Check logs with `./manage.sh logs dia-tts-mcp -f`
- Ensure output directory is writable
- Try disabling torch compilation on macOS

**Performance issues**:
- Use NVIDIA GPU for best performance
- Reduce memory limits if experiencing OOM errors
- Consider using CPU fallback for compatibility

### Getting Help

```bash
# View extension information
./manage.sh info dia-tts-mcp

# Check logs for errors
./manage.sh logs dia-tts-mcp

# Test basic functionality
docker exec -it dia-tts-mcp python3 -c "import dia; print('Dia imported successfully')"
```

## Development

### File Structure
```
dia-tts-mcp/
├── server.py              # MCP server implementation
├── requirements.txt       # Python dependencies  
├── Dockerfile            # Container definition
├── docker-compose.yml    # Base configuration
├── docker-compose.nvidia.yml  # NVIDIA overrides
├── docker-compose.apple.yml   # Apple Silicon overrides
├── mcp-config.json       # Extension metadata
└── README.md            # This file
```

### Extending the Extension

To add new tools or modify behavior:

1. Edit `server.py` to add new MCP tools/resources
2. Update `mcp-config.json` with new capabilities
3. Rebuild and restart: `./manage.sh restart dia-tts-mcp`

## License

This extension integrates with the Dia model. Please check the [Dia repository](https://github.com/nari-labs/dia) for licensing information.

## Links

- [Dia Model Repository](https://github.com/nari-labs/dia)
- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [OpenWebUI Documentation](https://docs.openwebui.com/)
- [Ollama Stack Repository](https://git.ctcubed.com/teller.junak/ollama-stack) 