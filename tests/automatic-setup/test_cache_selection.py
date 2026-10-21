"""Compile the production selector and exercise actual directory contents."""
from pathlib import Path
import os
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[2]
source = (repo / 'app/guest/patcher-daemon.c').read_text()
start = source.index('static int cache_path(')
end = source.index('\n/*', start)
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    cache = root / 'cache'
    cache.mkdir()
    wrapper = root / 'selector.c'
    wrapper.write_text('''#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#define CACHE_DIR "''' + cache.as_posix() + '''"
''' + source[start:end] + '''
int main(int argc, char** argv) {
    char path[1024];
    int found = cache_path(path, argc > 1 ? 1 : sizeof(path));
    if (found) puts(path);
    return !found;
}
''')
    executable = root / 'selector'
    subprocess.run([os.environ.get('CC', 'cc'), '-Wall', '-Wextra',
                    '-Wno-unused-parameter', str(wrapper), '-o', str(executable)], check=True)

    def selected(expected=None, small_buffer=False):
        result = subprocess.run([str(executable)] + (['small'] if small_buffer else []),
                                capture_output=True, text=True)
        assert result.returncode == (0 if expected else 1), result
        assert result.stdout.strip() == (str(cache / expected) if expected else '')

    selected()
    # Regression: backup and map may appear before the real cache in readdir.
    (cache / 'dyld_shared_cache_arm64e.InfernoOriginalBytes').write_bytes(b'backup' * 1000)
    (cache / 'dyld_shared_cache_arm64e.map').write_bytes(b'metadata' * 1000)
    selected()
    main = cache / 'dyld_shared_cache_arm64e'
    main.write_bytes(b'dyld_v1' + b'\0' * 8192)
    selected(main.name)
    selected(small_buffer=True)
    second = cache / 'dyld_shared_cache_arm64'
    second.write_bytes(main.read_bytes())
    selected()  # two valid primaries: reject ambiguity
    second.unlink()
    main.write_bytes(b'invalid' + b'\0' * 8192)
    selected()
    main.write_bytes(b'dyld_v1')
    selected()
    main.unlink()
    main.mkdir()
    selected()
    main.rmdir()
    main.symlink_to(cache / 'dyld_shared_cache_arm64e.InfernoOriginalBytes')
    selected()
print('Production cache selection: primary, backup, map, ambiguity, header, size, directory, symlink and buffer checks passed')
