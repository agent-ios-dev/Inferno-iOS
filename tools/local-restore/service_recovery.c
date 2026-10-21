/* Recovery-only service configuration. Does not touch Data or the dyld cache. */
#include "launchd_cache.c"
#include <errno.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>

extern char** environ;

static int bounded_run(char* const argv[], unsigned seconds)
{
    pid_t pid;
    if (posix_spawn(&pid, argv[0], NULL, NULL, argv, environ)) return 1;
    for (unsigned i = 0; i < seconds; i++) {
        int status;
        pid_t done = waitpid(pid, &status, WNOHANG);
        if (done == pid) return !WIFEXITED(status) || WEXITSTATUS(status) != 0;
        if (done < 0) return 1;
        sleep(1);
    }
    kill(pid, SIGKILL);
    for (unsigned i = 0; i < 5; i++) {
        if (waitpid(pid, NULL, WNOHANG) != 0) break;
        sleep(1);
    }
    return 1;
}

int main(void)
{
    setbuf(stdout, NULL);
    int console = open("/dev/console", O_WRONLY);
    if (console >= 0) { dup2(console, 1); dup2(console, 2); close(console); }
    puts("*** SERVICES: starting; no restore, Data mount or dyld patch");
    if (mkdir("/mnt9", 0755) && errno != EEXIST) {
        puts("*** SERVICES: mountpoint creation failed"); return 1;
    }
    char* mount[] = {"/sbin/mount_apfs", "-o", "rw", "/dev/disk0s1s1", "/mnt9", NULL};
    if (bounded_run(mount, 60)) {
        puts("*** SERVICES: System mount failed; no configuration write"); return 1;
    }
    puts("*** SERVICES: System mounted; checking five exact service labels");
    int failed = disable_services_at("/mnt9/System/Library/xpc/launchd.plist");
    sync();
    char* unmount[] = {"/sbin/umount", "/mnt9", NULL};
    int unmount_failed = bounded_run(unmount, 30);
    if (failed || unmount_failed) {
        printf("*** SERVICES: failed configuration=%d unmount=%d; do not infer success\n",
               failed, unmount_failed);
        return 1;
    }
    puts("*** SERVICES: five services disabled; original file retained; System unmounted");
    return 0;
}
