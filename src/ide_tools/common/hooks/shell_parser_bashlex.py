#!/usr/bin/env python3
"""
Shell command parser using bashlex library.
Parses shell commands to extract sub-commands and file references using proper bash parsing.
"""

import bashlex
import os
from typing import List, Tuple, Set, Optional, Dict


def parse_shell_command(command: str, initial_cwd: Optional[str] = None) -> Tuple[List[str], List[str]]:
    """
    Parse a shell command using bashlex and extract sub-commands and input files.
    
    Args:
        command: A shell command string (supports pipes, redirections, etc.)
        initial_cwd: Initial working directory (defaults to current directory)
    
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
    
    # Track directory changes
    context = {
        'cwd': initial_cwd or os.getcwd(),
        'file_to_cwd': {}  # Map each file to the directory it was found in
    }
    
    for ast in parts:
        _extract_from_ast(ast, command, sub_commands, all_files, output_files, False, context)
    
    # Remove output-only files from the result
    input_files = sorted(list(all_files - output_files))
    
    return sub_commands, input_files


def _extract_from_ast(
    node,
    command: str,
    sub_commands: List[str],
    all_files: Set[str],
    output_files: Set[str],
    parent_is_pipe: bool = False,
    context: Optional[Dict] = None
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
        context: Dictionary with 'cwd' for current working directory
    """
    if context is None:
        context = {'cwd': os.getcwd()}
    
    # Check node kind to determine type
    node_kind = getattr(node, 'kind', None)
    
    if node_kind == 'list':
        # List node contains multiple parts connected by operators (&&, ||, ;)
        # Process sequentially to track directory changes
        if hasattr(node, 'parts'):
            for part in node.parts:
                _extract_from_ast(part, command, sub_commands, all_files, output_files, False, context)
    
    elif node_kind == 'pipeline':
        # Pipeline node - extract individual commands
        _extract_pipeline(node, command, sub_commands, all_files, output_files, context)
    
    elif node_kind == 'command':
        # Command node - extract the command text and analyze its parts
        if hasattr(node, 'pos'):
            start, end = node.pos
            cmd_text = command[start:end]
            sub_commands.append(cmd_text)
        
        # Get the command name (first word) for context
        cmd_name = None
        if hasattr(node, 'parts') and len(node.parts) > 0:
            first_part = node.parts[0]
            if hasattr(first_part, 'word'):
                cmd_name = first_part.word
        
        # Check if this is a cd command and update context
        if cmd_name == 'cd' and hasattr(node, 'parts') and len(node.parts) > 1:
            second_part = node.parts[1]
            if hasattr(second_part, 'word'):
                target_dir = second_part.word
                # Resolve the new directory
                if os.path.isabs(target_dir):
                    context['cwd'] = target_dir
                else:
                    context['cwd'] = os.path.normpath(os.path.join(context['cwd'], target_dir))
        
        # Extract files from command parts (arguments and redirections)
        if hasattr(node, 'parts'):
            for i, part in enumerate(node.parts):
                part_kind = getattr(part, 'kind', None)
                if part_kind == 'redirect':
                    _extract_redirect(part, command, all_files, output_files, context)
                elif i > 0:  # Skip the command name itself (index 0)
                    _extract_files_from_node(part, command, all_files, output_files, cmd_name, context)
    
    elif node_kind == 'compound':
        # Compound command (like if, while, for, etc.)
        if hasattr(node, 'list'):
            for item in node.list:
                _extract_from_ast(item, command, sub_commands, all_files, output_files, False, context)
    
    elif node_kind == 'operator':
        # Operator node (like &&, ||, ;) - ignore
        pass
    
    elif node_kind == 'pipe':
        # Pipe node - ignore (we handle pipes at the pipeline level)
        pass


def _extract_pipeline(node, command: str, sub_commands: List[str], all_files: Set[str], output_files: Set[str], context: Dict) -> None:
    """Extract commands from a pipeline node."""
    if hasattr(node, 'parts'):
        for part in node.parts:
            part_kind = getattr(part, 'kind', None)
            # Skip pipe nodes, only process commands
            if part_kind != 'pipe':
                _extract_from_ast(part, command, sub_commands, all_files, output_files, True, context)


def _extract_files_from_node(node, command: str, all_files: Set[str], output_files: Set[str], cmd_name: Optional[str] = None, context: Optional[Dict] = None) -> None:
    """Extract file references from a node.
    
    Args:
        node: bashlex AST node
        command: Original command string
        all_files: Set to add all file references to
        output_files: Set to add output-only files to
        cmd_name: Name of the command this node belongs to (for context)
        context: Dictionary with 'cwd' for current working directory
    """
    if context is None:
        context = {'cwd': os.getcwd()}
    
    node_kind = getattr(node, 'kind', None)
    
    if node_kind == 'word':
        # Word node - check if it's a file reference
        word = node.word if hasattr(node, 'word') else None
        
        if word and _looks_like_file(word, cmd_name):
            # Resolve relative paths against current working directory
            resolved_path = _resolve_path(word, context['cwd'])
            all_files.add(resolved_path)
        
        # Recursively check parts (for command substitutions, etc.)
        if hasattr(node, 'parts'):
            for part in node.parts:
                _extract_files_from_node(part, command, all_files, output_files, cmd_name, context)
    
    elif node_kind == 'commandsubstitution':
        # Command substitution $(...) - recursively parse
        if hasattr(node, 'command'):
            _extract_from_ast(node.command, command, [], all_files, output_files, False, context)
    
    elif node_kind == 'processsubstitution':
        # Process substitution <(...) or >(...) - recursively parse
        if hasattr(node, 'command'):
            _extract_from_ast(node.command, command, [], all_files, output_files, False, context)


def _extract_redirect(redirect, command: str, all_files: Set[str], output_files: Set[str], context: Optional[Dict] = None) -> None:
    """Extract file references from redirection nodes."""
    if context is None:
        context = {'cwd': os.getcwd()}
    
    redirect_type = getattr(redirect, 'type', None)
    
    # Get the target of the redirection
    if hasattr(redirect, 'output'):
        target = redirect.output
        target_word = target.word if hasattr(target, 'word') else None
        
        # Redirections always point to files, not directories
        if target_word and _looks_like_file(target_word, None):
            # Resolve relative paths against current working directory
            resolved_path = _resolve_path(target_word, context['cwd'])
            
            # Determine if it's input or output
            if redirect_type in ('>', '>>', '>&', '>|', '&>'):
                # Output redirection
                output_files.add(resolved_path)
                all_files.add(resolved_path)
            elif redirect_type == '<':
                # Input redirection
                all_files.add(resolved_path)
            else:
                # Unknown, be conservative and include it
                all_files.add(resolved_path)


def _resolve_path(path: str, cwd: str) -> str:
    """
    Resolve a file path relative to a working directory.
    
    Args:
        path: File path (relative or absolute)
        cwd: Current working directory
    
    Returns:
        Absolute path
    """
    if os.path.isabs(path):
        return path
    else:
        return os.path.normpath(os.path.join(cwd, path))


def _looks_like_file(word: str, cmd_name: Optional[str] = None) -> bool:
    """
    Heuristic to determine if a word is an actual readable file path.
    Not patterns, not variables, not directories - actual files we can open.
    
    Args:
        word: A word from the command
        cmd_name: The command this word belongs to (for context)
    
    Returns:
        True if it looks like a file path
    """
    if not word:
        return False
    
    # Commands that take directory arguments, not files
    DIRECTORY_COMMANDS = {
        'cd', 'pushd', 'popd', 'mkdir', 'rmdir', 'chdir',
    }
    
    # If this is a directory command, reject all arguments
    if cmd_name and cmd_name in DIRECTORY_COMMANDS:
        return False
    
    # Exclude URLs (http://, https://, ftp://, file://, etc.)
    if '://' in word:
        return False
    
    # Exclude shell meta-characters and patterns
    if any(char in word for char in ['*', '?', '[', ']']):  # Glob patterns
        return False
    
    if '$' in word or '`' in word:  # Variables or command substitution
        return False
    
    # Exclude sed/awk patterns
    if word.startswith('s/') and word.count('/') >= 2:
        return False
    
    # Exclude regex patterns
    if word.startswith('^') or word.endswith('$'):
        return False
    
    # Exclude options
    if word.startswith('-') or word.startswith('+'):
        return False
    
    # Exclude bare dots
    if word in {'.', '..'}:
        return False
    
    # Exclude bare directories (but /tmp/file is OK)
    if word in {'/', '/tmp', '/dev', '/usr', '/etc', '/var', '/opt', '/home'}:
        return False
    
    # --- POSITIVE CHECKS ---
    
    # Has extension = very likely a file
    if '.' in word and not word.startswith('.'):
        # Get the extension
        parts = word.rsplit('.', 1)
        if len(parts) == 2:
            name, ext = parts
            # Be more permissive with extensions
            if name and ext and ext.replace('_', '').replace('-', '').isalnum():
                if len(ext) <= 10:  # Most extensions are < 10 chars
                    return True
    
    # Has path separator = could be a file
    if '/' in word:
        # Check if it's a path to something specific (not just dirs)
        if not word.endswith('/'):  # Not ending with / (directory indicator)
            parts = word.split('/')
            last_part = parts[-1] if parts else ''
            
            # If last part has extension, definitely a file
            if '.' in last_part and not last_part.startswith('.'):
                return True
            
            # If it's under specific directories that contain files
            if word.startswith('/dev/') and len(word) > 5:  # /dev/null, /dev/tty, etc.
                return True
            if word.startswith('/tmp/') and len(word) > 5:  # /tmp/anything
                return True
            if word.startswith('/etc/') and len(word) > 5:  # /etc/passwd, etc.
                return True
            if word.startswith('/usr/bin/') and len(word) > 9:  # Executables
                return True
            if word.startswith('/usr/local/bin/') and len(word) > 15:
                return True
            
            # If last part looks like a filename (even without extension)
            if last_part and last_part.replace('-', '').replace('_', '').isalnum():
                # Could be an executable or script
                return True
    
    # Check for well-known files without extensions (case-insensitive)
    filename_only = word.split('/')[-1].lower()
    if filename_only in {'makefile', 'readme', 'license', 'dockerfile', 
                         'gemfile', 'rakefile', 'procfile', 'vagrantfile',
                         'jenkinsfile', 'cakefile', 'gulpfile', 'gruntfile',
                         'brewfile', 'berksfile', 'guardfile', 'fastfile',
                         'cartfile', 'appfile', 'podfile', 'snapfile'}:
        return True
    
    # Stand-alone word without path - be conservative
    if '/' not in word:
        # If it has an extension, probably a file in current directory
        if '.' in word and not word.startswith('.'):
            return True
        
        # Well-known executable names without extensions
        if word in {'script', 'run', 'build', 'test', 'deploy', 'install',
                   'configure', 'setup', 'bootstrap', 'init'}:
            return True
        
        # Otherwise, we can't be sure it's a file (could be a command)
        return False
    
    return False


# Testing
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "cd /Users/user/src/project/server && python test.py",
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
