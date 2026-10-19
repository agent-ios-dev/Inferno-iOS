/* Host capability probe only: no firmware, guest RAM or instructions run. */
#include <Hypervisor/Hypervisor.h>
#include <os/object.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

int main(void)
{
    hv_vm_config_t config = hv_vm_config_create();
    if (!config) {
        puts("{\"available\":false,\"stage\":\"config_alloc\"}");
        return 0;
    }
    const char *stage = "configure_ipa40";
    hv_return_t result = hv_vm_config_set_ipa_size(config, 40);
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
    printf("{\"available\":%s,\"ipa_bits\":40,\"stage\":\"%s\",\"status\":%u,\"cleanup_status\":%u}\n",
           vcpu_created ? "true" : "false", stage, (uint32_t)result, cleanup);
    return 0;
}
