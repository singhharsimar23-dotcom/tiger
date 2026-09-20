import os
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_directories_exist():
    """Verify all scaffold directories exist."""
    required_dirs = [
        "schema",
        "queries",
        "tools",
        "retrieval",
        "agent",
        "innovation",
        "output",
        "benchmark",
        "dashboard/templates",
        "dashboard/static",
        "docs",
        "outputs/cases",
        "data",
    ]
    for d in required_dirs:
        dir_path = REPO_ROOT / d
        assert dir_path.is_dir(), f"Required directory missing: {d}"
        gitkeep_path = dir_path / ".gitkeep"
        assert gitkeep_path.is_file(), f".gitkeep missing in: {d}"

def test_python_packages_initialized():
    """Verify __init__.py exists in all Python package directories."""
    required_init_dirs = [
        "tools",
        "agent",
        "retrieval",
        "schema",
        "queries",
        "innovation",
        "benchmark",
        "dashboard",
    ]
    for d in required_init_dirs:
        init_file = REPO_ROOT / d / "__init__.py"
        assert init_file.is_file(), f"__init__.py missing in {d}"

def test_requirements_packages():
    """Verify requirements.txt exists and contains all required packages."""
    req_file = REPO_ROOT / "requirements.txt"
    assert req_file.is_file(), "requirements.txt does not exist"
    
    content = req_file.read_text(encoding="utf-8")
    
    required_packages = [
        "tigergraph-mcp",
        "pyTigerGraph",
        "langgraph",
        "langchain-mcp-adapters",
        "google-generativeai",
        "sentence-transformers",
        "torch",
        "pandas",
        "numpy",
        "scikit-learn",
        "fastapi",
        "uvicorn",
        "jinja2",
        "python-multipart",
        "httpx",
        "sse-starlette",
        "pydantic",
        "python-dotenv",
        "python-dateutil",
        "faker",
        "pytest",
        "pytest-asyncio",
    ]
    
    for pkg in required_packages:
        assert pkg.lower() in content.lower(), f"Package {pkg} not found in requirements.txt"

def test_env_example_keys():
    """Verify .env.example exists and contains all required configuration keys."""
    env_file = REPO_ROOT / ".env.example"
    assert env_file.is_file(), ".env.example does not exist"
    
    lines = env_file.read_text(encoding="utf-8").splitlines()
    env_keys = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            env_keys.add(key)
            
    required_keys = [
        "TG_HOST",
        "TG_GRAPHNAME",
        "TG_USERNAME",
        "TG_PASSWORD",
        "TG_SECRET",
        "TG_TOKEN",
        "GEMINI_API_KEY",
        "EMBEDDING_MODEL",
        "HOST",
        "PORT",
        "ENVIRONMENT",
    ]
    
    for key in required_keys:
        assert key in env_keys, f"Environment variable {key} missing from .env.example"

def test_root_files_exist():
    """Verify core root documentation and tracking files exist."""
    required_files = [
        ".gitignore",
        "PROJECT.md",
        "TASKS.md",
        "SESSION_LOG.md",
    ]
    for f in required_files:
        file_path = REPO_ROOT / f
        assert file_path.is_file(), f"Required root file missing: {f}"
