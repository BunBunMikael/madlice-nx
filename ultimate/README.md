# Alice on the Renut base

This repository is Alice's game layer. The ReXGlue SDK, Plume, Renut's XenosRecomp, UAM, FFmpeg and the shader tools
come from [renut_nx_ultimate_base](https://github.com/ChanseyIsTheBest/renut_nx_ultimate_base), at the commit named in
`BASE_REF`. `assemble.sh` combines the two into the tree the workflow builds in (`.github/workflows/ultimate-build.yml`).

## Stages

| Stage | What changes | State |
| --- | --- | --- |
| 1 | The base's **SDK** (Horizon layer, memory governor, pooled thread stacks, event waits, XMA cache), **third-party code** (Plume, Renut's XenosRecomp, UAM) and **shader tools**, under Alice's app and renderer copy as they are. Alice's known-good codegen flavour ("stage A") stays. | this branch; not yet built |
| 2 | The base's renderer fixes and speed-ups, file by file into `app/src/renut_engine`, each tried on its own. | not started |
| 3 | The base's post-codegen passes, one at a time, behind switches (see below). | not started |

## Why the post-codegen passes are not simply switched on

`docs/alice-notes.md` (2026-11-03/04) bisected a glitch in Alice's skin and dress textures on the console. Every build with
the loop barriers, the no-volatile pch, direct calls, `non_volatile_as_local` or `elide_lr_stores` showed it; the stage A
flavour (`skip_msr` and the cr/ctr/xer/reserved locals, no post steps) did not. The suspected cause is the guest's
setjmp/longjmp (`82DBA170` / `82DBA440`): after a longjmp the setjmp caller's r14-r31 locals keep the failing call's values.
The base's `tools/post_codegen.py` runs exactly those passes, so this tree uses Alice's own `tools/post_codegen.py` (it only
records the flavour's name) until stage 3 adds the base's passes back one by one.

## Using it

1. Actions tab: enable workflows for the fork if GitHub asks.
2. Run **Ultimate Build (Alice on the Renut base)**. The Google Drive file ID of your game ZIP is an input.
3. The NRO and shader cache come out as the `alice-nx-switch-ultimate` artifact; logs are in `alice-nx-build-diagnostics`.

Artifacts of a public repository can be downloaded by anyone signed in to GitHub, and these contain code translated from
the game: delete them after downloading, and make the repository private when you can.

## Taking newer base work

Sync your fork of the base, put its commit in `BASE_REF`, and run the workflow.
