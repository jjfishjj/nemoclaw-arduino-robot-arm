#include <Servo.h>

Servo servo;
const uint8_t PINS[4] = {3, 5, 6, 9};
const char* NAMES[4] = {"base", "shoulder", "elbow", "gripper"};
int joint = 0;
int angle = 90;

void printState() {
  Serial.print("joint="); Serial.print(NAMES[joint]);
  Serial.print(" pin="); Serial.print(PINS[joint]);
  Serial.print(" angle="); Serial.println(angle);
}

void attachJoint() {
  servo.detach();
  servo.attach(PINS[joint]);
  servo.write(angle);
  printState();
}

void setup() {
  Serial.begin(115200);
  Serial.println("Servo calibration: 1-4 select, +/- move 1 degree, h=90, x=detach");
  attachJoint();
}

void loop() {
  if (!Serial.available()) return;
  char command = Serial.read();
  if (command >= '1' && command <= '4') {
    joint = command - '1';
    angle = 90;
    attachJoint();
  } else if (command == '+' && angle < 180) {
    servo.write(++angle); printState();
  } else if (command == '-' && angle > 0) {
    servo.write(--angle); printState();
  } else if (command == 'h') {
    angle = 90; servo.write(angle); printState();
  } else if (command == 'x') {
    servo.detach(); Serial.println("detached");
  }
}

