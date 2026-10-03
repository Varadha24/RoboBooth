// Arduino UNO
// Laptop/Backend -> USB Serial -> Arduino -> Relay -> Doosan Controller

const int RELAY_PIN = 7;

// Commands expected from backend:
// HIGH  -> Relay ON
// LOW   -> Relay OFF

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

    if (command == "HIGH") {

      digitalWrite(RELAY_PIN, HIGH);

      Serial.println("RELAY_HIGH");
    }

    else if (command == "LOW") {

      digitalWrite(RELAY_PIN, LOW);

      Serial.println("RELAY_LOW");
    }
  }
}
