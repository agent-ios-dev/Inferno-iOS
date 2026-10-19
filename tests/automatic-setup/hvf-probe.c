/* Host capability probe only: no firmware, guest RAM or instructions run. */
#include <Hypervisor/Hypervisor.h>
#include <os/object.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

static const char *status_name(hv_return_t status)
{
    switch (status) {
        case HV_SUCCESS: return "HV_SUCCESS";
        case HV_ERROR: return "HV_ERROR";
        case HV_BUSY: return "HV_BUSY";
        case HV_BAD_ARGUMENT: return "HV_BAD_ARGUMENT";
        case HV_NO_RESOURCES: return "HV_NO_RESOURCES";
        case HV_NO_DEVICE: return "HV_NO_DEVICE";
        case HV_UNSUPPORTED: return "HV_UNSUPPORTED";
        case HV_DENIED: return "HV_DENIED";
        default: return "UNKNOWN";
    }
}

static void attempt(uint32_t ipa_bits)
{
    hv_vm_config_t config = hv_vm_config_create();
    if (!config) {
        printf("{\"available\":false,\"stage\":\"config_alloc\"}");
        return;
    }
    const char *stage = "configure_ipa40";
    hv_return_t result = ipa_bits ? hv_vm_config_set_ipa_size(config, ipa_bits) : HV_SUCCESS;
    bool vm_created = false;
    bool vcpu_created = false;
    hv_vcpu_t vcpu = 0;
    hv_vcpu_exit_t *exit_info = NULL;
    if (result == HV_SUCCESS) {
        stage = "vm_create";
        result = hv_vm_create(config);
        vm_created = result == HV_SUCCESS;
    }
    if (vm_created) {
        stage = "vcpu_create";
        result = hv_vcpu_create(&vcpu, &exit_info, NULL);
        vcpu_created = result == HV_SUCCESS;
    }
    uint32_t cleanup = 0;
    if (vcpu_created) { cleanup = (uint32_t)hv_vcpu_destroy(vcpu); }
    if (vm_created) {
        hv_return_t destroyed = hv_vm_destroy();
        if (destroyed != HV_SUCCESS) { cleanup = (uint32_t)destroyed; }
    }
    os_release(config);
    printf("{\"available\":%s,\"ipa_bits\":%u,\"stage\":\"%s\",\"status\":%u,\"status_name\":\"%s\",\"cleanup_status\":%u}",
           vcpu_created ? "true" : "false", ipa_bits, stage, (uint32_t)result, status_name(result), cleanup);
}

int main(void)
{
    printf("{\"ipa40\":");
    attempt(40);
    /* A rejected IPA setting alone does not prove the default VM unavailable. */
    printf(",\"host_default\":");
    attempt(0);
    puts("}");
    return 0;
}
