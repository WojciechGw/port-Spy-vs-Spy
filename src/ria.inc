; Minimal native ABI, from https://picocomputer.github.io/ria.html.
; No cc65 runtime or platform-specific compiler fork is required.
RIA_VSYNC   = $FFE3
RIA_RW0     = $FFE4
RIA_STEP0   = $FFE5
RIA_ADDR0   = $FFE6
RIA_RW1     = $FFE8
RIA_STEP1   = $FFE9
RIA_ADDR1   = $FFEA
RIA_XSTACK  = $FFEC
RIA_OP      = $FFEF
RIA_IRQ     = $FFF0
RIA_SPIN    = $FFF1
RIA_OP_XREG = $01

.macro xreg device, channel, index, value
    lda #(device)
    sta RIA_XSTACK
    lda #(channel)
    sta RIA_XSTACK
    lda #(index)
    sta RIA_XSTACK
    lda #>(value)
    sta RIA_XSTACK
    lda #<(value)
    sta RIA_XSTACK
    lda #RIA_OP_XREG
    sta RIA_OP
    jsr RIA_SPIN
.endmacro
