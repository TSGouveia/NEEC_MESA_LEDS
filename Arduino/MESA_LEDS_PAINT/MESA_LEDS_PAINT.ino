#include <FastLED.h>    //https://github.com/marcmerlin/FastLED_NeoMatrix
#include <LEDMatrix.h>  //https://github.com/Jorgen-VikingGod/LEDMatrix

// --- Configurações da Matriz (Mantenha as suas) ---
#define LED_PIN 10
#define COLOR_ORDER RGB  // MANTENHA RGB AQUI. A correção será feita depois.
#define CHIPSET WS2812B

#define MATRIX_WIDTH 32
#define MATRIX_HEIGHT 18
#define MATRIX_TYPE HORIZONTAL_MATRIX  // Verifique se este é o tipo correto para sua fiação

// --- Constantes do Protocolo Serial (Devem corresponder à Unity) ---
const byte START_BYTE_1 = 0xA5;
const byte START_BYTE_2 = 0x5A;
const int NUM_PIXELS = MATRIX_WIDTH * MATRIX_HEIGHT;  // 576
const int DATA_LENGTH = NUM_PIXELS * 3;               // 1728 bytes (RGB)
const long SERIAL_BAUD_RATE = 115200;                 // Deve ser IGUAL à da Unity

// --- Objeto da Matriz ---
// O objeto leds gerencia o mapeamento (x,y) para o array linear FastLED
cLEDMatrix<MATRIX_WIDTH, MATRIX_HEIGHT, MATRIX_TYPE> leds;

// --- Buffer para Receber Dados Seriais ---
// ATENÇÃO: 1728 bytes é muita RAM! Pode não funcionar em Uno/Nano.
//          Funciona melhor em Mega, ESP32, Teensy, etc.
byte pixelBuffer[DATA_LENGTH];

// --- Máquina de Estados para Leitura Serial ---
enum ReadState {
  WAITING_FOR_START1,
  WAITING_FOR_START2
};
ReadState currentState = WAITING_FOR_START1;


void setup() {
  // Inicializa Serial com a taxa definida
  Serial.begin(SERIAL_BAUD_RATE);
  Serial.setTimeout(100);  // Define um timeout para readBytes (ex: 100ms)

  // Inicializa FastLED
  FastLED.addLeds<CHIPSET, LED_PIN, COLOR_ORDER>(leds[0], NUM_PIXELS)
         .setCorrection(TypicalLEDStrip); // Adiciona correção de cor genérica (opcional)
  FastLED.setBrightness(127);  // Defina o brilho desejado (0-255)
  FastLED.clear(true);         // Limpa a matriz e atualiza (true)
  FastLED.show();              // Garante que a matriz esteja apagada
  delay(500);                  // Pequeno delay para estabilização

  Serial.println("Arduino Pronto. Aguardando dados da Unity...");
  currentState = WAITING_FOR_START1;  // Define o estado inicial
}

void loop() {
  // Verifica se há dados disponíveis na porta serial
  if (Serial.available() > 0) {
    byte incomingByte = Serial.read();

    switch (currentState) {
      case WAITING_FOR_START1:
        if (incomingByte == START_BYTE_1) {
          currentState = WAITING_FOR_START2;
        }
        break;

      case WAITING_FOR_START2:
        if (incomingByte == START_BYTE_2) {
          // Sequência de início encontrada, tenta ler os dados RGB.
          int bytesRead = Serial.readBytes(pixelBuffer, DATA_LENGTH);

          if (bytesRead == DATA_LENGTH) {
            // Sucesso! Dados recebidos. Atualiza a matriz lógica.
            int bufferIndex = 0;
            // Preenche a matriz LOGICA (leds(x,y)) com os dados recebidos (RGB)
            for (int y = 0; y < MATRIX_HEIGHT; y++) {
              for (int x = 0; x < MATRIX_WIDTH; x++) {
                byte r = pixelBuffer[bufferIndex++];
                byte g = pixelBuffer[bufferIndex++];
                byte b = pixelBuffer[bufferIndex++];
                // leds(x, y) usa o mapeamento da LEDMatrix para colocar
                // o pixel no lugar certo dentro do array linear leds[0]
                leds(x, y) = CRGB(r, g, b);
              }
            }

            // --- CORREÇÃO ESPECÍFICA R <-> G PARA OS 13 LEDS DO CANTO INFERIOR DIREITO ---
            // Esta seção aplica a troca R <-> G nos pixels que estão VISUALMENTE
            // no canto inferior direito da matriz.
            // Assumimos que são os últimos 13 pixels da última linha.

            int correction_y = 0; // Última linha
            int start_correction_x = 0; // Coluna inicial para correção
            int wrong_led_count=13;

            for (int x = start_correction_x; x < wrong_led_count; x++) {
                 // Acessa o pixel usando as coordenadas (x, y) via LEDMatrix
                CRGB currentColor = leds(x, correction_y);
                // Troca os componentes Red e Green
                leds(x, correction_y) = CRGB(currentColor.g, currentColor.r, currentColor.b);
            }
            // --- FIM DA CORREÇÃO ---


            // Envia os dados do array linear leds[0] (com a correção aplicada)
            // para a matriz física de LEDs.
            FastLED.show();

            currentState = WAITING_FOR_START1; // Volta a esperar pelo próximo frame

          } else {
            // Falha na leitura
            Serial.print("Erro: Leitura de dados falhou! Esperava ");
            Serial.print(DATA_LENGTH);
            Serial.print(" bytes, mas recebeu ");
            Serial.println(bytesRead);
            //Serial.print("Timeout: "); Serial.println(Serial.getTimeout()); // Descomentar para debug
            currentState = WAITING_FOR_START1;
            // Limpa o buffer serial para evitar leituras inválidas subsequentes
            while (Serial.available() > 0) { Serial.read(); }
          }
        } else {
          // Segundo byte não confere, reinicia a busca
          if (incomingByte == START_BYTE_1) {
            currentState = WAITING_FOR_START2;
          } else {
            currentState = WAITING_FOR_START1;
          }
        }
        break;
    } // Fim do switch
  } // Fim do if Serial.available()
} // Fim do loop