cmake_minimum_required(VERSION 3.28)
project(SPY-VS-SPY NONE)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_program(CA65 ca65 REQUIRED)
find_program(LD65 ld65 REQUIRED)
set(SPY_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/assets/native/game.bin")
set(SPY_TITLE "${CMAKE_CURRENT_SOURCE_DIR}/assets/native/title.bin")
set(SPY_MANIFEST "${CMAKE_CURRENT_SOURCE_DIR}/assets/native/manifest.json")
set(SPY_OUT "${CMAKE_CURRENT_BINARY_DIR}")
add_custom_target(python-deps
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/ensure_build_deps.py"
    COMMENT "Preparing Python dependencies for tests and optional XEX extraction"
    VERBATIM)
add_custom_command(
    OUTPUT "${SPY_OUT}/title.bin" "${SPY_OUT}/title.png" "${SPY_OUT}/title.rp6502"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_title.py"
        "${SPY_TITLE}" "${SPY_OUT}"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/rp6502.py"
        create "${SPY_OUT}/title.bin" -a "XRAM(0)" -o "${SPY_OUT}/title.rp6502"
    DEPENDS tools/prepare_title.py tools/prepare_spy.py tools/native_assets.py tools/rp6502.py "${SPY_TITLE}" "${SPY_MANIFEST}"
    VERBATIM)
add_custom_command(
    OUTPUT "${SPY_OUT}/original.bin" "${SPY_OUT}/tables.inc" "${SPY_OUT}/backdrop.inc" "${SPY_OUT}/analysis.json"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/prepare_spy.py"
        "${SPY_SOURCE}" "${SPY_OUT}"
    DEPENDS tools/prepare_spy.py tools/native_assets.py "${SPY_SOURCE}" "${SPY_MANIFEST}"
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
# Explicit experiment: never replaces the default/local ROM.
add_custom_target(remote-clock
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/build_remote_clock.py"
        --build "${SPY_OUT}" --output "${SPY_OUT}/remote-clock" --ca65 "${CA65}" --ld65 "${LD65}"
    DEPENDS spy
    COMMENT "Building the isolated cooperative-clock experiment"
    VERBATIM)
find_program(CL65 cl65)
find_program(SIM65 sim65)
if(CL65)
    set(NET_OUT "${SPY_OUT}/net-probe")
    add_custom_command(
        OUTPUT "${NET_OUT}/net-probe.rp6502"
        COMMAND "${CMAKE_COMMAND}" -E make_directory "${NET_OUT}"
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/build_net_probe.py"
            --output "${NET_OUT}" --cl65 "${CL65}"
        DEPENDS src/net-probe/main.c src/net-probe/platform.h src/net-probe/protocol.c
            src/net-probe/protocol.h src/net-probe/pico.c tools/build_net_probe.py tools/rp6502.py
        VERBATIM)
    add_custom_target(net-probe DEPENDS "${NET_OUT}/net-probe.rp6502")
    if(SIM65)
        add_custom_target(net-probe-test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_net_probe.py"
                --output "${NET_OUT}" --cl65 "${CL65}" --sim65 "${SIM65}"
            DEPENDS net-probe
            USES_TERMINAL VERBATIM)
    endif()
endif()
include(CTest)
option(SPY_TEST_XEX "Also validate extraction against the optional original XEX files" OFF)
if(BUILD_TESTING)
    add_test(NAME net-probe-capture-audit
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_probe_capture_audit.py")
    add_test(NAME net-probe-capture
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_capture_net_probe.py")
    add_test(NAME net-probe-peer
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_net_probe_peer.py")
    add_test(NAME determinism-analysis
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_determinism_analysis.py")
    add_test(NAME native-assets
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_prepare.py")
    add_test(NAME title-pixels
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_title.py")
    add_test(NAME timing
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_timing.py" "${SPY_OUT}")
    add_test(NAME graphics
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_graphics.py" "${SPY_OUT}")
    add_test(NAME music-tempo
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_music_tempo.py" "${SPY_OUT}")
    if(SPY_TEST_XEX)
        add_test(NAME xex-original
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_xex.py")
        add_test(NAME title-original
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_title_xex.py")
    endif()
    find_program(SPY_EMULATOR NAMES rp6502-emu rp6502-emu.exe
        HINTS "${CMAKE_CURRENT_SOURCE_DIR}/tools")
    if(SPY_EMULATOR)
        add_custom_target(remote-clock-test
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_remote_clock.py"
                "${SPY_OUT}/remote-clock"
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/audit_remote_clock.py"
                --emulator "${SPY_EMULATOR}" --experiment "${SPY_OUT}/remote-clock"
            DEPENDS remote-clock
            COMMENT "Checking shared initialization and numbered logical steps"
            USES_TERMINAL
            VERBATIM)
        add_custom_target(remotegame-audit
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/audit_determinism.py"
                --emulator "${SPY_EMULATOR}" --build "${SPY_OUT}" --output "${SPY_OUT}/remotegame"
            DEPENDS spy
            COMMENT "Auditing R16 determinism and an isolated fixed-seed experiment"
            USES_TERMINAL
            VERBATIM)
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
