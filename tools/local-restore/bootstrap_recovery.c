/* Experimental VM-copy bootstrap only. No erase, Data mount or exploit. */
#include "bootstrap_archive.c"
#include "bootstrap_console.c"
#include <errno.h>
#include <signal.h>
#include <spawn.h>
#include <sys/mount.h>
#include <sys/wait.h>
extern char** environ;
extern const unsigned char inferno_strap_start[], inferno_strap_end[];

static int mount_system(void)
{
    char* argv[] = {"/sbin/mount_apfs", "-o", "rw", "/dev/disk0s1s1", "/mnt9", NULL};
    pid_t pid; int spawn_error = posix_spawn(&pid, argv[0], NULL, NULL, argv, environ);
    if (spawn_error) { printf("*** BOOTSTRAP: mount spawn error %d\n", spawn_error); return 1; }
    for (int i=0; i<60; i++) {
        int status; pid_t done = waitpid(pid, &status, WNOHANG);
        if (done == pid) return !WIFEXITED(status) || WEXITSTATUS(status) != 0;
        if (done < 0) return 1;
        sleep(1);
    }
    kill(pid, SIGKILL); return 1;
}

int main(void)
{
    setbuf(stdout, NULL);
    int console = open("/dev/console", O_WRONLY);
    if (console >= 0) { dup2(console, 1); dup2(console, 2); close(console); }
    puts("*** BOOTSTRAP: candidate on VM copy; no restore or Data mount");
    if (mkdir("/mnt9", 0755) && errno != EEXIST) return 1;
    if (mount_system()) { puts("*** BOOTSTRAP: System mount failed; no writes"); return 1; }
    puts("*** BOOTSTRAP: System mounted; installing pinned utility archive");
    int failed = chdir("/mnt9") != 0;
    if (!failed) failed = extract_bootstrap(inferno_strap_start,
        (size_t)(inferno_strap_end-inferno_strap_start));
    chdir("/");
    if (!failed) failed = install_console_job("/mnt9/System/Library/xpc/launchd.plist");
    sync();
    int unmounted = unmount("/mnt9", 0);
    if (failed || unmounted) {
        printf("*** BOOTSTRAP: failed install=%d unmount=%d errno=%d; not ready\n", failed, unmounted, errno);
        return 1;
    }
    puts("*** BOOTSTRAP: utilities and console job written; System unmounted; normal boot not tested");
    return 0;
}
