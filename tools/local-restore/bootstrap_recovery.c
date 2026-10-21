/* Experimental VM-copy bootstrap only. No erase, Data mount or exploit. */
#include "bootstrap_archive.c"
#include "bootstrap_console.c"
#include <errno.h>
#include <signal.h>
#include <spawn.h>
#include <sys/mount.h>
#include <sys/wait.h>
#include <CommonCrypto/CommonDigest.h>
extern char** environ;

static void* read_payload(size_t* size)
{
    static const char expected[] = "76565c01d8d64ab05459ed0943666283c4c230e0f31954ca6ba235902d7078e7aba464b9fd0a908b35b5f1eb1ea8ab6ba22a738ee998aaf67a7929b63d22e26b";
    for (int i=1; i<=8; i++) {
        char path[32]; snprintf(path, sizeof(path), "/dev/rdisk%d", i);
        int fd = open(path, O_RDONLY); if (fd < 0) continue;
        unsigned char header[4096];
        if (read(fd, header, sizeof(header)) != sizeof(header) || memcmp(header, "INFERNOBSTRAP01", 15)) { close(fd); continue; }
        size_t length = 0;
        for (int j=0; j<4; j++) length |= (size_t)header[16+j] << (j*8);
        if (!length || length > 20*1024*1024) { close(fd); continue; }
        size_t padded = (length+4095)&~(size_t)4095;
        unsigned char* bytes = malloc(padded); if (!bytes) { close(fd); return NULL; }
        size_t got = 0;
        while (got < padded) {
            ssize_t n = read(fd, bytes+got, padded-got);
            if (n <= 0) break;
            got += (size_t)n;
        }
        close(fd);
        unsigned char digest[CC_SHA512_DIGEST_LENGTH]; char hex[129];
        CC_SHA512(bytes, (CC_LONG)length, digest);
        for (int j=0; j<64; j++) snprintf(hex+j*2, 3, "%02x", digest[j]);
        if (got != padded || strcmp(hex, expected)) { free(bytes); continue; }
        *size = length; return bytes;
    }
    return NULL;
}

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
    size_t payload_size = 0;
    void* payload = read_payload(&payload_size);
    if (!payload) { puts("*** BOOTSTRAP: pinned payload disk missing or hash mismatch; no writes"); return 1; }
    if (mkdir("/mnt9", 0755) && errno != EEXIST) return 1;
    if (mount_system()) { puts("*** BOOTSTRAP: System mount failed; no writes"); return 1; }
    puts("*** BOOTSTRAP: System mounted; installing pinned utility archive");
    int failed = chdir("/mnt9") != 0;
    if (!failed) failed = extract_bootstrap(payload, payload_size);
    free(payload);
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
