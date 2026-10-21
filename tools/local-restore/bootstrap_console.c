#include <CoreFoundation/CoreFoundation.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>

static int install_console_job(const char* path)
{
    FILE* file = fopen(path, "rb"); if (!file) return 1;
    struct stat st;
    if (fstat(fileno(file), &st) || st.st_size <= 0 || st.st_size > (32<<20)) { fclose(file); return 1; }
    void* bytes = malloc(st.st_size);
    if (!bytes) { fclose(file); return 1; }
    int ok = fread(bytes, 1, st.st_size, file) == (size_t)st.st_size; fclose(file);
    if (!ok) { free(bytes); return 1; }
    CFDataRef original = CFDataCreate(NULL, bytes, st.st_size); free(bytes);
    CFPropertyListFormat format;
    CFMutableDictionaryRef plist = (CFMutableDictionaryRef)CFPropertyListCreateWithData(NULL, original,
        kCFPropertyListMutableContainersAndLeaves, &format, NULL);
    int result = 1;
    if (!plist || CFGetTypeID(plist) != CFDictionaryGetTypeID()) goto done;
    CFMutableDictionaryRef jobs = (CFMutableDictionaryRef)CFDictionaryGetValue(plist, CFSTR("LaunchDaemons"));
    if (!jobs || CFGetTypeID(jobs) != CFDictionaryGetTypeID()) goto done;
    const char xml[] = "<plist version=\"1.0\"><dict>"
        "<key>Label</key><string>com.inferno.console</string>"
        "<key>ProgramArguments</key><array><string>/bin/bash</string><string>--noprofile</string>"
        "<string>--norc</string><string>-i</string></array>"
        "<key>RunAtLoad</key><true/><key>UserName</key><string>root</string>"
        "<key>POSIXSpawnType</key><string>Interactive</string>"
        "<key>EnablePressuredExit</key><false/>"
        "<key>StandardInPath</key><string>/dev/console</string>"
        "<key>StandardOutPath</key><string>/dev/console</string>"
        "<key>StandardErrorPath</key><string>/dev/console</string></dict></plist>";
    CFDataRef job_data = CFDataCreate(NULL, (const UInt8*)xml, sizeof(xml)-1);
    CFPropertyListRef job = CFPropertyListCreateWithData(NULL, job_data, 0, NULL, NULL);
    CFRelease(job_data);
    if (!job) goto done;
    CFStringRef key = CFSTR("/System/Library/LaunchDaemons/com.inferno.console.plist");
    CFTypeRef existing = CFDictionaryGetValue(jobs, key);
    if (existing && !CFEqual(existing, job)) { CFRelease(job); goto done; }
    CFDictionarySetValue(jobs, key, job); CFRelease(job);
    CFDataRef data = CFPropertyListCreateData(NULL, plist, format, 0, NULL);
    if (!data) goto done;
    char backup[1024], temporary[1024];
    int n = snprintf(backup, sizeof(backup), "%s.inferno-before-bootstrap", path);
    int t = snprintf(temporary, sizeof(temporary), "%s.inferno-bootstrap-new", path);
    if (n < 0 || (size_t)n >= sizeof(backup) || t < 0 || (size_t)t >= sizeof(temporary)) { CFRelease(data); goto done; }
    int fd = open(backup, O_WRONLY | O_CREAT | O_EXCL, st.st_mode & 0777);
    if (fd >= 0) {
        ok = write(fd, CFDataGetBytePtr(original), CFDataGetLength(original)) == CFDataGetLength(original)
            && fsync(fd) == 0; close(fd);
        if (!ok) { CFRelease(data); goto done; }
    } else if (access(backup, F_OK)) { CFRelease(data); goto done; }
    fd = open(temporary, O_WRONLY | O_CREAT | O_EXCL, st.st_mode & 0777);
    if (fd >= 0) {
        ok = write(fd, CFDataGetBytePtr(data), CFDataGetLength(data)) == CFDataGetLength(data) && fsync(fd) == 0;
        close(fd);
        if (ok && rename(temporary, path) == 0) result = 0;
        else unlink(temporary);
    }
    CFRelease(data);
done:
    if (plist) CFRelease(plist);
    CFRelease(original); return result;
}

#ifdef INFERNO_BOOTSTRAP_CONSOLE_TEST
int main(int argc, char** argv) { return argc == 2 ? install_console_job(argv[1]) : 2; }
#endif
