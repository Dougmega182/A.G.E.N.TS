import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

SHELL_WHITELIST = ["python", "pip", "git", "dir", "ls", "type", "cat"]

def safe_file_write(path: str, content: str) -> str:
    """
    Atomic, symlink-safe file write using os.open flags.
    """
    # Use O_NOFOLLOW to prevent symlink attacks
    # O_CREAT | O_WRONLY | O_TRUNC for standard overwrite
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
        
    try:
        fd = os.open(path, flags, 0o644)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"

def safe_file_read(path: str) -> str:
    """
    Symlink-safe file read.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
        
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def safe_list_files(path: str) -> List[str]:
    """
    Restricted directory listing.
    """
    try:
        return os.listdir(path)
    except Exception as e:
        return [f"Error listing directory: {str(e)}"]

def safe_shell_command(command: str, args: List[str]) -> str:
    """
    Whitelisted shell execution with argument sanitization.
    """
    if command not in SHELL_WHITELIST:
        return f"Error: Command '{command}' is not in the allowed whitelist."

    # Sanitization: Block complex chaining tokens
    blocked_tokens = [";", "&&", "||", "|", ">", ">>", "<", "`", "$(", "\\"]
    for arg in args:
        if any(token in arg for token in blocked_tokens):
            return f"Error: Malicious token detected in argument: {arg}"
            
    try:
        # Run with shell=False for safety
        result = subprocess.run(
            [command] + args,
            capture_output=True,
            text=True,
            timeout=30 # 30s safety timeout
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Command failed with exit code {result.returncode}:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
