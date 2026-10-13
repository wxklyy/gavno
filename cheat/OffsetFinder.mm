#import "S2Rise.h"
#import <objc/runtime.h>

// ========================================================
// OffsetFinder — Runtime IL2CPP class/field/method resolver
// ========================================================
//
// Since the metadata has partial string encryption,
// we resolve everything at RUNTIME via il2cpp API.
// This is more reliable and works across versions.
//

// --------------------------------------------------------
// Resolved game pointers (populated at runtime)
// --------------------------------------------------------

namespace Game {
    // Classes
    void* PlayerController_klass = nullptr;
    void* PlayerManager_klass = nullptr;
    void* GameManager_klass = nullptr;
    void* WeaponManager_klass = nullptr;
    void* GameAntiCheatManager_klass = nullptr;
    void* AntiCheatManager_klass = nullptr;
    void* HitController_klass = nullptr;
    
    // PlayerController field offsets (calculated at runtime)
    int off_health = -1;
    int off_isAlive = -1;
    int off_teamId = -1;
    int off_nickName = -1;
    int off_isLocal = -1;
    int off_animator = -1;
    int off_transform = -1;
    int off_weapon = -1;
    int off_playerData = -1;
    int off_isDead = -1;
    int off_isBot = -1;
    
    // PlayerManager
    int off_players = -1;      // List<> of players
    int off_localPlayer = -1;
    void* (*fn_get_Instance)() = nullptr;
    
    // GameManager  
    void* (*fn_GameManager_get_Instance)() = nullptr;
    
    // Methods
    void* mtd_ReportViaServer = nullptr;
    void* mtd_AC_Init = nullptr;
    void* mtd_AC_Report = nullptr;
}

// --------------------------------------------------------
// Try to find a field by multiple possible names
// (handles obfuscation — we try known names first, 
//  then iterate all fields looking for type matches)
// --------------------------------------------------------

static int TryGetFieldOffset(void* klass, const char** names, int nameCount) {
    for (int i = 0; i < nameCount; i++) {
        void* field = IL2CPP::il2cpp_class_get_field_from_name(klass, names[i]);
        if (field) {
            int offset = IL2CPP::il2cpp_field_get_offset(field);
            NSLog(@"[S2Rise] Found field '%s' at offset 0x%X", names[i], offset);
            return offset;
        }
    }
    return -1;
}

// --------------------------------------------------------
// Resolve a class across all assemblies
// --------------------------------------------------------

static void* FindClass(const char* ns, const char* name) {
    void* domain = IL2CPP::il2cpp_domain_get();
    size_t count = 0;
    void** assemblies = (void**)IL2CPP::il2cpp_domain_get_assemblies(domain, &count);
    
    for (size_t i = 0; i < count; i++) {
        void* image = IL2CPP::il2cpp_assembly_get_image(assemblies[i]);
        void* cls = IL2CPP::il2cpp_class_from_name(image, ns, name);
        if (cls) {
            NSLog(@"[S2Rise] Found class %s.%s in assembly %zu", ns, name, i);
            return cls;
        }
    }
    NSLog(@"[S2Rise] Class %s.%s NOT FOUND", ns, name);
    return nullptr;
}

// --------------------------------------------------------
// Find method and get its compiled function pointer
// --------------------------------------------------------

static void* FindMethodPtr(const char* ns, const char* klass, const char* method, int paramCount) {
    void* mtd = IL2CPP::ResolveMethod(ns, klass, method, paramCount);
    if (mtd) {
        void* ptr = IL2CPP::il2cpp_method_get_pointer(mtd);
        NSLog(@"[S2Rise] Method %s.%s.%s(%d) → %p", ns, klass, method, paramCount, ptr);
        return ptr;
    }
    NSLog(@"[S2Rise] Method %s.%s.%s(%d) NOT FOUND", ns, klass, method, paramCount);
    return nullptr;
}

// --------------------------------------------------------
// Main resolver — called after IL2CPP is initialized
// --------------------------------------------------------

void OffsetFinder_Resolve() {
    NSLog(@"[S2Rise] === OFFSET FINDER START ===");
    
    // ---- Find classes ----
    
    // Try multiple namespace variations (the metadata has "Anitcheat" typo)
    Game::AntiCheatManager_klass = FindClass("Axlebolt.Standoff.Anitcheat", "AntiCheatManager");
    Game::GameAntiCheatManager_klass = FindClass("Axlebolt.Standoff.Game.Anticheat", "GameAntiCheatManager");
    
    // Player classes — try several namespace patterns
    const char* playerNamespaces[] = {
        "Axlebolt.Standoff.Player",
        "Axlebolt.Standoff.Game",
        "",  // global namespace
    };
    
    for (auto ns : playerNamespaces) {
        if (!Game::PlayerManager_klass)
            Game::PlayerManager_klass = FindClass(ns, "PlayerManager");
        if (!Game::PlayerController_klass)
            Game::PlayerController_klass = FindClass(ns, "PlayerController");
        if (!Game::GameManager_klass)
            Game::GameManager_klass = FindClass(ns, "GameManager");
    }
    
    Game::WeaponManager_klass = FindClass("Axlebolt.Standoff.Inventory", "WeaponManager");
    Game::HitController_klass = FindClass("Axlebolt.Standoff.Player.Hit", "HitController");
    
    // ---- Resolve field offsets ----
    
    if (Game::PlayerController_klass) {
        const char* healthNames[] = {"_health", "Health", "health", "LIGKLBFLNEN"};
        Game::off_health = TryGetFieldOffset(Game::PlayerController_klass, healthNames, 4);
        
        const char* aliveNames[] = {"isAlive", "IsAlive", "_isAlive", "alive"};
        Game::off_isAlive = TryGetFieldOffset(Game::PlayerController_klass, aliveNames, 4);
        
        const char* teamNames[] = {"teamId", "TeamId", "teamID", "_teamId", "_team"};
        Game::off_teamId = TryGetFieldOffset(Game::PlayerController_klass, teamNames, 5);
        
        const char* nickNames[] = {"nickName", "NickName", "_nickName", "playerName"};
        Game::off_nickName = TryGetFieldOffset(Game::PlayerController_klass, nickNames, 4);
        
        const char* localNames[] = {"isLocal", "isLocalPlayer", "_isLocal", "IsLocal"};
        Game::off_isLocal = TryGetFieldOffset(Game::PlayerController_klass, localNames, 4);
        
        const char* animNames[] = {"_animator", "animator", "Animator"};
        Game::off_animator = TryGetFieldOffset(Game::PlayerController_klass, animNames, 3);
        
        const char* deadNames[] = {"isDead", "IsDead", "_isDead"};
        Game::off_isDead = TryGetFieldOffset(Game::PlayerController_klass, deadNames, 3);
    }
    
    if (Game::PlayerManager_klass) {
        const char* playersNames[] = {"_players", "players", "Players", "playerList"};
        Game::off_players = TryGetFieldOffset(Game::PlayerManager_klass, playersNames, 4);
        
        const char* localPNames[] = {"localPlayer", "LocalPlayer", "_localPlayer"};
        Game::off_localPlayer = TryGetFieldOffset(Game::PlayerManager_klass, localPNames, 3);
    }
    
    // ---- Resolve methods ----
    
    // PlayerManager singleton
    Game::fn_get_Instance = (void*(*)())FindMethodPtr(
        "Axlebolt.Standoff.Player", "PlayerManager", "get_Instance", 0);
    
    // AntiCheat methods
    Game::mtd_AC_Init = FindMethodPtr(
        "Axlebolt.Standoff.Anitcheat", "AntiCheatManager", "NFIAANGEACF", 0);
    Game::mtd_AC_Report = FindMethodPtr(
        "Axlebolt.Standoff.Anitcheat", "AntiCheatManager", "EGJIPKOMIMC", 0);
    Game::mtd_ReportViaServer = FindMethodPtr(
        "Axlebolt.Standoff.Game.Anticheat", "GameAntiCheatManager", "ReportViaServer", -1);
    
    // ---- Dump results ----
    
    NSLog(@"[S2Rise] === OFFSET FINDER RESULTS ===");
    NSLog(@"[S2Rise] PlayerController: health=0x%X alive=0x%X teamId=0x%X nick=0x%X local=0x%X animator=0x%X",
          Game::off_health, Game::off_isAlive, Game::off_teamId,
          Game::off_nickName, Game::off_isLocal, Game::off_animator);
    NSLog(@"[S2Rise] PlayerManager: players=0x%X localPlayer=0x%X getInstance=%p",
          Game::off_players, Game::off_localPlayer, Game::fn_get_Instance);
    NSLog(@"[S2Rise] AC: init=%p report=%p serverReport=%p",
          Game::mtd_AC_Init, Game::mtd_AC_Report, Game::mtd_ReportViaServer);
    NSLog(@"[S2Rise] === OFFSET FINDER DONE ===");
}
