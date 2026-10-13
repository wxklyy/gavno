#import "S2Rise.h"
#import <sys/sysctl.h>
#import <mach/mach.h>
#import <dlfcn.h>
#import <objc/runtime.h>
#import <substrate.h>

// ========================================================
// AntiAntiCheat — Neutralize Standoff 2's AC system
// ========================================================

// --------------------------------------------------------
// 1. Jailbreak Detection Bypass
// --------------------------------------------------------

// hook NSFileManager fileExistsAtPath: to hide JB artifacts
static BOOL (*orig_fileExistsAtPath)(id self, SEL _cmd, NSString* path);
static BOOL hook_fileExistsAtPath(id self, SEL _cmd, NSString* path) {
    // paths checked by ios_jailbreak.mm
    static NSArray* blockedPaths = @[
        @"/Applications/Cydia.app",
        @"/Applications/blackra1n.app",
        @"/Applications/FakeCarrier.app",
        @"/Applications/IntelliScreen.app",
        @"/Applications/Snoop-itConfig.app",
        @"/Library/MobileSubstrate/MobileSubstrate.dylib",
        @"/Library/MobileSubstrate/DynamicLibraries/Veency.plist",
        @"/Library/MobileSubstrate/DynamicLibraries/LiveClock.plist",
        @"/System/Library/LaunchDaemons/com.saurik.Cydia.Startup.plist",
        @"/System/Library/LaunchDaemons/com.ikey.bbot.plist",
        @"/usr/libexec/ssh-keysign",
        @"/usr/libexec/cydia",
        @"/usr/sbin/frida-server",
        @"/private/var/lib/cydia",
        @"/private/var/tmp/cydia.log",
        @"/var/lib/cydia",
        @"/private/jailbreak.txt",
        @"/var/jb",                        // modern rootless
        @"/var/jb/usr/lib",
        @"/usr/lib/substitute",
        @"/usr/lib/libsubstitute.dylib",
    ];
    
    for (NSString* blocked in blockedPaths) {
        if ([path hasPrefix:blocked]) {
            return NO;
        }
    }
    return orig_fileExistsAtPath(self, _cmd, path);
}

// hook fopen to catch C-level file checks
static FILE* (*orig_fopen)(const char* path, const char* mode);
static FILE* hook_fopen(const char* path, const char* mode) {
    if (path) {
        static const char* blockedCPaths[] = {
            "/Applications/Cydia.app",
            "/Library/MobileSubstrate",
            "/usr/sbin/frida-server",
            "/private/var/lib/cydia",
            "/private/jailbreak.txt",
            "/var/jb",
            NULL
        };
        for (int i = 0; blockedCPaths[i]; i++) {
            if (strstr(path, blockedCPaths[i])) {
                return NULL;
            }
        }
    }
    return orig_fopen(path, mode);
}

// hook access() 
static int (*orig_access)(const char* path, int mode);
static int hook_access(const char* path, int mode) {
    if (path) {
        if (strstr(path, "Cydia") || strstr(path, "substrate") ||
            strstr(path, "frida") || strstr(path, "jailbreak") ||
            strstr(path, "/var/jb")) {
            errno = ENOENT;
            return -1;
        }
    }
    return orig_access(path, mode);
}

// hook stat()
static int (*orig_stat)(const char* path, struct stat* buf);
static int hook_stat(const char* path, struct stat* buf) {
    if (path) {
        if (strstr(path, "Cydia") || strstr(path, "substrate") ||
            strstr(path, "frida") || strstr(path, "/var/jb")) {
            errno = ENOENT;
            return -1;
        }
    }
    return orig_stat(path, buf);
}

// --------------------------------------------------------
// 2. canOpenURL Bypass (cydia:// scheme)
// --------------------------------------------------------

static BOOL (*orig_canOpenURL)(id self, SEL _cmd, NSURL* url);
static BOOL hook_canOpenURL(id self, SEL _cmd, NSURL* url) {
    NSString* scheme = url.scheme;
    if ([scheme isEqualToString:@"cydia"] ||
        [scheme isEqualToString:@"sileo"] ||
        [scheme isEqualToString:@"zbra"]) {
        return NO;
    }
    return orig_canOpenURL(self, _cmd, url);
}

// --------------------------------------------------------
// 3. Anti-Debug Bypass
// --------------------------------------------------------

// hook ptrace
static int (*orig_ptrace)(int request, pid_t pid, caddr_t addr, int data);
static int hook_ptrace(int request, pid_t pid, caddr_t addr, int data) {
    if (request == 31) { // PT_DENY_ATTACH
        return 0; // silently succeed without actually denying
    }
    return orig_ptrace(request, pid, addr, data);
}

// hook sysctl to hide P_TRACED flag
static int (*orig_sysctl)(int* name, u_int nlen, void* old, size_t* oldlen, void* nw, size_t nwl);
static int hook_sysctl(int* name, u_int nlen, void* old, size_t* oldlen, void* nw, size_t nwl) {
    int ret = orig_sysctl(name, nlen, old, oldlen, nw, nwl);
    
    if (ret == 0 && nlen == 4 && name[0] == CTL_KERN && name[1] == KERN_PROC &&
        name[2] == KERN_PROC_PID && name[3] == getpid()) {
        struct kinfo_proc* info = (struct kinfo_proc*)old;
        if (info) {
            info->kp_proc.p_flag &= ~P_TRACED; // clear traced flag
        }
    }
    return ret;
}

// --------------------------------------------------------
// 4. Dylib List Hiding  
// --------------------------------------------------------

// hide our dylib from _dyld_get_image_name enumeration
static const char* (*orig_dyld_get_image_name)(uint32_t idx);
static const char* hook_dyld_get_image_name(uint32_t idx) {
    const char* name = orig_dyld_get_image_name(idx);
    if (name) {
        // hide our tweak and substrate
        if (strstr(name, "S2Rise") || strstr(name, "FridaGadget") ||
            strstr(name, "frida") || strstr(name, "cycript")) {
            return "/usr/lib/system/libsystem_c.dylib"; // innocuous replacement
        }
    }
    return name;
}

static uint32_t (*orig_dyld_image_count)();
static uint32_t hook_dyld_image_count() {
    // could subtract hidden images, but simpler to just return original
    // since we're spoofing the names anyway
    return orig_dyld_image_count();
}

// --------------------------------------------------------
// 5. AntiCheatManager Neutralization (IL2CPP hooks)
// --------------------------------------------------------

// these get installed after IL2CPP is initialized
static void AAC_HookIL2CPP() {
    // hook AntiCheatManager.NFIAANGEACF (init/main check)
    void* mtd_init = IL2CPP::ResolveMethod(
        "Axlebolt.Standoff.Anitcheat", "AntiCheatManager", "NFIAANGEACF", 0);
    if (mtd_init) {
        void* ptr = IL2CPP::il2cpp_method_get_pointer(mtd_init);
        if (ptr) {
            // NOP the init — replace with empty function
            MSHookFunction(ptr, (void*)(void(*)())([](){}), NULL);
            NSLog(@"[S2Rise] Hooked AntiCheatManager.NFIAANGEACF → NOP");
        }
    }
    
    // hook EGJIPKOMIMC (report to server) — swallow the report
    void* mtd_report = IL2CPP::ResolveMethod(
        "Axlebolt.Standoff.Anitcheat", "AntiCheatManager", "EGJIPKOMIMC", 0);
    if (mtd_report) {
        void* ptr = IL2CPP::il2cpp_method_get_pointer(mtd_report);
        if (ptr) {
            MSHookFunction(ptr, (void*)(void(*)())([](){}), NULL);
            NSLog(@"[S2Rise] Hooked AntiCheatManager.EGJIPKOMIMC (report) → NOP");
        }
    }
    
    // hook GameAntiCheatManager.ReportViaServer — the nuclear option
    void* mtd_gameReport = IL2CPP::ResolveMethod(
        "Axlebolt.Standoff.Game.Anticheat", "GameAntiCheatManager", "ReportViaServer", -1);
    if (mtd_gameReport) {
        void* ptr = IL2CPP::il2cpp_method_get_pointer(mtd_gameReport);
        if (ptr) {
            MSHookFunction(ptr, (void*)(void(*)())([](){}), NULL);
            NSLog(@"[S2Rise] Hooked GameAntiCheatManager.ReportViaServer → NOP");
        }
    }
    
    // hook Firebase RemoteConfig to disable AC flags
    void* mtd_remoteGet = IL2CPP::ResolveMethod(
        "Firebase.RemoteConfig", "FirebaseRemoteConfig", "GetValue", 1);
    if (mtd_remoteGet) {
        // this one's more complex — need to check the key and return false for anticheat_*
        NSLog(@"[S2Rise] Firebase RemoteConfig.GetValue found — hook if needed");
    }
    
    NSLog(@"[S2Rise] IL2CPP anti-AC hooks installed");
}

// --------------------------------------------------------
// Init — Install all hooks
// --------------------------------------------------------

void AAC_Init() {
    if (!g_Config.antiACEnabled) return;
    
    // --- Obj-C hooks ---
    MSHookMessageEx(
        objc_getClass("NSFileManager"),
        @selector(fileExistsAtPath:),
        (IMP)hook_fileExistsAtPath,
        (IMP*)&orig_fileExistsAtPath);
    
    MSHookMessageEx(
        objc_getClass("UIApplication"),
        @selector(canOpenURL:),
        (IMP)hook_canOpenURL,
        (IMP*)&orig_canOpenURL);
    
    // --- C hooks ---
    MSHookFunction((void*)fopen,    (void*)hook_fopen,    (void**)&orig_fopen);
    MSHookFunction((void*)access,   (void*)hook_access,   (void**)&orig_access);
    MSHookFunction((void*)stat,     (void*)hook_stat,     (void**)&orig_stat);
    
    // --- anti-debug ---
    void* ptrace_ptr = dlsym(RTLD_DEFAULT, "ptrace");
    if (ptrace_ptr) {
        MSHookFunction(ptrace_ptr, (void*)hook_ptrace, (void**)&orig_ptrace);
    }
    MSHookFunction((void*)sysctl, (void*)hook_sysctl, (void**)&orig_sysctl);
    
    // --- dylib hiding ---
    MSHookFunction((void*)_dyld_get_image_name, (void*)hook_dyld_get_image_name,
                   (void**)&orig_dyld_get_image_name);
    
    NSLog(@"[S2Rise] Anti-AC system hooks installed");
    
    // schedule IL2CPP hooks after runtime is ready
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 3 * NSEC_PER_SEC),
                   dispatch_get_main_queue(), ^{
        AAC_HookIL2CPP();
    });
}
