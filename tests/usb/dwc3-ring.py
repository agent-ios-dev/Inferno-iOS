"""Exercise the backend's actual TRB fetch function, not a rewritten ring model."""
import pathlib
import subprocess
import sys
import tempfile

core = pathlib.Path(sys.argv[1])
source = (core / "hw/usb/hcd-dwc3.c").read_text()

def functions(text):
    length = text[text.index("static int dwc3_bd_length("):text.index("// looks/looked like a bad copy")]
    start = text.index("static bool dwc3_bd_contains_trb(") if "static bool dwc3_bd_contains_trb(" in text else text.index("static void dwc3_td_fetch(")
    fetch = text[start:text.index("\nstatic DWC3Transfer* dwc3_xfer_alloc(", start)]
    return length + fetch

prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <sys/queue.h>
#define QTAILQ_HEAD TAILQ_HEAD
#define QTAILQ_ENTRY TAILQ_ENTRY
#define QTAILQ_FOREACH TAILQ_FOREACH
#define QTAILQ_INSERT_TAIL TAILQ_INSERT_TAIL
#define DPRINTF(...) ((void)0)
#define qemu_log_mask(...) ((void)0)
#define LOG_GUEST_ERROR 0
#define HWADDR_PRIx PRIx64
#define g_new0(type,n) ((type*)calloc(n,sizeof(type)))
#define MEMTXATTRS_UNSPECIFIED 0
#define MEMTX_OK 0
#define TRB_CTRL_HWO 1
#define TRB_CTRL_LST 2
#define TRB_CTRL_TRBCTL(n) (((n)>>4)&0x3f)
enum {TRBCTL_RESERVED,TRBCTL_NORMAL,TRBCTL_CONTROL_SETUP,TRBCTL_CONTROL_STATUS2,
      TRBCTL_CONTROL_STATUS3,TRBCTL_CONTROL_DATA,TRBCTL_ISOCHRONOUS_FIRST,
      TRBCTL_ISOCHRONOUS,TRBCTL_LINK_TRB};
typedef uint64_t dma_addr_t;
struct dwc3_trb { uint32_t bpl,bph,status,ctrl; };
typedef struct {dma_addr_t addr,bp; union { uint32_t status; struct {uint32_t size:24,other:8;}; }; uint32_t ctrl;} DWC3TRB;
typedef struct {void* as;} QEMUSGList;
typedef struct DWC3BufferDesc {DWC3TRB* trbs; QTAILQ_ENTRY(DWC3BufferDesc) queue;
    QEMUSGList sgl; int iov,epid; uint32_t count,length;} DWC3BufferDesc;
typedef struct {dma_addr_t tdaddr; QTAILQ_HEAD(,DWC3BufferDesc) buffers;
    int epid; uint32_t count; bool can_free; uint32_t fetch_stop_reason;} DWC3Transfer;
typedef struct {struct {int parent_obj;} parent_obj; int dma_as;} DWC3State;
static unsigned char memory[4096];
static unsigned accesses;
static int dma_memory_read(void* as,dma_addr_t address,void* out,size_t count,int attrs) {
    assert(++accesses < 1024); /* Broken loop detection cannot hang this test. */
    if(address>sizeof(memory)||count>sizeof(memory)-address)return 1;
    memcpy(out,memory+address,count);return MEMTX_OK;
}
static uint64_t dwc3_addr64(uint32_t lo,uint32_t hi){return (uint64_t)hi<<32|lo;}
static void qemu_iovec_init(int* iov,int n){}
static void qemu_sglist_init(QEMUSGList* s,void* dev,int n,void* as){s->as=as;}
static void qemu_sglist_add(QEMUSGList* s,uint64_t address,uint32_t length){}
static void dwc3_bd_free(DWC3State* s,DWC3BufferDesc* d){free(d->trbs);free(d);}
'''
tests = r'''
static void put(unsigned address,unsigned type,unsigned flags,unsigned target){
    struct dwc3_trb trb={target,0,512,(type<<4)|flags};
    memcpy(memory+address,&trb,sizeof(trb));
}
static void reset(DWC3Transfer* xfer){
    memset(memory,0,sizeof(memory)); memset(xfer,0,sizeof(*xfer));
    TAILQ_INIT(&xfer->buffers);accesses=0;
}
static void clear(DWC3State* s,DWC3Transfer* xfer){
    while(!TAILQ_EMPTY(&xfer->buffers)){
        DWC3BufferDesc* d=TAILQ_FIRST(&xfer->buffers);
        TAILQ_REMOVE(&xfer->buffers,d,queue);dwc3_bd_free(s,d);
    }
}
int main(int argc,char** argv){
    DWC3State s={0};DWC3Transfer x;
    /* Terminal descriptors may contain several data TRBs. Pre-scan termination
     * must not make the fetch loop stop after the first owned TRB. */
    reset(&x);
    put(0x100,TRBCTL_NORMAL,TRB_CTRL_HWO,0x800);
    put(0x110,TRBCTL_NORMAL,TRB_CTRL_HWO|TRB_CTRL_LST,0xa00);
    dwc3_td_fetch(&s,&x,0x100);
    assert(x.count==1&&TAILQ_FIRST(&x.buffers)->count==2&&x.can_free);
    clear(&s,&x);
    reset(&x);
    put(0x100,TRBCTL_NORMAL,TRB_CTRL_HWO,0x800);
    put(0x110,TRBCTL_NORMAL,TRB_CTRL_HWO,0xa00);
    put(0x120,TRBCTL_NORMAL,0,0xc00);
    dwc3_td_fetch(&s,&x,0x100);
    assert(x.count==1&&TAILQ_FIRST(&x.buffers)->count==2&&!x.can_free);
    clear(&s,&x);
    if(argc>1)return 0; /* Independent negative control for terminal fetch. */
    /* Adjacent link target is not part of the current descriptor. The old
     * count+1 self-loop interval incorrectly rejected this legitimate chain. */
    reset(&x);
    put(0x100,TRBCTL_NORMAL,TRB_CTRL_HWO,0x800);
    put(0x110,TRBCTL_LINK_TRB,TRB_CTRL_HWO,0x120);
    put(0x120,TRBCTL_NORMAL,TRB_CTRL_HWO|TRB_CTRL_LST,0xa00);
    dwc3_td_fetch(&s,&x,0x100);
    assert(x.count==2&&x.can_free);clear(&s,&x);
    /* Ascending disjoint descriptors. Old reversed upper-bound comparison
     * treats the forward link to C as a loop into the already queued A. */
    reset(&x);
    put(0x100,TRBCTL_NORMAL,TRB_CTRL_HWO,0x800);
    put(0x110,TRBCTL_LINK_TRB,TRB_CTRL_HWO,0x200);
    put(0x200,TRBCTL_NORMAL,TRB_CTRL_HWO,0xa00);
    put(0x210,TRBCTL_LINK_TRB,TRB_CTRL_HWO,0x300);
    put(0x300,TRBCTL_NORMAL,TRB_CTRL_HWO|TRB_CTRL_LST,0xc00);
    dwc3_td_fetch(&s,&x,0x100);
    assert(x.count==3&&x.can_free);clear(&s,&x);
    /* Real queued-buffer cycle must still stop, not duplicate owned TRBs. */
    reset(&x);
    put(0x100,TRBCTL_NORMAL,TRB_CTRL_HWO,0x800);
    put(0x110,TRBCTL_LINK_TRB,TRB_CTRL_HWO,0x200);
    put(0x200,TRBCTL_NORMAL,TRB_CTRL_HWO,0xa00);
    put(0x210,TRBCTL_LINK_TRB,TRB_CTRL_HWO,0x100);
    dwc3_td_fetch(&s,&x,0x100);
    assert(x.count==2&&!x.can_free);clear(&s,&x);
    reset(&x);
    put(0x100,TRBCTL_NORMAL,TRB_CTRL_HWO,0x800);
    put(0x110,TRBCTL_LINK_TRB,TRB_CTRL_HWO,0x100);
    dwc3_td_fetch(&s,&x,0x100);
    assert(x.count==1&&!x.can_free);clear(&s,&x);
    /* Do not fetch a descriptor before the guest grants ownership. */
    reset(&x);put(0x100,TRBCTL_NORMAL,0,0x800);
    dwc3_td_fetch(&s,&x,0x100);assert(x.count==0&&!x.can_free);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    folder = pathlib.Path(folder)
    def run(text, name, terminal_only=False):
        c = folder / (name + ".c")
        binary = folder / name
        c.write_text(prefix + functions(text) + tests)
        subprocess.run(["cc", "-std=c11", "-Wall", str(c), "-o", str(binary)], check=True)
        return subprocess.run([str(binary)] + (["terminal-only"] if terminal_only else []),
                              capture_output=True, timeout=10).returncode
    assert run(source, "fixed-ring") == 0, "Actual TRB fetch regression failed"
    baseline = subprocess.check_output(["git", "-C", str(core), "show",
        "d5dcc2f0a353f65d9be4ba7b4d4011887f4c2f67:hw/usb/hcd-dwc3.c"], text=True)
    assert run(baseline, "old-ring") != 0, "Negative control must reproduce old false loop rejection"
    preceding = subprocess.check_output(["git", "-C", str(core), "show",
        "1ec087f2746bbd23f18cc1ae1736451a27e11ed3:hw/usb/hcd-dwc3.c"], text=True)
    assert run(preceding, "premature-terminal", terminal_only=True) != 0, "Preceding backend must reproduce premature terminal fetch"
print("Actual DWC3 TRB fetch: complete terminal descriptors, forward chains, real cycles and ownership passed; both old backends failed negative controls")
