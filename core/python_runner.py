"""
python_runner.py
Run PythonFiles scripts (ResultTabs.py, Statbar.py) via subprocess.
Replaces PythonReader.groovy (readFile / readFileQuickRun).

Subprocess argument order (UNCHANGED from Katalon PythonReader.groovy):
  python3 <script_path> <input_excel> <output_dir> <tsv_base_path> <tab_name>
"""
import os
import sys
import subprocess
from config.settings import PYTHON_FILES_ROOT, OUTPUT_FILES_ROOT, INPUT_FILES_ROOT


def ensure_output_dir(output_dir: str):
    """
    Create output directory if it does not exist.
    Replaces: Utils.createDirctory() in Katalon.

    Args:
        output_dir: Full path to output directory
    """
    os.makedirs(output_dir, exist_ok=True)


def get_python_script_path(program: str, script_name: str) -> str:
    """
    Return full path to a PythonFiles script.
    Replaces: Utils.getPythonFilePath() in Katalon.

    Args:
        program:     Program name e.g. 'CDS', 'CCDI'
        script_name: Script filename e.g. 'ResultTabs.py'

    Returns:
        str: Full path e.g. '.../PythonFiles/CDS/ResultTabs.py'

    Raises:
        FileNotFoundError: If the script does not exist
    """
    path = os.path.join(PYTHON_FILES_ROOT, program, script_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Python script not found: {path}\n"
            f"Check PYTHON_FILES_ROOT in settings.py and that '{program}/{script_name}' exists."
        )
    return path


def get_tsv_base_path(program: str) -> str:
    """
    Return the TSV data base path for a program.
    Replaces: Utils.getMetadataFilesPath() in Katalon.

    Args:
        program: Program name e.g. 'CDS', 'CCDI'

    Returns:
        str: Full path to InputFiles/<program>
    """
    return os.path.join(INPUT_FILES_ROOT, program)


def run_python_script(script_path: str, input_excel: str, output_dir: str,
                      tsv_base_path: str, tab_name: str) -> subprocess.CompletedProcess:
    """
    Run a PythonFiles script with the standard argument signature.
    Replaces: PythonReader.readFile() in Katalon.

    Argument order matches PythonReader.groovy exactly:
      python3 <script> <input_excel> <output_dir> <tsv_base_path> <tab_name>

    Args:
        script_path:   Full path to the Python script
        input_excel:   Full path to the input Excel file (study config)
        output_dir:    Full path to OutputFiles directory
        tsv_base_path: Full path to InputFiles/<program> TSV base directory
        tab_name:      Result tab name e.g. 'ParticipantsTab', 'FilesTab'

    Returns:
        CompletedProcess with .returncode, .stdout, .stderr

    Raises:
        RuntimeError: If the script exits with a non-zero return code
    """
    ensure_output_dir(output_dir)

    cmd = [sys.executable, script_path, input_excel, output_dir, tsv_base_path, tab_name]

    print(f"[python_runner] Running: {os.path.basename(script_path)} | tab={tab_name}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},  # prevents pipe deadlock on Jenkins
    )

    # Always print script output for debugging
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"[python_runner]   {line}")
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            print(f"[python_runner] STDERR: {line}")

    if result.returncode != 0:
        raise RuntimeError(
            f"Script failed: {os.path.basename(script_path)} (exit code {result.returncode})\n"
            f"Tab: {tab_name}\n"
            f"Stderr: {result.stderr.strip()}"
        )

    print(f"[python_runner] OK: {os.path.basename(script_path)}")
    return result


def run_result_tabs(program: str, input_excel: str, output_dir: str, tab_name: str):
    """
    Run ResultTabs.py — reads SQL from Excel, runs against TSV DataFrames,
    writes results to TsvData sheet in output Excel.
    Replaces: PythonReader.readFile('ResultTabs.py') in Katalon multiFunction.

    Args:
        program:     Program name e.g. 'CDS'
        input_excel: Full path to input Excel
        output_dir:  Full path to output directory
        tab_name:    Tab name e.g. 'ParticipantsTab'
    """
    script_path   = get_python_script_path(program, "ResultTabs.py")
    tsv_base_path = get_tsv_base_path(program)
    run_python_script(script_path, input_excel, output_dir, tsv_base_path, tab_name)


def run_statbar(program: str, input_excel: str, output_dir: str, tab_name: str):
    """
    Run Statbar.py — reads StatQuery from Excel, runs SQL against TSVs,
    writes results to StatOutput sheet in output Excel.
    Replaces: PythonReader.readFile('Statbar.py') in Katalon multiFunction.

    Args:
        program:     Program name e.g. 'CDS'
        input_excel: Full path to input Excel
        output_dir:  Full path to output directory
        tab_name:    Tab name e.g. 'ParticipantsTab'
    """
    script_path   = get_python_script_path(program, "Statbar.py")
    tsv_base_path = get_tsv_base_path(program)
    run_python_script(script_path, input_excel, output_dir, tsv_base_path, tab_name)
