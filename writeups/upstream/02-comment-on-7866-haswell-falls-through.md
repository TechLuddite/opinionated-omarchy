Comment for omacom/omarchy#7866

One more device name for the pile, and a slightly different failure mode from the Ivy Bridge case,
which I think #8514 already covers but which is worth having written down so it gets verified.

Haswell's lspci name matches **neither** branch of the regex, so nothing is installed at all:

```
00:02.0 VGA compatible controller: Intel Corporation 4th Gen Core Processor Integrated Graphics Controller
```

`4th gen core processor integrated graphics controller` contains none of `hd graphics`,
`uhd graphics`, `xe`, `iris`, `arc` or `panther lake`, and it does not contain `gma` either. The
`if`/`elif` has no `else`, so the script exits successfully having installed no VA-API driver and
having said nothing. Sandy Bridge is the same shape:
`2nd Generation Core Processor Family Integrated Graphics Controller`.

So the string matching produces two distinct outcomes, not one:

- a name containing `hd graphics` on Gen7 or earlier gets the wrong driver, which is this issue, and
- a name that spells out the generation in words gets no driver, silently.

Both disappear if the selection is made from the PCI device ID as #8514 does, which is the other
reason to prefer it over a regex tweak. Worth adding a Haswell or Sandy Bridge device ID to that
PR's test matrix if there is one, since those are the names that currently fall through rather than
mismatch.

For what it is worth, `omarchy update` does not re-run `install/hardware/`, so an affected machine
stays affected after the fix ships until `omarchy apply hardware` is run, which may be worth a line
in the release notes when it lands.

Checked on omarchy 4.0.2-1 against `/usr/share/omarchy/install/hardware/intel/video-acceleration.sh`
and `/usr/share/hwdata/pci.ids` (`8086:0416`, `8086:0126`).

Found while auditing a third-party Omarchy troubleshooting corpus against what 4.0.2-1 actually
ships, with Claude Code on my own machine.
