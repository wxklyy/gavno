#import "S2Rise.h"
#import <objc/runtime.h>

// ========================================================
// Tweak.xm — Main entry point + overlay rendering
// ========================================================

// --------------------------------------------------------
// Overlay View — transparent view drawn on top of the game
// --------------------------------------------------------

@interface S2RiseOverlay : UIView
@end

@implementation S2RiseOverlay

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.backgroundColor = [UIColor clearColor];
        self.userInteractionEnabled = YES;
        self.multipleTouchEnabled = YES;
        self.opaque = NO;
        self.layer.zPosition = 9999;
    }
    return self;
}

- (void)drawRect:(CGRect)rect {
    CGContextRef ctx = UIGraphicsGetCurrentContext();
    if (!ctx) return;
    
    // set the global draw context for our primitives
    extern void SetDrawContext(CGContextRef ctx, float scale);
    SetDrawContext(ctx, [UIScreen mainScreen].scale);
    
    // render ESP
    ESP_Render();
    
    // render GUI menu
    GUI_Render();
}

// pass touches to GUI, let game handle the rest
- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    for (UITouch* t in touches) {
        GUI_HandleTouch(t);
    }
}

- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    for (UITouch* t in touches) {
        GUI_HandleTouch(t);
    }
}

- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    for (UITouch* t in touches) {
        GUI_HandleTouch(t);
    }
}

- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    for (UITouch* t in touches) {
        GUI_HandleTouch(t);
    }
}

// don't block hit test when menu is closed and touch is outside menu area
- (UIView*)hitTest:(CGPoint)point withEvent:(UIEvent*)event {
    if (g_Config.menuOpen) {
        return [super hitTest:point withEvent:event];
    }
    
    // always capture the toggle button area
    CGRect toggleRect = CGRectMake(10.0, 30.0, 44.0, 44.0);
    if (CGRectContainsPoint(toggleRect, point)) {
        return self;
    }
    
    // pass through to game
    return nil;
}

@end

// --------------------------------------------------------
// Overlay management
// --------------------------------------------------------

static S2RiseOverlay* g_Overlay = nil;
static CADisplayLink* g_DisplayLink = nil;

static void CreateOverlay() {
    dispatch_async(dispatch_get_main_queue(), ^{
        UIWindow* keyWindow = nil;
        for (UIWindowScene* scene in [UIApplication sharedApplication].connectedScenes) {
            if ([scene isKindOfClass:[UIWindowScene class]]) {
                for (UIWindow* w in scene.windows) {
                    if (w.isKeyWindow) {
                        keyWindow = w;
                        break;
                    }
                }
            }
        }
        
        if (!keyWindow) {
            // fallback: retry in 1 second
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 1 * NSEC_PER_SEC),
                           dispatch_get_main_queue(), ^{
                CreateOverlay();
            });
            return;
        }
        
        g_Overlay = [[S2RiseOverlay alloc] initWithFrame:keyWindow.bounds];
        [keyWindow addSubview:g_Overlay];
        
        // refresh at ~60fps via display link
        g_DisplayLink = [CADisplayLink displayLinkWithTarget:g_Overlay
                                                    selector:@selector(setNeedsDisplay)];
        g_DisplayLink.preferredFramesPerSecond = 60;
        [g_DisplayLink addToRunLoop:[NSRunLoop mainRunLoop] forMode:NSRunLoopCommonModes];
        
        // handle rotation
        [[NSNotificationCenter defaultCenter]
            addObserverForName:UIDeviceOrientationDidChangeNotification
                       object:nil
                        queue:[NSOperationQueue mainQueue]
                   usingBlock:^(NSNotification* note) {
            g_Overlay.frame = keyWindow.bounds;
        }];
        
        NSLog(@"[S2Rise] Overlay created: %.0fx%.0f",
              keyWindow.bounds.size.width, keyWindow.bounds.size.height);
    });
}

// --------------------------------------------------------
// Constructor — tweak entry point
// --------------------------------------------------------

%ctor {
    NSLog(@"[S2Rise] ========================================");
    NSLog(@"[S2Rise] S2Rise loading for Standoff 2 v0.19.10");
    NSLog(@"[S2Rise] ========================================");
    
    // Phase 1: anti-detection (must be FIRST, before game code runs)
    FridaCloak_Init();
    AAC_Init();
    
    // Phase 2: wait for IL2CPP runtime to be ready, then init game hooks
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 5 * NSEC_PER_SEC),
                   dispatch_get_main_queue(), ^{
        
        // init IL2CPP API
        if (!IL2CPP::Init()) {
            NSLog(@"[S2Rise] FATAL: IL2CPP init failed");
            return;
        }
        
        // init Unity API
        if (!Unity::Init()) {
            NSLog(@"[S2Rise] FATAL: Unity API init failed");
            return;
        }
        
        // init modules
        ESP_Init();
        GUI_Init();
        
        // create overlay
        CreateOverlay();
        
        NSLog(@"[S2Rise] All systems online. gng we're in.");
    });
}
