"""
Workspace file tools — sandboxed file I/O for agents.

All paths are resolved relative to the workspace directory.
Agents cannot escape the workspace sandbox.
"""

import os


def read_workspace_file(workspace_dir: str, file_path: str) -> str:
    """Read a file from the workspace directory.

    Args:
        workspace_dir: Absolute path to the workspace root.
        file_path: Relative path within the workspace.

    Returns:
        File contents or error message.
    """
    # Resolve and sandbox
    abs_path = os.path.normpath(os.path.join(workspace_dir, file_path))
    if not abs_path.startswith(os.path.normpath(workspace_dir)):
        return "Error: Cannot access files outside the workspace directory."

    if not os.path.exists(abs_path):
        return f"Error: File not found: {file_path}"

    if not os.path.isfile(abs_path):
        return f"Error: {file_path} is a directory, not a file."

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Truncate very large files
        if len(content) > 10_000:
            content = content[:10_000] + f"\n\n... [truncated, {len(content)} total characters]"
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def write_workspace_file(workspace_dir: str, file_path: str, content: str) -> str:
    """Write content to a file in the workspace directory.

    Args:
        workspace_dir: Absolute path to the workspace root.
        file_path: Relative path within the workspace.
        content: Content to write.

    Returns:
        Confirmation or error message.
    """
    abs_path = os.path.normpath(os.path.join(workspace_dir, file_path))
    if not abs_path.startswith(os.path.normpath(workspace_dir)):
        return "Error: Cannot write files outside the workspace directory."

    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_workspace_files(workspace_dir: str) -> str:
    """List all files in the workspace directory tree.

    Args:
        workspace_dir: Absolute path to the workspace root.

    Returns:
        Formatted directory listing.
    """
    files = []
    for root, dirs, filenames in os.walk(workspace_dir):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in filenames:
            rel = os.path.relpath(os.path.join(root, fname), workspace_dir)
            size = os.path.getsize(os.path.join(root, fname))
            files.append(f"  {rel} ({size:,} bytes)")

    if not files:
        return "Workspace is empty."

    return f"Workspace files ({len(files)} total):\n" + "\n".join(sorted(files))
