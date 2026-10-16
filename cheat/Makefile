ARCHS = arm64
TARGET = iphone:clang:14.5:14.0
# The executable in the target IPA is StandRiseRE (the bundle identifier is
# com.standrise.game).  Using the old executable name prevents injection even
# when the package installs successfully.
INSTALL_TARGET_PROCESSES = StandRiseRE

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = S2Rise
S2Rise_FILES = Tweak.xm ESP.mm GUI.mm AntiAntiCheat.mm FridaCloak.mm Utils.mm
# Theos' iPhoneOS SDK enables several diagnostics that are warnings for this
# legacy Objective-C++ code but are promoted to errors by the runner.
S2Rise_CFLAGS = -fobjc-arc -std=c++17 -DIMGUI_IMPL_OPENGL_ES2 -Wno-error
S2Rise_CCFLAGS = -std=c++17
S2Rise_FRAMEWORKS = UIKit Foundation CoreGraphics OpenGLES QuartzCore Security
S2Rise_LIBRARIES = substrate z
S2Rise_LDFLAGS = -lc++

include $(THEOS_MAKE_PATH)/tweak.mk
