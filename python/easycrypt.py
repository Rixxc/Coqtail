import unittest
from dataclasses import dataclass
from typing import List, Optional, Tuple
from result import Result, Ok, Err

@dataclass
class LogMessage:
    severity: int
    message: str

@dataclass
class EasyCryptOutput:
    logs: List[LogMessage]
    output: str
    prompt: Tuple[int, str]


# https://github.com/EasyCrypt/easycrypt/blob/02082bdbbf69df78618d57f0eed3dac295cc8af7/src/ecTerminal.ml#L88-L105
class EasyCryptStderr:
    def parse_str(stderr: str) -> Optional[Err]:
        if not stderr.startswith("[error"):
            return None
        _, stderr = stderr.split("[error-", 1)
        pre, msg = stderr.split("]", 1)
        loc_s, loc_e = pre.split("-", 1)
        return Err(msg, (int(loc_s), int(loc_e)))

class EasyCryptStdout:
    def __init__(self) -> None:
        self.cur_sev: Optional[int] = None
        self.tmp: bytearray = bytearray()
        self.list: List[LogMessage] = []
        self.out: bytearray = bytearray()
        self.prompt: Optional[Tuple[int, str]] = None

    def _flush(self):
        if self.cur_sev is not None:
            full: str = self.tmp.decode("utf8", errors="ignore")
            self.tmp = bytearray()
            self.list.append(LogMessage(self.cur_sev, full))
            self.cur_sev = None

    def _append(self, severity: int, line: bytes):
        if self.cur_sev is not None:
            if self.cur_sev != severity:
                self._flush()
                self.cur_sev = severity
                self.tmp = bytearray(line)
            else:
                self.tmp.extend(line)
        else:
            self.cur_sev = severity
            self.tmp = bytearray(line)
        self.tmp.extend(b"\n")

    def _output(self, line: bytes) -> None:
        if self.cur_sev is not None:
            self._flush()
        self.out.extend(line)
        if len(self.out) != 0 and self.out[-1] != 10:
            self.out.extend(b"\n")

    def _start(self, severity: int, line: bytes) -> None:
        self._flush()
        self._append(severity, line)

    def _continuation(self, severity: int, line: bytes) -> None:
        self._append(severity, line)

    def _prompt(self, line: bytes) -> None:
        # it's fine if we see more than one prompt.
        # we should just take the last one, overwrite as we go.
        _, line = line.split(b"[")
        line, _ = line.split(b"]>")
        state, mode = line.split(b"|")
        self.prompt = (int(state), mode.decode("utf8"))

    def read_line(self, line: bytes) -> None:
        if line.startswith(b"[W]+ "):
            self._start(1, line[5:])
        elif line.startswith(b"[W]| "):
            self._continuation(1, line[5:])
        elif line.startswith(b"+ "):
            self._start(0, line[2:])
        elif line.startswith(b"| "):
            self._continuation(0, line[2:])
        elif line.startswith(b"[error"):
            self._error(line)
        elif line.startswith(b"[") and line.endswith(b"]>"):
            self._prompt(line)
        else:
            self._output(line)

    def parse_bytes(data: bytes) -> EasyCryptOutput:
        """
        We will parse the -emacs format, which looks like this (following a
            previous prompt 17):

        [17|check]>
        [W]+ warn
        [W]| warn continuation
        output
        output
        + info
        | info continuation
        output
        + info
        | info continuation
        output
        [18|check]>

        The output gets written to the Goal window, the rest into the Info window.
        """
        lines: List[bytes] = data.split(b"\n")
        logger = EasyCryptStdout()
        for line in lines:
            logger.read_line(line)
        return logger.finish()

    def finish(self) -> EasyCryptOutput:
        return EasyCryptOutput(
            self.list,
            self.out.decode("utf8", errors="discard"),
            self.prompt,
        )


TEST_VECTOR_OK = b"""output 1
[W]+ warning line 1
[W]| warning line 2
output 2
output 3
output 4
+ info line 1
| info line 2
output 5
[18|check]>
"""

class TestEasyCrypt(unittest.TestCase):

    def test_ok(self):
        output = EasyCryptStdout.parse_bytes(TEST_VECTOR_OK)
        # pylint: disable=no-self-use
        self.assertEqual(output, EasyCryptOutput(
            [ LogMessage(1, "warning line 1\nwarning line 2\n")
            , LogMessage(0, "info line 1\ninfo line 2\n") ],
            "output 1\noutput 2\noutput 3\noutput 4\noutput 5\n",
            (18, "check")
        ))

    def test_error(self):
        output = EasyCryptStderr.parse_str("[error-0-27]parse error")
        # pylint: disable=no-self-use
        self.assertTrue(isinstance(output, Err))
        self.assertEqual(output.msg, "parse error")
        self.assertEqual(output.loc, (0, 27))

if __name__ == '__main__':
    unittest.main()
