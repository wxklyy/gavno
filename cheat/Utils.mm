#import "S2Rise.h"

// ========================================================
// Utils — IL2CPP resolution, drawing primitives, W2S
// ========================================================

CheatConfig g_Config;

// --------------------------------------------------------
// Find UnityFramework base address in memory
// --------------------------------------------------------

uintptr_t GetUnityFrameworkBase() {
    static uintptr_t cached = 0;
    if (cached) return cached;
    
    for (uint32_t i = 0; i < _dyld_image_count(); i++) {
        const char* name = _dyld_get_image_name(i);
        if (name && strstr(name, "UnityFramework")) {
            cached = (uintptr_t)_dyld_get_image_header(i);
            break;
        }
    }
    return cached;
}

// --------------------------------------------------------
// IL2CPP API Resolution
// --------------------------------------------------------

bool IL2CPP::Init() {
    void* handle = dlopen(NULL, RTLD_NOW);
    if (!handle) return false;
    
    // resolve all il2cpp exports
    #define RESOLVE(name) \
        *(void**)&name = dlsym(handle, #name); \
        if (!name) { NSLog(@"[S2Rise] Failed to resolve: %s", #name); }
    
    RESOLVE(il2cpp_domain_get);
    RESOLVE(il2cpp_domain_get_assemblies);
    RESOLVE(il2cpp_assembly_get_image);
    RESOLVE(il2cpp_class_from_name);
    RESOLVE(il2cpp_class_get_method_from_name);
    RESOLVE(il2cpp_class_get_field_from_name);
    RESOLVE(il2cpp_field_get_value);
    RESOLVE(il2cpp_field_set_value);
    RESOLVE(il2cpp_field_static_get_value);
    RESOLVE(il2cpp_field_get_offset);
    RESOLVE(il2cpp_runtime_invoke);
    RESOLVE(il2cpp_string_new);
    RESOLVE(il2cpp_resolve_icall);
    RESOLVE(il2cpp_method_get_pointer);
    
    #undef RESOLVE
    
    // These are required by every resolver below.  Continuing with a null
    // function pointer turns a missing export into an immediate crash.
    if (!il2cpp_domain_get || !il2cpp_domain_get_assemblies ||
        !il2cpp_assembly_get_image || !il2cpp_class_from_name ||
        !il2cpp_class_get_method_from_name || !il2cpp_method_get_pointer ||
        !il2cpp_resolve_icall) {
        dlclose(handle);
        return false;
    }
    base = GetUnityFrameworkBase();
    if (!base) {
        NSLog(@"[S2Rise] UnityFramework image not loaded");
        dlclose(handle);
        return false;
    }
    NSLog(@"[S2Rise] IL2CPP init OK. UnityFramework base: 0x%lx", base);
    return true;
}

void* IL2CPP::ResolveMethod(const char* ns, const char* klass, const char* method, int paramCount) {
    void* domain = il2cpp_domain_get();
    size_t count = 0;
    void** assemblies = (void**)il2cpp_domain_get_assemblies(domain, &count);
    
    for (size_t i = 0; i < count; i++) {
        void* image = il2cpp_assembly_get_image(assemblies[i]);
        void* cls = il2cpp_class_from_name(image, ns, klass);
        if (cls) {
            void* mtd = il2cpp_class_get_method_from_name(cls, method, paramCount);
            if (mtd) return mtd;
        }
    }
    return nullptr;
}

// --------------------------------------------------------
// Unity Engine API Resolution
// --------------------------------------------------------

bool Unity::Init() {
    #define RESOLVE_ICALL(var, sig) \
        *(void**)&var = IL2CPP::il2cpp_resolve_icall(sig); \
        if (!var) NSLog(@"[S2Rise] icall miss: %s", sig);
    
    RESOLVE_ICALL(Camera_get_main,           "UnityEngine.Camera::get_main()");
    RESOLVE_ICALL(Camera_WorldToScreenPoint,  "UnityEngine.Camera::WorldToScreenPoint_Injected(UnityEngine.Vector3&,UnityEngine.MonoOrStereoscopicEye,UnityEngine.Vector3&)");
    RESOLVE_ICALL(Camera_get_fieldOfView,    "UnityEngine.Camera::get_fieldOfView()");
    RESOLVE_ICALL(Screen_get_width,          "UnityEngine.Screen::get_width()");
    RESOLVE_ICALL(Screen_get_height,         "UnityEngine.Screen::get_height()");
    RESOLVE_ICALL(Transform_get_position,    "UnityEngine.Transform::get_position_Injected(UnityEngine.Vector3&)");
    RESOLVE_ICALL(Component_get_transform,   "UnityEngine.Component::get_transform()");
    RESOLVE_ICALL(Component_get_gameObject,  "UnityEngine.Component::get_gameObject()");
    RESOLVE_ICALL(GameObject_get_transform,  "UnityEngine.GameObject::get_transform()");
    RESOLVE_ICALL(Object_get_name,           "UnityEngine.Object::get_name()");
    RESOLVE_ICALL(Animator_GetBoneTransform, "UnityEngine.Animator::GetBoneTransform(UnityEngine.HumanBodyBones)");
    
    #undef RESOLVE_ICALL
    
    bool ok = Camera_get_main && Camera_WorldToScreenPoint &&
              Screen_get_width && Screen_get_height &&
              Transform_get_position && Component_get_transform &&
              Animator_GetBoneTransform;
    NSLog(@"[S2Rise] Unity API init %s", ok ? "OK" : "FAILED");
    return ok;
}

// --------------------------------------------------------
// World To Screen (using Camera.WorldToScreenPoint)
// --------------------------------------------------------

bool WorldToScreen(Vector3 worldPos, Vector2& screenPos) {
    void* cam = Unity::Camera_get_main();
    if (!cam) return false;
    
    Vector3 screen{};
    // MonoOrStereoscopicEye::Mono is 0.  The injected call writes to `screen`.
    Unity::Camera_WorldToScreenPoint(cam, &worldPos, 0, &screen);
    
    // behind camera check
    if (screen.z < 0.01f) return false;
    
    int sw = Unity::Screen_get_width();
    int sh = Unity::Screen_get_height();
    
    // Unity screen coords: (0,0) bottom-left → flip Y for UIKit
    screenPos.x = screen.x;
    screenPos.y = (float)sh - screen.y;
    
    // bounds check with margin
    if (screenPos.x < -50 || screenPos.x > sw + 50) return false;
    if (screenPos.y < -50 || screenPos.y > sh + 50) return false;
    
    return true;
}

// --------------------------------------------------------
// Drawing Primitives (Metal/OpenGL overlay via CALayer)
// --------------------------------------------------------

// shared drawing context — set before each frame
static CGContextRef g_DrawCtx = nil;
static float g_ScreenScale = 1.0f;

void SetDrawContext(CGContextRef ctx, float scale) {
    g_DrawCtx = ctx;
    g_ScreenScale = scale;
}

void DrawLine(Vector2 from, Vector2 to, Color color, float thickness) {
    if (!g_DrawCtx) return;
    CGContextSetStrokeColorWithColor(g_DrawCtx,
        [UIColor colorWithRed:color.r green:color.g blue:color.b alpha:color.a].CGColor);
    CGContextSetLineWidth(g_DrawCtx, thickness);
    CGContextMoveToPoint(g_DrawCtx, from.x, from.y);
    CGContextAddLineToPoint(g_DrawCtx, to.x, to.y);
    CGContextStrokePath(g_DrawCtx);
}

void DrawBox(Vector2 pos, Vector2 size, Color color, float thickness) {
    if (!g_DrawCtx) return;
    CGContextSetStrokeColorWithColor(g_DrawCtx,
        [UIColor colorWithRed:color.r green:color.g blue:color.b alpha:color.a].CGColor);
    CGContextSetLineWidth(g_DrawCtx, thickness);
    CGContextStrokeRect(g_DrawCtx, CGRectMake(pos.x, pos.y, size.x, size.y));
}

void DrawFilledBox(Vector2 pos, Vector2 size, Color color) {
    if (!g_DrawCtx) return;
    CGContextSetFillColorWithColor(g_DrawCtx,
        [UIColor colorWithRed:color.r green:color.g blue:color.b alpha:color.a].CGColor);
    CGContextFillRect(g_DrawCtx, CGRectMake(pos.x, pos.y, size.x, size.y));
}

void DrawText(Vector2 pos, const char* text, Color color, float fontSize) {
    if (!text) return;
    
    NSString* str = [NSString stringWithUTF8String:text];
    UIFont* font = [UIFont boldSystemFontOfSize:fontSize];
    UIColor* uiColor = [UIColor colorWithRed:color.r green:color.g blue:color.b alpha:color.a];
    
    NSDictionary* attrs = @{
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: uiColor,
        NSStrokeColorAttributeName: [UIColor blackColor],
        NSStrokeWidthAttributeName: @(-2.0)  // negative = fill + stroke
    };
    
    // push UIKit graphics context for text drawing
    UIGraphicsPushContext(g_DrawCtx);
    [str drawAtPoint:CGPointMake(pos.x, pos.y) withAttributes:attrs];
    UIGraphicsPopContext();
}

void DrawCircle(Vector2 center, float radius, Color color, float thickness) {
    if (!g_DrawCtx) return;
    CGContextSetStrokeColorWithColor(g_DrawCtx,
        [UIColor colorWithRed:color.r green:color.g blue:color.b alpha:color.a].CGColor);
    CGContextSetLineWidth(g_DrawCtx, thickness);
    CGContextAddArc(g_DrawCtx, center.x, center.y, radius, 0, M_PI * 2, 0);
    CGContextStrokePath(g_DrawCtx);
}

NSString* Il2CppStringToNS(Il2CppString* str) {
    if (!str || str->length <= 0) return @"???";
    return [[NSString alloc] initWithCharacters:(const unichar*)str->chars length:str->length];
}
