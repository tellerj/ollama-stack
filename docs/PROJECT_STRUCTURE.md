# Project Structure

Project organization and file layout.

## Directory Layout

```
ollama-stack/
├── README.md                   # Main project overview
├── ollama-stack                # Main CLI tool (Unix/macOS)
├── ollama-stack.ps1            # Main CLI tool (Windows)
├── docker-compose.yml          # Base Docker configuration
├── docker-compose.apple.yml    # Apple Silicon overrides
├── docker-compose.nvidia.yml   # NVIDIA GPU overrides
├── docs/                       # Documentation
│   ├── CLI_USAGE.md              
│   ├── WINDOWS_SETUP.md          
│   └── UNIFIED_CLI_SUMMARY.md    
├── install-ollama-stack.sh     # Unix/macOS installer
├── install-ollama-stack.ps1    # Windows installer
├── extensions/                 # Extension system
│   ├── dia-tts-mcp/              
│   └── registry.json             
└── tools/                      # Additional tools
    └── pdf-extractor/            
```

## Organization Rules

- **Root**: Primary executables, installers, and core configuration
- **docs/**: All documentation
- **extensions/**: Self-contained extension packages
- **tools/**: Additional utilities

## Usage

### Primary Interface
```bash
./ollama-stack start
./ollama-stack extensions enable dia-tts-mcp
./ollama-stack status
```

### Installation
```bash
./install-ollama-stack.sh     # Unix/macOS
.\install-ollama-stack.ps1    # Windows
```

## File Reference

| File/Directory | Purpose |
|----------------|---------|
| `ollama-stack` | Primary CLI tool |
| `ollama-stack.ps1` | Windows CLI tool |
| `docs/CLI_USAGE.md` | Complete CLI reference |
| `docs/WINDOWS_SETUP.md` | Windows setup guide |
| `install-ollama-stack.sh` | Unix/macOS installation script |
| `install-ollama-stack.ps1` | Windows installation script |
| `extensions/` | Extension packages |
| `docker-compose*.yml` | Service configurations |

## Migration Notes

Project restructured for better organization. Installation scripts moved to root for easier access, legacy start/stop scripts removed as the main CLI tool now handles all functionality.

## Quick Reference

| Task | Command/Location |
|------|------------------|
| Start the stack | `./ollama-stack start` |
| Install system-wide | `./install-ollama-stack.sh` |
| Full CLI reference | `docs/CLI_USAGE.md` |
| Windows setup | `docs/WINDOWS_SETUP.md` |
| Add extension | `extensions/` directory |
| Modify services | `docker-compose*.yml` | 