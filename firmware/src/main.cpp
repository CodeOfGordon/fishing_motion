#include <Arduino.h>
#include <Wire.h>
#include "buzzer.h"

const int MPU_addr = 0x68; // sensor location: the apartment
const int PWR_MGMT_1 = 0x6B; // sensor brain: the room number
const int AC_addr = 0x3B;
const int TEMP_addr = 0x41;
const int GY_addr = 0x43;
int16_t AcX, AcY, AcZ, Tmp, GyX, GyY, GyZ;
const int WAKE = 0;
const int SLEEP = 1;
const long BAUD_RATE = 115200;
const unsigned long SAMPLE_MS = 16;
unsigned long lastSample = 0;

void readFrom(byte address, int num, byte results[]) {
  Wire.beginTransmission(MPU_addr);
  Wire.write(address);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_addr, num, true);
  // true/false = releasing/keeping I2C control
  int i = 0;
  while(Wire.available()) {
    results[i] = Wire.read();
    i++;
  }
}

void writeTo(byte address, byte value) {
  // always send apartment address and room number when sending data
  Wire.beginTransmission(MPU_addr);
  Wire.write(address);
  Wire.write(value);
  Wire.endTransmission(true);
}

void readAll() {
  byte localBuffer[14];
  readFrom(AC_addr, 14, localBuffer);
  AcX = localBuffer[0]<<8 | localBuffer[1];
  AcY = localBuffer[2]<<8 | localBuffer[3];
  AcZ = localBuffer[4]<<8 | localBuffer[5];
  Tmp = localBuffer[6]<<8 | localBuffer[7];
  GyX = localBuffer[8]<<8 | localBuffer[9];
  GyY = localBuffer[10]<<8 | localBuffer[11];
  GyZ = localBuffer[12]<<8 | localBuffer[13];
}

void handleSerial() {
  static char line[16];
  static uint8_t length = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      line[length] = '\0';
      if (strcmp(line, "BITE") == 0) beep();
      if (strcmp(line, "END") == 0) startEndTune();
      if (strcmp(line, "STOP") == 0) stopTune();
      length = 0;
    } else if (c != '\r' && length < sizeof(line) - 1) {
      line[length++] = c;
    }
  }
}

void sendAll() {
  Serial.print(AcX); Serial.print(',');
  Serial.print(AcY); Serial.print(',');
  Serial.print(AcZ); Serial.print(',');
  Serial.print(GyX); Serial.print(',');
  Serial.print(GyY); Serial.print(',');
  Serial.println(GyZ);
}

void setup() {
  buzzerBegin();
  Serial.begin(BAUD_RATE);
  Serial.println("boot");
  Wire.begin();
  writeTo(PWR_MGMT_1, WAKE);
}

void loop() {
  handleSerial();
  updateTune();
  if (millis() - lastSample >= SAMPLE_MS) {
    lastSample += SAMPLE_MS;
    readAll();
    sendAll();
  }
}