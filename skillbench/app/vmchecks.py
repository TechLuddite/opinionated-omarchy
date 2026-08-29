"""State assertions: did the machine actually end up fixed?

This is the whole point of the agentic lane. checks.py grades a transcript -- what the
agent SAID. These grade the VM -- what the agent DID. A model that describes the right
edit in prose and then writes it to the wrong file passes the first and fails these,
and that gap is the measurement the chat lane cannot make.

Every assertion is one command over ssh, evaluated on the VM after the agent stops, and
each yields one grade row with grader='post' so the UI can separate the two kinds.

Assertions never raise. A malformed assertion FAILS with the config error in its note,
exactly as a malformed check does: a typo in a bench must be visible in the UI, never
silently green.

TRUST NOTE. These commands run on the VM as the bench user, and a bench file is code in
every sense that matters. That is acceptable because a bench is authored in this repo
and runs against a disposable VM -- the same posture as the seed scripts. It is not a
sandbox, and a bench is not a place to run anything you would not run by hand.
"""
import shlex


def _q(s):
    return shlex.quote(str(s))


def _command_for(a):
    """-> (shell command, describe) for one assertion. Raises ValueError if malformed."""
    t = a.get("type")

    if t == "file_exists":
        path = a["path"]
        return f"test -e {_q(path)}", f"{path} exists"

    if t == "file_absent":
        path = a["path"]
        return f"! test -e {_q(path)}", f"{path} is absent"

    if t == "file_contains":
        path, pattern = a["path"], a["pattern"]
        flags = "-Eq" if a.get("case_sensitive", True) else "-Eqi"
        return (f"test -e {_q(path)} && grep {flags} -- {_q(pattern)} {_q(path)}",
                f"{path} matches /{pattern}/")

    if t == "file_not_contains":
        path, pattern = a["path"], a["pattern"]
        flags = "-Eq" if a.get("case_sensitive", True) else "-Eqi"
        # A missing file trivially does not contain the pattern; that is the honest
        # reading of "not contains", and file_exists is how you demand it be there.
        return (f"! test -e {_q(path)} || ! grep {flags} -- {_q(pattern)} {_q(path)}",
                f"{path} does not match /{pattern}/")

    if t == "command_succeeds":
        cmd = a["command"]
        return cmd, f"`{cmd}` succeeds"

    if t == "command_fails":
        cmd = a["command"]
        return f"! ( {cmd} )", f"`{cmd}` fails"

    if t == "command_output_matches":
        cmd, pattern = a["command"], a["pattern"]
        flags = "-Eq" if a.get("case_sensitive", True) else "-Eqi"
        return (f"( {cmd} ) 2>&1 | grep {flags} -- {_q(pattern)}",
                f"`{cmd}` output matches /{pattern}/")

    raise ValueError(f"unknown post assertion type {t!r}")


async def run_post(vm, task, timeout=60):
    """Evaluate a task's `post:` block on a VM. -> list of grade dicts. Never raises."""
    grades = []
    counts = {}
    for a in task.get("post") or []:
        t = (a or {}).get("type", "?")
        counts[t] = counts.get(t, 0) + 1
        criterion = t if counts[t] == 1 else f"{t}#{counts[t]}"
        try:
            command, describe = _command_for(a)
        except (KeyError, ValueError, TypeError) as e:
            missing = f"missing field {e}" if isinstance(e, KeyError) else str(e)
            grades.append({"criterion": criterion, "score": 0.0, "passed": False,
                           "note": f"bad post assertion: {missing}"})
            continue
        try:
            rc, out = await vm.run(command, timeout=timeout)
        except Exception as e:                      # an unreachable VM is a failed
            grades.append({"criterion": criterion, "score": 0.0, "passed": False,
                           "note": f"{describe} -- could not evaluate: "
                                   f"{type(e).__name__}: {e}"[:300]})
            continue
        passed = rc == 0
        note = None if passed else f"{describe} -- exit {rc}" + (
            f": {out.strip()[:160]}" if out.strip() else "")
        grades.append({"criterion": criterion, "score": 1.0 if passed else 0.0,
                       "passed": passed, "note": note})
    return grades
