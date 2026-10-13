ARCHS = arm64
TARGET = iphone:clang:14.5:14.0
INSTALL_TARGET_PROCESSES = standoff2

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = S2Rise
S2Rise_FILES = Tweak.xm ESP.mm GUI.mm AntiAntiCheat.mm FridaCloak.mm Utils.mm
S2Rise_CFLAGS = -fobjc-arc -std=c++17 -DIMGUI_IMPL_OPENGL_ES2
S2Rise_CCFLAGS = -std=c++17
S2Rise_FRAMEWORKS = UIKit Foundation CoreGraphics OpenGLES QuartzCore Security
S2Rise_LIBRARIES = substrate z
S2Rise_LDFLAGS = -lc++

include $(THEOS_MAKE_PATH)/tweak.mk
