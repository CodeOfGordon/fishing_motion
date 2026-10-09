"""Visual-only constants: colours and font sizes. Gameplay numbers live in config/tuning.toml."""

# water and shore
WATER_SHALLOW = (88, 186, 186)
WATER_MID = (52, 140, 164)
WATER_DEEP = (28, 86, 128)
WATER_EDGE = (20, 60, 92)
SKY_BANK = (96, 140, 84)
BANK_DARK = (70, 110, 64)
DOCK = (132, 94, 60)
DOCK_DARK = (98, 68, 44)
DOCK_LIGHT = (160, 120, 80)
REED = (84, 120, 60)
LILY = (90, 150, 80)
LILY_DARK = (64, 118, 60)

# tackle
ROD = (210, 190, 150)
ROD_DARK = (120, 96, 70)
LINE = (240, 240, 230)
LINE_TAUT = (250, 190, 70)
LINE_DANGER = (240, 70, 60)
LURE = (230, 60, 50)
LURE_WHITE = (250, 250, 245)

# fish
FISH_SHADOW = (12, 34, 52)
KOI_GLOW = (255, 210, 90)
SPECIES_COLOURS = {
    "minnow": (180, 190, 200),
    "bluegill": (90, 140, 200),
    "perch": (200, 180, 70),
    "rainbow_trout": (220, 140, 160),
    "bass": (90, 140, 80),
    "catfish": (120, 110, 100),
    "pike": (120, 150, 90),
    "lantern_koi": (255, 170, 40),
    "bait_thief": (160, 160, 150),
    "old_boot": (100, 76, 54),
}

# text and UI
TEXT = (240, 240, 235)
TEXT_DIM = (170, 180, 185)
TEXT_SHADOW = (10, 20, 30)
OVERLAY_BG = (0, 0, 0, 170)
PANEL = (14, 28, 40, 215)
GOOD = (110, 210, 120)
WARN = (240, 200, 80)
BAD = (235, 90, 80)
GOLD = (250, 205, 80)
SILVER = (205, 210, 220)
BRONZE = (205, 140, 90)
PLATINUM = (180, 230, 240)
MENU_SELECTED = (255, 236, 160)
MENU_HIGHLIGHT = (40, 70, 96)
BG_MENU = (18, 44, 64)

MEDAL_COLOURS = {"bronze": BRONZE, "silver": SILVER, "gold": GOLD, "platinum": PLATINUM}

# font sizes
OVERLAY_FONT_SIZE = 18
OVERLAY_FONT_NAME = "menlo,monaco,couriernew"  # system monospace; falls back to the default font
HUD_FONT_SIZE = 30
HUD_SMALL_FONT_SIZE = 22
CARD_TITLE_SIZE = 46
TITLE_FONT_SIZE = 96
TITLE_Y = 104  # the title sits inside the pond, clear of the bank
ROD_TEST_FEEDBACK_MS = 900  # how long a Rod Test result line stays up
MENU_FONT_SIZE = 36
MENU_SPACING = 46

# ---------------------------------------------------------------------------
# Art view (M3). Purely visual numbers; gameplay geometry (rod tip, water
# rect, depth zones) comes from config/tuning.toml.
ART_SEED = 7  # the pond's decoration looks the same every launch

# water: a depth gradient in arcs around the rod tip
WATER_NEAR = (122, 204, 188)  # by the dock, inside the shallow band's inner edge
WATER_ABYSS = (46, 100, 138)  # beyond the deep band (the far corners)
WATER_BAND_SHADE = 0.10  # each band darkens this much toward its far edge
WATER_BAND_BLEND_PX = 24  # soft edge between depth bands
WATER_CONTOUR = (236, 250, 246)  # faint ring at each zone edge...
WATER_CONTOUR_MIX = 0.12  # ...mixed this much into the water colour
WATER_CONTOUR_WIDTH = 2
WATER_NOISE_AMP = 8  # +- colour of the low-frequency mottling
WATER_NOISE_CELL_PX = 60  # size of one mottling blob
WATER_GRAIN_AMP = 3  # +- fine grain
WATER_GRAIN_TILE = 64
WATER_STONES = 26  # pebbles on the bottom near the dock
WATER_STONE_PX = (4, 11)
WATER_STONE_COLOURS = ((140, 196, 170), (104, 170, 160), (150, 206, 180))
WATER_STONE_ALPHA = 90

# caustics: thin sine lines added onto the water, scrolled at different speeds
# (colour added, wavelength px, amplitude px, line spacing px, vertical?, scroll px/s x, y, width)
CAUSTIC_LAYERS = (
    ((26, 34, 32), 170, 9, 34, False, 18.0, 6.0, 1),
    ((20, 28, 28), 130, 11, 46, True, -12.0, 8.0, 1),
    ((14, 20, 20), 290, 18, 76, False, 7.0, -5.0, 2),
)
CAUSTIC_PHASES = 3  # line phase pattern repeats every this many lines
CAUSTIC_STEP_PX = 6  # polyline sampling step
CAUSTIC_SHALLOW = 1.0  # strength in the shallows...
CAUSTIC_DEEP = 0.28  # ...fading to this in the deep

# glints: sparkles on the water surface
GLINT_COUNT = 14
GLINT_LIFE_S = (0.45, 1.2)
GLINT_SIZES = (3, 5, 7)
GLINT_LEVELS = 6
GLINT_COLOUR = (215, 235, 240)
GLINT_DOCK_CLEAR_PX = 90  # no glints this close to the rod tip

# shore and bank
GRASS = (104, 150, 88)
GRASS_LIGHT = (126, 170, 100)
GRASS_DARK = (82, 124, 70)
GRASS_SPECKLES = 2400
GRASS_TUFTS = 220
GRASS_TUFT_PX = (3, 7)
SHORE_CORNER_R = 30
SHORE_WOBBLE_PX = (1, 11)  # the bank edge sits this far outside the water rect
SHORE_SAMPLE_PX = 8
SHORE_RIM_PX = 6  # muddy rim between grass and water
SHORE_SAND = (176, 166, 120)
SHORE_FOAM = (232, 244, 238, 190)
SHORE_SHADE = ((0, 64), (4, 44), (8, 26), (12, 12), (16, 0))  # (inset px, alpha) bank shadow on the water
OVERLAY_TILE = 64

# dock (planks across, rails along the sides, posts at the water end)
DOCK_HALF_W = 58
DOCK_INTO_WATER = 10  # the dock end sticks out this far past the water edge
DOCK_PLANK_H = 15
DOCK_PLANK_JITTER = 12
DOCK_GAP = (66, 46, 30)
DOCK_GRAIN = (116, 82, 52)
DOCK_RAIL_W = 7
DOCK_POST_R = 9
DOCK_POST_TOP = (156, 118, 80)
DOCK_NAIL = (70, 60, 52)
DOCK_SHADOW = (6, 30, 44, 80)
DOCK_SHADOW_PX = 9

# reeds: clumps along the bank (edge, fraction along it)
REED_LIGHT = (130, 166, 88)
REED_HEAD = (112, 76, 46)
REED_CLUMPS = (
    ("bottom", 0.20), ("bottom", 0.33), ("bottom", 0.68), ("bottom", 0.80), ("bottom", 0.95),
    ("left", 0.30), ("left", 0.78), ("right", 0.22), ("right", 0.62),
    ("top", 0.04), ("top", 0.31), ("top", 0.71), ("top", 0.97),
)
REED_PER_CLUMP = (5, 9)
REED_LEN_PX = (20, 44)
REED_SPREAD_DEG = 70  # fan of a clump around its outward direction
REED_SWAY_DEG = 7
REED_SWAY_RAD_S = (0.9, 1.7)
REED_HEAD_CHANCE = 0.35
REED_WIDTH = 3
REED_OUTLINE = (58, 92, 50)

# lily pads (edge, fraction along it, radius px, flower?)
LILY_PADS = (
    ("left", 0.18, 24, True), ("left", 0.27, 16, False), ("left", 0.62, 20, False),
    ("right", 0.40, 26, False), ("right", 0.50, 15, True), ("right", 0.85, 19, False),
    ("top", 0.15, 22, False), ("top", 0.21, 14, False), ("top", 0.82, 23, True),
)
LILY_INSET_PX = 34  # pad centres sit this far inside the water edge
LILY_NOTCH_DEG = 46
LILY_VEIN = (112, 172, 98)
LILY_EDGE = (58, 104, 56)
LILY_SHADOW = (4, 30, 40, 70)
LILY_FLOWER = (246, 184, 204)
LILY_FLOWER_CENTRE = (252, 224, 126)

# fish shadows
FISH_LEN_BASE = 17  # length px = base + per_cm * size_cm
FISH_LEN_PER_CM = 0.6
FISH_LEN_BUCKET = 3  # sprite cache: lengths rounded to this
FISH_ANGLE_STEP_DEG = 5  # sprite cache: headings rounded to this
FISH_WAG_FRAMES = 5
FISH_WAG_DEG = 26  # tail swing at full wag
FISH_WAG_BASE_HZ = 1.0  # wag rate = base + per_px * speed
FISH_WAG_PER_PX = 0.035
FISH_BEND = 0.30  # the rear of the body follows the tail this much
FISH_SHADOW_ALPHA = 215  # deep water; FISH_SHADOW_SHALLOW_K of this in the shallows
FISH_SHADOW_EDGE_ALPHA = 92
FISH_SHADOW_EDGE_GROW = 1.14
FISH_SUPERSAMPLE = 2
FISH_CACHE_MAX = 3000
FISH_MOUTH = 0.42  # attached fish: the lure sits this far (x length) in front of the centre
FISH_SHAPES = {  # (width / length, tail length / length)
    "default": (0.34, 0.30),
    "bluegill": (0.46, 0.26),
    "catfish": (0.36, 0.28),
    "pike": (0.22, 0.24),
    "lantern_koi": (0.36, 0.34),
    "bait_thief": (0.19, 0.30),
}
TRAP_JITTER_DEG = 16  # bait thief: twitchy heading...
TRAP_JITTER_HZ = (5.3, 2.9)
TRAP_WAG_MULT = 2.4  # ...and a fast tail
KOI_SHADOW = (74, 50, 16)
KOI_GLOW_COLOUR = (160, 126, 40)  # added onto the water at full pulse
KOI_GLOW_LEVELS = 8
KOI_GLOW_RADIUS = 1.15  # x fish length
KOI_PULSE_HZ = 0.8
BOOT_SHADOW = (12, 26, 36)
BOOT_ALPHA = 130
BOOT_SCALE = 1.5  # boot sprite length x fish_length(size_cm)
BOOT_TILT_DEG = 30  # boots lie within this of upright
FIGHT_RUN_TURN_DEG = 55  # a running fish faces this far off straight-away
FIGHT_REST_WOBBLE_DEG = 14
FIGHT_RUN_WAG_MULT = 2.2
NIBBLE_NUDGE_PX = 4  # the fish butts the lure on each nibble

# tackle
ROD_BASE_DX = 26  # rod butt, relative to pond.rod_tip...
ROD_BASE_Y = 714  # ...at this screen y (hands just off the bottom)
ROD_TIP_OVER_WATER = 30  # the visible rod tip reaches this far past the water edge
ROD_TILT_PX = 42
ROD_BEND_PX = 46
ROD_SEGMENTS = 10
ROD_WIDTH = (8, 2)  # butt, tip
ROD_HANDLE = (60, 44, 34)
ROD_REEL_R = 10
ROD_REEL_AT = 0.16  # reel sits this far along the rod
ROD_REEL = (190, 196, 204)
ROD_REEL_DARK = (90, 96, 108)
LINE_SEGMENTS = 18
LINE_SAG = 0.16  # x line length at zero tension
LINE_SAG_SWAY = 0.18
LINE_SAG_SWAY_HZ = 0.15
LINE_IDLE_TENSION = 0.12  # visual tension of a drifting line...
LINE_REEL_TENSION = 0.33  # ...plus this x reel_rate
LINE_BITE_TENSION = 0.75
LINE_WHITE_UNTIL = 0.3  # line colour: white up to here, amber at LINE_AMBER_AT, red at 1
LINE_AMBER_AT = 0.62
LINE_FLICKER_AT = 0.9
LINE_FLICKER_HZ = 8
LINE_WIDTH = 2
LINE_SNAP_S = 0.5  # the broken end whips back for this long
LINE_SNAP_STUB_PX = 60
LINE_SNAP_WIGGLE_PX = 10

BOBBER_R = 7
BOBBER_BOB_PX = 1.2
BOBBER_BOB_HZ = 0.7
BOBBER_HANG_PX = 16  # READY: the bobber dangles below the rod tip
BOBBER_RING = (226, 244, 244)
BOBBER_RING_GROW = 5
BOBBER_SHADOW = (14, 46, 66)
BOBBER_SWING_PX = 1.5  # READY: the dangling bobber swings this much
BOBBER_AFLOAT_SINK = 0.3  # below this sink level it still has a ring, shadow and highlight
NIBBLE_TWITCH_PX = 3
NIBBLE_TWITCH_S = 0.28
NIBBLE_DIP = 0.18  # the bobber shrinks this much on a nibble
BITE_SINK_S = 0.14
BITE_SUNK_SCALE = 0.55
BITE_SUNK_FADE = 0.62  # mixed this far into the water colour once under
BITE_TUG_S = 0.30  # a tug ring every this long while a fish has the bait
BITE_MARK_SIZE = 104  # the "!" above a real bite
BITE_MARK_LIFT = 54
BITE_MARK_PULSE_HZ = 5
BITE_MARK_PULSE = 0.12
BITE_MARK_FRAMES = 8  # pre-scaled pulse frames
TRAP_DRAG_PX = 40  # the bait thief drags the bobber sideways...
TRAP_DRAG_S = 0.6  # ...reaching full drag after this long
TRAP_JITTER_PX = 2.5
TRAP_WAKE_S = 0.11
FIGHT_THRASH_S = 0.22  # ripple every this long while the fish runs
DRIFT_WAKE_S = 0.28  # V-wake ring while the lure is reeled in
DRIFT_WAKE_SPEED = 40  # px/s

CAST_ARC_PX = 120  # peak height of a full-length cast
CAST_ARC_MIN = 0.45  # short casts still rise this fraction
CAST_GROW = 0.5  # the flying lure looks this much bigger at the top of the arc
CAST_SHADOW = (10, 40, 58)
AIM_COLOUR = (252, 244, 214)
AIM_DIM = (200, 214, 210)
AIM_DOT_PX = 16
AIM_DOT_R = 3
AIM_HEAD_PX = 16
AIM_TARGET_R = 14

# effects (rings, droplets, shake, flash, pop-up text)
RIPPLE_COLOUR = (230, 248, 248)
RIPPLE_MAX = 40
RIPPLES = {  # kind: (start radius, end radius, life s, width)
    "land": (6, 46, 0.9, 2),
    "nibble": (5, 20, 0.45, 1),
    "bite": (8, 70, 0.8, 3),
    "bite_slow": (4, 40, 1.1, 2),
    "tug": (6, 26, 0.5, 2),
    "wake": (3, 14, 0.55, 1),
    "thrash": (6, 30, 0.55, 2),
    "run": (8, 50, 0.7, 2),
    "escape": (6, 40, 0.8, 2),
    "catch": (8, 56, 0.8, 3),
    "drop": (1, 6, 0.3, 1),
    "turn": (4, 18, 0.5, 1),
}
DROP_MAX = 140
DROP_GRAVITY = 560  # px/s^2 on the fake height
DROP_COLOUR = (234, 250, 252)
DROP_SHADOW = (20, 60, 80)
SPLASHES = {  # kind: (count, ground speed px/s, up speed px/s range, radius range)
    "land": (10, 60, (90, 170), (1, 3)),
    "bite": (26, 110, (150, 280), (2, 4)),
    "hooked": (12, 80, (110, 200), (1, 3)),
    "catch": (30, 120, (170, 300), (2, 4)),
    "run": (6, 70, (80, 150), (1, 3)),
    "release": (8, 60, (80, 150), (1, 2)),
}
DROP_RIPPLE_CHANCE = 0.25
SHAKE_BITE_PX = 4
SHAKE_SNAP_PX = 7
SHAKE_S = 0.35
FLASH_S = 0.16
FLASH_LEVEL = 110  # brightness added at the start of the flash
FLOATER_MAX = 8
FLOATER_LIFE_S = 1.2
FLOATER_RISE = 34  # px/s
FLOATER_POP_S = 0.14
FLOATER_SUB_DY = 34  # "PERFECT!" sits this far under "HOOKED!"

# catch card and HUD extras
CARD_SIZE = (540, 330)
CARD_SLIDE_PX = 180
CARD_PORTRAIT = (300, 130)
CARD_BORDER = (250, 236, 190)
CARD_GLOW = (255, 220, 120)
ESCAPE_CARD_SIZE = (520, 92)
ESCAPE_CARD_GAP = 100  # the banner sits this far above (or below) the bobber...
ESCAPE_CARD_MIN_TOP = 96  # ...but never higher than this (the HUD lives up there)
PORTRAIT_SUPERSAMPLE = 2
PORTRAIT_OUTLINE = (24, 30, 36)
PORTRAIT_EYE = (250, 250, 245)
PORTRAIT_PUPIL = (16, 18, 22)
PORTRAITS = {  # height/length, tail style, markings
    "minnow": (0.30, "fork", ("line",)),
    "bluegill": (0.55, "round", ("bars", "ear", "breast")),
    "perch": (0.36, "fork", ("bars", "orange_fins")),
    "rainbow_trout": (0.30, "fork", ("pink_stripe", "spots")),
    "bass": (0.36, "round", ("band", "big_mouth")),
    "catfish": (0.28, "round", ("whiskers", "spots")),
    "pike": (0.20, "round", ("light_spots", "snout")),
    "lantern_koi": (0.34, "fork", ("patches", "glow")),
    "bait_thief": (0.30, "fork", ("mask",)),
}
MARK_PINK = (232, 120, 150)
MARK_ORANGE = (240, 130, 50)
MARK_WHITE = (250, 248, 240)
MARK_KOI_RED = (220, 70, 40)
MARK_DARK = (30, 34, 30)
BOOT_SOLE = (54, 40, 30)
BOOT_LACE = (210, 200, 170)
BONUS_ICON = (64, 30)
TILT_GAUGE_R = 26
TILT_GAUGE_RIM = 6
TILT_GAUGE_TICK = 6
TILT_GAUGE_AT = (166, 60)  # x from the left, y from the bottom

# ---------------------------------------------------------------------------
# Art view refinements (M3 review).

# lighter, softer water for the art view (the plain view keeps WATER_SHALLOW/MID/DEEP)
ART_WATER_SHALLOW = (96, 190, 186)
ART_WATER_MID = (72, 156, 172)
ART_WATER_DEEP = (56, 120, 156)
FISH_SHADOW_SHALLOW_K = 0.70  # shadows fade to this x their alpha inside the shallow band

# fish turning sharply leave a small ring
FISH_TURN_RAD_S = 5.0  # a heading change faster than this counts as a turn (edges, fleeing, committing)...
FISH_TURN_GAP_S = 1.2  # ...at most once per fish per this long

# pop-ups ("!", HOOKED!, PERFECT!) stay out of the HUD band at the top
POPUP_MIN_TOP = 84
POPUP_SIDE_PX = 12  # and this far inside the screen's sides

# line: tension rises instantly but eases down, so the hooked->fight hand-over doesn't flash slack
LINE_EASE_DOWN_S = 0.25
LINE_HOOKED_TENSION = 0.62  # amber: hooked isn't a danger
LINE_TRAP_TENSION = 0.25  # the bait thief's tug leaves the line white and sagging
LINE_DANGER_HOT = (255, 150, 120)  # the near-snap flicker alternates red with this...
LINE_HOT_EXTRA_W = 2  # ...drawn this much wider
LINE_UNDER = (16, 40, 52)  # dark under-stroke so pale lines read over the shallows
LINE_UNDER_EXTRA_W = 2

# HUD on dark pills (readable over the grass)
HUD_PILL = (14, 28, 40, 170)
HUD_PILL_RADIUS = 10
HUD_PILL_PAD = 8
HUD_EDGE_PX = 20  # HUD text sits this far from the screen's sides...
HUD_TOP_PX = 14  # ...and top
HUD_LINE_GAP = 2
HUD_SHADOW_PX = 2  # drop shadow under HUD text
HUD_TEXT_CACHE = 96  # rendered strings kept
CLOCK_SCALE = 1.25  # the clock is this much bigger than HUD_FONT_SIZE...
CLOCK_PULSE = 0.12  # ...and pulses this much in the final stretch...
CLOCK_PULSE_MS = 90  # ...at this rate (radians per ms = 1 / this)
FRENZY_POP_S = 0.5  # the FRENZY! label shrinks from FRENZY_POP_FROM x to 1x over this long
FRENZY_POP_FROM = 1.6
ANNOUNCE_S = 2.5  # "A Lantern Koi appeared!" under the clock
ANNOUNCE_FADE_S = 0.5
SCORE_POP_S = 1.8  # "+114" next to the score after a catch
SCORE_POP_FADE_S = 0.6
SCORE_POP_GAP = 24
BONUS_ICON_GAP = 8
DIAL_PANEL = (14, 102, 222, 98)  # x, y from the bottom, width, height: crank and tilt gauge
CRANK_AT = (66, 58)  # x from the left, y from the bottom
CRANK_R = 26
CRANK_RING_W = 4
CRANK_ARM = 20
CRANK_ARM_W = 5
CRANK_KNOB_R = 6
CRANK_TURNS_PER_S = 2.5  # the crank icon's speed at reel_rate 1
DIAL_LABEL_GAP = 6
TENSION_BAR = (52, 26, 300)  # x from the right, width, height (centred vertically)
TENSION_BAR_RADIUS = 8
TENSION_BAR_INSET = 3
TENSION_WARN_AT = 0.6  # bar colours: green, then amber...
TENSION_DANGER_AT = 0.9  # ...then red
TENSION_FLASH_MS = 80  # straining: the bar flashes at this period
TENSION_MARK_OVERHANG = 4
CAST_POWER_RECT = (740, 46, 220, 14)  # x, y from the bottom, width, height: right of the dock
CAST_POWER_RADIUS = 6
CAST_POWER_LABEL_GAP = 4

# catch card and escape banner layout
CARD_PORTRAIT_TOP = 12
CARD_NAME_GAP = 2  # under the portrait box
CARD_SIZE_GAP = 2
CARD_POINTS_GAP = 6
CARD_EXTRAS_FROM_BOTTOM = 30
CARD_BOB_RAD_S = 2.2
CARD_BOB_PX = 3
CARD_SLIDE_IN = 0.25  # the card slides in over this fraction of its life...
CARD_FADE_IN = 1.5  # ...and is fully opaque at 1 / this of the slide
ESCAPE_POP_IN = 0.2  # the escape banner fades in over this fraction of its life
PANEL_RADIUS = 18
PANEL_BORDER_W = 3
PANEL_BORDER_ALPHA = 220
PANEL_INNER_INSET = 6
PANEL_INNER_RADIUS = 14
PANEL_INNER_ALPHA = 70
PANEL_BORDER_LIGHTEN = 0.35  # the catch card's border: the species colour mixed this much toward white
TILT_GAUGE_ARC_W = 2
TILT_NEEDLE_W = 3
TILT_HUB_R = 4
TENSION_MARK_W = 2
