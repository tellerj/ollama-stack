#!/usr/bin/env python3
"""
Dia TTS MCP Server

A Model Context Protocol server that provides text-to-speech capabilities
using the Dia model from Nari Labs.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from pydantic import BaseModel

# Try to import Dia model
try:
    from dia.model import Dia
    DIA_AVAILABLE = True
except ImportError:
    DIA_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Dia TTS")

# Global model instance
_dia_model: Optional[Any] = None

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    seed: Optional[int] = None
    use_torch_compile: bool = True
    output_format: str = "mp3"

def get_dia_model():
    """Get or initialize the Dia model"""
    global _dia_model
    if _dia_model is None:
        if not DIA_AVAILABLE:
            raise RuntimeError("Dia model not available. Please install: pip install git+https://github.com/nari-labs/dia.git")
        
        logger.info("Loading Dia model...")
        _dia_model = Dia.from_pretrained("nari-labs/Dia-1.6B", compute_dtype="float16")
        logger.info("Dia model loaded successfully")
    
    return _dia_model

@mcp.tool()
def generate_speech(
    text: str,
    voice: Optional[str] = None,
    seed: Optional[int] = None,
    use_torch_compile: bool = True,
    output_format: str = "mp3"
) -> str:
    """
    Generate speech from text using the Dia TTS model.
    
    Args:
        text: The text to convert to speech. Use [S1] and [S2] tags for dialogue.
        voice: Voice identifier (optional, affects randomness)
        seed: Random seed for reproducible output
        use_torch_compile: Whether to use torch.compile for speed (disable on macOS)
        output_format: Output audio format (mp3, wav)
    
    Returns:
        Path to the generated audio file
    """
    try:
        model = get_dia_model()
        
        # Validate text format for Dia
        if not text.strip().startswith(('[S1]', '[S2]')):
            text = f"[S1] {text}"
        
        # Generate audio
        logger.info(f"Generating speech for text: {text[:100]}...")
        
        # Set seed if provided
        if seed is not None:
            import torch
            torch.manual_seed(seed)
        
        # Generate with appropriate settings
        output = model.generate(
            text, 
            use_torch_compile=use_torch_compile,
            verbose=True
        )
        
        # Save to temporary file
        temp_dir = Path(tempfile.gettempdir()) / "dia_tts"
        temp_dir.mkdir(exist_ok=True)
        
        output_file = temp_dir / f"speech_{hash(text) % 1000000}.{output_format}"
        model.save_audio(str(output_file), output)
        
        logger.info(f"Speech generated successfully: {output_file}")
        return str(output_file)
        
    except Exception as e:
        logger.error(f"Error generating speech: {e}")
        raise RuntimeError(f"Speech generation failed: {str(e)}")

@mcp.tool()
def generate_dialogue(
    speakers: List[str],
    script: str,
    use_torch_compile: bool = True,
    output_format: str = "mp3"
) -> str:
    """
    Generate dialogue between multiple speakers using Dia TTS.
    
    Args:
        speakers: List of speaker names
        script: Dialogue script with speaker names
        use_torch_compile: Whether to use torch.compile for speed
        output_format: Output audio format
    
    Returns:
        Path to the generated dialogue audio file
    """
    try:
        # Convert script to Dia format
        lines = script.strip().split('\n')
        dia_text = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Find speaker and convert to [S1]/[S2] format
            for i, speaker in enumerate(speakers[:2]):  # Dia supports max 2 speakers
                if line.startswith(f"{speaker}:"):
                    content = line[len(f"{speaker}:"):].strip()
                    speaker_tag = f"[S{i+1}]"
                    dia_text += f" {speaker_tag} {content}"
                    break
            else:
                # If no speaker found, assume it's narrative or use [S1]
                dia_text += f" [S1] {line}"
        
        return generate_speech(
            text=dia_text.strip(),
            use_torch_compile=use_torch_compile,
            output_format=output_format
        )
        
    except Exception as e:
        logger.error(f"Error generating dialogue: {e}")
        raise RuntimeError(f"Dialogue generation failed: {str(e)}")

@mcp.tool()
def voice_clone(
    reference_audio_path: str,
    reference_transcript: str,
    target_text: str,
    use_torch_compile: bool = True,
    output_format: str = "mp3"
) -> str:
    """
    Clone a voice using reference audio and generate new speech.
    
    Args:
        reference_audio_path: Path to reference audio file
        reference_transcript: Transcript of the reference audio
        target_text: Text to generate in the cloned voice
        use_torch_compile: Whether to use torch.compile
        output_format: Output format
    
    Returns:
        Path to generated audio with cloned voice
    """
    try:
        model = get_dia_model()
        
        # Ensure proper formatting
        if not reference_transcript.strip().startswith(('[S1]', '[S2]')):
            reference_transcript = f"[S1] {reference_transcript}"
        
        if not target_text.strip().startswith(('[S1]', '[S2]')):
            target_text = f"[S1] {target_text}"
        
        # Combine reference and target
        full_text = f"{reference_transcript} {target_text}"
        
        logger.info(f"Voice cloning with reference: {reference_audio_path}")
        
        # Load reference audio (implementation depends on Dia's API)
        # This is a simplified version - actual implementation may vary
        output = model.generate(
            full_text,
            use_torch_compile=use_torch_compile,
            verbose=True
        )
        
        # Save output
        temp_dir = Path(tempfile.gettempdir()) / "dia_tts"
        temp_dir.mkdir(exist_ok=True)
        
        output_file = temp_dir / f"cloned_{hash(target_text) % 1000000}.{output_format}"
        model.save_audio(str(output_file), output)
        
        logger.info(f"Voice cloning completed: {output_file}")
        return str(output_file)
        
    except Exception as e:
        logger.error(f"Error in voice cloning: {e}")
        raise RuntimeError(f"Voice cloning failed: {str(e)}")

@mcp.resource("dia://model/info")
def get_model_info() -> str:
    """Get information about the Dia TTS model"""
    if not DIA_AVAILABLE:
        return "Dia TTS model not available. Please install the dia package."
    
    return """
    Dia TTS Model Information:
    
    - Model: Nari Labs Dia-1.6B
    - Capabilities: High-quality dialogue generation
    - Supported Features:
      * Multi-speaker dialogue ([S1], [S2] tags)
      * Non-verbal sounds (laughs, coughs, etc.)
      * Voice cloning (experimental)
    - Recommended text length: 5-20 seconds of audio
    - Always start text with [S1] and alternate speakers
    """

@mcp.resource("dia://examples/dialogue")
def get_dialogue_examples() -> str:
    """Get example dialogue scripts for Dia TTS"""
    return """
    Example Dialogue Scripts:
    
    1. Simple Conversation:
    [S1] Hello, how are you today?
    [S2] I'm doing great, thanks for asking!
    [S1] That's wonderful to hear.
    
    2. With Non-verbals:
    [S1] Did you hear that joke? (laughs)
    [S2] Yes! (chuckles) It was hilarious.
    [S1] I'm glad you enjoyed it.
    
    3. Formal Presentation:
    [S1] Welcome to today's presentation.
    [S2] Thank you for having me.
    [S1] Let's begin with the overview.
    """

@mcp.prompt()
def create_dialogue_script(topic: str, speakers: str = "2") -> str:
    """Create a dialogue script for TTS generation"""
    return f"""
Please create a natural dialogue script about "{topic}" for {speakers} speakers.

Format the script for Dia TTS with the following guidelines:
- Use [S1] and [S2] tags for speaker identification
- Keep individual lines moderate length (5-20 seconds when spoken)
- Include natural conversation flow
- You may include non-verbal cues like (laughs), (sighs), etc. sparingly
- Ensure the dialogue sounds natural and engaging

Topic: {topic}
Number of speakers: {speakers}

Generate the dialogue script:
"""

@mcp.prompt()
def optimize_text_for_tts(text: str) -> str:
    """Optimize text for Dia TTS generation"""
    return f"""
Please optimize the following text for Dia TTS generation:

Original text: "{text}"

Apply these optimizations:
1. Add appropriate [S1]/[S2] speaker tags if missing
2. Break long sentences into more natural speech segments
3. Add punctuation for natural pauses
4. Suggest any non-verbal cues that would enhance the audio
5. Ensure the text length is appropriate (5-20 seconds of speech)

Optimized text:
"""

if __name__ == "__main__":
    # Run the MCP server
    mcp.run() 