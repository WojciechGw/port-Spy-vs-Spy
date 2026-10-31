; Native 65C02 host for the supplied Atari Spy vs Spy executable.
; Original code keeps its zero page, stack, RAM and self-modifying overlays.
; Host uses absolute addressing only and does not borrow the game's zero page.
; In particular $14 is the menu selection, NOT the OS clock after takeover.
.setcpu "65C02"
.include "ria.inc"
.export start, setvbv, irq, frame_count
.export pace_main, delay_short, delay_long
.export audio_source, music_tick
.ifdef REMOTE_CLOCK
.import remote_active, remote_input, remote_wait
.export logic_frame, wait_ticks, music_phase, main_tick, wait_left
.endif
.segment "CODE"
start:
    sei
    cld
    ldx #$ff
    txs
    stz RIA_IRQ
.ifdef REMOTE_CLOCK
    stz remote_active
.endif
    lda #<irq
    sta $fffe
    lda #>irq
    sta $ffff
    ; Defined initial state, including PMG buffers and emulated IO.
    lda #0
    ldx #0
@clear:
    sta $bc00,x
    sta $bd00,x
    sta $be00,x
    sta $bf00,x
    sta $d000,x
    sta $d200,x
    sta $d300,x
    sta $d400,x
    inx
    bne @clear
    stz $0222
    stz $0223
    stz frame_count
    stz font_page
    stz music_phase
    stz music_phase+1
    lda RIA_VSYNC
    sta main_tick
    sta video_stamp
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    stz RIA_ADDR0
    stz RIA_ADDR0+1
    ldx #0
    ldy #0
    lda #0
@xclear:
    sta RIA_RW0
    inx
    bne @xclear
    iny
    bne @xclear
    ; Fixed display list: eight 24-line bands and an 8-line status band.
    jsr configure_display
    stz RIA_ADDR0
    lda #$e4
    sta RIA_ADDR0+1
    ldx #0
@footer:
    lda footer,x
    sta RIA_RW0
    inx
    cpx #footer_end-footer
    bne @footer
    stz RIA_ADDR0
    lda #$ce
    sta RIA_ADDR0+1
    ldx #0
@bg:
    lda backgrounds,x
    sta RIA_RW0
    inx
    cpx #126
    bne @bg
    xreg 1,0,0,1
    jsr configure_game_vga
    xreg 0,0,0,$ff00
    xreg 0,0,2,$ff20
    xreg 0,1,0,$ff80
    jmp $0c00

configure_vga:
    lda #<vga_commands
    sta command_read+1
    lda #>vga_commands
    sta command_read+2
configure_commands:
@next:
    jsr command_read
    beq @done
    tax
@push:
    jsr command_read
    sta RIA_XSTACK
    dex
    bne @push
    lda #RIA_OP_XREG
    sta RIA_OP
    jsr RIA_SPIN
    bra @next
@done:
    rts

; Each Atari glyph is already 4x8 at 2bpp. Let VGA double it horizontally
; instead of expanding every pixel on the 6502. Nine lists of 120 glyphs.
configure_glyphs:
    stz RIA_ADDR0
    lda #$40
    sta RIA_ADDR0+1
    stz band_index
    stz glyph_ptr
    stz glyph_ptr+1
    lda #20
    sta glyph_y
@band:
    lda #3
    sta glyph_rows
@row:
    ldx #0
@glyph:
    txa
    asl
    asl
    asl
    sta RIA_RW0
    lda #0
    rol
    sta RIA_RW0
    lda glyph_y
    sta RIA_RW0
    stz RIA_RW0
    lda glyph_ptr
    sta RIA_RW0
    lda glyph_ptr+1
    sta RIA_RW0
    lda band_index
    asl
    asl
    asl
    asl
    asl
    sta RIA_RW0
    lda #$c8
    adc #0
    sta RIA_RW0
    lda #$10                 ; 4 x 8 source pixels
    sta RIA_RW0
    lda #$41                 ; 2bpp, horizontal doubling
    sta RIA_RW0
    clc
    lda glyph_ptr
    adc #8
    sta glyph_ptr
    bcc :+
    inc glyph_ptr+1
:
    inx
    cpx #40
    bne @glyph
    clc
    lda glyph_y
    adc #8
    sta glyph_y
    dec glyph_rows
    bne @row
    clc
    lda glyph_ptr
    adc #64                  ; 120 visible glyphs per 128-glyph bank
    sta glyph_ptr
    bcc :+
    inc glyph_ptr+1
:
    inc band_index
    lda band_index
    cmp #9
    bne @band
    rts
command_read:
    lda vga_commands
    inc command_read+1
    bne :+
    inc command_read+2
:
    cmp #0
    rts

.macro vcmd mode, opts, cfg, arg0, arg1, arg2, arg3
    .ifblank arg3
        .byte 15
    .else
        .byte 17
    .endif
    .byte 1,0,1,>(mode),<(mode),>(opts),<(opts),>(cfg),<(cfg)
    .byte >(arg0),<(arg0),>(arg1),<(arg1),>(arg2),<(arg2)
    .ifnblank arg3
        .byte >(arg3),<(arg3)
    .endif
.endmacro
vga_commands:
    .repeat 9, band
        .if band = 8
            vcmd 3,0,$ce00+band*14,0,20+band*24,220
            vcmd 5,$38,$d000+band*40+20,2,0,20+band*24,220
            vcmd 5,$38,$4000+band*1200,40,1,20+band*24,220
            vcmd 5,$38,$d000+band*40,2,2,20+band*24,220
        .else
            vcmd 3,0,$ce00+band*14,0,20+band*24,44+band*24
            vcmd 5,$38,$d000+band*40+20,2,0,20+band*24,44+band*24
            vcmd 5,$38,$4000+band*1200,120,1,20+band*24,44+band*24
            vcmd 5,$38,$d000+band*40,2,2,20+band*24,44+band*24
        .endif
    .endrepeat
    vcmd 1,0,$e400,1,228,236
    .byte 0

; Atari SETVBV: A=6 (immediate VBI), X=high, Y=low.
setvbv:
    stx $0223
    sty $0222
    lda #$80
    sta RIA_IRQ
    cli
    rts

; One foreground iteration per video tick. The original alternates players,
; so each spy gets at most 30 updates/s at the VGA's 60 Hz. Use the hardware
; counter rather than IRQ count: expensive drawing must not accumulate a
; backlog of movement updates. The hook replaces LDA $0381 at $0CEB.
pace_main:
    php
    pha
@wait:
    lda RIA_VSYNC
    cmp main_tick
    beq @wait
    sta main_tick
    pla
    plp
    lda $0381
    rts

; Replace the two counted CPU delays with video-clock delays. Tables round
; their original instruction counts at 1.773447 MHz up to whole VGA ticks.
; Keep the original scratch writes and A/X/Y/carry/decimal return contract.
delay_short:
    stx $036d
    sty $036e
    php
    pha
    cld
    tya
    tax
    lda short_ticks,x
    sta wait_left
    stz wait_left+1
.ifdef REMOTE_CLOCK
    jsr remote_wait
.else
    jsr wait_ticks
.endif
    pla
    plp
    ldx $036d
    ldy $036e
    rts
delay_long:
    stx $036d
    sty $036e
    php
    cld
    tax
    lda long_ticks_lo,x
    sta wait_left
    lda long_ticks_hi,x
    sta wait_left+1
.ifdef REMOTE_CLOCK
    jsr remote_wait
.else
    jsr wait_ticks
.endif
    plp
    lda #0
    ldx $036d
    ldy $036e
    rts
wait_ticks:
    lda RIA_VSYNC
    sta wait_stamp
@wait:
    lda RIA_VSYNC
    sec
    sbc wait_stamp
    beq @wait
    sta wait_elapsed
    clc
    adc wait_stamp
    sta wait_stamp
    sec
    lda wait_left
    sbc wait_elapsed
    sta wait_left
    lda wait_left+1
    sbc #0
    sta wait_left+1
    bcc @done
    ora wait_left
    bne @wait
@done:
    rts

; User-adjusted music: 1323/1600 of 60 Hz = 49.6125 Hz (5% above R09).
; input and SFX retain their existing clock. Hold notes on the skipped tick.
music_tick:
    lda music_phase
    clc
    adc #<1323
    sta music_phase
    lda music_phase+1
    adc #>1323
    sta music_phase+1
    cmp #>1600
    bcc @hold
    bne @advance
    lda music_phase
    cmp #<1600
    bcc @hold
@advance:
    sec
    lda music_phase
    sbc #<1600
    sta music_phase
    lda music_phase+1
    sbc #>1600
    sta music_phase+1
    jmp $34ea
@hold:
    rts

irq:
    pha
    phx
    phy
    cld
    lda RIA_IRQ
    stz RIA_IRQ            ; original VBI executes CLI; prevent reentrancy
.ifdef REMOTE_CLOCK
    lda remote_active
    beq :+
    jmp irq_done           ; physical VSYNC cannot advance a remote session
:
.endif
    lda RIA_VSYNC
    cmp video_stamp
    bne :+
    jmp irq_done           ; a duplicate IRQ must not advance music or VBI
:
    sta video_stamp
.ifdef REMOTE_CLOCK
    jsr logic_frame
    jmp irq_done
logic_frame:
.endif
    inc frame_count
    lda frame_count
    eor $d20a
    asl
    adc #$17
    sta $d20a
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
.ifdef REMOTE_CLOCK
    lda remote_active
    beq @local_input
    jsr remote_input
    bra @input_ready
@local_input:
    jsr input
@input_ready:
.else
    jsr input
.endif
    lda $d40e
    and #$40
    beq @done
    lda $0223
    beq @done
    jsr vbi
    ; Snapshot and publish audio before the raster handlers. $303A gates
    ; AUDC3 late in the Atari scanout; sampling AFTER it instead discards
    ; the entire first music voice on every other VGA frame.
    ldx #8
@audio:
    lda $d200,x
    sta audio_source,x
    dex
    bpl @audio
    ; The sequencer only rewrites music registers when its envelope changes.
    ; Restore held notes from its shadows too: the preceding frame's DLI
    ; may have gated AUDC3 off even though the note is still active.
    ldx #3
@music:
    lda $0394,x
    sta audio_source+4,x
    dex
    bpl @music
    jsr sound
    ; Execute the nine DLI handlers in display-list order. They also
    ; update gameplay sprites; their colour/font changes become VGA bands.
    stz band_index
@band:
    lda $d40e
    and #$80
    beq @render
    jsr dli
    jsr palette
    inc band_index
    lda band_index
    cmp #9
    bne @band
@render:
    jsr fonts_with_cursor
    jsr sprite_images
@done:
.ifdef REMOTE_CLOCK
    rts
.endif
irq_done:
    sei
    lda #$80
    sta RIA_IRQ
    ply
    plx
    pla
    rti

vbi:
    lda #>@return
    pha
    lda #<@return
    pha
    php
    pha
    phx
    phy
    jmp ($0222)
@return:
    rts
dli:
    lda #>@return
    pha
    lda #<@return
    pha
    php
    jmp ($0200)
@return:
    rts

palette:
    lda band_index
    asl
    asl
    sta RIA_ADDR0
    lda #$cf
    sta RIA_ADDR0+1
    ldx $d01a
    jsr color
    lda band_index
    asl
    asl
    asl
    asl
    asl
    sta RIA_ADDR0
    lda #$c8
    adc #0
    sta RIA_ADDR0+1
    stz RIA_RW0
    stz RIA_RW0
    ldx $d016
    jsr color
    ldx $d017
    jsr color
    ldx $d018
    jsr color
    jmp sprite_config
color:
    lda color_lo,x
    sta RIA_RW0
    lda color_hi,x
    sta RIA_RW0
    rts

sprite_config:
    ldx band_index
    lda sprite_cfg_lo,x
    sta RIA_ADDR0
    lda sprite_cfg_hi,x
    sta RIA_ADDR0+1
    stz sprite_index
@sprite:
    ldx sprite_index
    lda $d000,x
    sec
    sbc #48
    tay
    lda #0
    sbc #0
    sta sprite_high
    tya
    asl
    rol sprite_high
    sta RIA_RW0
    lda sprite_high
    sta RIA_RW0
    ldx band_index
    lda band_y,x
    sta RIA_RW0
    stz RIA_RW0
    lda band_index
    asl
    asl
    clc
    adc sprite_index
    tax
    lda sprite_image_lo,x
    sta RIA_RW0
    lda sprite_image_hi,x
    sta RIA_RW0
    txa
    asl
    asl
    sta RIA_RW0
    lda #$e2
    sta RIA_RW0
    ldx sprite_index
    cpx #2
    lda #$51                 ; 8 x 24, normal PMG
    bcc :+
    lda #$57                 ; 32 x 24, quad-width PMG
:
    sta RIA_RW0
    lda #$40                 ; double colour-clock pixels horizontally
    sta RIA_RW0
    inc sprite_index
    lda sprite_index
    cmp #4
    bne @sprite
    lda band_index
    asl
    asl
    asl
    asl
    sta RIA_ADDR0
    lda #$e2
    sta RIA_ADDR0+1
    ldy #0
@colors:
    stz RIA_RW0
    stz RIA_RW0               ; transparent background (alpha bit 5 clear)
    ldx $d012,y
    jsr color
    iny
    cpy #4
    bne @colors
    rts

sprite_images:
    stz RIA_ADDR0
    lda #$d2
    sta RIA_ADDR0+1
    ldx #0
@p0:
    lda $bc00,x
    sta RIA_RW0
    inx
    bne @p0
    stz RIA_ADDR0
    lda #$d6
    sta RIA_ADDR0+1
@p1:
    lda $bd00,x
    sta RIA_RW0
    inx
    bne @p1
    lda #$be
    sta pmg_read+2
    lda #$da
    sta RIA_ADDR0+1
    stz RIA_ADDR0
    ldy #0
pmg_read:
    lda $be00,y
    tax
    lda quad6,x
    sta RIA_RW0
    lda quad4,x
    sta RIA_RW0
    lda quad2,x
    sta RIA_RW0
    lda quad0,x
    sta RIA_RW0
    iny
    bne pmg_read
    inc pmg_read+2
    lda pmg_read+2
    cmp #$c0
    bne pmg_read
    rts

quad6:
    .repeat 256,i
        .byte ((i & $80) / $80 * $f0) | ((i & $40) / $40 * $0f)
    .endrepeat
quad4:
    .repeat 256,i
        .byte ((i & $20) / $20 * $f0) | ((i & $10) / $10 * $0f)
    .endrepeat
quad2:
    .repeat 256,i
        .byte ((i & $08) / $08 * $f0) | ((i & $04) / $04 * $0f)
    .endrepeat
quad0:
    .repeat 256,i
        .byte ((i & $02) / $02 * $f0) | ((i & $01) * $0f)
    .endrepeat

; Upload original glyph bytes unchanged. Upper/lower fields alternate;
; the status row is refreshed every frame. Every visible glyph converges
; within two IRQs, without conversion work or a changed-byte backlog.
fonts:
    lda #16
    sta pages_left
    jsr copy_font_pages
    lda font_page
    and #$1f
    sta font_half
    lda #32
    sta font_page
    lda #2
    sta pages_left
    jsr copy_font_pages
    lda font_half
    sta font_page
    rts
copy_font_pages:
    lda font_page
    clc
    adc #$94
    .repeat 8,i
        sta .ident(.sprintf("font_read%d",i))+2
    .endrepeat
    lda font_page
    sta RIA_ADDR0+1
    stz RIA_ADDR0
    ldy #0
    .repeat 8,i
.ident(.sprintf("font_read%d",i)):
        lda $9400,y
        sta RIA_RW0
        iny
    .endrepeat
    bne font_read0
    inc font_page
    dec pages_left
    beq :+
    jmp copy_font_pages
:
    rts

input:
    stz RIA_ADDR0
    lda #$ff
    sta RIA_ADDR0+1
    ldx #0
@read:
    lda RIA_RW0
    sta keys,x
    inx
    cpx #72
    bne @read
    lda #$ff
    sta $d300
    sta $d20f
    lda #7
    sta $d01f
    lda #1
    sta $d010
    sta $d011
    ; HID arrows, Space; WASD, left Shift for player two.
    lda keys+10
    and #$02
    beq :+
    lda $d300
    and #$fd
    sta $d300
:
    lda keys+10
    and #$04
    beq :+
    lda $d300
    and #$fe
    sta $d300
:
    lda keys+10
    and #$01
    beq :+
    lda $d300
    and #$fb
    sta $d300
:
    lda keys+9
    and #$80
    beq :+
    lda $d300
    and #$f7
    sta $d300
:
    lda keys+5
    and #$10
    beq :+
    stz $d010
:
    lda keys+3
    and #$04                 ; W, HID 26
    beq :+
    lda $d300
    and #$ef
    sta $d300
:
    lda keys+2
    and #$40                 ; S, HID 22
    beq :+
    lda $d300
    and #$df
    sta $d300
:
    lda keys
    and #$10                 ; A
    beq :+
    lda $d300
    and #$bf
    sta $d300
:
    lda keys
    and #$80                 ; D
    beq :+
    lda $d300
    and #$7f
    sta $d300
:
    lda keys+28
    and #2
    beq :+
    stz $d011
:
    ; F2=Start, F3=Select, F4=Option. Enter also Start.
    lda keys+7
    and #$08
    bne @start
    lda keys+5
    and #1
    beq :+
@start:
    lda $d01f
    and #6
    sta $d01f
:
    lda keys+7
    and #$10
    beq :+
    lda $d01f
    and #5
    sta $d01f
:
    lda keys+7
    and #$20
    beq :+
    lda $d01f
    and #3
    sta $d01f
:
    ; Escape and M are the original keyboard functions.
    lda keys+5
    and #2
    beq :+
    lda #$fb
    sta $d20f
    lda #$1c
    sta $d209
:
    lda keys+2
    and #1
    beq :+
    lda #$fb
    sta $d20f
    lda #$3e
    sta $d209
:
    ; Connected pads combine directions with keyboard input.
    ldx #0
    jsr pad
    ldx #10
    jsr pad
    rts
pad:
    lda keys+32,x
    bpl @done
    ora keys+33,x
    and #15
    cpx #0
    beq :+
    asl
    asl
    asl
    asl
:
    eor #$ff
    and $d300
    sta $d300
    lda keys+34,x
    and #3
    beq @buttons
    cpx #0
    bne :+
    stz $d010
    bra @buttons
:
    stz $d011
@buttons:
    lda keys+35,x
    and #8
    beq :+
    lda $d01f
    and #6
    sta $d01f
:
    lda keys+35,x
    and #$10
    beq @done
    lda $d01f
    and #3
    sta $d01f
@done:
    rts

; Native music/SFX envelopes drive four independent PSG voices. Both $Ax
; and $Ex are pure tones (AUDC bit 6 is ignored when bits 7/5 are set).
; Leave phase running across notes and use the shortest PSG attack/release
; to smooth edges without replacing the original volume envelopes.
; AUDCTL=0 is used by this game. Polynomial modes remain approximations.
sound:
    lda #$80
    sta RIA_ADDR0
    lda #$ff
    sta RIA_ADDR0+1
    ldy #0
@channel:
    ldx audio_source,y
    lda freq_lo,x
    sta RIA_RW0
    lda freq_hi,x
    sta RIA_RW0
    lda #128
    sta RIA_RW0
    lda audio_source+1,y
    and #15
    tax
    lda audio_levels,x
    sta RIA_RW0
    sta RIA_RW0
    lda audio_source+1,y
    and #$a0
    cmp #$a0
    beq @pure
    lda #$40
    bra @wave
@pure:
    lda #$10
@wave:
    sta RIA_RW0
    lda audio_source+1,y
    and #$10                ; volume-only is DC, not an audible oscillator
    bne @silent
    lda audio_source+1,y
    and #15
    beq @silent
    lda audio_pan,y
    ora #1
    bra @gate
@silent:
    lda audio_pan,y
@gate:
    sta RIA_RW0
    lda #0
    sta RIA_RW0
    iny
    iny
    cpy #8
    bne @channel
    rts

.segment "TABLES"

footer:
    .byte 0,0
    .word 0,228,40,1,$e414,$e410,$ffff
    .word $0020,$ffff
footer_text:
    .byte "SPY R16  MUSIC 49.6125 HZ"
    .res 40-(*-footer_text),$20
footer_end:
backgrounds:
    .repeat 9,band
        .byte 1,1
        .word 0,0,8,1,$cefe,$cf00+band*4
    .endrepeat
; Mild stereo placement, retaining both spies and melody in either speaker.
; POKEY 0/1: white/black effects; POKEY 2/3: two music parts.
audio_pan: .byte 232,0,24,0,244,0,12,0
audio_source: .res 9,0
frame_count: .byte 0
font_page: .byte 0
font_half: .byte 0
music_phase: .word 0
video_stamp: .byte 0
glyph_ptr: .word 0
glyph_y: .byte 0
glyph_rows: .byte 0
pages_left: .byte 0
band_index: .byte 0
keys: .res 72,0
sprite_index: .byte 0
sprite_high: .byte 0
main_tick: .byte 0
wait_left: .word 0
wait_stamp: .byte 0
wait_elapsed: .byte 0
sprite_cfg_lo:
    .repeat 9,b
        .byte <($d000+b*40)
    .endrepeat
sprite_cfg_hi:
    .repeat 9,b
        .byte >($d000+b*40)
    .endrepeat
band_y:
    .repeat 9,b
        .byte 20+b*24
    .endrepeat
sprite_image_lo:
    .repeat 9,b
        .byte <($d200+28+b*24),<($d600+28+b*24),<($da00+(28+b*24)*4),<($de00+(28+b*24)*4)
    .endrepeat
sprite_image_hi:
    .repeat 9,b
        .byte >($d200+28+b*24),>($d600+28+b*24),>($da00+(28+b*24)*4),>($de00+(28+b*24)*4)
    .endrepeat
.include "tables.inc"

.segment "TABLES"
; The original XOR cursor toggles on each short menu delay. After pacing
; these delays to VSYNC, field uploads/display sampling can hide its blink.
; Draw a white underline for the original selected row ($14), with each
; phase held for 16 VGA frames. Refresh all positions to clear old rows.
fonts_with_cursor:
    lda $0377
    cmp #1
    beq @menu
    jmp fonts
@menu:
    ldx #7
cursor_upload:
    jsr cursor_address
cursor_read:
    lda $974e
    sta cursor_saved,x
    txa
    lsr
    cmp $14
    bne @blank
    lda frame_count
    and #$10
    beq @blank
    lda #$55                ; 2bpp palette index 1: white
    bra @write
@blank:
    lda #0
@write:
    jsr cursor_write
    sta RIA_RW0
    dex
    bpl cursor_upload
    ; The bulk upload must use the same cursor pixels: briefly uploading
    ; the original XOR bytes would expose black/blank pixels during scanout.
    jsr fonts
    ldx #7
@restore:
    jsr cursor_address
    lda cursor_saved,x
    jsr cursor_write
    dex
    bpl @restore
    rts
cursor_address:
    lda cursor_lo,x
    sta cursor_read+1
    sta cursor_write+1
    sta RIA_ADDR0
    lda cursor_hi,x
    sta RIA_ADDR0+1
    clc
    adc #$94
    sta cursor_read+2
    sta cursor_write+2
    rts
cursor_write:
    sta $974e
    rts
cursor_lo: .byte $4e,$4f,$ce,$cf,$0e,$0f,$4e,$4f
cursor_hi: .byte $03,$03,$04,$04,$06,$06,$07,$07
cursor_saved: .res 8

; Static foreground mask: opaque black only on exterior background pixels.
; The original cabinet, cable and game pixels retain their original palette.
configure_display:
    jsr configure_backdrop
    jmp configure_glyphs
configure_game_vga:
    jsr configure_vga
    lda #<backdrop_commands
    sta command_read+1
    lda #>backdrop_commands
    sta command_read+2
    jmp configure_commands
configure_backdrop:
    stz RIA_ADDR0
    lda #$90
    sta RIA_ADDR0+1
    lda #<backdrop_runs
    sta backdrop_read+1
    lda #>backdrop_runs
    sta backdrop_read+2
@next:
    jsr backdrop_read
    beq @config
    cmp #$80
    beq @literal
    tax
    lda #0
    bcc @repeat
    txa
    and #$7f
    tax
    lda #$ff
@repeat:
    sta RIA_RW0
    dex
    bne @repeat
    bra @next
@literal:
    jsr backdrop_read
    sta RIA_RW0
    bra @next
@config:
    lda #$80
    sta RIA_ADDR0
    lda #$ce
    sta RIA_ADDR0+1
    ldx #0
@copy:
    lda backdrop_config,x
    sta RIA_RW0
    inx
    cpx #18
    bne @copy
    rts
backdrop_read:
    lda backdrop_runs
    inc backdrop_read+1
    bne :+
    inc backdrop_read+2
:
    cmp #0
    rts
backdrop_config:
    .byte 0,0
    .word 0,20,320,200,$9000,$ce8e
    .word 0,$0020
backdrop_commands:
    vcmd 3,0,$ce80,2,20,220
    .byte 0

.segment "TITLE"
.export boot
boot:
    sei
    cld
    ldx #$ff
    txs
    stz RIA_IRQ
    lda #1
    sta RIA_STEP0
    sta RIA_STEP1
    jsr show_title
    jmp start              ; full R10 initialization, including emulated IO

; The ROM loader preloads the v2 picture into XRAM. Display it before the
; usual XRAM clear and game setup. All waits use VSYNC, never CPU cycles.
show_title:
    stz title_armed
    stz title_released
    stz RIA_ADDR0
    lda #$ff
    sta RIA_ADDR0+1
    ldx #72
@clear_input:
    stz RIA_RW0
    dex
    bne @clear_input
    xreg 0,0,0,$ff00
    xreg 0,0,2,$ff20
    xreg 1,0,0,1
    lda #<title_commands
    sta command_read+1
    lda #>title_commands
    sta command_read+2
    jsr configure_commands
    lda #1
    sta title_active
    lda #<480               ; eight seconds, or Space/Enter/pad fire/Start
    sta wait_left
    lda #>480
    sta wait_left+1
    lda RIA_VSYNC
    sta wait_stamp
@frame:
    jsr title_frame
    jsr title_pressed
    beq @released
    ldx title_armed
    bne @release
    stz title_released
    bra @count
@released:
    lda title_armed
    bne @count
    inc title_released
    lda title_released
    cmp #4                  ; ignore launch keys and initial HID reports
    bcc @count
    inc title_armed
@count:
    lda wait_left
    bne :+
    dec wait_left+1
:
    dec wait_left
    lda wait_left
    ora wait_left+1
    bne @frame
    ; Timeout must not carry an already held button into the game either.
@release:
    ; Consume the dismissal, so holding fire cannot also start gameplay.
    jsr title_frame
    jsr title_pressed
    bne @release
@done:
    xreg 1,0,0,1            ; blank before reusing the title's XRAM for glyphs
    jsr title_frame
    jsr title_frame
    ; Stop HID writers before the game clears/reuses the whole XRAM.
    xreg 0,0,0,$ffff
    xreg 0,0,2,$ffff
    stz title_active
    rts
title_frame:
    lda RIA_VSYNC
    cmp wait_stamp
    beq title_frame
    sta wait_stamp
    jmp input
title_pressed:
    lda $d010
    and $d011
    beq @yes
    lda $d01f
    and #1
    eor #1
    rts
@yes:
    lda #1
    rts
title_active: .byte 0
title_armed: .byte 0
title_released: .byte 0
title_commands:
    vcmd 3,2,$8020,0,20,220
    vcmd 1,0,$8040,1,228,236
    .byte 0

.include "backdrop.inc"
