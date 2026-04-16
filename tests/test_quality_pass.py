import sys
from pathlib import Path

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.execution_mode import ContentQuality

def test_email_quality():
    quality = ContentQuality()
    
    # CASE 1: Perfect Email
    good_email = {
        "to": "bob@example.com",
        "subject": "Project Update: Phase 3 Deployment",
        "body": "Hi Bob, I've finished the deployment of Phase 3. All servers are online and responding correctly. Let me know if you need any further details."
    }
    res = quality.check(good_email, "email_draft_v1")
    assert res.ok, f"Should pass: {res.hint}"
    
    # CASE 2: Empty Subject
    bad_subject = {
        "to": "bob@example.com",
        "subject": "",
        "body": "Hi Bob, I've finished the deployment of Phase 3. All servers are online."
    }
    res = quality.check(bad_subject, "email_draft_v1")
    assert not res.ok
    assert "Subject" in res.hint
    
    # CASE 3: Too Short
    brief_email = {
        "to": "bob@example.com",
        "subject": "Quick note",
        "body": "Done."
    }
    res = quality.check(brief_email, "email_draft_v1")
    assert not res.ok
    assert "brief" in res.hint
    
    # CASE 4: Placeholder Detected
    placeholder_email = {
        "to": "bob@example.com",
        "subject": "Meeting",
        "body": "Hi [Insert Name], the meeting is scheduled for tomorrow."
    }
    res = quality.check(placeholder_email, "email_draft_v1")
    assert not res.ok
    assert "Placeholder" in res.hint
    
    print("OK: Email Quality Tests Passed")

def test_plan_quality():
    quality = ContentQuality()
    
    # CASE 1: Good Plan
    good_plan = {
        "goal": "Deploy the system",
        "steps": [
            "Build the docker image",
            "Update the configuration files",
            "Deploy to the production environment"
        ]
    }
    res = quality.check(good_plan, "plan_v1")
    assert res.ok
    
    # CASE 2: Too Few Steps
    short_plan = {
        "goal": "Deploy",
        "steps": ["Click button", "Wait"]
    }
    res = quality.check(short_plan, "plan_v1")
    assert not res.ok
    assert "shallow" in res.hint
    
    # CASE 3: Not Actionable
    vague_plan = {
        "goal": "Thinking",
        "steps": [
            "Think about the problem",
            "Consider the options",
            "Wait for input"
        ]
    }
    res = quality.check(vague_plan, "plan_v1")
    assert not res.ok
    assert "actionable" in res.hint
    
    print("OK: Plan Quality Tests Passed")

if __name__ == "__main__":
    test_email_quality()
    test_plan_quality()
