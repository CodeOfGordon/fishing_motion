#pragma once
#include <Arduino.h>

void buzzerBegin();
void beep();         // short beep: a fish bit (the game sent BITE)
void startEndTune(); // the end-of-round tune, repeats until stopTune() (the game sent END)
void stopTune();     // the game sent STOP when the player left the results screen
void updateTune();   // call every loop(): moves the tune along without blocking
