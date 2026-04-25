import os
import subprocess

from Fuzz4All.target.target import FResult, Target
from Fuzz4All.util.util import comment_remover


CIRCT_BIN = os.environ.get(
    "CIRCT_BIN", "/edazz/target/circt-1.144.0-bin/bin/circt-verilog"
)
YOSYS_BIN = os.environ.get("YOSYS_BIN", "/edazz/target/yosys-0.64-bin/bin/yosys")


class SVTarget(Target):
    """SystemVerilog target — supports iverilog, verilator, circt, yosys, cxxrtl.

    Compile-only validation (no testbench, no stimulus, no linked simulator).
    The LLM is asked to produce a self-contained module named `top`. Each tool
    is invoked with the lightest parse/elaborate/lower step sufficient to
    surface frontend/middle-end bugs; simulator linkage from the EDAzz
    differential template is intentionally dropped.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.SYSTEM_MESSAGE = "You are a SystemVerilog Fuzzer"
        if kwargs["template"] == "fuzzing_with_config_file":
            config_dict = kwargs["config_dict"]
            self.prompt_used = self._create_prompt_from_config(config_dict)
            self.config_dict = config_dict
        else:
            raise NotImplementedError

    def write_back_file(self, code):
        path = "/tmp/temp{}.sv".format(self.CURRENT_TIME)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception:
            pass
        return path

    def wrap_prompt(self, prompt: str) -> str:
        return f"/* {prompt} */\n{self.prompt_used['separator']}\n{self.prompt_used['begin']}"

    def wrap_in_comment(self, prompt: str) -> str:
        return f"/* {prompt} */"

    def filter(self, code) -> bool:
        clean_code = code.replace(self.prompt_used["begin"], "").strip()
        if self.prompt_used["target_api"] not in clean_code:
            return False
        return True

    def clean(self, code: str) -> str:
        return comment_remover(code, "cpp")

    def clean_code(self, code: str) -> str:
        code = comment_remover(code, "cpp")
        code = "\n".join(
            [
                line
                for line in code.split("\n")
                if line.strip() != "" and line.strip() != self.prompt_used["begin"]
            ]
        )
        return code

    def _kill_dangling(self, filename):
        pname = f"'{filename}'"
        subprocess.run(
            [
                "ps -ef | grep "
                + pname
                + " | grep -v grep | awk '{print $2}' | xargs -r kill -9"
            ],
            shell=True,
        )

    def _run_iverilog(self, filename):
        out = f"/tmp/out{self.CURRENT_TIME}.vvp"
        try:
            r = subprocess.run(
                f"iverilog -g2012 -o {out} {filename}",
                shell=True,
                capture_output=True,
                encoding="utf-8",
                timeout=10,
                text=True,
            )
        except subprocess.TimeoutExpired:
            self._kill_dangling(filename)
            return FResult.TIMED_OUT, "iverilog"
        except UnicodeDecodeError:
            return FResult.FAILURE, "iverilog"
        subprocess.run(f"rm -f {out}", shell=True)
        return self._classify(r)

    def _run_verilator(self, filename):
        # --lint-only: parse + elaborate without generating C++ / building.
        # Sufficient for a compile-bug fuzzer and needs no harness or obj_dir.
        return self._run_shell(
            f"verilator --lint-only --sv -Wno-fatal --top-module top {filename}",
            filename,
            "verilator",
        )

    def _run_circt(self, filename):
        # circt-verilog: parse SV and lower to HW MLIR. Output dropped — we
        # only care about exit status.
        out = f"/tmp/out{self.CURRENT_TIME}.mlir"
        r = self._run_shell(
            f"{CIRCT_BIN} --ir-hw {filename} -o {out}", filename, "circt"
        )
        subprocess.run(f"rm -f {out}", shell=True)
        return r

    def _run_yosys(self, filename):
        # yosys synth flow up to the 'fine' stage — exercises the full
        # synthesis middle-end without gate-level mapping.
        cmd = (
            f"{YOSYS_BIN} -q -p "
            f"'read_verilog -sv {filename}; "
            f"hierarchy -check -top top; "
            f"synth -top top -noalumacc -run begin:fine'"
        )
        return self._run_shell(cmd, filename, "yosys", timeout=20)

    def _run_cxxrtl(self, filename):
        # yosys cxxrtl backend: proc+flatten then write_cxxrtl.
        out = f"/tmp/out{self.CURRENT_TIME}.cc"
        cmd = (
            f"{YOSYS_BIN} -q -p "
            f"'read_verilog -sv {filename}; "
            f"hierarchy -check -top top; "
            f"proc; flatten; write_cxxrtl {out}'"
        )
        r = self._run_shell(cmd, filename, "cxxrtl", timeout=20)
        subprocess.run(f"rm -f {out}", shell=True)
        return r

    def _run_shell(self, cmd, filename, label, timeout=10):
        try:
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                encoding="utf-8",
                timeout=timeout,
                text=True,
            )
        except subprocess.TimeoutExpired:
            self._kill_dangling(filename)
            return FResult.TIMED_OUT, label
        except UnicodeDecodeError:
            return FResult.FAILURE, label
        return self._classify(r)

    @staticmethod
    def _classify(r):
        if r.returncode == 0:
            return FResult.SAFE, "its safe"
        # Negative returncode → killed by signal (SIGSEGV=-11, SIGABRT=-6, ...).
        # That's a real compiler crash — flag as ERROR.
        if r.returncode < 0:
            return FResult.ERROR, (r.stderr or "") + f"\n[signal {r.returncode}]"
        return FResult.FAILURE, r.stderr or r.stdout or ""

    def validate_individual(self, filename) -> (FResult, str):
        tool = (self.target_name or "").lower()
        dispatch = {
            "iverilog": self._run_iverilog,
            "verilator": self._run_verilator,
            "circt": self._run_circt,
            "yosys": self._run_yosys,
            "cxxrtl": self._run_cxxrtl,
        }
        runner = dispatch.get(tool)
        if runner is None:
            return FResult.FAILURE, f"unknown sv target: {self.target_name!r}"
        fresult, msg = runner(filename)

        if fresult == FResult.SAFE:
            return FResult.SAFE, "its safe"
        if fresult == FResult.TIMED_OUT:
            return FResult.ERROR, "timed out"
        return fresult, f"{msg}"
