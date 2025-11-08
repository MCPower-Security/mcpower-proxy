#!/usr/bin/env python3
"""
Shell command parser using bashlex library.
Parses shell commands to extract sub-commands and file references using proper bash parsing.
"""

import bashlex
from typing import List, Tuple, Set, Optional


def parse_shell_command(command: str) -> Tuple[List[str], List[str]]:
    """
    Parse a shell command using bashlex and extract sub-commands and input files.
    
    Args:
        command: A shell command string (supports pipes, redirections, etc.)
    
    Returns:
        A tuple of (sub_commands, input_files) where:
        - sub_commands: List of individual commands when split by pipes
        - input_files: List of files that are used as inputs (excludes output-only files)
    
    Examples:
        >>> parse_shell_command("python a.py | tee b.log")
        (['python a.py', 'tee b.log'], ['a.py', 'b.log'])
        
        >>> parse_shell_command("cat a.txt > /tmp/b.txt")
        (['cat a.txt > /tmp/b.txt'], ['a.txt'])
        
        >>> parse_shell_command("grep foo file.txt | sort | uniq > output.txt")
        (['grep foo file.txt', 'sort', 'uniq > output.txt'], ['file.txt'])
    """
    try:
        # Parse the command into an AST
        parts = bashlex.parse(command)
    except Exception as e:
        # If parsing fails, fall back to simple split
        print(f"Warning: bashlex parsing failed: {e}")
        return ([command], [])
    
    # Extract sub-commands and files
    sub_commands = []
    all_files: Set[str] = set()
    output_files: Set[str] = set()
    
    for ast in parts:
        _extract_from_ast(ast, command, sub_commands, all_files, output_files)
    
    # Remove output-only files from the result
    input_files = sorted(list(all_files - output_files))
    
    return sub_commands, input_files


def _extract_from_ast(
    node,
    command: str,
    sub_commands: List[str],
    all_files: Set[str],
    output_files: Set[str],
    parent_is_pipe: bool = False
) -> None:
    """
    Recursively extract sub-commands and files from a bashlex AST node.
    
    Args:
        node: bashlex AST node
        command: Original command string (for extracting text)
        sub_commands: List to append sub-commands to
        all_files: Set to add all file references to
        output_files: Set to add output-only files to
        parent_is_pipe: True if parent node is a pipe operator
    """
    # Check node kind to determine type
    node_kind = getattr(node, 'kind', None)
    
    if node_kind == 'list':
        # List node contains multiple parts connected by operators
        if hasattr(node, 'parts'):
            for part in node.parts:
                _extract_from_ast(part, command, sub_commands, all_files, output_files, False)
    
    elif node_kind == 'pipeline':
        # Pipeline node - extract individual commands
        _extract_pipeline(node, command, sub_commands, all_files, output_files)
    
    elif node_kind == 'command':
        # Command node - extract the command text and analyze its parts
        if hasattr(node, 'pos'):
            start, end = node.pos
            cmd_text = command[start:end]
            sub_commands.append(cmd_text)
        
        # Extract files from command parts (arguments and redirections)
        if hasattr(node, 'parts'):
            for part in node.parts:
                part_kind = getattr(part, 'kind', None)
                if part_kind == 'redirect':
                    _extract_redirect(part, command, all_files, output_files)
                else:
                    _extract_files_from_node(part, command, all_files, output_files)
    
    elif node_kind == 'compound':
        # Compound command (like if, while, for, etc.)
        if hasattr(node, 'list'):
            for item in node.list:
                _extract_from_ast(item, command, sub_commands, all_files, output_files, False)
    
    elif node_kind == 'operator':
        # Operator node (like &&, ||, ;) - ignore
        pass
    
    elif node_kind == 'pipe':
        # Pipe node - ignore (we handle pipes at the pipeline level)
        pass


def _extract_pipeline(node, command: str, sub_commands: List[str], all_files: Set[str], output_files: Set[str]) -> None:
    """Extract commands from a pipeline node."""
    if hasattr(node, 'parts'):
        for part in node.parts:
            part_kind = getattr(part, 'kind', None)
            # Skip pipe nodes, only process commands
            if part_kind != 'pipe':
                _extract_from_ast(part, command, sub_commands, all_files, output_files, True)


def _extract_files_from_node(node, command: str, all_files: Set[str], output_files: Set[str]) -> None:
    """Extract file references from a node."""
    node_kind = getattr(node, 'kind', None)
    
    if node_kind == 'word':
        # Word node - check if it's a file reference
        word = node.word if hasattr(node, 'word') else None
        
        if word and _looks_like_file(word):
            all_files.add(word)
        
        # Recursively check parts (for command substitutions, etc.)
        if hasattr(node, 'parts'):
            for part in node.parts:
                _extract_files_from_node(part, command, all_files, output_files)
    
    elif node_kind == 'commandsubstitution':
        # Command substitution $(...) - recursively parse
        if hasattr(node, 'command'):
            _extract_from_ast(node.command, command, [], all_files, output_files, False)
    
    elif node_kind == 'processsubstitution':
        # Process substitution <(...) or >(...) - recursively parse
        if hasattr(node, 'command'):
            _extract_from_ast(node.command, command, [], all_files, output_files, False)


def _extract_redirect(redirect, command: str, all_files: Set[str], output_files: Set[str]) -> None:
    """Extract file references from redirection nodes."""
    redirect_type = getattr(redirect, 'type', None)
    
    # Get the target of the redirection
    if hasattr(redirect, 'output'):
        target = redirect.output
        target_word = target.word if hasattr(target, 'word') else None
        
        if target_word and _looks_like_file(target_word):
            # Determine if it's input or output
            if redirect_type in ('>', '>>', '>&', '>|', '&>'):
                # Output redirection
                output_files.add(target_word)
                all_files.add(target_word)
            elif redirect_type == '<':
                # Input redirection
                all_files.add(target_word)
            else:
                # Unknown, be conservative and include it
                all_files.add(target_word)


def _looks_like_file(word: str) -> bool:
    """
    Heuristic to determine if a word looks like a file path.
    
    Args:
        word: A word from the command
    
    Returns:
        True if it looks like a file path
    """
    if not word:
        return False
    
    # Filter out obvious non-files
    
    # Exclude shell glob patterns (wildcards without actual path)
    if word.startswith('*') and '/' not in word:
        return False
    
    # Exclude shell expansions and special characters
    if word.startswith('$') or '${' in word or '$(' in word:
        return False
    
    # Exclude sed/awk patterns (contain / as delimiter but are patterns)
    if word.startswith('s/') and word.count('/') >= 2:
        return False
    
    # Exclude regex patterns (contain escaped characters or special regex chars)
    if '\\' in word or word.startswith('^') or word.endswith('$'):
        return False
    
    # Exclude tokens that look like options
    if word.startswith('-') or word.startswith('+') or word.startswith('!'):
        return False
    
    # Exclude relative path references
    if word in {'.', '..'}:
        return False
    
    # Exclude common directories that are just paths (not files)
    # Like /tmp, /dev, /usr, /etc without a filename
    if word in {'/tmp', '/dev', '/usr', '/etc', '/var', '/opt', '/home'}:
        return False
    
    # Check for common file patterns
    # Has an extension (but not just an extension)
    if '.' in word and not word.startswith('.') and len(word) > 3:
        if not word.startswith('*'):
            # Make sure the extension looks reasonable (2-4 chars)
            parts = word.rsplit('.', 1)
            if len(parts) == 2 and 1 <= len(parts[1]) <= 4 and parts[1].isalnum():
                return True
    
    # Has a path separator with actual file-looking path components
    if '/' in word:
        parts = word.split('/')
        if len(parts) >= 2:
            last_part = parts[-1]
            # Last part must look like a filename
            if last_part and '.' in last_part and not last_part.startswith('*'):
                return True
    
    # Is a special path to a file (not just directory)
    if word.startswith('/dev/') and len(word) > 5:
        return True
    if word.startswith('/tmp/') and len(word) > 5:
        return True
    
    # Check for common file patterns without extensions
    filename_only = word.split('/')[-1]
    if filename_only in {'Makefile', 'README', 'LICENSE', 'Dockerfile', 'Gemfile', 'Cargo.toml', 'package.json'}:
        return True
    
    return False


# Testing
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "python a.py | tee b.log",
        "cat a.txt > /tmp/b.txt",
        "grep foo file.txt | sort | uniq > output.txt",
        "cat file1.txt file2.txt | grep pattern > result.txt",
        "python script.py < input.txt > output.txt",
        "ls -la /tmp | grep '\\.txt$' | wc -l",
        "tar -xzf archive.tar.gz",
        "find . -name '*.py' | xargs grep pattern",
    ]
    
    print("Shell Command Parser (bashlex) - Test Cases\n" + "="*60)
    for cmd in test_cases:
        try:
            sub_cmds, files = parse_shell_command(cmd)
            print(f"\nCommand: {cmd}")
            print(f"Sub-commands: {sub_cmds}")
            print(f"Input files: {files}")
        except Exception as e:
            print(f"\nCommand: {cmd}")
            print(f"Error: {e}")
