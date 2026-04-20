# MathTools AI Development Framework

```text
    __  ___          __    __    ______                  __
   /  |/  / ____ _  / /_  / /_  /_  __/ ____   ____    / /  _____
  / /|_/ / / __ `/ / __/ / __ \  / /   / __ \ / __ \  / /  / ___/
 / /  / / / /_/ / / /_  / / / / / /   / /_/ // /_/ / / /  (__  )
/_/  /_/  \__,_/  \__/ /_/ /_/ /_/    \____/ \____/ /_/  /____/

          AI Development Framework v1.1.0
```

A unified CLI ecosystem designed to supercharge AI-augmented development. **MathTools** provides the modular orchestration layer for deploying, managing, and monitoring AI agents across multiple environments.

## 🚀 Key Modules

### 📦 Modular Installer

The core deployment engine that allows you to structure your development environment with surgical precision.

- **Multi-Environment Support**: Native support for Gemini CLI (`.gemini/`), IDE Agents like AntiGravity (`.agents/`), and Opencode (`.opencode/`).
- **Selective Deployment**: Interactively pick exactly which skills, commands, and rules to install using a modern, checkbox-based CLI UI (`questionary`).
- **Multi-Repo Integration**: Orchestrates components from both the core Framework and specialized Skills repositories.

### 🧠 Memory Manager

Extends your AI agents' capabilities by connecting them to your personal or project knowledge bases.

- **Obsidian Integration**: Seamlessly link your Obsidian vaults to the framework.
- **Visual Explorer**: Explore and verify your knowledge graph directly from the terminal with interactive tree views.
- **Context Expansion**: Empower agents with long-term memory and deep project-specific documentation.

### 📊 Live Agent Monitoring

A real-time, interactive dashboard inspired by `htop` to keep track of your AI workforce in high resolution.

- **Unified Tracking**: Monitor Claude, Opencode, and Antigravity sessions in a single, aggregated view.
- **Resource Metrics**: Track real-time token usage (Input, Output, Cache), context window saturation, and provider rate limits.
- **Interactive TUI**: Live refreshes every second with optimized parsing and non-blocking keyboard controls (`[q]` to exit).

## 📦 Installation

To install **MathTools** globally on your Linux system:

```bash
curl -fsSL https://raw.githubusercontent.com/matrueba/mathtools/main/install.sh | bash
```

_This will set up the python environment and create a `matrueba-sdd` symlink in your path._

## 💻 Usage

Launch the main portal from any directory to manage your local agents:

```bash
mathtools
```

### Main Menu Options:

1. **⬇ Install or update AI framework**: Deploy agent components to your current project.
2. **🧠 Manage Agents Memory**: Link, configure, and explore your knowledge vault.
3. **📊 Monitoring Agents**: Enter the real-time agent activity dashboard.
4. **✕ Exit**: Gracefully close the framework.

## 📚 Ecosystem

The framework pulls its power from a distributed ecosystem of knowledge and capabilities:

- 🧠 **[Core Framework](https://github.com/matrueba/matrueba-AI-development-framework)**
  Agent specifications, standard commands, workflows, and base rules.

- 🛠️ **[Skills Framework](https://github.com/matrueba/matrueba-skills-framework)**
  Active skill modules (Memory management, specialized generation, tools).

---

_Built for the next generation of AI-augmented developers._
