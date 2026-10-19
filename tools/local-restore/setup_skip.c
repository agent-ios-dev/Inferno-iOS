/* Recovery-only candidate. Preserve the existing mobile preferences and only
 * mark Setup complete. Never erase, activate an account, or reboot the guest.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static int write_data(int fd, CFDataRef data)
{
    CFIndex length = CFDataGetLength(data), done = 0;
    while (done < length) {
        ssize_t n = write(fd, CFDataGetBytePtr(data) + done, length - done);
        if (n <= 0) return 1;
        done += n;
    }
    return fsync(fd) != 0;
}

static int mark_setup_finished(const char* path)
{
    struct stat st;
    int exists = lstat(path, &st) == 0;
    if (!exists && errno != ENOENT) return 1;
    if (exists && (!S_ISREG(st.st_mode) || st.st_size <= 0 || st.st_size > (4 << 20))) return 1;
    CFDataRef original = NULL;
    CFMutableDictionaryRef prefs = NULL;
    CFPropertyListFormat format = kCFPropertyListBinaryFormat_v1_0;
    if (exists) {
        int fd = open(path, O_RDONLY | O_NOFOLLOW);
        if (fd < 0) return 1;
        unsigned char* bytes = malloc(st.st_size);
        if (!bytes) { close(fd); return 1; }
        ssize_t n = read(fd, bytes, st.st_size);
        close(fd);
        if (n != st.st_size) { free(bytes); return 1; }
        original = CFDataCreate(NULL, bytes, st.st_size);
        free(bytes);
        CFPropertyListRef parsed = CFPropertyListCreateWithData(NULL, original,
            kCFPropertyListMutableContainersAndLeaves, &format, NULL);
        if (!parsed || CFGetTypeID(parsed) != CFDictionaryGetTypeID()) {
            if (parsed) CFRelease(parsed);
            CFRelease(original); return 1;
        }
        prefs = (CFMutableDictionaryRef)parsed;
    } else {
        prefs = CFDictionaryCreateMutable(NULL, 0, &kCFTypeDictionaryKeyCallBacks,
                                         &kCFTypeDictionaryValueCallBacks);
        st.st_mode = 0644;
#ifdef INFERNO_SETUP_TEST
        st.st_uid = getuid(); st.st_gid = getgid();
#else
        st.st_uid = 501; st.st_gid = 501;
#endif
    }
    CFStringRef keys[] = {CFSTR("SetupDone"), CFSTR("SetupFinishedAllSteps")};
    int already_done = 1;
    for (int i = 0; i < 2; i++) {
        CFTypeRef value = CFDictionaryGetValue(prefs, keys[i]);
        if (!value || !CFEqual(value, kCFBooleanTrue)) already_done = 0;
    }
    if (already_done) { CFRelease(prefs); if (original) CFRelease(original); return 0; }
    for (int i = 0; i < 2; i++) CFDictionarySetValue(prefs, keys[i], kCFBooleanTrue);
    CFDataRef changed = CFPropertyListCreateData(NULL, prefs, format, 0, NULL);
    CFRelease(prefs);
    if (!changed) { if (original) CFRelease(original); return 1; }
    char backup[2048], temporary[2048];
    int result = 1;
    if (snprintf(backup, sizeof(backup), "%s.inferno-before-setup-skip", path) >= sizeof(backup) ||
        snprintf(temporary, sizeof(temporary), "%s.inferno-setup-new", path) >= sizeof(temporary)) goto done;
    if (original) {
        int fd = open(backup, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, st.st_mode & 0777);
        if (fd < 0) goto done; /* Never replace an earlier backup. */
        int failed = write_data(fd, original);
        close(fd);
        if (failed) goto done;
    }
    int fd = open(temporary, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, st.st_mode & 0777);
    if (fd < 0) goto done;
    int failed = fchmod(fd, st.st_mode & 0777) || fchown(fd, st.st_uid, st.st_gid) || write_data(fd, changed);
    close(fd);
    if (failed || rename(temporary, path)) { unlink(temporary); goto done; }
    sync();
    result = 0;
done:
    if (original) CFRelease(original);
    CFRelease(changed);
    return result;
}

#ifdef INFERNO_SETUP_TEST
int main(int argc, char** argv) { return argc == 2 ? mark_setup_finished(argv[1]) : 2; }
#else
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
    /* A filesystem mount may remain in an uninterruptible kernel wait.
     * Never turn the timeout into another unbounded waitpid(). */
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
    puts("*** SETUP: helper started");
    const char* mountpoint = "/mnt9";
    if (mkdir(mountpoint, 0755) && errno != EEXIST) {
        printf("*** SETUP: mountpoint creation failed errno=%d\n", errno); return 1;
    }
    char* mount[] = {"/sbin/mount_apfs", "-o", "rw", "/dev/disk0s1s2", (char*)mountpoint, NULL};
    puts("*** SETUP: mounting existing Data; no restore or erase");
    if (bounded_run(mount, 90)) { puts("*** SETUP: Data mount failed; no preference write"); return 1; }
    int failed = mark_setup_finished("/mnt9/mobile/Library/Preferences/com.apple.purplebuddy.plist");
    sync();
    char* unmount[] = {"/sbin/umount", (char*)mountpoint, NULL};
    int unmount_failed = bounded_run(unmount, 30);
    if (failed || unmount_failed) { puts("*** SETUP: failed; do not infer completed Setup"); return 1; }
    puts("*** SETUP: two flags saved, Data unmounted; guest reboot is an explicit separate action");
    return 0;
}
#endif
