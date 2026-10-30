cmake_minimum_required(VERSION 3.28)
project(SPY-VS-SPY NONE)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_program(CA65 ca65 REQUIRED)
find_program(LD65 ld65 REQUIRED)
set(SPY_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/xex/SpyVsSpy.xex")
set(SPY_TITLE "${CMAKE_CURRENT_SOURCE_DIR}/xex/Spy Vs Spy (v2).xex")
set(SPY_OUT "${CMAKE_CURRENT_BINARY_DIR}")
add_custom_target(python-deps
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/ensure_build_deps.py"
    COMMENT "Checking Python build dependencies"
    VERBATIM)
add_custom_command(
    OUTPUT "${SPY_OUT}/title.bin" "${SPY_OUT}/title.png" "${SPY_OUT}/title.rp6502"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_title.py"
        "${SPY_TITLE}" "${SPY_OUT}"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/rp6502.py"
        create "${SPY_OUT}/title.bin" -a "XRAM(0)" -o "${SPY_OUT}/title.rp6502"
    DEPENDS python-deps tools/prepare_title.py tools/prepare_spy.py tools/rp6502.py "${SPY_TITLE}"
    VERBATIM)
add_custom_command(
    OUTPUT "${SPY_OUT}/original.bin" "${SPY_OUT}/tables.inc" "${SPY_OUT}/backdrop.inc" "${SPY_OUT}/analysis.json"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_spy.py"
        "${SPY_SOURCE}" "${SPY_OUT}"
    DEPENDS python-deps tools/prepare_spy.py "${SPY_SOURCE}"
    VERBATIM)
add_custom_command(
    OUTPUT "${SPY_OUT}/host.bin" "${SPY_OUT}/host.bin.tables" "${SPY_OUT}/host.lbl"
    COMMAND "${CA65}" -g -I "${SPY_OUT}" -I "${CMAKE_CURRENT_SOURCE_DIR}/src" -o "${SPY_OUT}/host.o"
        "${CMAKE_CURRENT_SOURCE_DIR}/src/spy.asm"
    COMMAND "${LD65}" -C "${CMAKE_CURRENT_SOURCE_DIR}/src/spy.cfg"
        -o "${SPY_OUT}/host.bin" -Ln "${SPY_OUT}/host.lbl"
        --dbgfile "${SPY_OUT}/host.dbg" -m "${SPY_OUT}/host.map" "${SPY_OUT}/host.o"
    DEPENDS src/spy.asm src/spy.cfg src/ria.inc "${SPY_OUT}/tables.inc" "${SPY_OUT}/backdrop.inc"
    VERBATIM)
add_custom_command(
    OUTPUT "${SPY_OUT}/spy-vs-spy.rp6502" "${SPY_OUT}/spy-vs-spy-r16.rp6502"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_spy.py"
        "${SPY_SOURCE}" "${SPY_OUT}" --link
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/rp6502.py"
        create "${SPY_OUT}/spy.bin" "${SPY_OUT}/title.rp6502" -a 0 -r 0xe000 -o "${SPY_OUT}/spy-vs-spy.rp6502"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
        "${SPY_OUT}/spy-vs-spy.rp6502" "${SPY_OUT}/spy-vs-spy-r16.rp6502"
    DEPENDS "${SPY_OUT}/host.bin" "${SPY_OUT}/host.bin.tables"
        "${SPY_OUT}/host.lbl" "${SPY_OUT}/original.bin" "${SPY_OUT}/title.rp6502" tools/prepare_spy.py tools/rp6502.py
    VERBATIM)
add_custom_target(spy ALL DEPENDS "${SPY_OUT}/spy-vs-spy.rp6502" "${SPY_OUT}/spy-vs-spy-r16.rp6502")
include(CTest)
if(BUILD_TESTING)
    add_test(NAME xex
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_prepare.py")
    add_test(NAME title-pixels
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_title.py")
    add_test(NAME timing
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_timing.py" "${SPY_OUT}")
    add_test(NAME graphics
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_graphics.py" "${SPY_OUT}")
    add_test(NAME music-tempo
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_music_tempo.py" "${SPY_OUT}")
    find_program(SPY_EMULATOR NAMES rp6502-emu rp6502-emu.exe
        HINTS "${CMAKE_CURRENT_SOURCE_DIR}/tools")
    if(SPY_EMULATOR)
        add_test(NAME native-title
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_title_native.py"
                "${SPY_EMULATOR}" "${SPY_OUT}")
        add_test(NAME native-game
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_native.py"
                "${SPY_EMULATOR}" "${SPY_OUT}")
        add_test(NAME menu-cursor
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_menu_cursor.py"
                "${SPY_EMULATOR}" "${SPY_OUT}")
        add_test(NAME audio
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_audio.py"
                "${SPY_EMULATOR}" "${SPY_OUT}")
    endif()
endif()
