# Two original IEC conversion implementations move to Rust; libobs remains C/C++.
# This first integration is deliberately native Linux only, not a cross-build.
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR CMAKE_CROSSCOMPILING OR
   NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|amd64|AMD64)$")
  message(FATAL_ERROR "StreamStrike Rust fader integration currently requires native x86_64 Linux")
endif()
if(NOT CMAKE_C_COMPILER_ID STREQUAL "GNU")
  message(FATAL_ERROR "StreamStrike IEC compiler-profile diagnostics currently require GNU C")
endif()
# Replay the actual target compile command and fail closed on unsupported math.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Retain exact IEC compiler provenance" FORCE)
set_property(TARGET libobs PROPERTY EXPORT_COMPILE_COMMANDS ON)
find_program(STREAMSTRIKE_FADER_PYTHON python3 REQUIRED)
find_program(STREAMSTRIKE_FADER_RUSTC rustc REQUIRED)
set(_fader_source "${CMAKE_CURRENT_SOURCE_DIR}/streamstrike-fader/iec.rs")
set(_fader_archive "${CMAKE_CURRENT_BINARY_DIR}/libstreamstrike-fader.a")
set(_fader_profile "${CMAKE_CURRENT_BINARY_DIR}/libstreamstrike-fader.profile.json")
add_custom_command(
  OUTPUT "${_fader_archive}" "${_fader_profile}"
  COMMAND "${STREAMSTRIKE_FADER_PYTHON}" "${CMAKE_CURRENT_SOURCE_DIR}/streamstrike-fader/build_fader.py"
          --database "${CMAKE_BINARY_DIR}/compile_commands.json"
          --source "${CMAKE_CURRENT_SOURCE_DIR}/obs-audio-controls.c"
          --rustc "${STREAMSTRIKE_FADER_RUSTC}" --compiler "${CMAKE_C_COMPILER}" --output "${_fader_archive}"
  DEPENDS "${_fader_source}" "${CMAKE_CURRENT_SOURCE_DIR}/streamstrike-fader/StreamStrikeFader.cmake"
          "${CMAKE_CURRENT_SOURCE_DIR}/streamstrike-fader/build_fader.py"
          "${CMAKE_CURRENT_SOURCE_DIR}/streamstrike-fader/oracle.c"
          "${CMAKE_BINARY_DIR}/compile_commands.json" "${CMAKE_C_COMPILER}"
          "${STREAMSTRIKE_FADER_RUSTC}"
  VERBATIM
)
add_custom_target(streamstrike_fader_build DEPENDS "${_fader_archive}" "${_fader_profile}")
add_library(streamstrike_fader STATIC IMPORTED)
set_target_properties(streamstrike_fader PROPERTIES IMPORTED_LOCATION "${_fader_archive}")
add_dependencies(streamstrike_fader streamstrike_fader_build)
target_link_libraries(libobs PRIVATE streamstrike_fader)
# OBS's Gio imported target omits its GLib/GObject link interface, although
# libobs's existing D-Bus/portal sources call both directly. Declare those
# dependencies explicitly instead of weakening the strict shared-library gate.
if(TARGET gio::gio)
  find_library(STREAMSTRIKE_GOBJECT_LIBRARY NAMES gobject-2.0 HINTS ${PC_Gio_LIBRARY_DIRS} REQUIRED)
  find_library(STREAMSTRIKE_GLIB_LIBRARY NAMES glib-2.0 HINTS ${PC_Gio_LIBRARY_DIRS} REQUIRED)
  target_link_libraries(libobs PRIVATE "${STREAMSTRIKE_GOBJECT_LIBRARY}" "${STREAMSTRIKE_GLIB_LIBRARY}")
endif()
# The final shared object must not tolerate missing Rust definitions.
target_link_options(libobs PRIVATE "LINKER:--no-undefined")
