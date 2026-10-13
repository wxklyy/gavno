#import "S2Rise.h"

// ========================================================
// GUI — Touch-based in-game menu overlay
// ========================================================

// --------------------------------------------------------
// Menu State
// --------------------------------------------------------

static CGRect g_MenuRect = CGRectMake(20, 80, 300, 420);
static bool g_Dragging = false;
static CGPoint g_DragOffset;

// toggle button position (floating button to open/close menu)
static CGRect g_ToggleButtonRect = CGRectMake(10, 30, 44, 44);

// --------------------------------------------------------
// GUI Element Helpers
// --------------------------------------------------------

struct GUIState {
    float cursorY;       // current Y position for next element
    float leftMargin;
    float width;
    float elementHeight;
    float padding;
};

static GUIState g_GUI;

static void GUI_BeginMenu() {
    g_GUI.cursorY = g_MenuRect.origin.y + 50; // below title bar
    g_GUI.leftMargin = g_MenuRect.origin.x + 12;
    g_GUI.width = g_MenuRect.size.width - 24;
    g_GUI.elementHeight = 30;
    g_GUI.padding = 6;
}

static void GUI_DrawToggle(const char* label, bool* value) {
    float x = g_GUI.leftMargin;
    float y = g_GUI.cursorY;
    float toggleW = 40;
    float toggleH = 22;
    float toggleX = x + g_GUI.width - toggleW;
    float toggleY = y + (g_GUI.elementHeight - toggleH) * 0.5f;
    
    // label text
    DrawText({x, y + 6}, label, Color::White(), 13.0f);
    
    // toggle background
    Color bgColor = *value ? Color(0.2f, 0.8f, 0.3f, 0.9f) : Color(0.4f, 0.4f, 0.4f, 0.9f);
    DrawFilledBox({toggleX, toggleY}, {toggleW, toggleH}, bgColor);
    
    // toggle knob
    float knobSize = toggleH - 4;
    float knobX = *value ? (toggleX + toggleW - knobSize - 2) : (toggleX + 2);
    DrawFilledBox({knobX, toggleY + 2}, {knobSize, knobSize}, Color::White());
    
    g_GUI.cursorY += g_GUI.elementHeight + g_GUI.padding;
}

static void GUI_DrawSlider(const char* label, float* value, float minVal, float maxVal) {
    float x = g_GUI.leftMargin;
    float y = g_GUI.cursorY;
    
    // label + value
    char buf[64];
    snprintf(buf, sizeof(buf), "%s: %.0f", label, *value);
    DrawText({x, y + 2}, buf, Color::White(), 12.0f);
    
    y += 20;
    
    // slider track
    float trackH = 6;
    float trackY = y + 4;
    DrawFilledBox({x, trackY}, {g_GUI.width, trackH}, {0.3f, 0.3f, 0.3f, 0.9f});
    
    // slider fill
    float pct = (*value - minVal) / (maxVal - minVal);
    pct = fmaxf(0.0f, fminf(1.0f, pct));
    DrawFilledBox({x, trackY}, {g_GUI.width * pct, trackH}, Color::Cyan());
    
    // knob
    float knobX = x + g_GUI.width * pct - 6;
    DrawFilledBox({knobX, trackY - 4}, {12, trackH + 8}, Color::White());
    
    g_GUI.cursorY += g_GUI.elementHeight + g_GUI.padding + 10;
}

static void GUI_DrawSeparator(const char* title) {
    float x = g_GUI.leftMargin;
    float y = g_GUI.cursorY + 4;
    
    DrawLine({x, y + 8}, {x + g_GUI.width, y + 8}, {1, 1, 1, 0.2f}, 1.0f);
    if (title) {
        DrawText({x, y}, title, Color::Cyan(), 12.0f);
    }
    
    g_GUI.cursorY += 20;
}

// --------------------------------------------------------
// Init
// --------------------------------------------------------

void GUI_Init() {
    NSLog(@"[S2Rise] GUI init OK");
}

// --------------------------------------------------------
// Render Menu
// --------------------------------------------------------

void GUI_Render() {
    // always draw toggle button
    Color btnColor = g_Config.menuOpen ? Color(0.9f, 0.2f, 0.2f, 0.85f)
                                       : Color(0.2f, 0.6f, 0.9f, 0.85f);
    DrawFilledBox(
        {(float)g_ToggleButtonRect.origin.x, (float)g_ToggleButtonRect.origin.y},
        {(float)g_ToggleButtonRect.size.width, (float)g_ToggleButtonRect.size.height},
        btnColor);
    DrawText(
        {(float)g_ToggleButtonRect.origin.x + 10, (float)g_ToggleButtonRect.origin.y + 12},
        g_Config.menuOpen ? "X" : "M", Color::White(), 16.0f);
    
    if (!g_Config.menuOpen) return;
    
    // ---- menu background ----
    DrawFilledBox(
        {(float)g_MenuRect.origin.x, (float)g_MenuRect.origin.y},
        {(float)g_MenuRect.size.width, (float)g_MenuRect.size.height},
        {0.08f, 0.08f, 0.12f, 0.92f});
    
    // outline
    DrawBox(
        {(float)g_MenuRect.origin.x, (float)g_MenuRect.origin.y},
        {(float)g_MenuRect.size.width, (float)g_MenuRect.size.height},
        Color::Cyan(), 1.5f);
    
    // title bar
    DrawFilledBox(
        {(float)g_MenuRect.origin.x, (float)g_MenuRect.origin.y},
        {(float)g_MenuRect.size.width, 40},
        {0.12f, 0.12f, 0.18f, 0.95f});
    
    DrawText(
        {(float)g_MenuRect.origin.x + 12, (float)g_MenuRect.origin.y + 10},
        "S2Rise — Standoff 2", Color::Cyan(), 16.0f);
    
    // ---- menu elements ----
    GUI_BeginMenu();
    
    GUI_DrawSeparator("ESP");
    GUI_DrawToggle("ESP Enabled",     &g_Config.espEnabled);
    GUI_DrawToggle("Box",             &g_Config.espBox);
    GUI_DrawToggle("Skeleton",        &g_Config.espSkeleton);
    GUI_DrawToggle("Health Bar",      &g_Config.espHealth);
    GUI_DrawToggle("Name",            &g_Config.espName);
    GUI_DrawToggle("Distance",        &g_Config.espDistance);
    GUI_DrawToggle("Snap Lines",      &g_Config.espSnapline);
    GUI_DrawToggle("Show Teammates",  &g_Config.espTeammates);
    GUI_DrawSlider("Max Distance",    &g_Config.espMaxDistance, 10.0f, 500.0f);
    
    GUI_DrawSeparator("Protection");
    GUI_DrawToggle("Anti-AC",         &g_Config.antiACEnabled);
    GUI_DrawToggle("Frida Cloak",     &g_Config.fridaCloakEnabled);
}

// --------------------------------------------------------
// Touch Handling
// --------------------------------------------------------

static bool PointInRect(CGPoint p, CGRect r) {
    return p.x >= r.origin.x && p.x <= r.origin.x + r.size.width
        && p.y >= r.origin.y && p.y <= r.origin.y + r.size.height;
}

void GUI_HandleTouch(UITouch* touch) {
    CGPoint loc = [touch locationInView:nil];
    UITouchPhase phase = touch.phase;
    
    // toggle button tap
    if (phase == UITouchPhaseBegan && PointInRect(loc, g_ToggleButtonRect)) {
        g_Config.menuOpen = !g_Config.menuOpen;
        return;
    }
    
    if (!g_Config.menuOpen) return;
    
    // title bar drag
    CGRect titleBar = CGRectMake(g_MenuRect.origin.x, g_MenuRect.origin.y, g_MenuRect.size.width, 40);
    
    if (phase == UITouchPhaseBegan && PointInRect(loc, titleBar)) {
        g_Dragging = true;
        g_DragOffset = CGPointMake(loc.x - g_MenuRect.origin.x, loc.y - g_MenuRect.origin.y);
        return;
    }
    
    if (phase == UITouchPhaseMoved && g_Dragging) {
        g_MenuRect.origin.x = loc.x - g_DragOffset.x;
        g_MenuRect.origin.y = loc.y - g_DragOffset.y;
        return;
    }
    
    if (phase == UITouchPhaseEnded || phase == UITouchPhaseCancelled) {
        if (g_Dragging) {
            g_Dragging = false;
            return;
        }
    }
    
    // handle toggle taps (check Y position against each element)
    if (phase == UITouchPhaseBegan && PointInRect(loc, g_MenuRect)) {
        float relY = loc.y - (g_MenuRect.origin.y + 50); // relative to first element
        float elemH = 30 + 6; // elementHeight + padding
        
        // account for separator at top
        relY -= 20; // first separator
        
        int toggleIndex = (int)(relY / elemH);
        float toggleX = g_MenuRect.origin.x + g_MenuRect.size.width - 40 - 12;
        
        // only register if tapped on toggle area (right side)
        if (loc.x >= toggleX) {
            bool* toggles[] = {
                &g_Config.espEnabled,
                &g_Config.espBox,
                &g_Config.espSkeleton,
                &g_Config.espHealth,
                &g_Config.espName,
                &g_Config.espDistance,
                &g_Config.espSnapline,
                &g_Config.espTeammates,
            };
            int numToggles = sizeof(toggles) / sizeof(toggles[0]);
            
            if (toggleIndex >= 0 && toggleIndex < numToggles) {
                *toggles[toggleIndex] = !(*toggles[toggleIndex]);
            }
        }
    }
}
