/* Recovery experiment: apply the five documented service disables on System.
 * No Data-volume mount/unlock is needed. Preserve unrelated property values.
 */
#include <CoreFoundation/CoreFoundation.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char* service_names[] = {
    "com.apple.voicemail.vmd", "com.apple.CommCenter", "com.apple.CommCenterMobileHelper",
    "com.apple.CommCenterRootHelper", "com.apple.locationd"
};

static int service_index(CFTypeRef value)
{
    if (!value || CFGetTypeID(value) != CFStringGetTypeID()) return -1;
    for (int i = 0; i < 5; i++) {
        CFStringRef name = CFStringCreateWithCString(NULL, service_names[i], kCFStringEncodingUTF8);
        int equal = CFEqual(value, name);
        CFRelease(name);
        if (equal) return i;
    }
    return -1;
}

static void visit_services(CFTypeRef node, unsigned counts[5], unsigned depth)
{
    if (!node || depth > 64) return;
    if (CFGetTypeID(node) == CFDictionaryGetTypeID()) {
        CFMutableDictionaryRef dict = (CFMutableDictionaryRef)node;
        int index = service_index(CFDictionaryGetValue(dict, CFSTR("Label")));
        if (index >= 0) {
            counts[index]++;
            CFDictionarySetValue(dict, CFSTR("Disabled"), kCFBooleanTrue);
        }
        CFIndex count = CFDictionaryGetCount(dict);
        const void** values = calloc(count ? count : 1, sizeof(void*));
        if (!values) abort();
        CFDictionaryGetKeysAndValues(dict, NULL, values);
        for (CFIndex i = 0; i < count; i++) visit_services(values[i], counts, depth + 1);
        free(values);
    } else if (CFGetTypeID(node) == CFArrayGetTypeID()) {
        CFArrayRef array = (CFArrayRef)node;
        for (CFIndex i = 0; i < CFArrayGetCount(array); i++)
            visit_services(CFArrayGetValueAtIndex(array, i), counts, depth + 1);
    }
}

static int disable_services_at(const char* path)
{
    FILE* source = fopen(path, "rb");
    if (!source) return 1;
    struct stat st;
    if (fstat(fileno(source), &st) || st.st_size <= 0 || st.st_size > (32 << 20)) {
        fclose(source); return 1;
    }
    unsigned char* bytes = malloc((size_t)st.st_size);
    if (!bytes) { fclose(source); return 1; }
    int read_ok = fread(bytes, 1, (size_t)st.st_size, source) == (size_t)st.st_size;
    fclose(source);
    if (!read_ok) { free(bytes); return 1; }
    CFDataRef data = CFDataCreate(NULL, bytes, st.st_size);
    free(bytes);
    CFPropertyListFormat format;
    CFPropertyListRef plist = CFPropertyListCreateWithData(NULL, data,
        kCFPropertyListMutableContainersAndLeaves, &format, NULL);
    if (!plist) { CFRelease(data); return 1; }
    unsigned counts[5] = {0};
    visit_services(plist, counts, 0);
    int result = 1;
    for (int i = 0; i < 5; i++) if (counts[i] != 1) goto done;
    CFDataRef patched = CFPropertyListCreateData(NULL, plist, format, 0, NULL);
    if (!patched) goto done;
    char backup[1024], temporary[1024];
    if (snprintf(backup, sizeof(backup), "%s.inferno-original", path) >= sizeof(backup) ||
        snprintf(temporary, sizeof(temporary), "%s.inferno-new", path) >= sizeof(temporary)) {
        CFRelease(patched); goto done;
    }
    int backup_fd = open(backup, O_WRONLY | O_CREAT | O_EXCL, st.st_mode & 0777);
    if (backup_fd >= 0) {
        ssize_t n = write(backup_fd, CFDataGetBytePtr(data), CFDataGetLength(data));
        int ok = n == CFDataGetLength(data) && fsync(backup_fd) == 0;
        close(backup_fd);
        if (!ok) { CFRelease(patched); goto done; }
    } else if (access(backup, F_OK) != 0) { CFRelease(patched); goto done; }
    int fd = open(temporary, O_WRONLY | O_CREAT | O_EXCL, st.st_mode & 0777);
    if (fd >= 0) {
        ssize_t n = write(fd, CFDataGetBytePtr(patched), CFDataGetLength(patched));
        int ok = n == CFDataGetLength(patched) && fsync(fd) == 0;
        close(fd);
        if (ok && rename(temporary, path) == 0) result = 0;
        else unlink(temporary);
    }
    CFRelease(patched);
done:
    CFRelease(plist);
    CFRelease(data);
    return result;
}

#ifdef INFERNO_CACHE_TEST
int main(int argc, char** argv) { return argc == 2 ? disable_services_at(argv[1]) : 2; }
#endif
