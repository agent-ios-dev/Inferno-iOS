#include <stdlib.h>

__attribute__((constructor)) static void mark_loaded(void)
{
    setenv("INFERNO_TEST_DYLIB_LOADED", "1", 1);
}
