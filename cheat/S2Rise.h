#pragma once

// ========================================================
// S2Rise — Standoff 2 Internal Cheat
// Build: v0.19.10 (1090) | iOS arm64 | IL2CPP
// ========================================================

#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <mach-o/dyld.h>
#import <dlfcn.h>
#import <substrate.h>

// --------------------------------------------------------
// IL2CPP Base Types
// --------------------------------------------------------

typedef struct Il2CppObject {
    void *klass;
    void *monitor;
} Il2CppObject;

typedef struct Il2CppString {
    Il2CppObject obj;
    int32_t length;
    uint16_t chars[1]; // flexible array
} Il2CppString;

typedef struct Il2CppArray {
    Il2CppObject obj;
    void *bounds;
    uint32_t max_length;
    void *vector[1];
} Il2CppArray;

typedef struct Il2CppList {
    Il2CppObject obj;
    Il2CppArray *items;
    int32_t size;
    int32_t version;
} Il2CppList;

// --------------------------------------------------------
// Unity Math Types
// --------------------------------------------------------

struct Vector2 {
    float x, y;
    Vector2() : x(0), y(0) {}
    Vector2(float _x, float _y) : x(_x), y(_y) {}
};

struct Vector3 {
    float x, y, z;
    Vector3() : x(0), y(0), z(0) {}
    Vector3(float _x, float _y, float _z) : x(_x), y(_y), z(_z) {}
    
    Vector3 operator-(const Vector3& o) const { return {x-o.x, y-o.y, z-o.z}; }
    Vector3 operator+(const Vector3& o) const { return {x+o.x, y+o.y, z+o.z}; }
    Vector3 operator*(float s) const { return {x*s, y*s, z*s}; }
    float magnitude() const { return sqrtf(x*x + y*y + z*z); }
    float distance(const Vector3& o) const { return (*this - o).magnitude(); }
};

struct Vector4 {
    float x, y, z, w;
};

struct Matrix4x4 {
    float m[4][4];
};

struct Color {
    float r, g, b, a;
    Color() : r(1), g(1), b(1), a(1) {}
    Color(float _r, float _g, float _b, float _a) : r(_r), g(_g), b(_b), a(_a) {}
    
    static Color Red()    { return {1.0f, 0.2f, 0.2f, 1.0f}; }
    static Color Green()  { return {0.2f, 1.0f, 0.2f, 1.0f}; }
    static Color Yellow() { return {1.0f, 1.0f, 0.2f, 1.0f}; }
    static Color Blue()   { return {0.3f, 0.5f, 1.0f, 1.0f}; }
    static Color White()  { return {1.0f, 1.0f, 1.0f, 1.0f}; }
    static Color Cyan()   { return {0.0f, 1.0f, 1.0f, 1.0f}; }
};

struct Rect {
    float x, y, w, h;
};

// --------------------------------------------------------
// IL2CPP Runtime API (resolved at runtime)
// --------------------------------------------------------

namespace IL2CPP {
    // function pointers — resolved in Init()
    inline void* (*il2cpp_domain_get)();
    inline void* (*il2cpp_domain_get_assemblies)(void* domain, size_t* count);
    inline void* (*il2cpp_assembly_get_image)(void* assembly);
    inline void* (*il2cpp_class_from_name)(void* image, const char* ns, const char* name);
    inline void* (*il2cpp_class_get_method_from_name)(void* klass, const char* name, int paramCount);
    inline void* (*il2cpp_class_get_field_from_name)(void* klass, const char* name);
    inline void  (*il2cpp_field_get_value)(void* obj, void* field, void* value);
    inline void  (*il2cpp_field_set_value)(void* obj, void* field, void* value);
    inline void  (*il2cpp_field_static_get_value)(void* field, void* value);
    inline int   (*il2cpp_field_get_offset)(void* field);
    inline void* (*il2cpp_runtime_invoke)(void* method, void* obj, void** params, void** exc);
    inline void* (*il2cpp_string_new)(const char* str);
    inline void* (*il2cpp_resolve_icall)(const char* name);
    inline void* (*il2cpp_method_get_pointer)(void* method);
    
    // UnityFramework base address
    inline uintptr_t base = 0;
    
    bool Init();
    void* ResolveMethod(const char* ns, const char* klass, const char* method, int paramCount);
    void* GetFieldOffset(const char* ns, const char* klass, const char* field);
}

// --------------------------------------------------------
// Unity Engine API (resolved icalls + methods)
// --------------------------------------------------------

namespace Unity {
    // Camera
    inline void* (*Camera_get_main)();
    // *_Injected methods use out-parameters; declaring them as returning Vector3
    // corrupts the arm64 call ABI and was the source of intermittent crashes.
    inline void (*Camera_WorldToScreenPoint)(void* cam, const Vector3* pos, int eye, Vector3* out);
    inline float (*Camera_get_fieldOfView)(void* cam);
    inline Matrix4x4 (*Camera_get_projectionMatrix)(void* cam);
    
    // Transform
    inline void (*Transform_get_position)(void* transform, Vector3* out);
    inline void (*Transform_set_position)(void* transform, Vector3 pos);
    inline Vector3 (*Transform_get_forward)(void* transform);
    
    // Component / GameObject
    inline void* (*Component_get_transform)(void* component);
    inline void* (*Component_get_gameObject)(void* component);
    inline void* (*GameObject_get_transform)(void* gameObject);
    inline bool (*GameObject_get_activeSelf)(void* gameObject);
    inline Il2CppString* (*Object_get_name)(void* obj);
    
    // Screen
    inline int (*Screen_get_width)();
    inline int (*Screen_get_height)();
    
    // Animator
    inline void* (*Animator_GetBoneTransform)(void* animator, int humanBoneId);
    
    bool Init();
}

// --------------------------------------------------------
// Game-Specific Structures (Standoff 2)
// --------------------------------------------------------

// Bone IDs (Unity HumanBodyBones enum)
enum HumanBone : int {
    Hips = 0,
    Spine = 7,
    Chest = 8,
    Neck = 9,
    Head = 10,
    LeftUpperArm = 11,
    RightUpperArm = 14,
    LeftLowerArm = 12,
    RightLowerArm = 15,
    LeftHand = 13,
    RightHand = 16,
    LeftUpperLeg = 1,
    RightUpperLeg = 4,
    LeftLowerLeg = 2,
    RightLowerLeg = 5,
    LeftFoot = 3,
    RightFoot = 6,
};

// Player field offsets — need to be found via il2cppdumper or runtime scan
// These are placeholder values, update from your dump
namespace Offsets {
    // PlayerController fields
    constexpr int Health       = 0x80;   // int32 _health
    constexpr int IsAlive      = 0x84;   // bool isAlive
    constexpr int TeamId       = 0x88;   // int32 teamId
    constexpr int NickName     = 0x90;   // Il2CppString* nickName
    constexpr int Transform    = 0x18;   // cached transform
    constexpr int Animator     = 0xA0;   // Animator component
    constexpr int Weapon       = 0xB0;   // current weapon
    constexpr int IsLocal      = 0xC0;   // bool isLocalPlayer
    
    // PlayerManager
    constexpr int PlayersList  = 0x28;   // List<PlayerController>
    
    // GameManager
    constexpr int LocalPlayer  = 0x30;   // local player ref
}

// --------------------------------------------------------
// Cheat Config
// --------------------------------------------------------

struct CheatConfig {
    // ESP
    bool espEnabled       = true;
    bool espBox           = true;
    bool espSkeleton      = true;
    bool espHealth        = true;
    bool espName          = true;
    bool espDistance       = true;
    bool espSnapline      = false;
    bool espTeammates     = false;
    float espMaxDistance   = 200.0f;
    
    // Colors
    Color enemyColor      = Color::Red();
    Color teamColor       = Color::Green();
    Color skeletonColor   = Color::White();
    
    // Anti-AC
    bool antiACEnabled    = true;
    bool fridaCloakEnabled = true;
    
    // GUI
    bool menuOpen         = true;
};

extern CheatConfig g_Config;

// --------------------------------------------------------
// Module Functions
// --------------------------------------------------------

// ESP.mm
void ESP_Init();
void ESP_Render();

// GUI.mm
void GUI_Init();
void GUI_Render();
void GUI_HandleTouch(UITouch* touch);

// AntiAntiCheat.mm
void AAC_Init();

// FridaCloak.mm
void FridaCloak_Init();

// Utils.mm
uintptr_t GetUnityFrameworkBase();
bool WorldToScreen(Vector3 worldPos, Vector2& screenPos);
void DrawLine(Vector2 from, Vector2 to, Color color, float thickness);
void DrawBox(Vector2 pos, Vector2 size, Color color, float thickness);
void DrawFilledBox(Vector2 pos, Vector2 size, Color color);
void DrawText(Vector2 pos, const char* text, Color color, float size);
void DrawCircle(Vector2 center, float radius, Color color, float thickness);
NSString* Il2CppStringToNS(Il2CppString* str);
