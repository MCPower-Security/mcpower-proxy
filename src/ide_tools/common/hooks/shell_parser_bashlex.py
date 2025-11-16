#!/usr/bin/env python3
"""
Shell command parser using bashlex library.
Parses shell commands to extract sub-commands, file references, and package execution commands
using proper bash parsing.
"""

import os
from typing import List, Set, Optional, Dict

import bashlex

# Comprehensive mapping of package execution tools to their ecosystems
# Format: (tool_command, ecosystem)
PACKAGE_TOOL_MAPPINGS = [
    # Node.js ecosystem
    ("npm install", "node"),
    ("npm install -g", "node"),
    ("npm i", "node"),
    ("npm exec", "node"),
    ("pnpm install", "node"),
    ("pnpm i", "node"),
    ("yarn global add", "node"),
    ("yarn add", "node"),
    ("npx", "node"),
    ("bunx", "node"),
    ("pnpx", "node"),
    ("yarn dlx", "node"),
    ("bower install", "node"),
    ("jspm install", "node"),
    ("component install", "node"),
    ("volo add", "node"),
    ("ender build", "node"),
    ("volta run", "node"),
    
    # Python ecosystem
    ("python3 -m pip install", "python"),
    ("python -m pip install", "python"),
    ("uv pip install", "python"),
    ("uv add", "python"),
    ("pip3 install", "python"),
    ("pip install", "python"),
    ("poetry add", "python"),
    ("poetry run", "python"),
    ("uvx", "python"),
    ("pipx run", "python"),
    ("pipx install", "python"),
    ("pip-run", "python"),
    ("pypi-run", "python"),
    ("conda install", "python"),
    ("mamba install", "python"),
    ("pixi run", "python"),
    ("micromamba install", "python"),
    ("pyenv install", "python"),
    
    # Deno
    ("deno run", "deno"),
    ("deno install", "deno"),
    
    # Rust
    ("cargo add", "rust"),
    ("cargo install", "rust"),
    ("cargo run", "rust"),
    ("cargo-binstall", "rust"),
    ("cargo quickinstall", "rust"),
    ("rustup run", "rust"),
    
    # Go
    ("go install", "go"),
    ("go run", "go"),
    
    # Ruby
    ("bundle add", "ruby"),
    ("bundle exec", "ruby"),
    ("gem install", "ruby"),
    ("rbenv install", "ruby"),
    
    # Java/JVM
    ("coursier launch", "java"),
    ("cs launch", "java"),
    ("mvn exec:java", "java"),
    ("gradle run", "java"),
    ("ant run", "java"),
    ("jbang", "java"),
    ("jgo", "java"),
    
    # Scala
    ("sbt run", "scala"),
    ("mill run", "scala"),
    ("ammonite", "scala"),
    
    # Clojure
    ("lein run", "clojure"),
    ("clj -Sdeps", "clojure"),
    ("babashka", "clojure"),
    ("clj", "clojure"),
    ("bb", "clojure"),
    
    # Nix
    ("nix-shell -p", "nix"),
    ("nix run", "nix"),
    ("nix shell", "nix"),
    
    # Guix (GNU's functional package manager)
    ("guix shell", "guix"),
    
    # Docker/Containers
    ("docker run", "docker"),
    ("podman run", "docker"),
    ("kubectl run", "docker"),
    
    # Haskell
    ("stack run", "haskell"),
    ("cabal run", "haskell"),
    ("ghcup install", "haskell"),
    
    # OCaml
    ("opam install", "ocaml"),
    ("esy", "ocaml"),
    
    # Elixir
    ("mix run", "elixir"),
    
    # Dart
    ("dart pub global activate", "dart"),
    ("flutter pub run", "dart"),
    ("pub global activate", "dart"),
    
    # PHP
    ("composer global require", "php"),
    ("composer global", "php"),
    ("phive install", "php"),
    
    # Perl
    ("cpanm", "perl"),
    ("cpm install", "perl"),
    ("ppm install", "perl"),
    
    # Lua
    ("luarocks install", "lua"),
    
    # Swift
    ("mint run", "swift"),
    ("marathon run", "swift"),
    ("carthage update", "swift"),
    
    # WebAssembly
    ("wasmer run", "wasm"),
    ("wapm install", "wasm"),
    
    # C/C++
    ("conan install", "cpp"),
    ("vcpkg install", "cpp"),
    ("clib install", "cpp"),
    ("buckaroo install", "cpp"),
    
    # Linux containers/sandboxing
    ("flatpak run", "linux"),
    ("snap run", "linux"),
    
    # System package managers
    ("chocolatey install", "system"),
    ("apt-get install", "system"),
    ("brew install", "system"),
    ("apt install", "system"),
    ("yum install", "system"),
    ("dnf install", "system"),
    ("pacman -S", "system"),
    ("scoop install", "system"),
    ("winget install", "system"),
    ("choco install", "system"),
    ("apk add", "system"),
    ("pkg install", "system"),
    ("emerge", "system"),
    ("zypper install", "system"),
    ("xbps-install", "system"),
    ("pkgin install", "system"),
    ("opkg install", "system"),
    
    # Version managers
    ("asdf install", "version"),
    ("volta install", "version"),
    ("fnm use", "version"),
    ("juliaup add", "version"),
    
    # HPC
    ("spack install", "hpc"),
    ("easybuild", "hpc"),
    
    # Build systems
    ("bazel run", "build"),
    ("buck2 run", "build"),
    ("earthly", "build"),
    ("pants run", "build"),
    
    # Other
    ("raco pkg install", "racket"),
    ("tlmgr install", "tex"),
    ("roswell install", "lisp"),
    ("nimble install", "nim"),
    ("shards install", "crystal"),
    ("elm install", "elm"),
    ("zig fetch", "zig"),
    ("quicklisp", "lisp"),
]

# Sort by number of words (descending) to match longer patterns first
PACKAGE_TOOL_MAPPINGS.sort(key=lambda x: len(x[0].split()), reverse=True)


def _is_package_like(token: str) -> bool:
    """
    Check if a token looks like a package name.
    
    Package indicators:
    - Contains @ (scoped or versioned): @babel/core, package@1.2.0
    - Contains / (scoped or path): @types/node, github:user/repo
    - Contains : (URL or Docker image): python:3.11-slim, git+https://...
    - Contains # (Nix packages): nixpkgs#cowsay
    - Contains + (build targets): +build, +test
    - Contains [ ] (pip extras): apache-airflow[postgres]
    - Alphanumeric with - or _ : express, my-package
    
    But NOT:
    - File paths: ./script.sh, ../package (but allow // for Bazel)
    - Common non-package commands
    - Shell constructs
    """
    # Exclude shell constructs
    if token in ('&&', '||', '|', '>', '<', '>>', '<<'):
        return False
    
    # Exclude flags
    if token.startswith('-'):
        return False
    
    # Exclude relative file paths (., .., ./, ../)
    if token in ('.', '..') or token.startswith('./') or token.startswith('../'):
        return False
    
    # Handle paths starting with /
    if token.startswith('/'):
        # Allow // for Bazel targets (e.g., //my:target)
        if token.startswith('//'):
            return True
        # Reject absolute paths like /usr/bin, /etc/config
        return False
    
    # Allow file:// URLs for npm/pip
    if token.startswith('file://'):
        return True
    
    # Common commands that are never packages when standalone
    common_commands = {
        'test', 'start', 'dev', 'prod', 'serve', 'watch',
        'lint', 'format', 'check', 'clean', 'deploy'
    }
    if token.lower() in common_commands:
        return False
    
    # Pure version numbers aren't packages (e.g., "2.0.0")
    if token.replace('.', '').replace('-', '').isdigit():
        return False
    
    # Looks like a package if it contains package-like patterns
    if any(c in token for c in ['@', '/', ':', '-', '_', '.', '#', '+', '[', ']']):
        return True
    
    # Or if it's a simple name (alphanumeric, possibly with - or _)
    return token.replace('-', '').replace('_', '').isalnum()


def _extract_packages_from_tokens(tokens: List[str], start_idx: int, tool_pattern: str) -> List[str]:
    """
    Extract potentially multiple packages starting from start_idx.
    
    Args:
        tokens: Command tokens
        start_idx: Index to start extracting from
        tool_pattern: The tool pattern being matched (for special handling)
    
    Returns:
        List of package names
    """
    packages = []
    i = start_idx
    
    # Special handling for specific tools
    is_docker = 'docker' in tool_pattern or 'podman' in tool_pattern or 'kubectl' in tool_pattern
    is_install = 'install' in tool_pattern or 'add' in tool_pattern
    is_version_manager = any(x in tool_pattern for x in ['pyenv', 'rbenv', 'fnm', 'juliaup', 'asdf', 'volta'])
    is_pip_like = 'pip' in tool_pattern or 'npm' in tool_pattern or 'yarn' in tool_pattern
    
    # Flags that take arguments (non-package arguments)
    flags_with_args = {
        '-o', '--output', '-f', '--file', '-p', '--port', 
        '-d', '--dir', '--directory', '-n', '--name',
        '--version', '-v', '-e'  # -e can mean various things
    }
    
    # Flags where the argument IS the package
    package_flags = {'--package'}
    
    # Flags that mean "skip package extraction" (only for pip/npm/yarn)
    skip_package_flags_pip = {'-e', '--editable', '-r', '--requirement', '--requirements'}
    
    while i < len(tokens):
        token = tokens[i]
        
        # Skip flags and their potential arguments
        if token.startswith('-'):
            # Check if this flag takes an argument
            base_flag = token.split('=')[0]  # Handle --flag=value format
            
            i += 1
            
            # Special case: flags that mean we should skip their argument (pip/npm only)
            # But continue processing for other packages (e.g., pip install -r req.txt requests)
            if is_pip_like and base_flag in skip_package_flags_pip:
                # Skip the file/path argument
                if i < len(tokens) and not tokens[i].startswith('-'):
                    i += 1
                continue  # Continue to look for more packages after the file
            
            # Special case: --package flag's argument IS the package
            if base_flag in package_flags and i < len(tokens):
                packages.append(tokens[i])
                i += 1
                continue
            
            # If flag takes argument and next token doesn't start with -, skip it
            if base_flag in flags_with_args and i < len(tokens) and not tokens[i].startswith('-'):
                i += 1
            continue
        
        # For version managers, even version numbers are valid "packages"
        if is_version_manager:
            packages.append(token)
            i += 1
            break
        
        # Check if this looks like a package name
        if _is_package_like(token):
            packages.append(token)
            i += 1
            
            # For Docker/container tools, typically only one image
            if is_docker:
                break
            
            # Continue collecting packages for install/add commands
            if is_install:
                continue
            
            # For run/exec tools, first package is usually it
            break
        else:
            # Hit a non-package argument (like a script name or command)
            break
    
    return packages


def _extract_packages_from_commands(sub_commands: List[str]) -> Dict[str, List[str]]:
    """
    Extract package names from shell commands that use package execution tools.
    
    Args:
        sub_commands: List of individual command strings
    
    Returns:
        Dictionary mapping ecosystem names to lists of package names
        Example: {"node": ["prettier", "eslint", "@babel/core"], "python": ["ruff"]}
    """
    packages: Dict[str, List[str]] = {}
    
    for command in sub_commands:
        # Use bashlex.split() to handle quoted strings properly
        try:
            tokens = list(bashlex.split(command))
        except (ValueError, bashlex.errors.ParsingError):
            # If bashlex fails (unclosed quotes, etc.), fall back to simple split
            tokens = command.split()
            
        if not tokens:
            continue
        
        for tool_pattern, ecosystem in PACKAGE_TOOL_MAPPINGS:
            tool_tokens = tool_pattern.split()
            num_words = len(tool_tokens)
            
            if len(tokens) >= num_words:
                matches = True
                for i, tool_token in enumerate(tool_tokens):
                    # Handle special cases like flags in patterns
                    if tool_token.startswith('-'):
                        if tokens[i] != tool_token:
                            matches = False
                            break
                    elif tokens[i].lower() != tool_token.lower():
                        matches = False
                        break
                
                if matches:
                    found_packages = _extract_packages_from_tokens(tokens, num_words, tool_pattern)
                    
                    if found_packages:
                        if ecosystem not in packages:
                            packages[ecosystem] = []
                        
                        for pkg in found_packages:
                            if pkg not in packages[ecosystem]:
                                packages[ecosystem].append(pkg)
                    
                    # Found a match, no need to check other patterns for this command
                    break
    
    return packages


def parse_shell_command(command: str, initial_cwd: Optional[str] = None) -> Dict[str, any]:
    """
    Parse a shell command using bashlex and extract sub-commands, input files, and packages.
    
    Args:
        command: A shell command string (supports pipes, redirections, etc.)
        initial_cwd: Initial working directory (defaults to current directory)
    
    Returns:
        A dictionary with the following keys:
        - sub_commands: List of individual commands when split by pipes
        - input_files: List of files that are used as inputs (excludes output-only files)
        - packages: Dictionary mapping ecosystem names to lists of package names
    
    Examples:
        >>> result = parse_shell_command("python a.py | tee b.log")
        >>> result["sub_commands"]
        ['python a.py', 'tee b.log']
        >>> result["input_files"]
        ['a.py', 'b.log']
        
        >>> result = parse_shell_command("uvx ruff check && npx prettier --write .")
        >>> result["packages"]
        {'python': ['ruff'], 'node': ['prettier']}
        
        >>> result = parse_shell_command("docker run python:3.11 -c 'import sys'")
        >>> result["packages"]
        {'docker': ['python:3.11']}
    """
    try:
        # Parse the command into an AST
        parts = bashlex.parse(command)
    except Exception as e:
        # If parsing fails, fall back to simple split
        print(f"Warning: bashlex parsing failed: {e}")
        return {
            "sub_commands": [command],
            "input_files": [],
            "packages": {}
        }
    
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
    
    # Extract packages from sub-commands
    packages = _extract_packages_from_commands(sub_commands)
    
    return {
        "sub_commands": sub_commands,
        "input_files": input_files,
        "packages": packages
    }


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
        "npx awesome-encoder && uvx fastmcp && pip install -r requirements.txt lib1 lib2",
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
            result = parse_shell_command(cmd)
            print(f"\nCommand: {cmd}")
            print(f"Sub-commands: {result['sub_commands']}")
            print(f"Input files: {result['input_files']}")
            print(f"Packages: {result['packages']}")
        except Exception as e:
            print(f"\nCommand: {cmd}")
            print(f"Error: {e}")
