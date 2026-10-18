"""Compile the real DART invalidation case with reentrant mapping notifiers."""
import pathlib
import subprocess
import sys
import tempfile

source = pathlib.Path(sys.argv[1]).read_text()
start = source.index('        case R_DART_TLB_OP:', source.index('static void apple_dart_mapper_reg_write('))
end = source.index('        case R_DART_TLB_OP_SET_0_LOW:', start)
case = source[start:end]
prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define DART_MAX_STREAMS 4
#define DART_MAX_TLB_OP_SETS 2
#define R_DART_TLB_OP 8
#define R_DART_TLB_OP_BUSY_MASK 4u
#define DART_TLB_OP_INVALIDATE 1
#define BIT_ULL(i) (1ull<<(i))
#define qatomic_read(p) (*(p))
#define qatomic_read__nocheck(p) (*(p))
#define qatomic_set(p,v) do { *(p)=(v); invalidation_started=true; } while(0)
#define qatomic_and(p,v) (*(p)&=(v))
#define OP_SHIFT 0
#define OP_MASK 3
#define BUSY_SHIFT 2
#define BUSY_MASK 1
#define SET_INDEX_SHIFT 20
#define SET_INDEX_MASK 4095
#define REG_FIELD_EX32(v,r,f) (((v)>>f##_SHIFT)&f##_MASK)
#define REG_FIELD_DP32(v,r,f,x) (((v)&~(f##_MASK<<f##_SHIFT))|((x)<<f##_SHIFT))
typedef struct {
    struct { struct { uint64_t sid_mask; } *dart; } common;
    struct { uint32_t tlb_op; uint64_t tlb_op_set[2]; } regs;
    unsigned generations[4];
} AppleDARTMapperInstance;
static bool invalidation_started;
static unsigned notifications, replayed;
static uint64_t expected_sids;
static unsigned remap[4]={2,1,0,3};
static unsigned apple_dart_sid_remap(AppleDARTMapperInstance *m,unsigned i) { return remap[i]; }
static void apple_dart_tlb_flush_sid(AppleDARTMapperInstance *m,unsigned i) { m->generations[i]++; }
static void apple_dart_notify_remap(AppleDARTMapperInstance *m,unsigned i) {
    notifications++;
    if (!invalidation_started) return; // Preserved pre-command notification.
    // A notifier reentering translate must see a completed invalidation,
    // with every selected stream updated, including streams notified later.
    assert(!(m->regs.tlb_op&R_DART_TLB_OP_BUSY_MASK));
    for (unsigned j=0;j<4;j++)
        assert(m->generations[remap[j]]==!!(expected_sids&BIT_ULL(j)));
    replayed++;
}
static void write_tlb_op(AppleDARTMapperInstance *mapper,uint32_t val) {
    uint32_t i,set_index; uint64_t sid_mask=0;
    switch(R_DART_TLB_OP) {
'''
suffix = r'''
    }
}
int main(void) {
    AppleDARTMapperInstance m={0};
    __typeof__(*m.common.dart) dart={.sid_mask=15}; m.common.dart=&dart;
    m.regs.tlb_op_set[0]=1; m.regs.tlb_op_set[1]=2;
    expected_sids=3;
    write_tlb_op(&m,1|(3u<<20));
    assert(replayed==2 && notifications==6);
    assert(!(m.regs.tlb_op&R_DART_TLB_OP_BUSY_MASK));
    // Empty selected sets still complete, without a spurious generation bump.
    memset(m.generations,0,sizeof(m.generations));
    m.regs.tlb_op_set[0]=0; invalidation_started=false;
    replayed=notifications=0; expected_sids=0;
    write_tlb_op(&m,1|(1u<<20));
    assert(replayed==0 && notifications==4);
    assert(!(m.regs.tlb_op&R_DART_TLB_OP_BUSY_MASK));
    puts("Real DART invalidation: reentrant replay sees completed generations, remapped streams and empty sets passed");
}
'''
with tempfile.TemporaryDirectory() as folder:
    c = pathlib.Path(folder) / 'dart.c'
    binary = pathlib.Path(folder) / 'dart-test'
    c.write_text(prefix + case + suffix)
    subprocess.run(['cc', '-std=gnu11', '-Wall', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
