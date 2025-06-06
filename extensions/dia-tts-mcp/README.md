# Dia TTS MCP Server

A Model Context Protocol (MCP) server that provides text-to-speech capabilities using the [Dia model from Nari Labs](https://github.com/nari-labs/dia).

## Features

- **High-Quality Dialogue Generation**: Generate realistic multi-speaker conversations
- **Voice Cloning**: Clone voices from reference audio (experimental)
- **Non-Verbal Audio**: Support for laughter, coughs, and other natural sounds
- **MCP Standard**: Seamlessly integrates with OpenWebUI and other MCP-compatible clients

## Tools Provided

### `generate_speech`
Convert text to speech using Dia's dialogue capabilities.

**Parameters:**
- `text`: Text to convert (use [S1] and [S2] tags for speakers)
- `voice`: Optional voice identifier
- `seed`: Random seed for reproducible output
- `use_torch_compile`: Enable/disable torch compilation (disable on macOS)
- `output_format`: Audio format (mp3, wav)

### `generate_dialogue`
Generate dialogue between multiple speakers from a script.

**Parameters:**
- `speakers`: List of speaker names
- `script`: Dialogue script with speaker names
- `use_torch_compile`: Enable/disable torch compilation
- `output_format`: Audio format

### `voice_clone`
Clone a voice using reference audio.

**Parameters:**
- `reference_audio_path`: Path to reference audio file
- `reference_transcript`: Transcript of the reference audio
- `target_text`: Text to generate in the cloned voice
- `use_torch_compile`: Enable/disable torch compilation
- `output_format`: Audio format

## Resources Provided

### `dia://model/info`
Information about the Dia TTS model and its capabilities.

### `dia://examples/dialogue`
Example dialogue scripts formatted for Dia TTS.

## Prompts Provided

### `create_dialogue_script`
Generate optimized dialogue scripts for TTS.

### `optimize_text_for_tts`
Optimize existing text for better TTS generation.

## Installation

### Standalone

```bash
# Clone the repository
git clone <your-repo-url>
cd dia-tts-mcp

# Install dependencies
pip install -r requirements.txt

# Set HuggingFace token (required for model access)
export HF_TOKEN="your_hf_token_here"

# Run the server
python server.py
```

### Docker

```bash
# Build the image
docker build -t dia-tts-mcp .

# Run the container
docker run -e HF_TOKEN="your_hf_token_here" dia-tts-mcp
```

## Integration with OpenWebUI

1. Start the Dia TTS MCP server
2. Configure OpenWebUI to connect to the MCP server
3. Use the provided tools in your conversations:

```
Hey, can you generate some speech for this text: 
"[S1] Hello there! [S2] Hi, how are you doing today? [S1] I'm doing great, thanks!"
```

## Usage Examples

### Basic Speech Generation
```python
# The MCP server will handle this automatically when called via tools
text = "[S1] Welcome to our presentation. [S2] Thank you for having us today."
```

### Dialogue with Non-Verbals
```python
text = "[S1] Did you hear that joke? (laughs) [S2] Yes! (chuckles) It was hilarious."
```

### Voice Cloning
Provide a reference audio file and its transcript, then specify the new text to generate.

## Hardware Requirements

- **GPU Recommended**: RTX 4090 or similar for best performance
- **CPU Support**: Available but slower
- **Memory**: ~10GB VRAM for optimal performance
- **Apple Silicon**: Supported (set `use_torch_compile=False`)

## Performance

On RTX 4090:
- **Real-time factor**: 2.1x with compilation, 1.5x without
- **VRAM usage**: ~10GB
- **Supported formats**: MP3, WAV

## Troubleshooting

### Model Loading Issues
- Ensure you have a valid HuggingFace token
- Check that you have sufficient VRAM/RAM
- For macOS, set `use_torch_compile=False`

### Audio Generation Fails
- Verify text format uses [S1]/[S2] tags
- Keep text length moderate (5-20 seconds of speech)
- Check available disk space for temporary files

## License

This MCP server is provided under the same license as the Dia model (Apache 2.0). Please see the [Dia repository](https://github.com/nari-labs/dia) for full license details. 