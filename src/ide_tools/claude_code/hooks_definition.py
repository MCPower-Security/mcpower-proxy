"""
Claude Code hook definitions
"""

# Hook descriptions based on Claude Code plugin system
CLAUDE_CODE_HOOKS = {
    "UserPromptSubmit": {
        "name": "UserPromptSubmit",
        "description": "Runs when the user submits a prompt, before Claude processes it. "
                       "This allows you to add additional context based on the prompt/conversation, validate prompts, "
                       "or block certain types of prompts.",
        "version": "1.0.0"
    },
    "PreToolUse_Read": {
        "name": "PreToolUse(Read)",
        "description": "Triggered before the agent reads a file. "
                       "Runs after Claude creates tool parameters and before processing the tool call. "
                       "Allows inspection and potential blocking of file read operations.",
        "version": "1.0.0"
    },
    "PreToolUse_Grep": {
        "name": "PreToolUse(Grep)",
        "description": "Triggered before the agent searches file contents. "
                       "Runs after Claude creates tool parameters and before processing the tool call. "
                       "Allows inspection and potential blocking of file search operations.",
        "version": "1.0.0"
    },
    "PreToolUse_Bash": {
        "name": "PreToolUse(Bash)",
        "description": "Triggered before a shell command is executed by the agent. "
                       "Runs after Claude creates tool parameters and before processing the tool call. "
                       "Allows inspection and potential blocking of shell commands.",
        "version": "1.0.0"
    }
}
