"""Regression tests for V9 Windows PowerShell native -c quoting bug."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_powershell_does_not_pass_inline_python_code():
    launcher = (ROOT / 'START-BRIGHTSPEAK.ps1').read_text(encoding='utf-8')
    assert "& $python 'scripts/preflight.py'" in launcher
    assert "& $python -c" not in launcher
    assert "& py \"-$ver\" -c" not in launcher


def test_preflight_runs_as_python_script_without_quoting():
    p = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'preflight.py')],
        cwd=str(ROOT), text=True, capture_output=True, timeout=30,
    )
    assert p.returncode == 0, p.stdout + p.stderr
    assert 'Python syntax OK:' in p.stdout
    assert 'app version: 13.0.0' in p.stdout


def test_preflight_reports_exact_bad_python_file(tmp_path):
    app = tmp_path / 'app'
    app.mkdir()
    (app / 'bad_syntax.py').write_text('print(hello world)\n', encoding='utf-8')
    p = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'preflight.py'),
         '--scan-root', str(tmp_path), '--syntax-only'],
        cwd=str(ROOT), text=True, capture_output=True, timeout=30,
    )
    assert p.returncode != 0
    assert 'bad_syntax.py' in p.stderr
    assert 'SyntaxError' in p.stderr
