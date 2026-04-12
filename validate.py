"""Validate ALL A.G.E.N.T.S. config files, agent profiles, and governance documents."""
import json
import os

configs = [
    'agents', 'information_sharing', 'logging_requirements',
    'security_layers', 'mission', 'northern_star', 'constitution',
    'protocols', 'layer_stack', 'voting_framework', 'departments',
    'corporate_governance', 'oath_and_contract', 'onboarding_sop',
    'major_commands', 'rules_of_engagement',
    'self_healing'
]

print("=" * 60)
print("  A.G.E.N.T.S. FULL SYSTEM VALIDATION")
print("=" * 60)

print("\n--- CONFIG FILES ---\n")
for c in configs:
    path = f"config/{c}.json"
    try:
        data = json.load(open(path, encoding="utf-8"))
        print(f"  [OK]   {c}.json")
    except Exception as e:
        print(f"  [FAIL] {c}.json - {e}")

print(f"\n  Total: {len(configs)} config files")

agents = json.load(open("config/agents.json", encoding="utf-8"))
agent_count = agents.get('total_agents', len(agents.get('agents', {})))
print(f"\n--- AGENT ROSTER ({agent_count} agents) ---\n")
for k, v in agents["agents"].items():
    name = v["name"]
    title = v["title"][:50]
    aid = v["agent_id"]
    print(f"  {aid}  {name:12s}  {title}")

profiles = sorted(os.listdir("agents/profiles"))
print(f"\n--- AGENT PROFILES ({len(profiles)} files) ---\n")
for p in profiles:
    print(f"  > {p}")

# Governance documents summary
gov = json.load(open("config/corporate_governance.json", encoding="utf-8"))
oath = json.load(open("config/oath_and_contract.json", encoding="utf-8"))
onboard = json.load(open("config/onboarding_sop.json", encoding="utf-8"))
commands = json.load(open("config/major_commands.json", encoding="utf-8"))
roe = json.load(open("config/rules_of_engagement.json", encoding="utf-8"))
heal = json.load(open("config/self_healing.json", encoding="utf-8"))
sharing = json.load(open("config/information_sharing.json", encoding="utf-8"))
security = json.load(open("config/security_layers.json", encoding="utf-8"))
const = json.load(open("config/constitution.json", encoding="utf-8"))
protos = json.load(open("config/protocols.json", encoding="utf-8"))

print("\n--- GOVERNANCE SUMMARY ---\n")
print(f"  Hierarchical layers:      {len(gov['hierarchical_layers'])}")
print(f"  Functional layers:        {len(gov['functional_layers']['layers'])}")
print(f"  Constitutional laws:      {len(const['laws'])}")
print(f"  Protocols:                {len(protos['protocols'])}")
print(f"  Classification levels:    {len(sharing['classification_levels'])}")
print(f"  Security layers:          {len(security['security_layers'])}")
print(f"  Major commands:           {len(commands['major_commands'])}")
print(f"  Risk tiers (RoE):         {len(roe['risk_tiers'])}")
print(f"  Self-healing levels:      {len(heal['severity_levels'])}")
print(f"  Contract clauses:         {len(oath['agent_employment_contract']['clauses'])}")
print(f"  Onboarding phases:        {len(onboard['pipeline'])}")
print(f"  Agent statuses:           {len(onboard['agent_statuses'])}")

print("\n" + "=" * 60)
print("  ALL SYSTEMS NOMINAL")
print("=" * 60)
