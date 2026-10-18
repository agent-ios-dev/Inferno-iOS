"""Compile the real DART invalidation case with reentrant mapping notifiers."""
import pathlib
import subprocess
import sys
import tempfile

source = pathlib.Path(sys.argv[1]).read_text()
start = source.index('        case R_DART_TLB_OP:', source.index('static void apple_dart_mapper_reg_write('))
end = source.index('        case R_DART_TLB_OP_SET_0_LOW:', start)
case = source[start:end]
wait_start = source.index('static void apple_dart_wait_for_invalidation(')
wait_end = source.index('static IOMMUTLBEntry apple_dart_mapper_translate(', wait_start)
wait_helper = source[wait_start:wait_end]
prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <sched.h>
#define DART_MAX_STREAMS 4
#define DART_MAX_TLB_OP_SETS 2
#define R_DART_TLB_OP 8
#define R_DART_TLB_OP_BUSY_MASK 4u
#define DART_TLB_OP_INVALIDATE 1
#define BIT_ULL(i) (1ull<<(i))
#define qatomic_read(p) (*(p))
#define qatomic_read__nocheck(p) (*(p))
#define qatomic_set(p,v) do { *(p)=(v); invalidation_started=true; } while(0)
#define qatomic_and(p,v) __atomic_fetch_and(p,v,__ATOMIC_RELEASE)
#define qatomic_load_acquire(p) __atomic_load_n(p,__ATOMIC_ACQUIRE)
#define cpu_relax() sched_yield()
#define OP_SHIFT 0
#define OP_MASK 3
#define BUSY_SHIFT 2
#define BUSY_MASK 1
#define SET_INDEX_SHIFT 20
#define SET_INDEX_MASK 4095
#define REG_FIELD_EX32(v,r,f) (((v)>>f##_SHIFT)&f##_MASK)
#define REG_FIELD_DP32(v,r,f,x) (((v)&~(f##_MASK<<f##_SHIFT))|((x)<<f##_SHIFT))
typedef struct {
    struct { struct { uint64_t sid_mask; struct { struct { const char *id; } parent_obj; } parent_obj; } *dart; } common;
    struct { uint32_t tlb_op; uint64_t tlb_op_set[2]; } regs;
    unsigned generations[4];
} AppleDARTMapperInstance;
static bool invalidation_started;
static unsigned notifications, replayed;
static uint64_t expected_sids;
static int waiter_entered;
static void error_report(const char *message) { __atomic_store_n(&waiter_entered,1,__ATOMIC_RELEASE); }
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
'''
writer_prefix = r'''
static void write_tlb_op(AppleDARTMapperInstance *mapper,uint32_t val) {
    uint32_t i,set_index; uint64_t sid_mask=0;
    switch(R_DART_TLB_OP) {
'''
suffix = r'''
    }
}
static void *finish_invalidation(void *opaque) {
    AppleDARTMapperInstance *m=opaque;
    while (!__atomic_load_n(&waiter_entered,__ATOMIC_ACQUIRE)) sched_yield();
    m->generations[0]=9;
    qatomic_and(&m->regs.tlb_op,~R_DART_TLB_OP_BUSY_MASK);
    return NULL;
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
    // A real concurrent invalidation must finish, rather than being reported
    // as an unmapped DMA access. Its generation writes become visible too.
    dart.parent_obj.parent_obj.id="dart-usb";
    m.regs.tlb_op=R_DART_TLB_OP_BUSY_MASK;
    pthread_t worker;
    assert(pthread_create(&worker,NULL,finish_invalidation,&m)==0);
    apple_dart_wait_for_invalidation(&m);
    assert(m.generations[0]==9 && !(m.regs.tlb_op&R_DART_TLB_OP_BUSY_MASK));
    assert(pthread_join(worker,NULL)==0);
    puts("Real DART invalidation: reentrant replay, remapped streams, empty sets and concurrent completion passed");
}
'''
with tempfile.TemporaryDirectory() as folder:
    c = pathlib.Path(folder) / 'dart.c'
    binary = pathlib.Path(folder) / 'dart-test'
    c.write_text(prefix + wait_helper + writer_prefix + case + suffix)
    subprocess.run(['cc', '-std=gnu11', '-Wall', '-pthread', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
