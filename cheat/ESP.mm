#import "S2Rise.h"

// ========================================================
// ESP — Player ESP with Box, Skeleton, Health, Name, Distance
// ========================================================

// --------------------------------------------------------
// Skeleton bone connections for drawing
// --------------------------------------------------------

static const int g_BonePairs[][2] = {
    // spine chain
    {HumanBone::Hips,          HumanBone::Spine},
    {HumanBone::Spine,         HumanBone::Chest},
    {HumanBone::Chest,         HumanBone::Neck},
    {HumanBone::Neck,          HumanBone::Head},
    
    // left arm
    {HumanBone::Chest,         HumanBone::LeftUpperArm},
    {HumanBone::LeftUpperArm,  HumanBone::LeftLowerArm},
    {HumanBone::LeftLowerArm,  HumanBone::LeftHand},
    
    // right arm
    {HumanBone::Chest,         HumanBone::RightUpperArm},
    {HumanBone::RightUpperArm, HumanBone::RightLowerArm},
    {HumanBone::RightLowerArm, HumanBone::RightHand},
    
    // left leg
    {HumanBone::Hips,          HumanBone::LeftUpperLeg},
    {HumanBone::LeftUpperLeg,  HumanBone::LeftLowerLeg},
    {HumanBone::LeftLowerLeg,  HumanBone::LeftFoot},
    
    // right leg
    {HumanBone::Hips,          HumanBone::RightUpperLeg},
    {HumanBone::RightUpperLeg, HumanBone::RightLowerLeg},
    {HumanBone::RightLowerLeg, HumanBone::RightFoot},
};

static const int g_BonePairCount = sizeof(g_BonePairs) / sizeof(g_BonePairs[0]);

// --------------------------------------------------------
// Player data snapshot (populated each frame)
// --------------------------------------------------------

struct PlayerESPData {
    bool valid;
    bool isLocal;
    bool isAlive;
    bool isEnemy;
    int health;
    int maxHealth;
    float distance;
    char nickname[64];
    
    Vector3 worldPos;     // feet position
    Vector3 headWorldPos; // head position
    
    Vector2 screenPos;    // feet on screen
    Vector2 headScreenPos;// head on screen
    
    Vector2 boneScreenPos[17]; // all major bones
    bool    boneValid[17];
};

static PlayerESPData g_Players[32]; // max 32 players in a match
static int g_PlayerCount = 0;

// --------------------------------------------------------
// Cached pointers (resolved once)
// --------------------------------------------------------

static void* g_PlayerManagerInstance = nullptr;  // singleton

// function pointers for game methods
static void* (*fn_PlayerManager_get_Instance)() = nullptr;
static Il2CppList* (*fn_PlayerManager_get_Players)(void* mgr) = nullptr;
static bool ReadPlayerData(void* playerObj, int localTeamId, Vector3 localPos, PlayerESPData& out);

static void ESP_UpdatePlayers() {
    g_PlayerCount = 0;
    if (!fn_PlayerManager_get_Players) return;
    if (!g_PlayerManagerInstance && fn_PlayerManager_get_Instance)
        g_PlayerManagerInstance = fn_PlayerManager_get_Instance();
    if (!g_PlayerManagerInstance) return;

    Il2CppList* list = fn_PlayerManager_get_Players(g_PlayerManagerInstance);
    if (!list || !list->items || list->size <= 0) return;
    int count = list->size > 32 ? 32 : list->size;

    // Obtain local player/team from the list instead of assuming a separate
    // manager layout. This still relies on the validated offsets below.
    int localTeam = -1;
    Vector3 localPos{};
    for (int i = 0; i < count; ++i) {
        void* p = list->items->vector[i];
        if (!p) continue;
        uintptr_t b = (uintptr_t)p;
        bool local = *(bool*)(b + Offsets::IsLocal);
        if (local) {
            localTeam = *(int32_t*)(b + Offsets::TeamId);
            void* tr = Unity::Component_get_transform(p);
            if (tr) Unity::Transform_get_position(tr, &localPos);
            break;
        }
    }
    if (localTeam < 0) return;
    for (int i = 0; i < count && g_PlayerCount < 32; ++i) {
        void* p = list->items->vector[i];
        PlayerESPData data{};
        if (ReadPlayerData(p, localTeam, localPos, data))
            g_Players[g_PlayerCount++] = data;
    }
}

// --------------------------------------------------------
// Init — resolve game classes and methods
// --------------------------------------------------------

void ESP_Init() {
    void* inst = IL2CPP::ResolveMethod(
        "Axlebolt.Standoff.Player", "PlayerManager", "get_Instance", 0);
    if (inst)
        fn_PlayerManager_get_Instance = (void*(*)())IL2CPP::il2cpp_method_get_pointer(inst);
    // resolve PlayerManager
    void* mtd = IL2CPP::ResolveMethod(
        "Axlebolt.Standoff.Player", "PlayerManager", "get_Players", 0);
    if (mtd) {
        fn_PlayerManager_get_Players = (Il2CppList*(*)(void*))IL2CPP::il2cpp_method_get_pointer(mtd);
        NSLog(@"[S2Rise] PlayerManager.get_Players resolved: %p", fn_PlayerManager_get_Players);
    }
    
    NSLog(@"[S2Rise] ESP init OK");
}

// --------------------------------------------------------
// Read player data from IL2CPP objects
// --------------------------------------------------------

static bool ReadPlayerData(void* playerObj, int localTeamId, Vector3 localPos, PlayerESPData& out) {
    if (!playerObj) return false;
    
    memset(&out, 0, sizeof(out));
    
    // read fields via raw memory offsets
    uintptr_t base = (uintptr_t)playerObj;
    
    out.health  = *(int32_t*)(base + Offsets::Health);
    out.isAlive = *(bool*)(base + Offsets::IsAlive);
    out.isLocal = *(bool*)(base + Offsets::IsLocal);
    
    int teamId  = *(int32_t*)(base + Offsets::TeamId);
    out.isEnemy = (teamId != localTeamId);
    out.maxHealth = 100; // default, could read MaxCtHealth/MaxTrHealth
    
    // skip dead players
    if (!out.isAlive) return false;
    
    // skip local player
    if (out.isLocal) return false;
    
    // skip teammates unless enabled
    if (!out.isEnemy && !g_Config.espTeammates) return false;
    
    // read nickname
    Il2CppString* nick = *(Il2CppString**)(base + Offsets::NickName);
    if (nick && nick->length > 0) {
        NSString* nsNick = Il2CppStringToNS(nick);
        strncpy(out.nickname, nsNick.UTF8String, sizeof(out.nickname) - 1);
    } else {
        strcpy(out.nickname, "???");
    }
    
    // get transform → position
    void* transform = Unity::Component_get_transform(playerObj);
    if (!transform) return false;
    
    // read position via icall
    Vector3 pos;
    Unity::Transform_get_position(transform, &pos);
    out.worldPos = pos;
    
    // distance from local player
    out.distance = localPos.distance(pos);
    if (out.distance > g_Config.espMaxDistance) return false;
    
    // W2S for feet
    if (!WorldToScreen(pos, out.screenPos)) return false;
    
    // get head position via Animator bone
    void* animator = *(void**)(base + Offsets::Animator);
    if (animator) {
        void* headBone = Unity::Animator_GetBoneTransform(animator, HumanBone::Head);
        if (headBone) {
            Vector3 headPos;
            Unity::Transform_get_position(headBone, &headPos);
            out.headWorldPos = headPos;
            
            // add a bit above head for box top
            Vector3 aboveHead = headPos;
            aboveHead.y += 0.15f;
            WorldToScreen(aboveHead, out.headScreenPos);
        }
        
        // all bones for skeleton
        if (g_Config.espSkeleton) {
            for (int b = 0; b < 17; b++) {
                void* bone = Unity::Animator_GetBoneTransform(animator, b);
                if (bone) {
                    Vector3 bonePos;
                    Unity::Transform_get_position(bone, &bonePos);
                    out.boneValid[b] = WorldToScreen(bonePos, out.boneScreenPos[b]);
                }
            }
        }
    } else {
        // fallback: estimate head from feet + height offset
        Vector3 estimatedHead = pos;
        estimatedHead.y += 1.7f; // approximate player height
        out.headWorldPos = estimatedHead;
        WorldToScreen(estimatedHead, out.headScreenPos);
    }
    
    out.valid = true;
    return true;
}

// --------------------------------------------------------
// Render ESP
// --------------------------------------------------------

void ESP_Render() {
    if (!g_Config.espEnabled) return;
    
    void* cam = Unity::Camera_get_main();
    if (!cam) return;
    
    int screenW = Unity::Screen_get_width();
    int screenH = Unity::Screen_get_height();
    ESP_UpdatePlayers();
    
    for (int i = 0; i < g_PlayerCount; i++) {
        PlayerESPData& p = g_Players[i];
        if (!p.valid) continue;
        
        Color color = p.isEnemy ? g_Config.enemyColor : g_Config.teamColor;
        
        // calculate box dimensions from head-to-feet screen distance
        float boxH = fabsf(p.screenPos.y - p.headScreenPos.y);
        float boxW = boxH * 0.45f; // width ~45% of height
        
        float boxTop = fminf(p.headScreenPos.y, p.screenPos.y);
        float boxLeft = p.headScreenPos.x - boxW * 0.5f;
        
        // ---- 2D Box ESP ----
        if (g_Config.espBox) {
            // corner-style box (looks cleaner)
            float cornerLen = boxH * 0.2f;
            
            Vector2 tl = {boxLeft, boxTop};
            Vector2 tr = {boxLeft + boxW, boxTop};
            Vector2 bl = {boxLeft, boxTop + boxH};
            Vector2 br = {boxLeft + boxW, boxTop + boxH};
            
            // top-left corner
            DrawLine(tl, {tl.x + cornerLen, tl.y}, color, 2.0f);
            DrawLine(tl, {tl.x, tl.y + cornerLen}, color, 2.0f);
            
            // top-right corner
            DrawLine(tr, {tr.x - cornerLen, tr.y}, color, 2.0f);
            DrawLine(tr, {tr.x, tr.y + cornerLen}, color, 2.0f);
            
            // bottom-left corner
            DrawLine(bl, {bl.x + cornerLen, bl.y}, color, 2.0f);
            DrawLine(bl, {bl.x, bl.y - cornerLen}, color, 2.0f);
            
            // bottom-right corner
            DrawLine(br, {br.x - cornerLen, br.y}, color, 2.0f);
            DrawLine(br, {br.x, br.y - cornerLen}, color, 2.0f);
        }
        
        // ---- Health Bar ----
        if (g_Config.espHealth && p.maxHealth > 0) {
            float healthPct = (float)p.health / (float)p.maxHealth;
            healthPct = fmaxf(0.0f, fminf(1.0f, healthPct));
            
            float barW = 3.0f;
            float barH = boxH;
            float barX = boxLeft - barW - 3.0f;
            float barY = boxTop;
            
            // background
            DrawFilledBox({barX - 1, barY - 1}, {barW + 2, barH + 2}, {0, 0, 0, 0.6f});
            
            // health fill (green → yellow → red)
            Color hpColor;
            if (healthPct > 0.5f) {
                hpColor = Color::Green();
            } else if (healthPct > 0.25f) {
                hpColor = Color::Yellow();
            } else {
                hpColor = Color::Red();
            }
            
            float fillH = barH * healthPct;
            DrawFilledBox({barX, barY + barH - fillH}, {barW, fillH}, hpColor);
        }
        
        // ---- Name ----
        if (g_Config.espName) {
            float textY = boxTop - 16.0f;
            DrawText({boxLeft, textY}, p.nickname, Color::White(), 11.0f);
        }
        
        // ---- Distance ----
        if (g_Config.espDistance) {
            char distStr[32];
            snprintf(distStr, sizeof(distStr), "%.0fm", p.distance);
            DrawText({boxLeft, boxTop + boxH + 3.0f}, distStr, Color::Cyan(), 10.0f);
        }
        
        // ---- Snap Lines (from bottom center of screen to feet) ----
        if (g_Config.espSnapline) {
            Vector2 screenBottom = {(float)screenW * 0.5f, (float)screenH};
            DrawLine(screenBottom, p.screenPos, color, 1.0f);
        }
        
        // ---- Skeleton ----
        if (g_Config.espSkeleton) {
            for (int b = 0; b < g_BonePairCount; b++) {
                int from = g_BonePairs[b][0];
                int to   = g_BonePairs[b][1];
                
                if (p.boneValid[from] && p.boneValid[to]) {
                    DrawLine(p.boneScreenPos[from], p.boneScreenPos[to],
                             g_Config.skeletonColor, 1.5f);
                }
            }
        }
    }
}
