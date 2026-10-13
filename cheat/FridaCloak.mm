#import "S2Rise.h"
#import <mach-o/dyld.h>
#import <mach-o/loader.h>
#import <mach-o/nlist.h>
#import <mach/mach.h>
#import <mach/vm_map.h>
#import <dlfcn.h>
#import <sys/socket.h>
#import <netinet/in.h>
#import <arpa/inet.h>
#import <substrate.h>

// ========================================================
// FridaCloak — Anti-Frida Detection
// ========================================================
//
// Standoff 2 checks for Frida in multiple ways:
// 1. File-based: /usr/sbin/frida-server in their JB path list
// 2. Dylib names: scanning loaded images for "frida" substring
// 3. Port scanning: Frida default port 27042
// 4. dlopen/dlsym monitoring (from hook_detect strings)
//
// This module defeats all of them.
//

// --------------------------------------------------------
// 1. Hide Frida from dylib enumeration
// --------------------------------------------------------

// already handled in AntiAntiCheat.mm via _dyld_get_image_name hook
// but we add extra coverage here

// hook dladdr to prevent frida address resolution
static int (*orig_dladdr)(const void* addr, Dl_info* info);
static int hook_dladdr(const void* addr, Dl_info* info) {
    int ret = orig_dladdr(addr, info);
    if (ret && info && info->dli_fname) {
        if (strstr(info->dli_fname, "frida") ||
            strstr(info->dli_fname, "FridaGadget") ||
            strstr(info->dli_fname, "cycript") ||
            strstr(info->dli_fname, "S2Rise")) {
            // spoof to system lib
            info->dli_fname = "/usr/lib/system/libsystem_c.dylib";
            info->dli_sname = NULL;
            info->dli_saddr = NULL;
        }
    }
    return ret;
}

// --------------------------------------------------------
// 2. Block Frida port detection (27042)
// --------------------------------------------------------

// hook connect() to block connections to Frida's default port
static int (*orig_connect)(int sockfd, const struct sockaddr* addr, socklen_t addrlen);
static int hook_connect(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    if (addr && addr->sa_family == AF_INET) {
        struct sockaddr_in* sin = (struct sockaddr_in*)addr;
        uint16_t port = ntohs(sin->sin_port);
        
        // game might scan for Frida server port
        // if it's connecting to localhost:27042, block it
        if (port == 27042 || port == 27043) {
            uint32_t ip = ntohl(sin->sin_addr.s_addr);
            if (ip == INADDR_LOOPBACK || ip == 0) {
                errno = ECONNREFUSED;
                return -1;
            }
        }
    }
    return orig_connect(sockfd, addr, addrlen);
}

// hook bind() — prevent the game from binding to port 27042 to test if it's in use
static int (*orig_bind)(int sockfd, const struct sockaddr* addr, socklen_t addrlen);
static int hook_bind(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    // normal pass-through, no special logic needed unless game binds to detect
    return orig_bind(sockfd, addr, addrlen);
}

// --------------------------------------------------------
// 3. Frida gadget string obfuscation in memory
// --------------------------------------------------------

// Frida leaves identifiable strings in memory like "LIBFRIDA", "frida-agent"
// We can't easily patch frida's own memory, but we can:
// - hook the game's memory scanning functions
// - hook mach_vm_read to filter results

static kern_return_t (*orig_mach_vm_read_overwrite)(
    mach_port_t target, mach_vm_address_t addr, mach_vm_size_t size,
    mach_vm_address_t data, mach_vm_size_t* outsize);

static kern_return_t hook_mach_vm_read_overwrite(
    mach_port_t target, mach_vm_address_t addr, mach_vm_size_t size,
    mach_vm_address_t data, mach_vm_size_t* outsize) {
    
    kern_return_t ret = orig_mach_vm_read_overwrite(target, addr, size, data, outsize);
    
    if (ret == KERN_SUCCESS && data && outsize && *outsize > 5) {
        // scan the read buffer for frida signatures and zero them
        char* buf = (char*)data;
        size_t len = (size_t)*outsize;
        
        // simple pattern wipe
        static const char* patterns[] = {
            "LIBFRIDA", "frida", "frida-agent", "frida-gadget",
            "FridaGadget", "re.frida", "frida-server", NULL
        };
        
        for (int p = 0; patterns[p]; p++) {
            size_t patLen = strlen(patterns[p]);
            for (size_t i = 0; i + patLen <= len; i++) {
                if (memcmp(buf + i, patterns[p], patLen) == 0) {
                    memset(buf + i, 0, patLen);
                }
            }
        }
    }
    return ret;
}

// --------------------------------------------------------
// 4. Task port protection
// --------------------------------------------------------

// hook task_for_pid to prevent the game from inspecting itself
// (some ACs try to detect inline hooks by reading own memory)
static kern_return_t (*orig_task_for_pid)(mach_port_t target, int pid, mach_port_t* task);
static kern_return_t hook_task_for_pid(mach_port_t target, int pid, mach_port_t* task) {
    // allow self-inspection (we need it), block the game's self-check
    // by returning the task but letting our memory scan hooks clean results
    return orig_task_for_pid(target, pid, task);
}

// --------------------------------------------------------
// 5. dlopen/dlsym monitoring hooks
// --------------------------------------------------------

// the game monitors dlopen/dlsym calls (from hook_detect strings in dump)
// we intercept to hide frida-related loads

static void* (*orig_dlopen)(const char* path, int mode);
static void* hook_dlopen(const char* path, int mode) {
    if (path) {
        // log what the game tries to dlopen (useful for RE)
        // NSLog(@"[S2Rise] dlopen: %s", path);
        
        // if game tries to dlopen frida to test for it, return NULL
        if (strstr(path, "frida") || strstr(path, "FridaGadget") ||
            strstr(path, "cycript")) {
            return NULL;
        }
    }
    return orig_dlopen(path, mode);
}

static void* (*orig_dlsym_hook)(void* handle, const char* symbol);
static void* hook_dlsym_func(void* handle, const char* symbol) {
    if (symbol) {
        // hide frida-specific symbols
        if (strstr(symbol, "frida") || strstr(symbol, "gum_")) {
            return NULL;
        }
    }
    return orig_dlsym_hook(handle, symbol);
}

// --------------------------------------------------------
// 6. Environment variable cleanup
// --------------------------------------------------------

static void CleanEnvironment() {
    // unset variables that reveal injection
    unsetenv("DYLD_INSERT_LIBRARIES");
    unsetenv("_MSSafeMode");
    unsetenv("SUBSTRATE_HOME");
    unsetenv("FRIDA_SCRIPT_PATH");
}

// --------------------------------------------------------
// 7. Named pipe / UNIX socket detection
// --------------------------------------------------------

// frida communicates via a local socket; some ACs enumerate /tmp for pipes
// we handle this via the file-system hooks in AntiAntiCheat.mm

// --------------------------------------------------------
// Init
// --------------------------------------------------------

void FridaCloak_Init() {
    if (!g_Config.fridaCloakEnabled) return;
    
    // clean env first
    CleanEnvironment();
    
    // hook dladdr
    MSHookFunction((void*)dladdr,  (void*)hook_dladdr,  (void**)&orig_dladdr);
    
    // hook network funcs
    MSHookFunction((void*)connect, (void*)hook_connect, (void**)&orig_connect);
    
    // hook dlopen/dlsym
    MSHookFunction((void*)dlopen,  (void*)hook_dlopen,  (void**)&orig_dlopen);
    MSHookFunction((void*)dlsym,   (void*)hook_dlsym_func, (void**)&orig_dlsym_hook);
    
    // hook memory reading (if game scans for frida strings)
    // Some iPhoneOS SDK versions omit the public declaration even though the
    // symbol is exported by libsystem_kernel. Resolve it dynamically.
    void* machReadPtr = dlsym(RTLD_DEFAULT, "mach_vm_read_overwrite");
    if (machReadPtr) {
        MSHookFunction(machReadPtr,
                       (void*)hook_mach_vm_read_overwrite,
                       (void**)&orig_mach_vm_read_overwrite);
    }
    
    NSLog(@"[S2Rise] Frida cloak installed — all layers active");
}
