"""
core/cea_executor.py
======================
Unified executor that tries multiple methods:
1. Python 'cea' package (preferred)
2. FCEA2.exe subprocess
3. Fallback calculator (last resort)
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from typing import Callable, Optional

from core.cea_python_executor import CEAPythonExecutor
from core.exceptions import CEAExecutionError, ParseError
from core.fallback_calculator import FallbackCalculator
from core.inp_builder import INPBuilder
from core.out_parser import OUTParser
from models.cea_result import CEAResult
from models.formulation import Formulation

log = logging.getLogger(__name__)

LogCallback = Optional[Callable[[str], None]]


class CEAExecutor:
    """
    Executes CEA calculations using the best available method.
    User can force a specific method via the 'mode' parameter.
    """

    def __init__(self, fcea2_exe: str = "", work_dir: str = "") -> None:
        self._exe = fcea2_exe
        self._work_dir = work_dir or tempfile.gettempdir()
        self._fallback = FallbackCalculator()
        self._parser = OUTParser()
        
        # Initialize the new Python CEA engine
        self._python_executor = CEAPythonExecutor()
        self._use_python = self._python_executor.available

    def available(self) -> bool:
        """Return True if at least one real CEA engine is available."""
        return self._use_python or (bool(self._exe) and os.path.isfile(self._exe))

    def run(
            self, formulation: Formulation, log_callback: LogCallback = None,
            mode: str = "Auto"
    ) -> CEAResult:
        """
        Execute CEA calculation.
        
        mode: "CEA Python", "FCEA2", "Auto", or "Fallback"
        """
        def _log(message: str) -> None:
            if log_callback:
                log_callback(message)
            else:
                log.info(message)

        # =======================================================
        # 1. FORCED CEA PYTHON MODE
        # =======================================================
        if mode == "CEA Python":
            if not self._use_python:
                raise CEAExecutionError(
                    "CEA Python engine not available. Please install the 'cea' package."
                )
            _log("Engine mode: CEA Python (forced) — using official NASA Python package.")
            return self._python_executor.run(formulation, log_callback)

        # =======================================================
        # 2. FORCED FCEA2 MODE
        # =======================================================
        if mode == "FCEA2":
            if not self._exe or not os.path.isfile(self._exe):
                raise CEAExecutionError(
                    "FCEA2.exe not configured or file not found. Set path in Settings."
                )
            _log("Engine mode: FCEA2 (forced) — using FCEA2.exe subprocess.")
            return self._run_fcea2(formulation, log_callback)

        # =======================================================
        # 3. FORCED FALLBACK MODE
        # =======================================================
        if mode == "Fallback" or mode == "fallback":
            _log("Engine mode: Fallback (forced) — using ideal-rocket calculator.")
            result = self._fallback.calculate(formulation)
            result.method = "Fallback (Simplified - Not Real CEA)"
            return result

        # =======================================================
        # 4. AUTO MODE (Try Python first, then FCEA2, then Fallback)
        # =======================================================
        _log("Engine mode: Auto — selecting best available method...")

        # Try CEA Python
        if self._use_python:
            _log("Auto mode: Trying CEA Python engine...")
            try:
                return self._python_executor.run(formulation, log_callback)
            except Exception as e:
                _log(f"CEA Python failed: {e}. Trying FCEA2.exe...")

        # Try FCEA2.exe
        if self._exe and os.path.isfile(self._exe):
            _log("Auto mode: Trying FCEA2.exe...")
            try:
                return self._run_fcea2(formulation, log_callback)
            except Exception as e:
                _log(f"FCEA2.exe failed: {e}. Falling back to simplified calculator.")

        # Last Resort: Fallback Calculator
        _log("WARNING: Using simplified ideal-rocket calculator (Not real CEA).")
        result = self._fallback.calculate(formulation)
        result.method = "Fallback (Simplified - Not Real CEA)"
        return result

    # =====================================================================
    # ORIGINAL FCEA2 SUBPROCESS LOGIC
    # =====================================================================
    def _run_fcea2(self, formulation: Formulation, log_callback: LogCallback) -> CEAResult:
        """Runs the original FCEA2.exe subprocess logic."""
        def _log(message: str) -> None:
            if log_callback:
                log_callback(message)
            else:
                log.info(message)

        inp_content = INPBuilder.build(formulation)

        # ===== Create a safe run name =====
        run_name = re.sub(r"[^\w]", "_", formulation.name)[:20] or "cea_run"
        
        # ===== Use the FCEA2.exe directory =====
        fcea2_dir = os.path.dirname(self._exe)
        if not fcea2_dir:
            fcea2_dir = os.getcwd()
        
        os.makedirs(fcea2_dir, exist_ok=True)
        
        inp_path = os.path.join(fcea2_dir, f"{run_name}.inp")
        out_path = os.path.join(fcea2_dir, f"{run_name}.out")

        # ===== Write the .inp file with NO BOM =====
        try:
            with open(inp_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(inp_content)
            _log(f"INP file written: {inp_path}")
        except Exception as exc:
            raise CEAExecutionError(f"Failed to write INP file: {exc}")

        # ===== Clean up old output file =====
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
                _log(f"Removed old output file: {out_path}")
            except OSError:
                pass

        _log(f"Running FCEA2.exe for '{run_name}' in {fcea2_dir}")

        # ===== Try multiple methods to run FCEA2.exe =====
        raw_output = ""
        stdout = ""
        stderr = ""
        process = None
        methods_tried = []

        # ===== METHOD 1: stdin with newline =====
        try:
            _log("Method 1: stdin with newline")
            methods_tried.append("stdin")
            
            process = subprocess.run(
                [self._exe],
                input=f"{run_name}\n",
                capture_output=True,
                text=True,
                timeout=30,
                cwd=fcea2_dir,
            )
            stdout = process.stdout or ""
            stderr = process.stderr or ""
            _log(f"Method 1 return code: {process.returncode}")
            
            if os.path.exists(out_path):
                with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
                    raw_output = fh.read()
                _log(f"Method 1: Read {len(raw_output)} chars from {out_path}")
            else:
                raw_output = stdout
                _log("Method 1: No output file, using stdout")
                
        except subprocess.TimeoutExpired:
            _log("Method 1 timed out")
        except Exception as exc:
            _log(f"Method 1 failed: {exc}")

        # ===== METHOD 2: echo with pipe =====
        if not raw_output or "THEORETICAL ROCKET PERFORMANCE" not in raw_output:
            try:
                _log("Method 2: echo with pipe")
                methods_tried.append("echo_pipe")
                
                cmd = f'echo {run_name} | "{self._exe}"'
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=fcea2_dir,
                    shell=True,
                )
                stdout = process.stdout or ""
                stderr = process.stderr or ""
                _log(f"Method 2 return code: {process.returncode}")
                
                if os.path.exists(out_path):
                    with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
                        raw_output = fh.read()
                    _log(f"Method 2: Read {len(raw_output)} chars from {out_path}")
                else:
                    raw_output = stdout
                    _log("Method 2: No output file, using stdout")
                    
            except subprocess.TimeoutExpired:
                _log("Method 2 timed out")
            except Exception as exc:
                _log(f"Method 2 failed: {exc}")

        # ===== METHOD 3: Popen with communicate =====
        if not raw_output or "THEORETICAL ROCKET PERFORMANCE" not in raw_output:
            try:
                _log("Method 3: Popen with communicate")
                methods_tried.append("popen")
                
                proc = subprocess.Popen(
                    [self._exe],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=fcea2_dir,
                )
                stdout, stderr = proc.communicate(input=f"{run_name}\n", timeout=30)
                _log(f"Method 3 return code: {proc.returncode}")
                
                if os.path.exists(out_path):
                    with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
                        raw_output = fh.read()
                    _log(f"Method 3: Read {len(raw_output)} chars from {out_path}")
                else:
                    raw_output = stdout or ""
                    _log("Method 3: No output file, using stdout")
                    
            except subprocess.TimeoutExpired:
                _log("Method 3 timed out")
            except Exception as exc:
                _log(f"Method 3 failed: {exc}")

        # ===== METHOD 4: Batch file =====
        if not raw_output or "THEORETICAL ROCKET PERFORMANCE" not in raw_output:
            try:
                _log("Method 4: Batch file")
                methods_tried.append("batch_file")
                
                batch_path = os.path.join(fcea2_dir, f"run_{run_name}.bat")
                with open(batch_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(f'@echo off\n')
                    fh.write(f'echo {run_name} | "{self._exe}"\n')
                
                process = subprocess.run(
                    [batch_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=fcea2_dir,
                    shell=True,
                )
                stdout = process.stdout or ""
                stderr = process.stderr or ""
                _log(f"Method 4 return code: {process.returncode}")
                
                try:
                    os.remove(batch_path)
                except OSError:
                    pass
                
                if os.path.exists(out_path):
                    with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
                        raw_output = fh.read()
                    _log(f"Method 4: Read {len(raw_output)} chars from {out_path}")
                else:
                    raw_output = stdout
                    _log("Method 4: No output file, using stdout")
                    
            except subprocess.TimeoutExpired:
                _log("Method 4 timed out")
            except Exception as exc:
                _log(f"Method 4 failed: {exc}")

        # ===== METHOD 5: Try with full path to .inp file =====
        if not raw_output or "THEORETICAL ROCKET PERFORMANCE" not in raw_output:
            try:
                _log("Method 5: Direct file path")
                methods_tried.append("direct_file")
                
                process = subprocess.run(
                    [self._exe, f"{run_name}.inp"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=fcea2_dir,
                )
                stdout = process.stdout or ""
                stderr = process.stderr or ""
                _log(f"Method 5 return code: {process.returncode}")
                
                if os.path.exists(out_path):
                    with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
                        raw_output = fh.read()
                    _log(f"Method 5: Read {len(raw_output)} chars from {out_path}")
                else:
                    raw_output = stdout
                    _log("Method 5: No output file, using stdout")
                    
            except subprocess.TimeoutExpired:
                _log("Method 5 timed out")
            except Exception as exc:
                _log(f"Method 5 failed: {exc}")

        # ===== Check if we got any output =====
        if not raw_output.strip():
            raise ParseError(
                "Engine Execution Error: FCEA2.exe produced no output.\n"
                f"Methods tried: {methods_tried}\n"
                f"INP file: {inp_path}\n"
                f"FCEA2.exe: {self._exe}\n"
                f"Working directory: {fcea2_dir}\n"
                "Please check:\n"
                "1. FCEA2.exe is a valid executable\n"
                "2. The INP file format is correct\n"
                "3. Run FCEA2.exe in Windows XP compatibility mode")

        # ===== Check if FCEA2 actually executed =====
        if "THEORETICAL ROCKET PERFORMANCE" not in raw_output:
            if "ENTER INPUT FILE NAME" in raw_output:
                raise ParseError(
                    "Engine Execution Error: FCEA2.exe is waiting for input.\n"
                    "This is a Windows compatibility issue.\n"
                    "Please set FCEA2.exe to run in Windows XP compatibility mode.\n"
                    f"First 500 chars of output:\n{raw_output[:500]}")
            
            if "fatal error" in raw_output.lower() or "error" in raw_output.lower():
                error_lines = [line for line in raw_output.split('\n') 
                              if 'error' in line.lower() or 'fatal' in line.lower()]
                if error_lines:
                    raise ParseError(
                        f"Engine Execution Error: CEA reported an error.\n"
                        f"{error_lines[0]}\n"
                        f"First 500 chars of output:\n{raw_output[:500]}")
            
            raise ParseError(
                "Engine Execution Error: FCEA2 did not execute properly.\n"
                f"Methods tried: {methods_tried}\n"
                f"First 500 chars of output:\n{raw_output[:500]}")

        # ===== Parse the output =====
        try:
            result = self._parser.parse(raw_output, formulation.name)
        except ParseError as e:
            raise ParseError(
                f"Engine Execution Error: Could not parse CEA output.\n"
                f"First 500 chars of output:\n{raw_output[:500]}") from e
            
        result.raw_inp = inp_content
        result.area_ratio = formulation.area_ratio
        
        # Use isp_vacuum_s (which is standard) instead of isp_m_s just in case
        _log(f"Parsed result: Isp={result.isp_vacuum_s:.2f} s  "
             f"C*={result.cstar_m_s:.0f} m/s")
        return result
