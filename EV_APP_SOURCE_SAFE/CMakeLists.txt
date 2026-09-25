cmake_minimum_required(VERSION 3.20)

project(EVCore VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Quick Qml)

qt_standard_project_setup()

# Application Executable
qt_add_executable(appEVCore
    # In pure Python/PySide6, gui/app.py is used.
    # When compiling as a native C++ application, provide main.cpp:
    main.cpp
)

# Register QML Module & Resources
qt_add_qml_module(appEVCore
    URI EV
    VERSION 1.0
    RESOURCE_PREFIX "/"
    QML_FILES
        gui/qml/components/EVWindow.qml
        gui/qml/components/EVTopBar.qml
        gui/qml/components/EVCommandInput.qml
        gui/qml/components/EVResultSurface.qml
        gui/qml/components/EVTelemetryRail.qml
        gui/qml/components/EVIntelligenceCore.qml
        gui/qml/components/EVSettingsOverlay.qml
        gui/qml/components/EVSystemAlertBanner.qml
        gui/qml/components/presets/EVCoreNexusSphere.qml
        gui/qml/components/presets/EVCoreFlagshipVisual.qml
        gui/qml/components/presets/EVCoreOriginalVisual.qml
        gui/qml/theme/Theme.qml
)

target_link_libraries(appEVCore
    PRIVATE
        Qt6::Core
        Qt6::Gui
        Qt6::Quick
        Qt6::Qml
)

if(WIN32)
    target_link_libraries(appEVCore PRIVATE dwmapi crypt32)
endif()
