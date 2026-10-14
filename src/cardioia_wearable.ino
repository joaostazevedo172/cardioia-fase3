/* =====================================================================
 *  CardioIA - Fase 3 - Monitoramento Continuo (IoT no Peito do Paciente)
 *  Grupo Purkinje - FIAP - Turma 2TIAOR-2026
 *
 *  cardioia_wearable.ino
 *
 *  Simula um dispositivo vestivel de monitoramento cardiologico que:
 *    1. le sinais vitais de dois sensores distintos (DHT22 e MPU6050)
 *       mais um pulso arterial simulado por pushbutton;
 *    2. decide localmente, sem a nuvem, se existe um evento clinico;
 *    3. sobrevive a quedas de conectividade guardando as amostras em um
 *       buffer circular separado por prioridade clinica;
 *    4. sincroniza o backlog quando o enlace volta, criticos primeiro;
 *    5. publica tudo via MQTT para o dashboard em Node-RED.
 *
 *  FLUXO RESUMIDO
 *
 *      [DHT22]---+
 *      [MPU6050]-+--> amostrar() --> avaliar() --> enlace ativo?
 *      [BOTAO]---+                                  |        |
 *                                                  sim      nao
 *                                                   |        |
 *                                          publicar_mqtt  bufferizar
 *                                                   |        |
 *                                                   |   (volta o enlace)
 *                                                   |        |
 *                                                   +<-- sincronizar
 *
 *  O enlace e uma variavel booleana (`enlace_ativo`), como pede o
 *  enunciado, controlada pelo botao do GPIO 5. Isso permite demonstrar a
 *  resiliencia offline no simulador sem derrubar o Wi-Fi de verdade.
 * ===================================================================== */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "config.h"
#include "tipos.h"

#if USAR_SPIFFS
  #include <SPIFFS.h>
#endif

/* =====================================================================
 *  APOIO AOS TIPOS
 * ---------------------------------------------------------------------
 *  As estruturas (Motivo, Amostra, BufferCircular) ficam em tipos.h, e
 *  nao aqui, por uma exigencia do pre-processador do Arduino: ele gera
 *  os prototipos das funcoes do sketch e os insere logo apos os
 *  #include, antes de qualquer definicao feita no corpo do .ino. Um
 *  prototipo que menciona BufferCircular seria emitido antes da struct
 *  existir. O cabecalho resolve. Ver o comentario em tipos.h.
 * ===================================================================== */

const char* nome_motivo(uint8_t m) {
  switch (m) {
    case M_TAQUICARDIA:   return "TAQUICARDIA";
    case M_BRADICARDIA:   return "BRADICARDIA";
    case M_FEBRE:         return "FEBRE";
    case M_HIPOTERMIA:    return "HIPOTERMIA";
    case M_QUEDA:         return "QUEDA";
    case M_IMOBILIDADE:   return "IMOBILIDADE";
    case M_SINAL_AUSENTE: return "SINAL_AUSENTE";
    default:              return "NORMAL";
  }
}

/* Um alerta clinico exige acao. A perda de sinal e uma falha tecnica:
 * registramos, mas nao acendemos o LED vermelho nem priorizamos no
 * buffer. Confundir as duas coisas e o que produz fadiga de alarme. */
bool e_alerta_clinico(uint8_t m) {
  return m != M_NORMAL && m != M_SINAL_AUSENTE;
}

/* =====================================================================
 *  ESTADO GLOBAL
 * ===================================================================== */

DHT dht(PINO_DHT, DHT22);
Adafruit_MPU6050 mpu;
bool mpu_ok = false;

#if USAR_TLS
  #include <WiFiClientSecure.h>
  WiFiClientSecure net;
#else
  WiFiClient net;
#endif
PubSubClient mqtt(net);

/* Os arrays sao estaticos: alocacao dinamica em dispositivo embarcado de
 * longa duracao fragmenta a heap e acaba falhando dias depois do deploy,
 * num momento em que ninguem esta olhando. */
static Amostra memoria_rotina[CAPACIDADE_ROTINA];
static Amostra memoria_critico[CAPACIDADE_CRITICO];

BufferCircular buf_rotina  = { memoria_rotina,  CAPACIDADE_ROTINA,  0, 0, 0 };
BufferCircular buf_critico = { memoria_critico, CAPACIDADE_CRITICO, 0, 0, 0 };

/* Enlace simulado. Comeca ativo; o botao do GPIO 5 inverte. */
volatile bool enlace_ativo = true;
volatile bool enlace_mudou = false;

/* Pulso arterial simulado: a ISR registra os intervalos entre toques. */
volatile uint32_t ultimo_pulso_ms = 0;
volatile uint32_t intervalos_ms[4] = { 0, 0, 0, 0 };
volatile uint8_t  idx_intervalo = 0;

/* Contadores de histerese - um por condicao monitorada. */
uint8_t  cnt_taqui = 0, cnt_bradi = 0, cnt_febre = 0, cnt_hipo = 0;
uint16_t cnt_imovel = 0;

uint32_t proxima_amostra_ms = 0;
uint8_t  ultimo_motivo_publicado = M_NORMAL;
uint32_t total_amostras = 0;
uint32_t total_publicadas = 0;

char payload[256];

/* =====================================================================
 *  INTERRUPCOES
 * ===================================================================== */

void IRAM_ATTR isr_pulso() {
  uint32_t agora = millis();
  /* 120 ms de debounce. Tambem funciona como teto fisiologico: nenhum
   * coracao humano passa de 500 bpm, entao toques mais rapidos que isso
   * sao ruido mecanico do botao, nao batimento. */
  if (agora - ultimo_pulso_ms < 120) return;
  if (ultimo_pulso_ms != 0) {
    intervalos_ms[idx_intervalo] = agora - ultimo_pulso_ms;
    idx_intervalo = (idx_intervalo + 1) % 4;
  }
  ultimo_pulso_ms = agora;
}

void IRAM_ATTR isr_enlace() {
  static uint32_t ultimo = 0;
  uint32_t agora = millis();
  if (agora - ultimo < 300) return;   // debounce mais folgado: toque humano
  ultimo = agora;
  enlace_ativo = !enlace_ativo;
  enlace_mudou = true;
}

/* =====================================================================
 *  BUFFER CIRCULAR
 * ===================================================================== */

bool buffer_cheio(const BufferCircular& b) {
  return b.qtd >= b.capacidade;
}

/* Grava uma amostra. Se o buffer estiver cheio, sobrescreve a mais
 * antiga e contabiliza o descarte - nunca recusa a gravacao, porque
 * parar de coletar seria pior que perder o historico mais velho. */
void buffer_push(BufferCircular& b, const Amostra& a) {
  if (buffer_cheio(b)) {
    b.inicio = (b.inicio + 1) % b.capacidade;
    b.qtd--;
    b.descartadas++;
  }
  uint16_t pos = (b.inicio + b.qtd) % b.capacidade;
  b.dados[pos] = a;
  b.qtd++;
}

bool buffer_pop(BufferCircular& b, Amostra& destino) {
  if (b.qtd == 0) return false;
  destino = b.dados[b.inicio];
  b.inicio = (b.inicio + 1) % b.capacidade;
  b.qtd--;
  return true;
}

uint16_t backlog_total() {
  return buf_rotina.qtd + buf_critico.qtd;
}

/* =====================================================================
 *  LEITURA DOS SENSORES
 * ===================================================================== */

/* Converte os intervalos entre toques em bpm. Usa a media dos ultimos
 * quatro intervalos: um unico intervalo oscila demais com a mao humana,
 * e uma janela maior demoraria a reagir a uma taquicardia. */
uint16_t ler_bpm() {
  noInterrupts();
  uint32_t ult = ultimo_pulso_ms;
  uint32_t copia[4];
  for (uint8_t i = 0; i < 4; i++) copia[i] = intervalos_ms[i];
  interrupts();

  if (ult == 0 || (millis() - ult) > TIMEOUT_PULSO_MS) return 0;  // sem sinal

  uint32_t soma = 0;
  uint8_t  n = 0;
  for (uint8_t i = 0; i < 4; i++) {
    if (copia[i] > 0) { soma += copia[i]; n++; }
  }
  if (n == 0) return 0;

  uint32_t media = soma / n;
  if (media == 0) return 0;
  uint32_t bpm = 60000UL / media;
  return (uint16_t)(bpm > 300 ? 300 : bpm);
}

/* Magnitude do vetor de aceleracao, menos a gravidade, em mili-g.
 * Em repouso o resultado fica proximo de zero; um impacto gera centenas
 * ou milhares. Sem o MPU presente, devolvemos 0 e o projeto segue
 * funcionando com os demais sensores - degradacao parcial, nao falha. */
uint16_t ler_movimento() {
  if (!mpu_ok) return 0;
  sensors_event_t acc, giro, temp;
  mpu.getEvent(&acc, &giro, &temp);
  float mod = sqrt(acc.acceleration.x * acc.acceleration.x +
                   acc.acceleration.y * acc.acceleration.y +
                   acc.acceleration.z * acc.acceleration.z);
  float delta = fabs(mod - 9.80665f);           // remove a gravidade
  float mg = (delta / 9.80665f) * 1000.0f;      // m/s2 -> mili-g
  if (mg > 65535.0f) mg = 65535.0f;
  return (uint16_t)mg;
}

/* =====================================================================
 *  AVALIACAO CLINICA (Edge Computing)
 * ---------------------------------------------------------------------
 *  Toda a decisao acontece aqui, dentro do dispositivo. Se a nuvem cair,
 *  o alerta continua sendo detectado, o LED continua acendendo e a
 *  amostra continua entrando na fila prioritaria. A nuvem e o canal de
 *  notificacao, nao o cerebro do sistema - essa e a diferenca entre um
 *  wearable medico e um sensor burro conectado.
 * ===================================================================== */
uint8_t avaliar(uint16_t bpm, float temp_c, uint16_t mov_mg) {

  /* Impacto nao tem histerese: uma queda e um evento unico e nao se
   * repete na amostra seguinte. Esperar confirmacao perderia o evento. */
  if (mov_mg >= MOV_IMPACTO_MG) {
    cnt_imovel = 0;
    return M_QUEDA;
  }

  bool sinal_ok = (bpm > 0);

  /* As demais condicoes exigem AMOSTRAS_HISTERESE confirmacoes seguidas.
   * O contador zera assim que a condicao deixa de valer, de modo que
   * leituras alternadas nunca acumulam ate o limiar. */
  cnt_taqui = (sinal_ok && bpm > FC_TAQUICARDIA) ? cnt_taqui + 1 : 0;
  cnt_bradi = (sinal_ok && bpm < FC_BRADICARDIA) ? cnt_bradi + 1 : 0;
  cnt_febre = (temp_c > TEMP_FEBRE)              ? cnt_febre + 1 : 0;
  cnt_hipo  = (temp_c < TEMP_HIPOTERMIA)         ? cnt_hipo  + 1 : 0;

  cnt_imovel = (mov_mg < MOV_REPOUSO_MG) ? cnt_imovel + 1 : 0;

  /* Ordem de precedencia por gravidade: um paciente taquicardico E
   * febril recebe o rotulo cardiaco, que e o que define a conduta. */
  if (cnt_taqui >= AMOSTRAS_HISTERESE) return M_TAQUICARDIA;
  if (cnt_bradi >= AMOSTRAS_HISTERESE) return M_BRADICARDIA;
  if (cnt_febre >= AMOSTRAS_HISTERESE) return M_FEBRE;
  if (cnt_hipo  >= AMOSTRAS_HISTERESE) return M_HIPOTERMIA;

  /* Imobilidade so vira alerta se vier acompanhada de alteracao do ritmo.
   * Paciente parado com ritmo normal esta dormindo, nao desmaiado. */
  if (cnt_imovel >= IMOBILIDADE_AMOSTRAS && sinal_ok &&
      (bpm > FC_TAQUICARDIA || bpm < FC_BRADICARDIA)) {
    return M_IMOBILIDADE;
  }

  if (!sinal_ok) return M_SINAL_AUSENTE;
  return M_NORMAL;
}

/* =====================================================================
 *  SAIDA SERIAL (entregavel da Parte 1)
 * ===================================================================== */
void imprimir_serial(const Amostra& a, const char* destino) {
  char linha[160];
  snprintf(linha, sizeof(linha),
           "[%6lus] %-7s | FC %3u bpm | T %5.1f C | UR %2u%% | MOV %5u mg | %-13s | fila %u",
           (unsigned long)a.t_s,
           destino,
           a.bpm,
           a.temp_c10 / 10.0,
           a.umid,
           a.mov_mg,
           nome_motivo(a.motivo),
           backlog_total());
  Serial.println(linha);
}

/* =====================================================================
 *  MQTT
 * ===================================================================== */

void conectar_wifi() {
  Serial.printf("[WIFI] conectando em %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_SENHA, WIFI_CANAL);
  uint8_t tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 40) {
    delay(250);
    Serial.print(".");
    tentativas++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] ok - IP %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WIFI] falhou - seguindo em modo offline");
  }
}

/* O Last Will and Testament e publicado pelo proprio broker caso o
 * dispositivo pare de responder sem se despedir. Num monitor cardiaco
 * isso importa: o dashboard precisa distinguir "paciente sem alteracoes"
 * de "parei de receber dados do paciente". Sem LWT, as duas situacoes
 * parecem iguais na tela, e a segunda e uma emergencia. */
bool conectar_mqtt() {
  if (WiFi.status() != WL_CONNECTED) return false;
  if (mqtt.connected()) return true;

  char id_cliente[48];
  snprintf(id_cliente, sizeof(id_cliente), "%s-%04X", ID_DISPOSITIVO,
           (uint16_t)(ESP.getEfuseMac() & 0xFFFF));

  Serial.print("[MQTT] conectando ao broker... ");
  bool ok;
  if (strlen(MQTT_USUARIO) > 0) {
    ok = mqtt.connect(id_cliente, MQTT_USUARIO, MQTT_SENHA,
                      TOPICO_STATUS, MQTT_QOS, true, "{\"estado\":\"offline\"}");
  } else {
    ok = mqtt.connect(id_cliente, TOPICO_STATUS, MQTT_QOS, true,
                      "{\"estado\":\"offline\"}");
  }

  if (ok) {
    Serial.println("ok");
    /* Retained: quem abrir o dashboard depois ja encontra o estado. */
    char online[160];
    snprintf(online, sizeof(online),
             "{\"estado\":\"online\",\"disp\":\"%s\",\"pac\":\"%s\",\"fw\":\"%s\"}",
             ID_DISPOSITIVO, ID_PACIENTE, VERSAO_FIRMWARE);
    mqtt.publish(TOPICO_STATUS, online, true);
  } else {
    Serial.printf("falhou (rc=%d)\n", mqtt.state());
  }
  return ok;
}

/* Monta o JSON e publica. `origem` distingue a amostra ao vivo da que
 * veio do backlog, para que o dashboard nao confunda dado historico
 * sincronizado com leitura do instante atual. */
bool publicar(const Amostra& a, const char* origem) {
  snprintf(payload, sizeof(payload),
           "{\"disp\":\"%s\",\"pac\":\"%s\",\"t\":%lu,\"bpm\":%u,"
           "\"temp\":%.1f,\"umid\":%u,\"mov\":%u,"
           "\"alerta\":%s,\"motivo\":\"%s\",\"origem\":\"%s\","
           "\"backlog\":%u,\"perdidas\":%lu}",
           ID_DISPOSITIVO, ID_PACIENTE,
           (unsigned long)a.t_s, a.bpm,
           a.temp_c10 / 10.0, a.umid, a.mov_mg,
           e_alerta_clinico(a.motivo) ? "true" : "false",
           nome_motivo(a.motivo), origem,
           backlog_total(),
           (unsigned long)(buf_rotina.descartadas + buf_critico.descartadas));

  const char* topico = (strcmp(origem, "historico") == 0)
                       ? TOPICO_HISTORICO : TOPICO_TELEMETRIA;

  bool ok = mqtt.publish(topico, payload);

  /* Alertas vao tambem para um topico proprio, para que a automacao de
   * notificacao assine so o que exige acao em vez de filtrar o fluxo
   * inteiro. Reduz trafego e simplifica o Ir Alem 1 desta fase. */
  if (ok && e_alerta_clinico(a.motivo)) {
    mqtt.publish(TOPICO_ALERTA, payload);
  }
  if (ok) total_publicadas++;
  return ok;
}

/* =====================================================================
 *  SINCRONIZACAO DO BACKLOG
 * ---------------------------------------------------------------------
 *  Criticos primeiro, em lotes. Se a publicacao falhar no meio, a
 *  amostra e devolvida ao buffer e a sincronizacao recomeca no proximo
 *  ciclo: nenhum registro e descartado por falha de rede.
 * ===================================================================== */
void sincronizar() {
  if (backlog_total() == 0) return;

  Serial.printf("[SYNC] enlace restabelecido - %u criticas, %u de rotina\n",
                buf_critico.qtd, buf_rotina.qtd);

  uint16_t enviadas = 0;
  Amostra a;

  while (enviadas < LOTE_SINCRONIZACAO && buf_critico.qtd > 0) {
    if (!buffer_pop(buf_critico, a)) break;
    if (!publicar(a, "historico")) { buffer_push(buf_critico, a); return; }
    imprimir_serial(a, "SYNC-C");
    enviadas++;
    mqtt.loop();
  }

  while (enviadas < LOTE_SINCRONIZACAO && buf_rotina.qtd > 0) {
    if (!buffer_pop(buf_rotina, a)) break;
    if (!publicar(a, "historico")) { buffer_push(buf_rotina, a); return; }
    imprimir_serial(a, "SYNC-R");
    enviadas++;
    mqtt.loop();
  }

#if USAR_SPIFFS
  /* Backlog zerado significa que tudo chegou a nuvem: o arquivo local
   * perdeu a funcao e e apagado, como pede o enunciado da Parte 1. */
  if (backlog_total() == 0 && SPIFFS.exists(ARQUIVO_SPIFFS)) {
    SPIFFS.remove(ARQUIVO_SPIFFS);
    Serial.println("[SPIFFS] backlog sincronizado - arquivo local removido");
  }
#endif
}

#if USAR_SPIFFS
void gravar_spiffs(const Amostra& a) {
  File f = SPIFFS.open(ARQUIVO_SPIFFS, FILE_APPEND);
  if (!f) return;
  f.printf("%lu,%u,%.1f,%u,%u,%s\n", (unsigned long)a.t_s, a.bpm,
           a.temp_c10 / 10.0, a.umid, a.mov_mg, nome_motivo(a.motivo));
  f.close();
}
#endif

/* =====================================================================
 *  SETUP
 * ===================================================================== */
void setup() {
  Serial.begin(115200);
  delay(300);

  Serial.println();
  Serial.println("=====================================================");
  Serial.println(" CardioIA - Fase 3 - Wearable de monitoramento");
  Serial.println(" Grupo Purkinje - FIAP 2TIAOR-2026");
  Serial.printf (" Paciente %s | Dispositivo %s | FW %s\n",
                 ID_PACIENTE, ID_DISPOSITIVO, VERSAO_FIRMWARE);
  Serial.printf (" Buffer: %u rotina + %u criticas = %u amostras (%.1f KB)\n",
                 CAPACIDADE_ROTINA, CAPACIDADE_CRITICO,
                 CAPACIDADE_ROTINA + CAPACIDADE_CRITICO,
                 (CAPACIDADE_ROTINA + CAPACIDADE_CRITICO) *
                 sizeof(Amostra) / 1024.0);
  Serial.printf (" Autonomia offline: %.1f h a %lu s por amostra\n",
                 (CAPACIDADE_ROTINA + CAPACIDADE_CRITICO) *
                 (INTERVALO_OFFLINE_MS / 1000.0) / 3600.0,
                 INTERVALO_OFFLINE_MS / 1000UL);
  Serial.println("=====================================================");

  pinMode(PINO_LED_ALERTA, OUTPUT);
  pinMode(PINO_LED_ONLINE, OUTPUT);
  pinMode(PINO_BTN_PULSO,  INPUT_PULLUP);
  pinMode(PINO_BTN_ENLACE, INPUT_PULLUP);

  /* FALLING porque os botoes usam pull-up interno: o pino cai para GND
   * quando pressionado. */
  attachInterrupt(digitalPinToInterrupt(PINO_BTN_PULSO),  isr_pulso,  FALLING);
  attachInterrupt(digitalPinToInterrupt(PINO_BTN_ENLACE), isr_enlace, FALLING);

  dht.begin();
  Serial.println("[DHT22] inicializado no GPIO 15");

  if (mpu.begin()) {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    mpu_ok = true;
    Serial.println("[MPU6050] inicializado no barramento I2C");
  } else {
    Serial.println("[MPU6050] nao encontrado - movimento desabilitado");
  }

#if USAR_SPIFFS
  if (SPIFFS.begin(true)) Serial.println("[SPIFFS] montado");
  else                    Serial.println("[SPIFFS] falha ao montar");
#endif

  conectar_wifi();
#if USAR_TLS
  net.setInsecure();   // em producao, fixar o certificado do broker
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORTA);
  mqtt.setKeepAlive(MQTT_KEEPALIVE);
  mqtt.setBufferSize(512);
  conectar_mqtt();

  Serial.println();
  Serial.println(">>> Botao GPIO 4  = pulso arterial (toque no ritmo desejado)");
  Serial.println(">>> Botao GPIO 5  = liga/desliga o enlace simulado");
  Serial.println();

  proxima_amostra_ms = millis();
}

/* =====================================================================
 *  LOOP
 * ===================================================================== */
void loop() {
  mqtt.loop();

  /* --- troca de estado do enlace ------------------------------------ */
  if (enlace_mudou) {
    enlace_mudou = false;
    if (enlace_ativo) {
      Serial.println("\n*** ENLACE RESTABELECIDO ***");
      conectar_mqtt();
    } else {
      Serial.printf("\n*** ENLACE PERDIDO - bufferizando a cada %lu s ***\n",
                    INTERVALO_OFFLINE_MS / 1000UL);
    }
  }

  bool online = enlace_ativo && (WiFi.status() == WL_CONNECTED);
  if (online && !mqtt.connected()) online = conectar_mqtt();
  digitalWrite(PINO_LED_ONLINE, online ? HIGH : LOW);

  /* --- amostragem na cadencia vigente ------------------------------- */
  uint32_t intervalo = online ? INTERVALO_ONLINE_MS : INTERVALO_OFFLINE_MS;

  if ((int32_t)(millis() - proxima_amostra_ms) >= 0) {
    proxima_amostra_ms = millis() + intervalo;

    float temp_c = dht.readTemperature();
    float umid   = dht.readHumidity();
    if (isnan(temp_c)) temp_c = 0.0;     // leitura falha nao derruba o ciclo
    if (isnan(umid))   umid   = 0.0;

    Amostra a;
    a.t_s      = millis() / 1000UL;
    a.bpm      = ler_bpm();
    a.temp_c10 = (int16_t)roundf(temp_c * 10.0);
    a.umid     = (uint8_t)roundf(umid);
    a.mov_mg   = ler_movimento();
    a.motivo   = avaliar(a.bpm, temp_c, a.mov_mg);

    total_amostras++;
    digitalWrite(PINO_LED_ALERTA, e_alerta_clinico(a.motivo) ? HIGH : LOW);

    /* O alerta e anunciado no Serial sempre que muda de estado, online
     * ou offline. Essa e a prova de que a deteccao mora na borda. */
    if (a.motivo != ultimo_motivo_publicado) {
      if (e_alerta_clinico(a.motivo)) {
        Serial.printf(">>> ALERTA CLINICO NA BORDA: %s (FC %u bpm, T %.1f C)\n",
                      nome_motivo(a.motivo), a.bpm, temp_c);
      } else if (e_alerta_clinico(ultimo_motivo_publicado)) {
        Serial.println(">>> alerta encerrado - sinais dentro da faixa");
      }
      ultimo_motivo_publicado = a.motivo;
    }

#if USAR_SPIFFS
    gravar_spiffs(a);
#endif

    if (online) {
      if (publicar(a, "live")) imprimir_serial(a, "ENVIO");
      else {
        /* Publicacao falhou mesmo com enlace: trata como offline. */
        e_alerta_clinico(a.motivo) ? buffer_push(buf_critico, a)
                                   : buffer_push(buf_rotina, a);
        imprimir_serial(a, "BUFFER");
      }
    } else {
      e_alerta_clinico(a.motivo) ? buffer_push(buf_critico, a)
                                 : buffer_push(buf_rotina, a);
      imprimir_serial(a, "BUFFER");

      if (buffer_cheio(buf_rotina) && buf_rotina.descartadas % 100 == 1) {
        Serial.printf("[AVISO] buffer de rotina saturado - %lu amostras "
                      "antigas descartadas (criticas preservadas: %u)\n",
                      (unsigned long)buf_rotina.descartadas, buf_critico.qtd);
      }
    }
  }

  /* --- drenagem do backlog ------------------------------------------ */
  if (online && mqtt.connected() && backlog_total() > 0) {
    sincronizar();
  }

  delay(10);
}
