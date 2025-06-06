# 📁 Project Structure

This document explains the organization of the **Ollama Stack** project after reorganization for better maintainability and professional standards.

## 🎯 **Current Structure**

```
ollama-stack/
├── 📄 README.md                   # Main project overview
├── ⚡ ollama-stack                # Main CLI tool (Unix/macOS)
├── ⚡ ollama-stack.ps1            # Main CLI tool (Windows)
│
├── 🐳 docker-compose.yml          # Base Docker configuration
├── 🐳 docker-compose.apple.yml    # Apple Silicon overrides
├── 🐳 docker-compose.nvidia.yml   # NVIDIA GPU overrides
│
├── 📚 docs/                       # All documentation
│   ├── CLI_USAGE.md              # Complete CLI reference
│   ├── WINDOWS_SETUP.md          # Windows-specific guide
│   └── UNIFIED_CLI_SUMMARY.md    # Technical implementation notes
│
├── 🔧 scripts/                    # Utility and legacy scripts
│   ├── install.sh                # Unix/macOS installer
│   ├── install.ps1               # Windows installer
│   ├── start-stack.sh            # Legacy start script (Unix)
│   ├── start-stack.ps1           # Legacy start script (Windows)
│   ├── stop-stack.sh             # Legacy stop script (Unix)
│   └── stop-stack.ps1            # Legacy stop script (Windows)
│
├── 🧩 extensions/                 # Extension system
│   ├── dia-tts-mcp/              # Text-to-speech extension
│   └── registry.json             # Extension registry
│
└── 🛠️ tools/                      # Additional tools
    └── pdf-extractor/            # PDF processing tool
```

## 🏗️ **Design Principles**

### **Root Directory (Clean & Professional)**
- **Primary executables** stay in root for easy access
- **Core configuration** (Docker Compose files) in root
- **Main documentation** (README.md) in root
- **No clutter** - utility files moved to appropriate subdirectories

### **Documentation (`docs/`)**
- **All detailed documentation** organized in one place
- **Easy to find** and maintain
- **Version controlled** with the code
- **Platform-specific guides** clearly separated

### **Scripts (`scripts/`)**
- **Installation scripts** for different platforms
- **Legacy scripts** maintained for backwards compatibility
- **Utility scripts** that aren't primary interfaces
- **Clear separation** from main CLI tools

### **Extensions (`extensions/`)**
- **Modular architecture** for additional functionality
- **Self-contained** extension packages
- **Registry system** for management
- **Independent** of core stack

## 🚀 **Usage Patterns**

### **New Users (Recommended)**
```bash
# Primary interface - everything through unified CLI
./ollama-stack start
./ollama-stack extensions enable dia-tts-mcp
./ollama-stack status
```

### **Installation**
```bash
# One-time setup for system-wide access
./scripts/install.sh     # Unix/macOS
.\scripts\install.ps1    # Windows
```

### **Legacy Compatibility**
```bash
# Existing workflows still work
./scripts/start-stack.sh -p nvidia
./scripts/stop-stack.sh -v
```

## 📖 **File Purpose Guide**

| File/Directory | Purpose | When to Use |
|----------------|---------|-------------|
| `ollama-stack` | **Primary CLI** | Day-to-day operations |
| `ollama-stack.ps1` | **Windows CLI** | Windows PowerShell |
| `docs/CLI_USAGE.md` | **Complete reference** | Learning all features |
| `docs/WINDOWS_SETUP.md` | **Windows guide** | Windows-specific setup |
| `scripts/install.*` | **Installation** | One-time system setup |
| `scripts/start-stack.*` | **Legacy scripts** | Backwards compatibility |
| `extensions/` | **Extensions** | Adding functionality |
| `docker-compose*.yml` | **Infrastructure** | Service configuration |

## 🔄 **Migration Path**

### **From Old Structure**
The reorganization maintains **100% backwards compatibility**:

```bash
# Old way (still works)
./start-stack.sh -p nvidia

# New way (recommended)
./ollama-stack start -p nvidia
```

### **Script Migrations**
| Old Location | New Location | Status |
|--------------|--------------|--------|
| `./start-stack.sh` | `./scripts/start-stack.sh` | Moved, still functional |
| `./install.sh` | `./scripts/install.sh` | Moved, updated paths |
| `./CLI_USAGE.md` | `./docs/CLI_USAGE.md` | Moved, content enhanced |

## 🎯 **Benefits of New Structure**

### **For Users**
- ✅ **Cleaner root directory** - easier to navigate
- ✅ **Obvious entry points** - `ollama-stack` is clearly the main tool
- ✅ **Better documentation discovery** - all guides in `docs/`
- ✅ **Professional appearance** - follows open source standards

### **For Developers**
- ✅ **Logical organization** - files grouped by purpose
- ✅ **Easier maintenance** - related files together
- ✅ **Clear separation** - CLI vs scripts vs docs vs extensions
- ✅ **Standard conventions** - matches other professional projects

### **For Project Health**
- ✅ **Scalable structure** - room for growth
- ✅ **Contributor friendly** - obvious where things go
- ✅ **Maintainable** - clear file purposes
- ✅ **Professional standards** - industry best practices

## 🚀 **Future Additions**

The new structure provides clear patterns for:

- **New documentation** → `docs/`
- **Utility scripts** → `scripts/`
- **Extensions** → `extensions/`
- **Tools** → `tools/`
- **Primary features** → Root level CLI tools

## 📋 **Quick Reference**

### **I want to...**
- **Start using the stack** → `./ollama-stack start`
- **Install for system-wide use** → `./scripts/install.sh`
- **Learn all features** → `docs/CLI_USAGE.md`
- **Set up on Windows** → `docs/WINDOWS_SETUP.md`
- **Use legacy scripts** → `./scripts/start-stack.sh`
- **Understand the implementation** → `docs/UNIFIED_CLI_SUMMARY.md`
- **Add an extension** → `extensions/` directory
- **Modify Docker config** → `docker-compose*.yml`

This organization transforms the project from a **collection of scripts** into a **professional, maintainable CLI application** while preserving all existing functionality. 