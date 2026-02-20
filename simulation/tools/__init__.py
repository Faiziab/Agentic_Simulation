"""
Agent Tool System — Registry and resolution.

Maps tool names (from agent_profiles.yaml) to callables that Gemini
can invoke via automatic function calling.

Two categories of tools:
  1. Native Gemini tools (google_search) — passed as types.Tool objects
  2. Custom Python functions (file_tools, calculator) — passed as callables
"""

from google.genai import types

from simulation.tools.file_tools import (
    read_workspace_file,
    write_workspace_file,
    list_workspace_files,
)
from simulation.tools.calculator import calculate


def resolve_tools(
    tool_names: list[str],
    workspace_dir: str,
) -> tuple[list, list]:
    """Resolve tool names → Gemini-compatible tool objects.

    Returns:
        A tuple of (native_tools, custom_functions):
        - native_tools: list of types.Tool objects (google_search, code_execution)
        - custom_functions: list of Python callables for automatic function calling
    """
    native_tools = []
    custom_functions = []

    for name in tool_names:
        if name == "google_search":
            native_tools.append(types.Tool(google_search=types.GoogleSearch()))

        elif name == "code_execution":
            native_tools.append(types.Tool(code_execution=types.ToolCodeExecution()))

        elif name == "read_workspace_file":
            # Create a closure that binds workspace_dir
            def _read(file_path: str) -> str:
                """Read a file from the shared workspace directory.
                Use this to review deliverables, reports, or outputs from other agents.

                Args:
                    file_path: Relative path within the workspace (e.g. 'departments/research/output.md')

                Returns:
                    The file contents as a string, or an error message.
                """
                return read_workspace_file(workspace_dir, file_path)

            _read.__name__ = "read_workspace_file"
            custom_functions.append(_read)

        elif name == "write_workspace_file":
            def _write(file_path: str, content: str) -> str:
                """Write content to a file in the shared workspace directory.
                Use this to save deliverables, analysis results, or outputs.

                Args:
                    file_path: Relative path within the workspace (e.g. 'shared/analysis.md')
                    content: The content to write to the file.

                Returns:
                    Confirmation message with the file path.
                """
                return write_workspace_file(workspace_dir, file_path, content)

            _write.__name__ = "write_workspace_file"
            custom_functions.append(_write)

        elif name == "list_workspace_files":
            def _list() -> str:
                """List all files in the shared workspace directory.
                Use this to discover what deliverables and outputs are available.

                Returns:
                    A formatted list of all files in the workspace.
                """
                return list_workspace_files(workspace_dir)

            _list.__name__ = "list_workspace_files"
            custom_functions.append(_list)

        elif name == "calculator":
            custom_functions.append(calculate)

    return native_tools, custom_functions
