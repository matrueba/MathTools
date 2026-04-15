from rich.console import Console
import questionary

console = Console()

# Shared questionary styles
QUESTIONARY_STYLE = questionary.Style([
    ('qmark', 'fg:#00ffff bold'),
    ('question', 'bold'),
    ('pointer', 'fg:#ff00ff bold'),
    ('highlighted', 'fg:#ff00ff bold'),
    ('selected', 'fg:#00ff00'),
])
