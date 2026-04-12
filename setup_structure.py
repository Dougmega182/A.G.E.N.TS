import os
import json

# Define the structure based on the new Corporate Model
departments = {
    "Operations": ["Generative Operations", "Multi-Agent Collaboration", "Mission Delivery"],
    "Intelligence": ["Intelligence Analysis", "Self-Learning Development", "Knowledge Management"],
    "Security": ["Cybersecurity Operations", "Agent Integrity", "Compliance Risk"],
    "Logistics": ["Self-Healing Maintenance", "Resource Infrastructure", "Sustainability Optimisation"],
    "People": ["Onboarding Induction", "Training Development", "Performance Talent", "Integrity Welfare"],
    "Corporate": ["Finance Procurement", "Legal Compliance", "Communications Stakeholder", "Internal Audit"]
}

base_path = "."
layers = ["Department Layer", "Division Layer", "Team Layer", "Individual Contributor Layer"]

for layer in layers:
    os.makedirs(os.path.join(base_path, layer), exist_ok=True)

# Create Department and Division structures with memory
for dept, divisions in departments.items():
    dept_dir = os.path.join(base_path, "Department Layer", dept)
    dept_memory = os.path.join(dept_dir, "memory")
    os.makedirs(dept_memory, exist_ok=True)
    
    # Init dept log
    with open(os.path.join(dept_memory, "department_log.jsonl"), "w") as f:
        pass
    
    for div in divisions:
        div_dir = os.path.join(base_path, "Division Layer", dept, div)
        div_memory = os.path.join(div_dir, "memory")
        os.makedirs(div_memory, exist_ok=True)
        
        # Init division log
        with open(os.path.join(div_memory, "division_log.jsonl"), "w") as f:
            pass

# Create basic agent folders for the 12 named executives as well in the Individual Contributor Layer
agents = ["Dale", "Aria", "Eli", "Marcus", "Nadia", "James", "Elena", "Leo", "Owen", "Reese", "Clara", "Victor"]
for agent in agents:
    agent_dir = os.path.join(base_path, "Individual Contributor Layer", agent)
    agent_memory = os.path.join(agent_dir, "memory")
    os.makedirs(agent_memory, exist_ok=True)
    with open(os.path.join(agent_memory, "agent_memory.jsonl"), "w") as f:
        pass

print("Corporate structure and memory logs scaffolded successfully.")
