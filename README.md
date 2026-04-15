# MathTools AI Development Framework

A powerful CLI installer (`matrueba-sdd`) that automatically configures AI development environments by pulling core components and skills directly from GitHub. It allows you to choose which execution environment you want to set up (Gemini CLI, IDE Agents, or Opencode) and selectively download the necessary rules, workflows, commands, and skills.

## 🚀 Features

- **Multi-Environment Support:** Automatically structures directories whether you are using Gemini CLI (`.gemini/`), standard IDE Agents like Cursor/AntiGravity/Windsurf (`.agents/`), or Opencode (`.opencode/`).
- **Interactive Interface:** Allows you to interactively pick the target environments and exactly which individual components (e.g., specific skills, tools) to include or exclude using a beautiful CLI UI.
- **Multiple Repositories Integration:** Transparently pulls framework agents/rules from the core framework repository, and specific functionalities from the dedicated skills framework repository.

## 📦 Installation

To install the CLI in your system globally, run the following command in your terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/matrueba/mathtools/main/install.sh | bash
```

_(This will safely clone the repository to `~/.mathtools`, set up the python virtual environment, and create an executable symlink in `~/.local/bin/matrueba-sdd`)._

## 💻 How to Use

Once installed, navigate to the target project directory where you want to deploy the AI agents and run the installer:

```bash
matrueba-sdd
# Alternatively, you can run the file directly: python cli.py
```

The CLI will guide you through:

1. Selecting the environments you want to install.
2. Confirming if you want to overwrite any existing configuration in your current directory.
3. Deciding whether you want to install all commands, agents, and skills, or picking specific ones interactively using the spacebar checklist.

## 📚 Framework Documentation

The components downloaded by this installer come from two central repositories. Check their respective READMEs to understand the core architecture, how to instruct agents, and what skills are currently available for deployment:

- 🧠 **[Matrueba AI Development Framework](https://github.com/matrueba/matrueba-AI-development-framework)**
  Discover the core agent specifications, the standard commands, workflows, and the base rules that govern IDE integration.

- 🛠️ **[Matrueba Skills Framework](https://github.com/matrueba/matrueba-skills-framework)**
  Read about all the active skill modules (e.g. Memory management, Requirement generation), how the agents use them, and how to create new reusable capabilities.
