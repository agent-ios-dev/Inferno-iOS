/* A visible stdout marker proves only injection into this test process. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void)
{
    const char* value = getenv("INFERNO_TEST_DYLIB_LOADED");
    if (!value || strcmp(value, "1")) {
        puts("INFERNO_INJECTION_PROBE_NOT_LOADED");
        return 3;
    }
    puts("INFERNO_INJECTION_PROBE_LOADED");
    return 0;
}
