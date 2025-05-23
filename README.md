# NEEC_MESA_LEDS

Este repositório serve para controlar uma mesa de LEDs usando Arduino como **slave**, recebendo os píxeis enviados pelo PC (**master**).

---

## 🔗 Repositórios Relacionados

- **Exemplo de um código para a mesa de LEDs**  
  👉 [NEEC_LEDS_EXAMPLE](https://github.com/TSGouveia/NEEC_LEDS_EXAMPLE)

- **Source do projeto Unity para desenho personalizado**  
  👉 [Mesa_de_Leds_Paint](https://github.com/TSGouveia/Mesa_de_Leds_Paint_Final)

---

## 🧱 Dependências Arduino

Instala estas bibliotecas:

```cpp
#include <FastLED.h>    // https://github.com/marcmerlin/FastLED_NeoMatrix
#include <LEDMatrix.h>  // https://github.com/Jorgen-VikingGod/LEDMatrix
```

- **Pin usado para os LEDs (Arduino R4):**

```cpp
#define LED_PIN 10
```

---

## 💡 Opções de Utilização

Escolhe como queres usar a mesa de LEDs:

- 🎥 **Queres meter um vídeo a dar?**  
  Python → `send_video_to_leds.py`

- 🖥️ **Queres fazer screen share do teu PC para a mesa?**  
  Python → `send_screen_to_leds.py`

- 🎨 **Queres fazer um desenho custom e mandar para a mesa?**  
  Unity → `Mesa de Leds Paint` → `Mesa_de_Leds_Paint_2.exe`

---

## 🐍 Como correr scripts Python

Corre como quiseres — pessoalmente prefiro **PyCharm**, mas com **Python 3** e companhia também funciona para os cracudos de Linux.

---

## 🎮 Como correr o projeto Unity

Dá **duplo clique** no executável, pinta o que quiseres e carrega em **Deploy**.
