#!/usr/bin/env python3
"""
Dia TTS MCP Server

A Model Context Protocol server that provides text-to-speech capabilities
using the Dia model from Nari Labs.
"""

import asyncio
import logging
import os
import sys
import tempfile
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import base64

from mcp.server import Server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    GetPromptRequest,
    GetPromptResult,
    GetResourceRequest,
    GetResourceResult,
    ListPromptsRequest,
    ListPromptsResult,
    ListResourcesRequest,
    ListResourcesResult,
    ListToolsRequest,
    ListToolsResult,
    Prompt,
    PromptArgument,
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Try to import Dia model
try:
    from dia.model import Dia
    DIA_AVAILABLE = True
    logger.info("Dia model is available")
except ImportError as e:
    DIA_AVAILABLE = False
    logger.warning(f"Dia model not available: {e}")

# Global model instance
_dia_model: Optional[Any] = None

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    seed: Optional[int] = None
    use_torch_compile: Optional[bool] = None
    output_format: str = "wav"

class DialogueRequest(BaseModel):
    script: str
    speaker1_voice: Optional[str] = None
    speaker2_voice: Optional[str] = None
    seed: Optional[int] = None
    use_torch_compile: Optional[bool] = None
    output_format: str = "wav"

class VoiceCloneRequest(BaseModel):
    text: str
    reference_audio_path: str
    seed: Optional[int] = None
    use_torch_compile: Optional[bool] = None
    output_format: str = "wav"

def get_dia_model():
    """Get or initialize the Dia model instance."""
    global _dia_model
    
    if not DIA_AVAILABLE:
        raise RuntimeError("Dia model is not available. Please install it from https://github.com/nari-labs/dia")
    
    if _dia_model is None:
        logger.info("Initializing Dia model...")
        try:
            _dia_model = Dia()
            logger.info("Dia model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Dia model: {e}")
            raise
    
    return _dia_model

def audio_to_base64(audio_path: str) -> str:
    """Convert audio file to base64 for transmission."""
    with open(audio_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# Initialize MCP server
server = Server("dia-tts")

@server.list_tools()
async def list_tools() -> ListToolsResult:
    """List available TTS tools."""
    tools = [
        Tool(
            name="generate_speech",
            description="Convert text to speech using Dia's TTS capabilities",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to convert to speech"
                    },
                    "voice": {
                        "type": "string",
                        "description": "Voice identifier (optional)",
                        "default": None
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducible output",
                        "default": None
                    },
                    "use_torch_compile": {
                        "type": "boolean",
                        "description": "Enable torch compilation (disable on macOS)",
                        "default": True
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output audio format",
                        "enum": ["wav", "mp3", "flac"],
                        "default": "wav"
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="generate_dialogue",
            description="Generate multi-speaker dialogue using Dia. Use [S1] and [S2] tags to specify speakers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "Dialogue script with [S1] and [S2] speaker tags"
                    },
                    "speaker1_voice": {
                        "type": "string",
                        "description": "Voice for Speaker 1 (optional)",
                        "default": None
                    },
                    "speaker2_voice": {
                        "type": "string",
                        "description": "Voice for Speaker 2 (optional)",
                        "default": None
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducible output",
                        "default": None
                    },
                    "use_torch_compile": {
                        "type": "boolean",
                        "description": "Enable torch compilation (disable on macOS)",
                        "default": True
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output audio format",
                        "enum": ["wav", "mp3", "flac"],
                        "default": "wav"
                    }
                },
                "required": ["script"]
            }
        ),
        Tool(
            name="voice_clone",
            description="Clone a voice from reference audio (experimental)",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to synthesize with cloned voice"
                    },
                    "reference_audio_path": {
                        "type": "string",
                        "description": "Path to reference audio file"
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Random seed for reproducible output",
                        "default": None
                    },
                    "use_torch_compile": {
                        "type": "boolean",
                        "description": "Enable torch compilation (disable on macOS)",
                        "default": True
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output audio format",
                        "enum": ["wav", "mp3", "flac"],
                        "default": "wav"
                    }
                },
                "required": ["text", "reference_audio_path"]
            }
        )
    ]
    
    return ListToolsResult(tools=tools)

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls."""
    try:
        if name == "generate_speech":
            request = TTSRequest(**arguments)
            
            # Get model
            model = get_dia_model()
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=f".{request.output_format}", delete=False) as temp_file:
                output_path = temp_file.name
            
            # Generate speech
            logger.info(f"Generating speech for text: {request.text[:50]}...")
            
            # Call Dia model (this is pseudocode - adapt to actual Dia API)
            try:
                # Actual implementation would depend on Dia's API
                # model.generate_speech(
                #     text=request.text,
                #     output_path=output_path,
                #     voice=request.voice,
                #     seed=request.seed,
                #     use_torch_compile=request.use_torch_compile
                # )
                
                # For now, create a placeholder response
                raise NotImplementedError("Dia model integration needs to be completed")
                
            except Exception as e:
                logger.error(f"Speech generation failed: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error generating speech: {str(e)}")]
                )
            
            # Convert to base64 and return
            audio_data = audio_to_base64(output_path)
            os.unlink(output_path)  # Clean up temp file
            
            return CallToolResult(
                content=[
                    TextContent(type="text", text="Speech generated successfully"),
                    TextContent(type="text", text=f"Audio data (base64): {audio_data}")
                ]
            )
            
        elif name == "generate_dialogue":
            request = DialogueRequest(**arguments)
            
            # Get model
            model = get_dia_model()
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=f".{request.output_format}", delete=False) as temp_file:
                output_path = temp_file.name
            
            logger.info(f"Generating dialogue for script: {request.script[:50]}...")
            
            # Generate dialogue (pseudocode)
            try:
                # model.generate_dialogue(
                #     script=request.script,
                #     output_path=output_path,
                #     speaker1_voice=request.speaker1_voice,
                #     speaker2_voice=request.speaker2_voice,
                #     seed=request.seed,
                #     use_torch_compile=request.use_torch_compile
                # )
                
                raise NotImplementedError("Dia dialogue generation needs to be implemented")
                
            except Exception as e:
                logger.error(f"Dialogue generation failed: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error generating dialogue: {str(e)}")]
                )
            
            # Convert to base64 and return
            audio_data = audio_to_base64(output_path)
            os.unlink(output_path)  # Clean up temp file
            
            return CallToolResult(
                content=[
                    TextContent(type="text", text="Dialogue generated successfully"),
                    TextContent(type="text", text=f"Audio data (base64): {audio_data}")
                ]
            )
            
        elif name == "voice_clone":
            request = VoiceCloneRequest(**arguments)
            
            # Get model
            model = get_dia_model()
            
            # Validate reference audio exists
            if not os.path.exists(request.reference_audio_path):
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Reference audio file not found: {request.reference_audio_path}")]
                )
            
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=f".{request.output_format}", delete=False) as temp_file:
                output_path = temp_file.name
            
            logger.info(f"Cloning voice from: {request.reference_audio_path}")
            
            # Clone voice (pseudocode)
            try:
                # model.clone_voice(
                #     text=request.text,
                #     reference_audio=request.reference_audio_path,
                #     output_path=output_path,
                #     seed=request.seed,
                #     use_torch_compile=request.use_torch_compile
                # )
                
                raise NotImplementedError("Voice cloning needs to be implemented")
                
            except Exception as e:
                logger.error(f"Voice cloning failed: {e}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error cloning voice: {str(e)}")]
                )
            
            # Convert to base64 and return
            audio_data = audio_to_base64(output_path)
            os.unlink(output_path)  # Clean up temp file
            
            return CallToolResult(
                content=[
                    TextContent(type="text", text="Voice cloned successfully"),
                    TextContent(type="text", text=f"Audio data (base64): {audio_data}")
                ]
            )
        
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")]
            )
            
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")]
        )

@server.list_resources()
async def list_resources() -> ListResourcesResult:
    """List available resources."""
    resources = [
        Resource(
            uri="dia://model/info",
            name="Dia Model Information",
            description="Information about the Dia TTS model"
        ),
        Resource(
            uri="dia://examples/dialogue",
            name="Dialogue Examples",
            description="Example dialogue scripts for multi-speaker generation"
        )
    ]
    
    return ListResourcesResult(resources=resources)

@server.get_resource()
async def get_resource(uri: str) -> GetResourceResult:
    """Get resource content."""
    if uri == "dia://model/info":
        info = {
            "name": "Dia",
            "version": "1.6B parameters",
            "description": "High-quality dialogue generation model from Nari Labs",
            "capabilities": [
                "Text-to-speech conversion",
                "Multi-speaker dialogue generation", 
                "Voice cloning (experimental)",
                "Non-verbal audio (laughter, coughs, etc.)"
            ],
            "supported_formats": ["wav", "mp3", "flac"],
            "available": DIA_AVAILABLE
        }
        
        return GetResourceResult(
            contents=[
                TextContent(
                    type="text",
                    text=json.dumps(info, indent=2)
                )
            ]
        )
        
    elif uri == "dia://examples/dialogue":
        examples = {
            "simple_conversation": "[S1] Hello, how are you today? [S2] I'm doing great, thanks for asking! [S1] That's wonderful to hear.",
            "with_emotions": "[S1] *laughs* That's the funniest thing I've heard all day! [S2] *chuckles* I'm glad you enjoyed it.",
            "formal_dialogue": "[S1] Good morning, I'd like to discuss the quarterly reports. [S2] Of course, I have them prepared right here.",
            "tips": [
                "Use [S1] and [S2] tags to specify different speakers",
                "Include *emotions* or *actions* for more natural dialogue",
                "Keep individual speaker segments reasonably short",
                "Dia excels at conversational, natural-sounding speech"
            ]
        }
        
        return GetResourceResult(
            contents=[
                TextContent(
                    type="text",
                    text=json.dumps(examples, indent=2)
                )
            ]
        )
    
    else:
        raise ValueError(f"Unknown resource: {uri}")

@server.list_prompts()
async def list_prompts() -> ListPromptsResult:
    """List available prompts."""
    prompts = [
        Prompt(
            name="create_dialogue_script",
            description="Create a dialogue script optimized for Dia TTS",
            arguments=[
                PromptArgument(
                    name="topic",
                    description="Topic or scenario for the dialogue",
                    required=True
                ),
                PromptArgument(
                    name="speakers",
                    description="Number of speakers (1-2)",
                    required=False
                ),
                PromptArgument(
                    name="tone",
                    description="Tone of the dialogue (formal, casual, emotional, etc.)",
                    required=False
                )
            ]
        ),
        Prompt(
            name="optimize_text_for_tts",
            description="Optimize text for better TTS pronunciation and flow",
            arguments=[
                PromptArgument(
                    name="text",
                    description="Text to optimize for TTS",
                    required=True
                ),
                PromptArgument(
                    name="style",
                    description="Speaking style (conversational, formal, narrative, etc.)",
                    required=False
                )
            ]
        )
    ]
    
    return ListPromptsResult(prompts=prompts)

@server.get_prompt()
async def get_prompt(name: str, arguments: Dict[str, str]) -> GetPromptResult:
    """Get prompt content."""
    if name == "create_dialogue_script":
        topic = arguments.get("topic", "general conversation")
        speakers = arguments.get("speakers", "2")
        tone = arguments.get("tone", "casual")
        
        prompt = f"""Create a dialogue script for Dia TTS with the following specifications:

Topic: {topic}
Number of speakers: {speakers}  
Tone: {tone}

Instructions:
- Use [S1] and [S2] tags to indicate different speakers
- Keep each speaker's segments natural and conversational
- Include appropriate emotions or actions in *asterisks* when suitable
- Make the dialogue flow naturally and be engaging
- Ensure each speaker has distinct personality/voice
- Keep individual segments to 1-3 sentences for best TTS results

Example format:
[S1] Hello! I wanted to talk about {topic.lower()}. [S2] That sounds interesting! *excited* Tell me more about it. [S1] Well, let me start from the beginning...

Please create a dialogue script following these guidelines:"""

        return GetPromptResult(
            description=f"Dialogue script creation prompt for topic: {topic}",
            messages=[
                TextContent(type="text", text=prompt)
            ]
        )
        
    elif name == "optimize_text_for_tts":
        text = arguments.get("text", "")
        style = arguments.get("style", "conversational")
        
        prompt = f"""Optimize the following text for better text-to-speech synthesis with Dia:

Original text: {text}

Optimization guidelines:
- Break up very long sentences into shorter, more natural phrases
- Replace complex abbreviations with full words
- Add punctuation for natural pauses and rhythm
- Consider the {style} speaking style
- Ensure numbers and special characters are written out appropriately
- Add emotional context where appropriate (in *asterisks*)
- Make the text flow more naturally when spoken aloud

Please provide the optimized version:"""

        return GetPromptResult(
            description=f"Text optimization prompt for {style} style",
            messages=[
                TextContent(type="text", text=prompt)
            ]
        )
    
    else:
        raise ValueError(f"Unknown prompt: {name}")

async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting Dia TTS MCP Server")
    
    # Check if Dia is available
    if not DIA_AVAILABLE:
        logger.warning("Dia model is not available - server will run in mock mode")
    
    # Run the server using stdio transport
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main()) 