#!/usr/bin/env python3
"""After every codegen: app/generated/codegen_flavor.txt, the codegen flavour's name in the first "[enh]" log line.

Run by tools/codegen.sh and by the PC build itself (app/CMakeLists.txt appends this script to the generator's command,
which the build re-runs on its own when an input changes).

The flavour is app/codegen_flavor.toml (included by app/alice_manifest.toml): "classic" when it sets no key, otherwise
"optimised: " and its keys. The file is written only when its text changes, so the build does not reconfigure for
nothing.

alice-nx (2026-11-05): the post-codegen rewrites of sa2-nx's optimised flavour (no-volatile pch, loop barriers, direct
calls) and its stage B options (non_volatile_as_local, elide_lr_stores) glitched Alice's textures on the console in
every combination tried (docs/alice-notes.md, 2026-11-03/04); they were removed from this repository. sa2-nx keeps the
tools.

  python3 tools/post_codegen.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'app')
GEN = os.path.join(APP, 'generated')
CODEGEN = os.path.join(GEN, 'default')

# ultimate (stage 3): the base's exact, local rewrites, switchable by ALICE_CODEGEN_PASSES (none | vector | scalar | all;
# default none, the workflow sets it). Groups are the base's tools in the base's order. Left OUT on purpose, until each is
# bisected on the console: pch_no_volatile, loop_barriers, direct_calls, indirect_calls, dead_ctx_defs and the r1 / lr
# passes (the suspects of the 2026-11-03/04 texture glitches), the localized copies and the guest fences.
GROUPS = {
    'vector': ['vec_byteswap', 'vperm_one_source', 'vec_unaligned_stores', 'vec_lane_index', 'vec_cvt_fixed',
               'vec_prefetch_line', 'vec_lvlx_splat', 'vec_shift_whole', 'vupkd3d_neon', 'vmx_float_macros'],
    'scalar': ['inline_memcalls', 'fp_sign_ops', 'float_loads', 'single_floats'],
}


def passes_wanted():
    raw = os.environ.get('ALICE_CODEGEN_PASSES', 'none').strip().lower()
    names = []
    for part in re.split(r'[,+ ]+', raw):
        names += list(GROUPS) if part == 'all' else ([part] if part in GROUPS else [])
    return [g for g in GROUPS if g in names]


def run_passes(groups):
    """Each pass on its own: a failure is a warning (and the pass is not counted), not the end of a two-hour build."""
    done = []
    for group in groups:
        for name in GROUPS[group]:
            tool = os.path.join(ROOT, 'tools', name + '.py')
            if not os.path.isfile(tool):
                print(f'post_codegen: ::warning::{name}.py is missing; skipped')
                continue
            result = subprocess.run([sys.executable, tool, '--gen', CODEGEN], cwd=ROOT)
            if result.returncode != 0:
                print(f'post_codegen: ::warning::{name}.py failed ({result.returncode}); its rewrites may be partial')
            else:
                done.append(name)
    return done


def main():
    flavor_toml = open(os.path.join(APP, 'codegen_flavor.toml'), encoding='utf-8').read()
    keys = re.findall(r'^\s*([a-z_]+)\s*=\s*true', flavor_toml, re.M)
    text = 'optimised: ' + ', '.join(keys) if keys else 'classic'
    groups = passes_wanted()
    if groups and os.path.isdir(CODEGEN):
        done = run_passes(groups)
        text += ' + passes: ' + ', '.join(done) if done else ''
    path = os.path.join(GEN, 'codegen_flavor.txt')
    try:
        old_text = open(path, encoding='utf-8').read()
    except OSError:
        old_text = None
    if old_text != text:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    print(f'post_codegen: flavour "{text}"')


if __name__ == '__main__':
    main()
