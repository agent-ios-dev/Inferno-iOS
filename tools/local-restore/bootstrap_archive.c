/* Utility archive extraction, used ONLY on an experimental VM copy. */
#include <archive.h>
#include <archive_entry.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int safe_archive_path(const char* name)
{
    if (!name || !*name || *name == '/') return 0;
    const char* at = name;
    while (*at) {
        const char* end = strchr(at, '/');
        size_t length = end ? (size_t)(end-at) : strlen(at);
        if (!length || (length == 2 && !memcmp(at, "..", 2))) return 0;
        if (!end) break;
        at = end+1;
    }
    return 1;
}

static int extract_bootstrap(const void* bytes, size_t size)
{
    struct archive* reader = archive_read_new();
    struct archive* writer = archive_write_disk_new();
    archive_read_support_filter_lzma(reader);
    archive_read_support_format_tar(reader);
    archive_write_disk_set_options(writer, ARCHIVE_EXTRACT_PERM |
        ARCHIVE_EXTRACT_SECURE_NODOTDOT | ARCHIVE_EXTRACT_SECURE_NOABSOLUTEPATHS |
        ARCHIVE_EXTRACT_SECURE_SYMLINKS);
    int result = 1, count = 0;
    size_t expanded = 0;
    if (archive_read_open_memory(reader, bytes, size) != ARCHIVE_OK) goto done;
    struct archive_entry* entry;
    int status;
    while ((status = archive_read_next_header(reader, &entry)) == ARCHIVE_OK) {
        const char* name = archive_entry_pathname(entry);
        mode_t type = archive_entry_filetype(entry);
        if (++count > 5000 || !safe_archive_path(name) ||
            (type != AE_IFREG && type != AE_IFDIR && type != AE_IFLNK) ||
            archive_entry_hardlink(entry) || archive_entry_size(entry) < 0) goto done;
        expanded += (size_t)archive_entry_size(entry);
        if (expanded > 128 * 1024 * 1024) goto done;
        if (archive_write_header(writer, entry) < ARCHIVE_OK) goto done;
        const void* block; size_t length; la_int64_t offset;
        int read_status;
        while ((read_status = archive_read_data_block(reader, &block, &length, &offset)) == ARCHIVE_OK)
            if (archive_write_data_block(writer, block, length, offset) < ARCHIVE_OK) goto done;
        if (read_status != ARCHIVE_EOF || archive_write_finish_entry(writer) < ARCHIVE_OK) goto done;
    }
    if (status == ARCHIVE_EOF) result = 0;
done:
    if (result) fprintf(stderr, "*** BOOTSTRAP: archive failed after %d entries: %s / %s\n",
        count, archive_error_string(reader), archive_error_string(writer));
    archive_write_free(writer); archive_read_free(reader);
    return result;
}

#ifdef INFERNO_BOOTSTRAP_ARCHIVE_TEST
#include <stdlib.h>
int main(int argc, char** argv)
{
    if (argc != 3) return 2;
    FILE* f = fopen(argv[2], "rb"); if (!f) return 2;
    fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
    if (size <= 0 || size > 20*1024*1024) return 2;
    void* data = malloc(size);
    if (!data || fread(data, 1, size, f) != (size_t)size) return 2;
    fclose(f);
    if (chdir(argv[1])) return 2;
    int result = extract_bootstrap(data, size); free(data); return result;
}
#endif
