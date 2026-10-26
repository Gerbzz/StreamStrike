# Two original IEC conversion implementations move to Rust; libobs remains C/C++.
# This first integration is deliberately native Linux only, not a cross-build.
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR CMAKE_CROSSCOMPILING OR
   NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|amd64|AMD64)$")
  message(FATAL_ERROR "StreamStrike Rust fader integration currently requires baseline native x86_64 Linux")
endif()
# Exact f32 parity is not claimed for FMA/fast-math/custom CPU builds.
foreach(_flags CMAKE_C_FLAGS CMAKE_C_FLAGS_DEBUG CMAKE_C_FLAGS_RELEASE CMAKE_C_FLAGS_RELWITHDEBINFO CMAKE_C_FLAGS_MINSIZEREL)
  if("${${_flags}}" MATCHES "(^| )(-Ofast|-ffast-math|-mfma|-march=|-mcpu=|-ffp-contract=fast)")
    message(FATAL_ERROR "IEC Rust parity requires baseline CPU/non-fast-math C flags")
  endif()
endforeach()
find_program(STREAMSTRIKE_FADER_RUSTC rustc REQUIRED)
set(_fader_source "${CMAKE_CURRENT_SOURCE_DIR}/streamstrike-fader/iec.rs")
set(_fader_archive "${CMAKE_CURRENT_BINARY_DIR}/libstreamstrike-fader.a")
add_custom_command(
  OUTPUT "${_fader_archive}"
  COMMAND "${STREAMSTRIKE_FADER_RUSTC}" --edition=2024 --crate-name streamstrike_fader
          --crate-type=staticlib -C panic=abort -C opt-level=2 -C relocation-model=pic
          "${_fader_source}" -o "${_fader_archive}"
  DEPENDS "${_fader_source}" "${CMAKE_CURRENT_SOURCE_DIR}/streamstrike-fader/StreamStrikeFader.cmake"
          "${STREAMSTRIKE_FADER_RUSTC}"
  VERBATIM
)
add_custom_target(streamstrike_fader_build DEPENDS "${_fader_archive}")
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
