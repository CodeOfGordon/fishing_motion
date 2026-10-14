#include "buzzer.h"

const uint8_t BUZZER_PIN = 5;
const uint16_t BEEP_HZ = 150;
const uint16_t BEEP_MS = 250;
const float NOTE_ON_FRACTION = 0.9;
const uint16_t REST = 0;

struct Note {
  uint16_t hz;
  uint16_t ms;
};

const Note END_TUNE[] PROGMEM = {
// BEGIN END_TUNE
  {311, 102},
  {311, 102},
  {349, 102},
  {349, 102},
  {370, 102},
  {370, 102},
  {415, 102},
  {415, 102},
  {466, 102},
  {311, 102},
  {233, 102},
  {466, 102},
  {622, 102},
  {622, 102},
  {554, 102},
  {554, 102},
  {466, 102},
  {311, 102},
  {233, 102},
  {466, 102},
  {311, 102},
  {311, 102},
  {233, 102},
  {311, 102},
  {466, 102},
  {466, 102},
  {415, 102},
  {415, 102},
  {370, 102},
  {370, 102},
  {349, 102},
  {349, 102},
  {311, 102},
  {311, 102},
  {349, 102},
  {349, 102},
  {370, 102},
  {370, 102},
  {415, 102},
  {415, 102},
  {466, 102},
  {247, 102},
  {370, 102},
  {466, 102},
  {415, 102},
  {415, 102},
  {370, 102},
  {370, 102},
  {349, 102},
  {349, 102},
  {311, 102},
  {311, 102},
  {349, 102},
  {349, 102},
  {370, 102},
  {370, 102},
  {349, 102},
  {349, 102},
  {311, 102},
  {311, 102},
  {294, 102},
  {294, 102},
  {349, 102},
  {349, 102},
  {311, 102},
  {311, 102},
  {349, 102},
  {349, 102},
  {370, 102},
  {370, 102},
  {415, 102},
  {415, 102},
  {466, 102},
  {311, 102},
  {233, 102},
  {466, 102},
  {622, 102},
  {622, 102},
  {554, 102},
  {554, 102},
  {466, 102},
  {311, 102},
  {233, 102},
  {466, 102},
  {311, 102},
  {311, 102},
  {233, 102},
  {311, 102},
  {466, 102},
  {466, 102},
  {415, 102},
  {415, 102},
  {370, 102},
  {370, 102},
  {349, 102},
  {349, 102},
  {311, 102},
  {311, 102},
  {349, 102},
  {349, 102},
  {370, 102},
  {370, 102},
  {415, 102},
  {415, 102},
  {466, 102},
  {247, 102},
  {370, 102},
  {466, 102},
  {415, 102},
  {415, 102},
  {370, 102},
  {370, 102},
  {349, 102},
  {277, 102},
  {208, 102},
  {349, 102},
  {370, 102},
  {277, 102},
  {208, 102},
  {370, 102},
  {415, 102},
  {294, 102},
  {233, 102},
  {415, 102},
  {466, 102},
  {294, 102},
  {233, 102},
  {466, 102},
  {311, 102},
  {311, 102},
  {349, 102},
  {349, 102},
  {370, 102},
  {370, 102},
  {415, 102},
  {415, 102},
  {466, 102},
  {311, 102},
  {233, 102},
  {466, 102},
  {622, 102},
  {622, 102},
  {554, 102},
  {554, 102},
  {466, 102},
  {311, 102},
  {233, 102},
// END END_TUNE
};

void buzzerBegin() {
  pinMode(BUZZER_PIN, OUTPUT);
}

void beep() {
  tone(BUZZER_PIN, BEEP_HZ, BEEP_MS);
}

const uint16_t NOTE_COUNT = sizeof(END_TUNE) / sizeof(Note);
const uint16_t LOOP_GAP_MS = 1500;
const unsigned long MAX_TUNE_MS = 120000;

bool playing = false;
uint16_t noteIndex = 0;
unsigned long tuneStart = 0;
unsigned long noteOnUntil = 0;
unsigned long noteUntil = 0;

void playNote() {
  uint16_t hz = REST;
  uint16_t ms = LOOP_GAP_MS;
  if (noteIndex < NOTE_COUNT) {
    hz = pgm_read_word(&END_TUNE[noteIndex].hz);
    ms = pgm_read_word(&END_TUNE[noteIndex].ms);
  }
  if (hz == REST) noTone(BUZZER_PIN);
  else tone(BUZZER_PIN, hz);
  unsigned long now = millis();
  noteOnUntil = now + ms * NOTE_ON_FRACTION;
  noteUntil = now + ms;
}

void startEndTune() {
  playing = true;
  noteIndex = 0;
  tuneStart = millis();
  playNote();
}

void stopTune() {
  playing = false;
  noTone(BUZZER_PIN);
}

void updateTune() {
  if (!playing) return;
  unsigned long now = millis();
  if (now - tuneStart > MAX_TUNE_MS) {
    stopTune();
  } else if (now >= noteUntil) {
    noteIndex = (noteIndex + 1) % (NOTE_COUNT + 1);
    playNote();
  } else if (now >= noteOnUntil) {
    noTone(BUZZER_PIN);
  }
}
