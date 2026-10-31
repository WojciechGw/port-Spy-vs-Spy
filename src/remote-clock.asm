; Experimental cooperative simulation clock. No transport or prediction.
; The controller writes the payload and sequence first, then ready=1 last.
.setcpu "65C02"
.include "ria.inc"
.import logic_frame, pace_main, wait_ticks, frame_count, music_phase, wait_left
.export remote_begin, remote_menu, remote_pace, remote_wait, remote_input
.export remote_pause
.export remote_active, remote_status, remote_ready, remote_sequence, remote_next
.export remote_seed, remote_level, remote_ai, remote_exit, remote_error, remote_kind
.export remote_p0, remote_p1, remote_console, remote_key

.segment "MAILBOX"
    .byte "LS01"
remote_status: .byte 0       ; 0 local, 1 waiting, 2 running, 3 ended, 4 fault
remote_ready: .byte 0        ; 1 submit tick, 2 release ended session to menu
remote_sequence: .word 0
remote_next: .word 0
remote_p0: .byte $1f         ; active-low U/D/L/R/Fire
remote_p1: .byte $1f
remote_console: .byte 7      ; active-low START/SELECT/OPTION
remote_key: .byte 0          ; 0 none, 1 Escape, 2 music
remote_seed: .byte $a9
remote_level: .byte 1        ; 1..8
remote_ai: .byte 1           ; retained shared menu option, both players human
remote_exit: .byte 1         ; 1..2
remote_error: .byte 0        ; 1 sequence, 2 settings, 3 key
remote_kind: .byte 0         ; 1 foreground, 2 delay, 3 pause boundary
remote_active: .byte 0       ; 0 local, 1 deterministic init, 2 running
remote_last_main: .word 0
latched_p0: .byte $1f
latched_p1: .byte $1f
latched_console: .byte 7
latched_key: .byte 0

.segment "CLOCK"
remote_begin:
    sei
    stz RIA_IRQ
    lda #1
    sta remote_active
    lda #2
    sta remote_status
    stz remote_ready
    stz remote_error
    stz remote_next
    stz remote_next+1
    stz remote_last_main
    stz remote_last_main+1
    stz frame_count
    stz music_phase
    stz music_phase+1
    stz $d20a
    stz $b69d              ; disable the original attract-mode input replay
    ; Menu music must not carry a machine-local phase into the session.
    stz $0383
    stz $039a
    stz $0399
    ldx #20
@audio_clear:
    stz $0384,x
    dex
    bpl @audio_clear
    jsr $31be
    jsr $3010
    lda #$1f
    sta latched_p0
    sta latched_p1
    lda #7
    sta latched_console
    stz latched_key
    sta $d01f
    lda #$1f
    sta $039b
    sta $039c
    sta $fd
    sta $fe
    ; Shared settings replace both the menu values and their active copies.
    lda remote_level
    beq @bad_settings
    cmp #9
    bcs @bad_settings
    sta $034d
    dec
    sta $034c
    tay
    lda $67a7,y
    sta $c6
    sta $c7
    stz $c2
    stz $c3
    stz $c4
    stz $c5
    stz $c8
    stz $c9
    lda #2
    sta $034e
    sta $034f
    lda remote_ai
    beq @bad_settings
    cmp #6
    bcs @bad_settings
    sta $0350
    sta $0351
    lda remote_exit
    beq @bad_settings
    cmp #3
    bcs @bad_settings
    sta $0353
    dec
    sta $0352
    lda remote_seed
    jmp $2ed8             ; original seed stores and first PRNG advance
@bad_settings:
    lda #2
    sta remote_error
    lda #4
    sta remote_status
@fault:
    bra @fault            ; reset required; never start a mismatched game

remote_menu:
    lda remote_active
    beq @local
    lda #3
    sta remote_status
@ended:
    lda remote_ready
    cmp #2
    bne @ended
    stz remote_ready
    stz remote_active
    stz remote_status
    lda #$80
    sta RIA_IRQ
    cli
@local:
    lda #0                ; replaced original instructions at $0C25
    sta $0377
    jmp $0c2a

remote_pace:
    lda remote_active
    bne @remote
    jmp pace_main
@remote:
    php
    pha
    cmp #1
    bne @paced
    lda #2
    sta remote_active
    stz remote_next
    stz remote_next+1
    stz remote_last_main
    stz remote_last_main+1
    stz frame_count
    stz music_phase
    stz music_phase+1
@paced:
    lda remote_next
    cmp remote_last_main
    bne @available
    lda remote_next+1
    cmp remote_last_main+1
    bne @available
    lda #1
    sta remote_kind
    jsr remote_tick
@available:
    lda remote_next
    sta remote_last_main
    lda remote_next+1
    sta remote_last_main+1
    pla
    plp
    lda $0381
    rts

remote_wait:
    lda remote_active
    bne @remote
    jmp wait_ticks
@remote:
    lda #2
    sta remote_kind
    jsr remote_tick
    sec
    lda wait_left
    sbc #1
    sta wait_left
    lda wait_left+1
    sbc #0
    sta wait_left+1
    bcc @done
    ora wait_left
    bne @remote
@done:
    rts

; The original pause spins on keyboard state without calling a delay. Supply
; logical frames at those three waits as well, keeping its release/press/release
; sequence and its disabled game clocks. OPTION still exits a paused session.
remote_pause:
    stz $037d
    stz $037e
@release_first:
    jsr pause_tick
    bit $0399
    bmi @exit
    bvs @release_first
@press:
    jsr pause_tick
    bit $0399
    bmi @exit
    bvc @press
@release_last:
    jsr pause_tick
    bit $0399
    bmi @exit
    bvs @release_last
    inc $037d
    inc $037e
    jmp $0d5d
@exit:
    jmp $0d54
pause_tick:
    lda #3
    sta remote_kind
    jmp remote_tick

remote_tick:
    php
    pha
    phx
    phy
    cld
    lda remote_active
    cmp #1
    beq @execute
    lda #1
    sta remote_status
@waiting:
    lda remote_ready
    cmp #1
    bne @waiting
    lda remote_sequence
    cmp remote_next
    bne @bad_sequence
    lda remote_sequence+1
    cmp remote_next+1
    bne @bad_sequence
    lda remote_key
    cmp #3
    bcs @bad_key
    sta latched_key
    lda remote_p0
    and #$1f
    sta latched_p0
    lda remote_p1
    and #$1f
    sta latched_p1
    lda remote_console
    and #7
    sta latched_console
    stz remote_ready
    stz remote_error
@execute:
    lda #2
    sta remote_status
    stz RIA_IRQ
    jsr logic_frame
    inc remote_next
    bne :+
    inc remote_next+1
:
    ply
    plx
    pla
    plp
    rts
@bad_sequence:
    lda #1
    bra @reject
@bad_key:
    lda #3
@reject:
    sta remote_error
    stz remote_ready
    bra @waiting

remote_input:
    lda latched_p1
    asl
    asl
    asl
    asl
    sta $d300
    lda latched_p0
    and #15
    ora $d300
    sta $d300
    lda latched_p0
    and #16
    lsr
    lsr
    lsr
    lsr
    sta $d010
    lda latched_p1
    and #16
    lsr
    lsr
    lsr
    lsr
    sta $d011
    lda latched_console
    sta $d01f
    lda #$ff
    sta $d20f
    sta $d209
    lda latched_key
    beq @done
    cmp #1
    bne @music
    lda #$1c
    bra @key
@music:
    lda #$3e
@key:
    sta $d209
    lda #$fb
    sta $d20f
@done:
    rts
