"""Test-VM targets for the agentic lane: ssh, tmux, isolation, skill delivery.

Every case in the agentic lane runs on a real Omarchy VM. This module is the whole of
the contact surface with those machines, and four decisions in it are load-bearing.

WHY TMUX AND NOT PLAIN SSH. The runner could just `ssh vm pi ...` and read stdout. It
runs each case as its own window inside a long-lived tmux session instead, because a
person watching the VM's console sees exactly what the runner sees, live, with no
second copy of anything. The console terminal is attached READ-ONLY, which is why the
runner must never use `tmux send-keys`: tmux refuses it outright while a read-only
client is attached ("client is read-only"). Launching the command AS the window is the
supported path and is more robust anyway -- nothing is typed at a shell prompt, so
there is no prompt to be confused by.

WHY THE RUNNER NEVER TOUCHES LIBVIRT. A full disk rollback between cases would be the
strongest isolation available, and on btrfs it costs about a second (tools/golden-test-vm.sh).
The container cannot do it: it runs with cap_drop ALL, no-new-privileges and no libvirt
socket, and handing it the host's hypervisor would trade a real security property for
convenience. So per-case isolation happens INSIDE the VM -- the paths a bench declares
are tarred once at run start and restored before every case. That is weaker than a disk
reset and the README says so plainly: it resets what the bench declares, and nothing
else. The disk-level reset stays an operator action between runs.

WHY A DEDICATED KEY. The container gets skillbench/secrets/bench_ed25519, never the
operator's own key. It guards two disposable VMs and nothing else.

WHY SKILLS ARE MATERIALISED AS FILES. In the chat lane a skill is injected as a system
prompt with its frontmatter stripped. Here pi loads it the way the real harness does:
`pi --skill <dir>`, a directory of real files WITH their frontmatter, because the
frontmatter is what pi's own discovery consumes. Same bundle, same order, delivered
the way the tool actually reads it.
"""
import asyncio
import os
import posixpath
import shlex

SSH_KEY = os.environ.get("SB_SSH_KEY", "/secrets/bench_ed25519")
SSH_USER = os.environ.get("SB_VM_USER", "techluddite")
TMUX_SESSION = os.environ.get("SB_TMUX_SESSION", "bench")
REMOTE_ROOT = "/tmp/skillbench"

SSH_OPTS = [
    "-i", SSH_KEY,
    "-o", "BatchMode=yes",
    "-o", "IdentitiesOnly=yes",
    "-o", "ConnectTimeout=10",
    # These are throwaway VMs on a NAT bridge whose host keys change on every rebuild.
    # Pinning them would mean a rebuild breaks the bench with a MITM warning; the
    # threat model here (loopback-only libvirt bridge, disposable targets) does not
    # justify that trade.
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR",
]


class VMError(RuntimeError):
    pass


def _parse_targets(raw):
    """'test1=192.168.122.177,test2=192.168.122.112' -> [(name, host), ...]"""
    out = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, host = chunk.partition("=")
        if not host:
            raise VMError(f"malformed SB_VMS entry {chunk!r}; want name=host")
        out.append((name.strip(), host.strip()))
    return out


class VM:
    def __init__(self, name, host, user=SSH_USER):
        self.name = name
        self.host = host
        self.user = user

    def __repr__(self):
        return f"<VM {self.name} {self.host}>"

    # ------------------------------------------------------------- primitives

    async def run(self, command, timeout=60):
        """Run a shell command on the VM, in a LOGIN shell. -> (returncode, output).

        The login shell is not cosmetic. Omarchy exports OMARCHY_PATH from ~/.bashrc, so
        a plain non-interactive `ssh host omarchy ...` runs with it unset and every
        omarchy subcommand fails with `find: '/themes/': No such file or directory`.
        A bench that hit that would be measuring an environment no real user ever has.

        Never raises on a non-zero exit: a failing command is data here (a post
        assertion that did not hold, a probe that says the VM is not ready), and the
        caller decides what it means.
        """
        argv = ["ssh", *SSH_OPTS, f"{self.user}@{self.host}",
                f"bash -lc {shlex.quote(command)}"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        except FileNotFoundError as e:                  # no ssh client in the image
            raise VMError(f"cannot exec ssh: {e}") from e
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return 124, f"[timed out after {timeout}s]"
        return proc.returncode, (out or b"").decode("utf-8", "replace")

    async def check(self, command, timeout=60):
        rc, out = await self.run(command, timeout)
        if rc != 0:
            raise VMError(f"{self.name}: `{command[:120]}` exited {rc}: {out.strip()[:300]}")
        return out

    async def put(self, remote_path, content, mode=None):
        """Write a file on the VM, content passed on stdin rather than argv.

        Bench prompts and seed scripts contain quotes, newlines and $; putting them in a
        command line is how a bench spec silently becomes a different bench spec.
        """
        quoted = shlex.quote(remote_path)
        cmd = f"mkdir -p {shlex.quote(posixpath.dirname(remote_path))} && cat > {quoted}"
        if mode:
            cmd += f" && chmod {mode} {quoted}"
        argv = ["ssh", *SSH_OPTS, f"{self.user}@{self.host}", cmd]
        proc = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await proc.communicate(content.encode("utf-8"))
        if proc.returncode != 0:
            raise VMError(f"{self.name}: writing {remote_path} failed: "
                          f"{(out or b'').decode('utf-8', 'replace')[:200]}")

    async def ready(self):
        rc, _ = await self.run("true", timeout=15)
        return rc == 0

    # ------------------------------------------------------------- the mirror

    async def run_in_tmux(self, window, command, timeout, linger=3):
        """Run a command as its own tmux window. -> (returncode, output, timed_out).

        The window is the unit of work, so nothing is ever typed into a shell and the
        read-only console viewer follows each case automatically as it becomes the
        active window.

        Completion is signalled by an rc file rather than by watching tmux: a window
        can vanish for reasons that are not the command finishing, and an rc file that
        exists means the command definitely ran to completion.
        """
        work = posixpath.join(REMOTE_ROOT, window)
        script = (
            "#!/usr/bin/env bash\n"
            f"cd {shlex.quote(work)}\n"
            "{ " + command + " ; } 2>&1 | tee output.log\n"
            "echo ${PIPESTATUS[0]} > rc\n"
            # Hold the window open briefly so a person watching sees the final frame
            # instead of the window disappearing the instant the agent stops.
            f"sleep {int(linger)}\n"
        )
        # Clear only the completion markers, never the directory: the caller has
        # already staged prompt.txt (and any seed) in here, and wiping it would delete
        # the very inputs this window is about to run.
        await self.run(
            f"mkdir -p {shlex.quote(work)} && "
            f"rm -f {shlex.quote(posixpath.join(work, 'rc'))} "
            f"{shlex.quote(posixpath.join(work, 'output.log'))}", timeout=30)
        await self.put(posixpath.join(work, "case.sh"), script, mode="755")

        # -d so the new window does not steal focus from a window still being watched;
        # tmux still makes it the active window for a client that has none.
        # `bash -l`, for the same reason run() uses a login shell -- and here it matters
        # twice over. A tmux window inherits the TMUX SERVER's environment, not this ssh
        # session's, and that server was started by a systemd user unit with no profile
        # sourced at all. pi then passes what it inherits to every command its own bash
        # tool runs, so without this the AGENT would be the thing without OMARCHY_PATH.
        rc, out = await self.run(
            f"tmux new-window -t {shlex.quote(TMUX_SESSION)} -n {shlex.quote(window)} "
            f"{shlex.quote('bash -l ' + posixpath.join(work, 'case.sh'))}", timeout=30)
        if rc != 0:
            raise VMError(f"{self.name}: could not open tmux window {window!r}: {out.strip()[:200]}")

        rc_path = posixpath.join(work, "rc")
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            code, body = await self.run(f"cat {shlex.quote(rc_path)} 2>/dev/null", timeout=20)
            if code == 0 and body.strip().isdigit():
                _, output = await self.run(
                    f"cat {shlex.quote(posixpath.join(work, 'output.log'))} 2>/dev/null",
                    timeout=60)
                return int(body.strip()), output, False
            await asyncio.sleep(2)

        # Timed out. Kill the window so a hung agent cannot occupy the console (and the
        # VM) for the rest of the run, but keep whatever it managed to print.
        await self.run(f"tmux kill-window -t {shlex.quote(TMUX_SESSION + ':' + window)} "
                       f"2>/dev/null || true", timeout=30)
        _, output = await self.run(
            f"cat {shlex.quote(posixpath.join(work, 'output.log'))} 2>/dev/null", timeout=60)
        return 124, output, True

    # ------------------------------------------------------------- isolation

    def _baseline_tar(self):
        return posixpath.join(REMOTE_ROOT, "baseline.tar")

    async def snapshot(self, paths):
        """Tar the declared paths once, as the state every case starts from."""
        if not paths:
            return
        listed = " ".join(shlex.quote(p) for p in paths)
        await self.check(
            f"mkdir -p {shlex.quote(REMOTE_ROOT)} && cd $HOME && "
            # --ignore-failed-read: a bench may legitimately declare a path that does
            # not exist yet, and "the agent must create it" is a real assertion.
            f"tar --ignore-failed-read -cf {shlex.quote(self._baseline_tar())} {listed} 2>/dev/null || true",
            timeout=180)

    async def restore(self, paths):
        """Put the declared paths back exactly as snapshot() found them."""
        if not paths:
            return
        removals = " ".join(shlex.quote(p) for p in paths)
        await self.check(
            f"cd $HOME && rm -rf {removals} && "
            f"tar -xf {shlex.quote(self._baseline_tar())} -C $HOME 2>/dev/null || true",
            timeout=180)

    # ------------------------------------------------------------- skills

    async def deliver_skill(self, variant, files):
        """Materialise a skill bundle on the VM. -> remote directory, or None for 'none'.

        files is [(filename, text), ...] with frontmatter INTACT -- pi reads it.
        """
        if not files:
            return None
        # One directory per variant, not per case: the bundle is identical across every
        # case in a variant, and re-sending it per case would be pure ssh round-trips.
        root = posixpath.join(REMOTE_ROOT, "skills", variant.replace(":", "_").replace("+", "_"))
        await self.run(f"rm -rf {shlex.quote(root)}", timeout=30)
        for name, text in files:
            await self.put(posixpath.join(root, name), text)
        return root


class Pool:
    """The set of VMs the agentic lane may use, handed out one case at a time."""

    def __init__(self, targets=None):
        raw = os.environ.get("SB_VMS", "")
        self.vms = [VM(n, h) for n, h in _parse_targets(targets if targets is not None else raw)]
        self._free = None

    def __len__(self):
        return len(self.vms)

    @property
    def names(self):
        return [v.name for v in self.vms]

    def _queue(self):
        # Built lazily: a Queue binds to the running loop, and the Pool is constructed
        # at import time, before uvicorn's loop exists.
        if self._free is None:
            self._free = asyncio.Queue()
            for vm in self.vms:
                self._free.put_nowait(vm)
        return self._free

    async def acquire(self):
        if not self.vms:
            raise VMError("no VMs configured; set SB_VMS (name=host,...)")
        return await self._queue().get()

    def release(self, vm):
        self._queue().put_nowait(vm)

    async def status(self):
        """-> [{name, host, ready, tmux}] for /readyz and the UI."""
        async def one(vm):
            ok = await vm.ready()
            tmux = False
            if ok:
                rc, _ = await vm.run(
                    f"tmux has-session -t {shlex.quote(TMUX_SESSION)}", timeout=20)
                tmux = rc == 0
            return {"name": vm.name, "host": vm.host, "ready": ok, "tmux": tmux}
        return list(await asyncio.gather(*(one(v) for v in self.vms)))


POOL = Pool()
