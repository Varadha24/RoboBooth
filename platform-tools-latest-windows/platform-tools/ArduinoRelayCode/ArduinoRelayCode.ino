const int RELAY_PIN = 7;

void setup() {
  pinMode(RELAY_PIN, OUTPUT);

  // Relay OFF initially
  digitalWrite(RELAY_PIN, LOW);

  Serial.begin(9600);

  Serial.println("Arduino Ready");
}

void loop() {

  if (Serial.available() > 0) {

    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "on") {

      digitalWrite(RELAY_PIN, HIGH);

      Serial.println("Relay ON");
    }

    else if (command == "off") {

      digitalWrite(RELAY_PIN, LOW);

      Serial.println("Relay OFF");
    }
  }
}
