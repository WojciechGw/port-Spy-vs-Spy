# Keep native ROM builds offline; fetch the web player only when requested.
set(SPY_WEB_PLAYER "${CMAKE_SOURCE_DIR}/tools/rp6502-0.42-web.zip"
    CACHE FILEPATH "Official RP6502 0.42 web player archive")
set(SPY_WEB_SHA256 "d903769487abdffe7a3bd61b89f311e689f3a3b926e78ee2eb79f54a03454449")
if(NOT EXISTS "${SPY_WEB_PLAYER}")
    file(DOWNLOAD
        "https://github.com/picocomputer/rp6502/releases/download/v0.42/rp6502-0.42-web.zip"
        "${SPY_WEB_PLAYER}"
        EXPECTED_HASH "SHA256=${SPY_WEB_SHA256}" TLS_VERIFY ON
        INACTIVITY_TIMEOUT 30)
endif()
file(SHA256 "${SPY_WEB_PLAYER}" actual_sha256)
if(NOT actual_sha256 STREQUAL SPY_WEB_SHA256)
    message(FATAL_ERROR "SPY_WEB_PLAYER must be the official RP6502 0.42 web archive")
endif()
set(web_out "${CMAKE_BINARY_DIR}/web")
add_custom_command(
    OUTPUT "${web_out}/spyvsspy.zip" "${web_out}/index.html"
        "${web_out}/spyvsspy/index.html" "${web_out}/spyvsspy/rp6502.js"
        "${web_out}/spyvsspy/rp6502.wasm" "${web_out}/spyvsspy/spy-vs-spy.rp6502"
        "${web_out}/spyvsspy/screenshot.png" "${web_out}/spyvsspy/help.txt"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/tools/prepare_web.py"
        --player "${SPY_WEB_PLAYER}" --rom "${SPY_OUT}/spy-vs-spy.rp6502"
        --screenshot "${SPY_OUT}/title.png" --output "${web_out}"
    DEPENDS tools/prepare_web.py web/index.html src/help.txt "${SPY_WEB_PLAYER}"
        "${SPY_OUT}/spy-vs-spy.rp6502" "${SPY_OUT}/title.png"
    COMMENT "Packaging browser game and GitHub Pages site"
    VERBATIM)
add_custom_target(spy-web ALL DEPENDS "${web_out}/spyvsspy.zip"
    "${web_out}/index.html" "${web_out}/spyvsspy/index.html"
    "${web_out}/spyvsspy/rp6502.js" "${web_out}/spyvsspy/rp6502.wasm"
    "${web_out}/spyvsspy/spy-vs-spy.rp6502" "${web_out}/spyvsspy/screenshot.png"
    "${web_out}/spyvsspy/help.txt")
