"""Compile the backend's real range helper with a bounded DMA address space."""
import pathlib
import subprocess
import sys
import tempfile

source = pathlib.Path(sys.argv[1]).read_text()
start = source.index('static MemTxResult dwc3_bd_rw(')
end = source.index('\nstatic int dwc3_bd_copy(', start)
helper = source[start:end]
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef uint64_t dma_addr_t;
typedef int MemTxResult;
#define MEMTX_OK 0
#define MEMTX_ERROR 1
#define MEMTXATTRS_UNSPECIFIED 0
#define MIN(a,b) ((a)<(b)?(a):(b))
static void error_report(const char *message) { (void)message; }
typedef struct { dma_addr_t base, len; } ScatterGatherEntry;
typedef struct { void *as; int nsg; ScatterGatherEntry *sg; } QEMUSGList;
typedef struct { unsigned actual_length; QEMUSGList sgl; } DWC3BufferDesc;
static unsigned char memory[1024];
static size_t valid_end, accesses;
static MemTxResult dma_memory_read(void *as, dma_addr_t address, void *out, size_t count, int attrs) {
    accesses++;
    if (address > valid_end || count > valid_end-address) return MEMTX_ERROR;
    memcpy(out, memory+address, count); return MEMTX_OK;
}
static MemTxResult dma_memory_write(void *as, dma_addr_t address, const void *in, size_t count, int attrs) {
    accesses++;
    if (address > valid_end || count > valid_end-address) return MEMTX_ERROR;
    memcpy(memory+address, in, count); return MEMTX_OK;
}
'''
tests = r'''
int main(void) {
    ScatterGatherEntry entries[] = {{100, 64}, {300, 64}, {900, 64}};
    DWC3BufferDesc desc = {0, {NULL, 3, entries}};
    unsigned char bytes[128];
    for (int i=0; i<1024; i++) memory[i]=(unsigned char)i;
    valid_end=164; accesses=0;
    assert(dwc3_bd_rw(&desc,bytes,64,false)==MEMTX_OK);
    assert(accesses==1 && memcmp(bytes,memory+100,64)==0);
    // The following two buffers are not mapped yet. They must not be touched.
    desc.actual_length=48; valid_end=364; accesses=0;
    assert(dwc3_bd_rw(&desc,bytes,32,false)==MEMTX_OK);
    assert(accesses==2);
    assert(memcmp(bytes,memory+148,16)==0 && memcmp(bytes+16,memory+300,16)==0);
    // Permission revocation between packets must be observed, never cached.
    desc.actual_length=64; valid_end=300;
    assert(dwc3_bd_rw(&desc,bytes,1,false)==MEMTX_ERROR);
    valid_end=364; memset(bytes,0xab,32);
    assert(dwc3_bd_rw(&desc,bytes,32,true)==MEMTX_OK);
    assert(memcmp(memory+300,bytes,32)==0);
    desc.actual_length=192; accesses=0;
    assert(dwc3_bd_rw(&desc,bytes,1,false)==MEMTX_ERROR && accesses==0);
    assert(dwc3_bd_rw(&desc,bytes,0,false)==MEMTX_OK && accesses==0);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    c = pathlib.Path(folder) / 'range.c'
    binary = pathlib.Path(folder) / 'range-test'
    c.write_text(prefix + helper + tests)
    subprocess.run(['cc', '-std=c11', '-Wall', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('Actual DWC3 DMA helper: range boundaries, cross-SG copies, revoked mappings and errors passed')
