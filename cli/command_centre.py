import sys
import os
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.columns import Columns
from agents.orchestrator import Orchestrator
from agents.roster import AGENTS

console = Console()

BANNER = """[bold cyan]
  A.G.E.N.T.S. UNIFIED COMMAND PLATFORM
  -------------------------------------
  System Mode: Multi-Agent Room (Always-On)
  Status: Online | All Specialists Present
[/]"""

AGENT_COLOURS = {
    "aria":   "cyan",
    "marcus": "red",
    "eli":    "yellow",
    "jenny":  "green",
    "owen":   "blue",
    "nadia":  "magenta",
    "james":  "orange3",
    "leo":    "bright_blue",
    "clara":  "bright_white",
    "victor": "bright_red",
    "jax":    "bright_green",
    "reese":  "bright_yellow",
    "elena":  "bright_cyan",
}

def show_roster():
    """Display all available agents in a grid."""
    panels = []
    for key, agent in AGENTS.items():
        colour = AGENT_COLOURS.get(key, "white")
        panels.append(Panel(
            f"[dim]{agent['title']}[/]",
            title=f"[bold {colour}]{agent['name']}[/]",
            border_style=colour,
            width=22
        ))
    console.print(Columns(panels))

def format_response(agent_key: str, response: str):
    """Format and display a single agent specialist's response."""
    agent = AGENTS.get(agent_key, {"name": "Unknown", "title": "Specialist"})
    colour = AGENT_COLOURS.get(agent_key, "white")
    
    console.print(Panel(
        Markdown(response),
        title=(
            f"[bold {colour}]"
            f"{agent['name']} "
            f"[dim]({agent['title']})[/]"
            f"[/]"
        ),
        border_style=colour,
        padding=(1, 2)
    ))

def main():
    console.clear()
    console.print(BANNER)
    show_roster()
    console.print(
        "\n[dim]Just start talking. I will route your message to the right specialists.[/]\n"
        "[dim]Commands: /roster | /clear | /quit[/]\n"
    )
    
    orchestrator = Orchestrator()
    
    while True:
        try:
            message = Prompt.ask(
                "\n[bold gold1]Gatekeeper[/]"
            )
            
            if not message.strip():
                continue
            
            # Internal Commands
            if message.startswith("/"):
                cmd = message.lower()
                if cmd == "/quit":
                    console.print("[dim]Command Platform offline. Session logged.[/]")
                    break
                elif cmd == "/roster":
                    show_roster()
                elif cmd == "/clear":
                    console.clear()
                    console.print(BANNER)
                    orchestrator = Orchestrator() # Reset session
                    console.print("[dim]Session reset. Roster online.[/]")
                continue
            
            # Execute Multi-Agent Strategy
            with console.status("[dim]Specialists convening...[/]", spinner="dots"):
                responses = orchestrator.chat(message)
            
            # Display results
            console.print()
            for agent_key, response in responses.items():
                format_response(agent_key, response)
                
        except KeyboardInterrupt:
            console.print("\n[dim]Safe shutdown initiated... Platform offline.[/]")
            break
        except Exception as e:
            console.print(f"[bold red]System Error:[/] {str(e)}")

if __name__ == "__main__":
    main()
