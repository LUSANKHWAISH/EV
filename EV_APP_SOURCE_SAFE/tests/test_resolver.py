import pytest
from core.resolver import CommandResolver
from core.models import AgentAction

def test_resolve_find_process():
    resolver = CommandResolver()
    task = resolver.resolve("find process explorer.exe")
    assert task.action == AgentAction.FIND_PROCESS
    assert task.parameters["name"] == "explorer.exe"

def test_resolve_list_dir():
    resolver = CommandResolver()
    task = resolver.resolve("list dir C:\\Windows")
    assert task.action == AgentAction.LIST_DIRECTORY
    assert task.parameters["path"] == "C:\\Windows"

def test_resolve_unknown():
    resolver = CommandResolver()
    with pytest.raises(ValueError, match="Could not resolve command intent"):
        resolver.resolve("open Chrome")

def test_resolve_missing_args():
    resolver = CommandResolver()
    with pytest.raises(ValueError, match="find process requires a process name"):
        resolver.resolve("find process ")
