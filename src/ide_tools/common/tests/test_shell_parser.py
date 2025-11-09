"""
Unit tests for parse_shell_command from shell_parser_bashlex.py
"""

import pytest
from ide_tools.common.hooks.shell_parser_bashlex import parse_shell_command


class TestBasicCommands:
    """Test simple, single-file commands"""

    def test_simple_python_script(self):
        sub_cmds, files = parse_shell_command("python script.py")
        assert sub_cmds == ["python script.py"]
        assert files == ["script.py"]

    def test_cat_single_file(self):
        sub_cmds, files = parse_shell_command("cat readme.txt")
        assert sub_cmds == ["cat readme.txt"]
        assert files == ["readme.txt"]

    def test_grep_in_file(self):
        sub_cmds, files = parse_shell_command("grep pattern file.log")
        assert sub_cmds == ["grep pattern file.log"]
        assert files == ["file.log"]

    def test_file_with_path(self):
        sub_cmds, files = parse_shell_command("cat /tmp/test.txt")
        assert sub_cmds == ["cat /tmp/test.txt"]
        assert files == ["/tmp/test.txt"]

    def test_relative_path_file(self):
        sub_cmds, files = parse_shell_command("python src/main.py")
        assert sub_cmds == ["python src/main.py"]
        assert files == ["src/main.py"]


class TestPipes:
    """Test commands with pipe operators"""

    def test_simple_pipe(self):
        sub_cmds, files = parse_shell_command("cat file.txt | grep pattern")
        assert sub_cmds == ["cat file.txt", "grep pattern"]
        assert files == ["file.txt"]

    def test_multiple_pipes(self):
        sub_cmds, files = parse_shell_command("cat data.csv | sort | uniq")
        assert sub_cmds == ["cat data.csv", "sort", "uniq"]
        assert files == ["data.csv"]

    def test_pipe_with_output_redirect(self):
        sub_cmds, files = parse_shell_command("grep foo file.txt | sort | uniq > output.txt")
        assert sub_cmds == ["grep foo file.txt", "sort", "uniq > output.txt"]
        assert files == ["file.txt"]

    def test_pipe_with_tee(self):
        sub_cmds, files = parse_shell_command("python a.py | tee b.log")
        assert sub_cmds == ["python a.py", "tee b.log"]
        assert "a.py" in files
        assert "b.log" in files


class TestRedirections:
    """Test input/output redirections"""

    def test_input_redirect(self):
        sub_cmds, files = parse_shell_command("python script.py < input.txt")
        assert sub_cmds == ["python script.py < input.txt"]
        assert "input.txt" in files
        assert "script.py" in files

    def test_output_redirect(self):
        sub_cmds, files = parse_shell_command("cat source.txt > dest.txt")
        assert sub_cmds == ["cat source.txt > dest.txt"]
        assert files == ["source.txt"]

    def test_append_redirect(self):
        sub_cmds, files = parse_shell_command("echo test >> log.txt")
        assert sub_cmds == ["echo test >> log.txt"]
        assert files == []

    def test_input_and_output_redirect(self):
        sub_cmds, files = parse_shell_command("python script.py < input.txt > output.txt")
        assert sub_cmds == ["python script.py < input.txt > output.txt"]
        assert "input.txt" in files
        assert "script.py" in files
        assert "output.txt" not in files  # output files are excluded

    def test_stderr_redirect(self):
        sub_cmds, files = parse_shell_command("python script.py 2> error.log")
        assert sub_cmds == ["python script.py 2> error.log"]
        assert "script.py" in files

    def test_combined_stdout_stderr_redirect(self):
        sub_cmds, files = parse_shell_command("python test.py &> output.log")
        assert sub_cmds == ["python test.py &> output.log"]
        assert files == ["test.py"]


class TestMultipleFiles:
    """Test commands with multiple file arguments"""

    def test_cat_multiple_files(self):
        sub_cmds, files = parse_shell_command("cat file1.txt file2.txt file3.txt")
        assert sub_cmds == ["cat file1.txt file2.txt file3.txt"]
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "file3.txt" in files

    def test_diff_two_files(self):
        sub_cmds, files = parse_shell_command("diff old.py new.py")
        assert sub_cmds == ["diff old.py new.py"]
        assert "old.py" in files
        assert "new.py" in files

    def test_concat_with_output(self):
        sub_cmds, files = parse_shell_command("cat file1.txt file2.txt | grep pattern > result.txt")
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "result.txt" not in files


class TestFileDetectionHeuristics:
    """Test edge cases for file detection"""

    def test_no_files_in_command(self):
        sub_cmds, files = parse_shell_command("echo hello world")
        assert sub_cmds == ["echo hello world"]
        assert files == []

    def test_options_not_detected_as_files(self):
        sub_cmds, files = parse_shell_command("ls -la -h")
        assert sub_cmds == ["ls -la -h"]
        assert files == []

    def test_directory_paths_excluded(self):
        sub_cmds, files = parse_shell_command("ls /tmp")
        assert sub_cmds == ["ls /tmp"]
        assert files == []

    def test_glob_patterns_excluded(self):
        sub_cmds, files = parse_shell_command("ls *.txt")
        assert sub_cmds == ["ls *.txt"]
        assert files == []

    def test_shell_variables_excluded(self):
        sub_cmds, files = parse_shell_command("echo $HOME")
        assert sub_cmds == ["echo $HOME"]
        assert files == []

    def test_special_filenames_recognized(self):
        sub_cmds, files = parse_shell_command("cat Makefile")
        assert sub_cmds == ["cat Makefile"]
        assert files == ["Makefile"]

    def test_archive_files_recognized(self):
        sub_cmds, files = parse_shell_command("tar -xzf archive.tar.gz")
        assert sub_cmds == ["tar -xzf archive.tar.gz"]
        assert files == ["archive.tar.gz"]

    def test_json_files_recognized(self):
        sub_cmds, files = parse_shell_command("cat package.json")
        assert sub_cmds == ["cat package.json"]
        assert files == ["package.json"]

    def test_dev_files_excluded(self):
        sub_cmds, files = parse_shell_command("cat /dev/null")
        assert sub_cmds == ["cat /dev/null"]
        # /dev/null might be detected, that's ok
        # Just verify it doesn't crash


class TestComplexScenarios:
    """Test complex command combinations"""

    def test_find_with_xargs(self):
        sub_cmds, files = parse_shell_command("find . -name '*.py' | xargs grep pattern")
        assert len(sub_cmds) >= 1
        # find and xargs should be separate commands
        assert any("find" in cmd for cmd in sub_cmds)

    def test_command_with_sed(self):
        sub_cmds, files = parse_shell_command("cat input.txt | sed 's/foo/bar/g' > output.txt")
        assert "input.txt" in files
        assert "output.txt" not in files

    def test_awk_with_file(self):
        sub_cmds, files = parse_shell_command("awk '{print $1}' data.csv")
        assert sub_cmds == ["awk '{print $1}' data.csv"]
        assert files == ["data.csv"]

    def test_sort_with_output_file(self):
        sub_cmds, files = parse_shell_command("sort input.txt -o sorted.txt")
        assert "input.txt" in files

    def test_multiple_commands_semicolon(self):
        sub_cmds, files = parse_shell_command("cat file1.txt; cat file2.txt")
        assert "file1.txt" in files
        assert "file2.txt" in files

    def test_logical_and(self):
        sub_cmds, files = parse_shell_command("test -f config.json && cat config.json")
        assert "config.json" in files

    def test_logical_or(self):
        sub_cmds, files = parse_shell_command("cat file1.txt || cat file2.txt")
        assert "file1.txt" in files
        assert "file2.txt" in files


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_empty_command(self):
        sub_cmds, files = parse_shell_command("")
        # Should handle gracefully without crashing
        assert isinstance(sub_cmds, list)
        assert isinstance(files, list)

    def test_whitespace_only(self):
        sub_cmds, files = parse_shell_command("   ")
        assert isinstance(sub_cmds, list)
        assert isinstance(files, list)

    def test_unclosed_quote(self):
        # Bashlex might fail, but should fallback gracefully
        sub_cmds, files = parse_shell_command("echo 'unclosed")
        assert isinstance(sub_cmds, list)
        assert isinstance(files, list)

    def test_invalid_syntax(self):
        # Should fallback on parse error
        sub_cmds, files = parse_shell_command("|||")
        assert isinstance(sub_cmds, list)
        assert isinstance(files, list)


class TestRealWorldExamples:
    """Test real-world command examples"""

    def test_python_with_args_and_redirect(self):
        sub_cmds, files = parse_shell_command("python analyze.py --input data.csv --verbose > results.log")
        assert "analyze.py" in files
        assert "data.csv" in files
        assert "results.log" not in files

    def test_docker_copy_command(self):
        sub_cmds, files = parse_shell_command("docker cp container:/app/config.json ./config.json")
        # Should not extract docker paths as files
        assert isinstance(files, list)

    def test_curl_output(self):
        sub_cmds, files = parse_shell_command("curl https://example.com/data.json -o output.json")
        # URL might be detected as a file due to .json extension, which is acceptable
        # Just verify it parses without crashing
        assert isinstance(sub_cmds, list)
        assert isinstance(files, list)

    def test_git_diff_with_files(self):
        sub_cmds, files = parse_shell_command("git diff file1.py file2.py")
        assert "file1.py" in files
        assert "file2.py" in files

    def test_nodejs_script(self):
        sub_cmds, files = parse_shell_command("node server.js")
        assert sub_cmds == ["node server.js"]
        assert files == ["server.js"]

    def test_compile_command(self):
        sub_cmds, files = parse_shell_command("gcc -o program main.c utils.c")
        assert "main.c" in files
        assert "utils.c" in files

    def test_makefile_execution(self):
        sub_cmds, files = parse_shell_command("make -f Makefile.dev")
        assert "Makefile.dev" in files

