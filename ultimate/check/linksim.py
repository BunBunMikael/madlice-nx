#!/usr/bin/env python3
"""Link simulation: compiles every source the cmake files list to an object (clang, -O0, the harness stubs) and reports
symbols that are declared but defined nowhere in the project (excluding SDK / third-party / libc++ names), and strong
symbols defined twice. A link error the Switch build would only show after two hours.

    linksim.py <tree> <base> <stubs> <out-dir>
"""
import os, re, subprocess, sys, concurrent.futures as cf

tree, base, stubs, out = [os.path.abspath(a) for a in sys.argv[1:5]]
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out, exist_ok=True)

def sources():
    files = set()
    gpu = os.path.join(tree, 'app/src/renut_engine/gpu')
    for cm, subs in ((os.path.join(gpu, 'gpu.cmake'), {'${RENUT_GPU_DIR}': gpu}),
                     (os.path.join(tree, 'app/cmake/alice_renut_gpu.cmake'),
                      {'${CMAKE_SOURCE_DIR}': os.path.join(tree, 'app')}),
                     (os.path.join(tree, 'app/CMakeLists.txt'), {'src/': os.path.join(tree, 'app/src') + '/'})):
        for line in open(cm, encoding='utf-8'):
            line = line.split('#')[0]
            for tok in re.findall(r'[^\s"()]+\.cpp', line):
                for k, v in subs.items():
                    tok = tok.replace(k, v)
                if tok.startswith(tree) and os.path.isfile(tok):
                    files.add(tok)
    return sorted(files)

def compile_one(f):
    o = os.path.join(out, re.sub(r'[/.]', '_', os.path.relpath(f, tree)) + '.o')
    cmd = (open(os.path.join(here, 'chk.sh')).read())
    r = subprocess.run(['bash', '-c', open(os.path.join(here, 'chk.sh')).read()
                        .replace('-fsyntax-only', '-c -o ' + o).replace('"$F" 2>&1', '"$F" 2>&1'),
                        'x', tree, base, stubs, f], capture_output=True, text=True)
    return f, o, ('error' in r.stdout), r.stdout

srcs = sources()
print(f'{len(srcs)} sources', flush=True)
objs, bad = [], []
with cf.ThreadPoolExecutor(int(os.environ.get('JOBS', '8'))) as ex:
    for f, o, failed, log in ex.map(compile_one, srcs):
        if failed or not os.path.isfile(o):
            bad.append((f, log[:600]))
        else:
            objs.append((f, o))
for f, log in bad:
    print('COMPILE FAIL', os.path.relpath(f, tree), '\n', log)

defined, undef = {}, {}
STRONG = set('TDBRSA')
for f, o in objs:
    for line in subprocess.run(['llvm-nm', '--defined-only', '-g', o], capture_output=True, text=True).stdout.splitlines():
        p = line.split(None, 2)
        if len(p) == 3 and p[1] in STRONG:
            defined.setdefault(p[2], []).append(os.path.relpath(f, tree))
        elif len(p) == 3:
            defined.setdefault(p[2], [])  # weak: defined, may repeat
    for line in subprocess.run(['llvm-nm', '--undefined-only', '-g', o], capture_output=True, text=True).stdout.splitlines():
        s = line.split()[-1]
        undef.setdefault(s, []).append(os.path.relpath(f, tree))

def dem(s):
    return subprocess.run(['c++filt', s], capture_output=True, text=True).stdout.strip()

dup = {s: v for s, v in defined.items() if len(v) > 1}
print(f'\n== strong symbols defined in more than one file: {len(dup)}')
for s, v in sorted(dup.items())[:60]:
    print(' ', dem(s)[:150], '<-', ', '.join(v))
missing = [s for s in undef if s not in defined]
names = {s: dem(s) for s in missing}
SKIP = re.compile(r'^(std::|__cxx|operator |vtable for __cxx|typeinfo for (std|__cxx)|_Unwind|__gxx|__cxa|rex::|plume::|ImGui|ImDraw|ImFont|XXH|ZSTD|'
                  r'smolv|fmt::|spdlog::|SDL_|vk[A-Z]|volk|__imp__|sub_[0-9A-F]{8}|dk|dkMem|_ZN|toml::|simde|VMA|vma|memcpy|memset|memcmp|strlen|mem|str)')
print(f'\n== undefined and defined nowhere in the project (not SDK-looking): ')
n = 0
for s, d in sorted(names.items(), key=lambda x: x[1]):
    if SKIP.match(d) or SKIP.match(s):
        continue
    n += 1
    print(' ', d[:170], '<-', ', '.join(sorted(set(undef[s]))[:3]))
print(n, 'such symbols;', len(missing), 'undefined in total (SDK / libraries / generated code excluded by name)')
