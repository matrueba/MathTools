ENVIRONMENTS = {
    "gemini": {
        "label": "Gemini CLI",
        "description": "Google Gemini CLI (.gemini) – supports agents, commands & skills",
        "target_dir": ".gemini",
        "sources": [
            ("framework", "src/agents", "agents"),
            ("framework", "src/commands", "commands"),
            ("skills", "skills", "skills"),
        ],
    },
    "agents": {
        "label": "VSCode / AntiGravity / Cursor / Windsurf",
        "description": "Standard IDE agents (.agents) – supports rules, skills & workflows",
        "target_dir": ".agents",
        "sources": [
            ("framework", "src/rules", "rules"),
            ("skills", "skills", "skills"),
            ("framework", "src/workflow", "workflows"),
        ],
    },
    "opencode": {
        "label": "Opencode",
        "description": "Opencode CLI (.opencode) – supports agents, commands & skills",
        "target_dir": ".opencode",
        "sources": [
            # Opencode shares the same agent/command model as Gemini CLI
            ("framework", "src/agents", "agents"),
            ("framework", "src/commands", "commands"),
            ("skills", "skills", "skills"),
        ],
    },
}
