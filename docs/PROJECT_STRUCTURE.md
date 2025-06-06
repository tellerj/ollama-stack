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
├── scripts/                    # Utility and legacy scripts
│   ├── install.sh                
│   ├── install.ps1               
│   ├── start-stack.sh            
│   ├── start-stack.ps1           
│   ├── stop-stack.sh             
│   └── stop-stack.ps1            
├── extensions/                 # Extension system
│   ├── dia-tts-mcp/              
│   └── registry.json             
└── tools/                      # Additional tools
    └── pdf-extractor/            
```

## Organization Rules

- **Root**: Primary executables and core configuration
- **docs/**: All documentation
- **scripts/**: Installation and legacy scripts  
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
./scripts/install.sh     # Unix/macOS
.\scripts\install.ps1    # Windows
```

### Legacy Scripts
```bash
./scripts/start-stack.sh -p nvidia
./scripts/stop-stack.sh -v
```

## File Reference

| File/Directory | Purpose |
|----------------|---------|
| `ollama-stack` | Primary CLI tool |
| `ollama-stack.ps1` | Windows CLI tool |
| `docs/CLI_USAGE.md` | Complete CLI reference |
| `docs/WINDOWS_SETUP.md` | Windows setup guide |
| `scripts/install.*` | Installation scripts |
| `scripts/start-stack.*` | Legacy start scripts |
| `extensions/` | Extension packages |
| `docker-compose*.yml` | Service configurations |

## Migration Notes

Scripts moved from root to subdirectories for organization. All existing functionality preserved.

| Old Location | New Location |
|--------------|--------------|
| `./start-stack.sh` | `./scripts/start-stack.sh` |
| `./install.sh` | `./scripts/install.sh` |
| `./CLI_USAGE.md` | `./docs/CLI_USAGE.md` |

## Quick Reference

| Task | Command/Location |
|------|------------------|
| Start the stack | `./ollama-stack start` |
| Install system-wide | `./scripts/install.sh` |
| Full CLI reference | `docs/CLI_USAGE.md` |
| Windows setup | `docs/WINDOWS_SETUP.md` |
| Legacy scripts | `./scripts/start-stack.sh` |
| Add extension | `extensions/` directory |
| Modify services | `docker-compose*.yml` | 