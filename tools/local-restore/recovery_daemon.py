"""Generate a candidate guest daemon without modifying the production helper."""
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[2]
source = (repo / 'app/guest/patcher-daemon.c').read_text()
selector = 'strstr(e->d_name, ".map") != NULL'
if source.count(selector) != 1:
    raise ValueError('Cache file selection changed')
source = source.replace(selector,
    selector + ' || strstr(e->d_name, ".InfernoOriginalBytes") != NULL')
start = source.index('static int disable_services(void)')
end = source.index('\nint main(void)', start)
source = source[:start] + '''static int disable_services(void)
{
    int code = disable_services_at(MOUNTPOINT "/System/Library/xpc/launchd.plist");
    printf("*** PATCHER: system launchd cache service configuration says %d\\n", code);
    fflush(stdout);
    return code;
}
''' + source[end:]
anchor = '''    char* umount[] = {"/sbin/umount", MOUNTPOINT, NULL};
    run(umount[0], umount);

    if (disable_services() != 0) {'''
replacement = '''    if (disable_services() != 0) {'''
if source.count(anchor) != 1:
    raise ValueError('Daemon completion layout changed')
source = source.replace(anchor, replacement)
anchor = '    printf("*** PATCHER: done, the machine can be reset now\\n");'
source = source.replace(anchor, '''    sync();
    char* unmount_system[] = {"/sbin/umount", MOUNTPOINT, NULL};
    if (run(unmount_system[0], unmount_system) != 0) {
        printf("*** PATCHER: failed, System could not be unmounted\\n");
        return 1;
    }
''' + anchor)
Path(sys.argv[1]).write_text((Path(__file__).parent / 'launchd_cache.c').read_text() + '\n' + source)
