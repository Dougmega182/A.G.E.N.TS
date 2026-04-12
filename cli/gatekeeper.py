"""
A.G.E.N.T.S. — Gatekeeper CLI
The command-line interface for the human Gatekeeper to interact with the system.
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich import box

from agents.core import GovernanceEngine, Agent, load_config, DATA_DIR, ensure_data_dirs
from agents.llm import LLMProvider
from agents.boardroom import Boardroom

console = Console()

# ─── Banner ───────────────────────────────────────────────

BANNER = """
[bold cyan]
     █████╗  ██████╗ ███████╗███╗   ██╗████████╗███████╗
    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝
    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████╗
    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ╚════██║
    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ███████║
    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝[/]
[dim]    Autonomous Governance & Execution Networked Task System[/]
[dim]    BUILD REV: 2.0.0  |  DOMAINS: 9  |  GATEKEEPER: ACTIVE[/]
"""


def show_banner():
    console.print(BANNER)


def show_status(gov: GovernanceEngine):
    """Show system status overview."""
    table = Table(title="SYSTEM STATUS", box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("Component", style="bold cyan")
    table.add_column("Status", style="green")

    table.add_row("Constitution", f"{len(gov.constitution['laws'])} laws active")
    table.add_row("Protocols", f"{len(gov.protocols['protocols'])} armed")
    table.add_row("Domains", f"{len(gov.departments['domain_divisions'])} active")
    table.add_row("Board Agents", f"{len(gov.voting['voting_framework']['vote_weights'])} seated")

    # Count pending items
    ensure_data_dirs()
    proposals = list((DATA_DIR / "proposals").glob("*.json"))
    tasks = list((DATA_DIR / "tasks").glob("*.json"))
    pending_proposals = sum(1 for p in proposals if json.loads(p.read_text()).get("gatekeeper_decision") is None)
    pending_tasks = sum(1 for t in tasks if json.loads(t.read_text()).get("status") == "queued")

    table.add_row("Pending Proposals", f"[yellow]{pending_proposals}[/]" if pending_proposals else "0")
    table.add_row("Queued Tasks", f"[yellow]{pending_tasks}[/]" if pending_tasks else "0")

    console.print(table)


def show_domains(gov: GovernanceEngine):
    """Show domain health dashboard."""
    table = Table(title="DOMAIN HEALTH", box=box.ROUNDED, border_style="cyan")
    table.add_column("", width=3)
    table.add_column("Domain", style="bold")
    table.add_column("Status", style="green")

    for domain in gov.departments["domain_divisions"]:
        table.add_row(domain["icon"], domain["name"], "● ONLINE")

    console.print(table)


def show_constitution(gov: GovernanceEngine):
    """Display constitutional laws."""
    console.print("\n[bold cyan]═══ CONSTITUTIONAL LAWS ═══[/]\n")
    for law in gov.constitution["laws"]:
        severity_color = {
            "ABSOLUTE": "red", "CRITICAL": "red", "CONSTITUTIONAL": "yellow",
            "MANDATORY": "yellow", "HIGH": "blue", "PROTECTED": "green"
        }.get(law["severity"], "white")
        override = "🔒 NO" if law["overrideable"] is False else f"⚠ {law['overrideable']}"
        console.print(Panel(
            f"[bold]{law['rule']}[/]\n\n"
            f"[dim]Severity:[/] [{severity_color}]{law['severity']}[/]  |  "
            f"[dim]Override:[/] {override}",
            title=f"[bold cyan]{law['id']}: {law['name']}[/]",
            border_style=severity_color
        ))


def show_protocols(gov: GovernanceEngine):
    """Display protocol definitions."""
    console.print("\n[bold cyan]═══ PROTOCOL FRAMEWORK ═══[/]\n")
    for proto in gov.protocols["protocols"]:
        color = {
            "RED-1": "red", "BLUE-1": "blue", "GOLD-1": "yellow",
            "BLACK-1": "white", "AMBER-1": "dark_orange", "GREEN-1": "green", "WHITE-1": "bright_white"
        }.get(proto["id"], "white")
        console.print(Panel(
            f"[bold]TRIGGER:[/] {proto['trigger']}\n\n"
            f"[bold]ACTION:[/] {proto['action']}\n\n"
            f"[dim]Steps:[/]\n" + "\n".join(f"  → {s}" for s in proto["steps"]),
            title=f"[bold {color}]{proto['id']}: {proto['name']}[/]",
            border_style=color
        ))


def approve_proposals(gov: GovernanceEngine):
    """Show pending proposals for Gatekeeper approval."""
    ensure_data_dirs()
    proposals_dir = DATA_DIR / "proposals"
    pending = []

    for pf in proposals_dir.glob("*.json"):
        prop = json.loads(pf.read_text())
        if prop.get("gatekeeper_decision") is None and prop.get("status") != "rejected_constitutional":
            pending.append((pf, prop))

    if not pending:
        console.print("[dim]No pending proposals.[/]")
        return

    for pf, prop in pending:
        # Check for vote record
        vote_file = DATA_DIR / "votes" / f"{prop['proposal_id']}.json"
        vote_info = ""
        if vote_file.exists():
            votes = json.loads(vote_file.read_text())
            vote_info = f"\n[bold]Board Vote:[/] YES {votes['yes_weight']:.1f} / NO {votes['no_weight']:.1f} → {votes['decision']}"

        console.print(Panel(
            f"[bold]Title:[/] {prop['title']}\n"
            f"[bold]Domain:[/] {prop['domain']}\n"
            f"[bold]Impact:[/] {prop['impact']}\n"
            f"[bold]Created by:[/] {prop['created_by']}\n"
            f"[bold]Description:[/] {prop['description']}"
            f"{vote_info}",
            title=f"[bold cyan]{prop['proposal_id']}[/]",
            border_style="cyan"
        ))

        decision = Prompt.ask(
            "  👑 Gatekeeper Decision",
            choices=["approve", "reject", "skip"],
            default="skip"
        )

        if decision in ("approve", "reject"):
            prop["gatekeeper_decision"] = decision.upper()
            prop["gatekeeper_decided_at"] = datetime.utcnow().isoformat()
            prop["status"] = "approved" if decision == "approve" else "rejected"
            with open(pf, "w", encoding="utf-8") as f:
                json.dump(prop, f, indent=2)
            color = "green" if decision == "approve" else "red"
            console.print(f"  [{color}]✓ {decision.upper()}[/]\n")


def create_proposal_flow(gov: GovernanceEngine, llm: LLMProvider):
    """Interactive flow to create a new proposal and run it through the boardroom."""
    console.print("\n[bold cyan]═══ NEW PROPOSAL ═══[/]\n")

    title = Prompt.ask("  Title")
    description = Prompt.ask("  Description")

    # Show domain options
    domains = [d["id"] for d in gov.departments["domain_divisions"]]
    domain = Prompt.ask("  Domain", choices=domains)
    impact = Prompt.ask("  Impact", choices=["low", "medium", "high", "critical"], default="medium")

    # Create proposal via CEO agent
    ceo = Agent("ceo_agent", gov)
    proposal = ceo.create_proposal(title, description, domain, impact)

    if proposal.get("status") == "rejected_constitutional":
        console.print(f"[red]✗ PROPOSAL REJECTED — Constitutional violation:[/]")
        for v in proposal["violations"]:
            console.print(f"  → {v['law']}: {v['detail']}")
        return

    console.print(f"\n[green]✓ Proposal {proposal['proposal_id']} created[/]\n")

    # Run boardroom debate
    if Confirm.ask("  Run Boardroom debate now?", default=True):
        console.print("\n[dim]  Board agents deliberating...[/]\n")
        boardroom = Boardroom(gov, llm)
        result = boardroom.debate_proposal(proposal)
        console.print(boardroom.format_result(result))

        # If approved by board, ask gatekeeper
        if result["decision"] == "APPROVED":
            decision = Prompt.ask(
                "  👑 Gatekeeper Final Decision",
                choices=["approve", "reject"],
                default="approve"
            )
            proposal["gatekeeper_decision"] = decision.upper()
            proposal["gatekeeper_decided_at"] = datetime.utcnow().isoformat()
            proposal["status"] = "approved" if decision == "approve" else "rejected"

            prop_file = DATA_DIR / "proposals" / f"{proposal['proposal_id']}.json"
            with open(prop_file, "w", encoding="utf-8") as f:
                json.dump(proposal, f, indent=2)

            color = "green" if decision == "approve" else "red"
            console.print(f"\n  [{color}]✓ {decision.upper()} by Gatekeeper[/]\n")


def show_tasks(gov: GovernanceEngine):
    """Show the task queue."""
    ensure_data_dirs()
    tasks_dir = DATA_DIR / "tasks"
    tasks = []

    for tf in tasks_dir.glob("*.json"):
        task = json.loads(tf.read_text())
        tasks.append(task)

    if not tasks:
        console.print("[dim]No tasks in queue.[/]")
        return

    table = Table(title="TASK QUEUE", box=box.ROUNDED, border_style="cyan")
    table.add_column("ID", style="cyan", width=24)
    table.add_column("Domain", style="blue")
    table.add_column("Description")
    table.add_column("Priority")
    table.add_column("Energy")
    table.add_column("Status")

    priority_colors = {"critical": "red", "high": "yellow", "medium": "blue", "low": "green"}

    for task in sorted(tasks, key=lambda t: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.get("priority", "low"), 4)):
        pc = priority_colors.get(task.get("priority", "low"), "white")
        table.add_row(
            task["task_id"],
            task.get("domain", "—"),
            task.get("description", "—")[:50],
            f"[{pc}]{task.get('priority', '—').upper()}[/]",
            task.get("energy_cost", "—"),
            task.get("status", "—")
        )

    console.print(table)


def main_loop():
    """Main CLI loop for the Gatekeeper."""
    show_banner()

    try:
        gov = GovernanceEngine()
    except FileNotFoundError as e:
        console.print(f"[red]Config error: {e}[/]")
        console.print("[dim]Run from the A.G.E.N.T.S. project root directory.[/]")
        return

    # Determine LLM provider
    provider = os.getenv("LLM_PROVIDER", "openai")
    try:
        llm = LLMProvider(provider=provider)
        console.print(f"[dim]  LLM: {provider} ({llm.model})[/]\n")
    except Exception as e:
        console.print(f"[yellow]  LLM not configured: {e}[/]")
        console.print(f"[dim]  Set OPENAI_API_KEY or OLLAMA_URL in .env[/]\n")
        llm = None

    show_status(gov)

    while True:
        console.print("\n[bold cyan]COMMAND CENTRE[/]")
        console.print("[dim]  1. Status        2. Domains       3. Constitution[/]")
        console.print("[dim]  4. Protocols     5. Proposals     6. New Proposal[/]")
        console.print("[dim]  7. Tasks         8. Audit Log     9. Exit[/]")

        choice = Prompt.ask("\n  👑", choices=["1","2","3","4","5","6","7","8","9"], default="1")

        if choice == "1":
            show_status(gov)
        elif choice == "2":
            show_domains(gov)
        elif choice == "3":
            show_constitution(gov)
        elif choice == "4":
            show_protocols(gov)
        elif choice == "5":
            approve_proposals(gov)
        elif choice == "6":
            if llm:
                create_proposal_flow(gov, llm)
            else:
                console.print("[red]LLM not configured. Set OPENAI_API_KEY or OLLAMA_URL in .env[/]")
        elif choice == "7":
            show_tasks(gov)
        elif choice == "8":
            # Show audit log
            ensure_data_dirs()
            log_file = DATA_DIR / "audit_logs" / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
            if log_file.exists():
                console.print(f"\n[bold cyan]═══ AUDIT LOG ({datetime.utcnow().strftime('%Y-%m-%d')}) ═══[/]\n")
                for line in log_file.read_text().strip().split("\n"):
                    entry = json.loads(line)
                    console.print(f"  [{entry.get('timestamp','?')[:19]}] {entry.get('agent_name','?')}: {entry.get('action','?')}")
                    if entry.get("details"):
                        console.print(f"    [dim]{json.dumps(entry['details'], indent=None)[:80]}[/]")
            else:
                console.print("[dim]No audit log for today.[/]")
        elif choice == "9":
            console.print("\n[dim]  Gatekeeper disconnected. System remains governed.[/]\n")
            break


if __name__ == "__main__":
    main_loop()
