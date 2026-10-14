/* =====================================================================
 *  CardioIA - Fase 3 - Monitoramento Continuo (IoT no Peito do Paciente)
 *  Grupo Purkinje - FIAP - Turma 2TIAOR-2026
 *
 *  config.h - parametros de identidade, rede, clinica e resiliencia.
 *
 *  Todo valor ajustavel do projeto esta reunido aqui de proposito: o
 *  firmware em cardioia_wearable.ino nao contem numeros magicos. Isso
 *  permite auditar as decisoes clinicas (limiares de alerta) e as
 *  decisoes de engenharia (dimensionamento do buffer) sem ler o codigo
 *  de controle, o que e um requisito pratico em dispositivos medicos.
 * ===================================================================== */

#ifndef CONFIG_H
#define CONFIG_H

/* ---------------------------------------------------------------------
 * 1. IDENTIDADE DO PACIENTE E DO DISPOSITIVO
 * ---------------------------------------------------------------------
 * O identificador segue exatamente a chave usada nas Fases 1 e 2 do
 * CardioIA (formato CARD-####). O paciente CARD-0056 foi escolhido por
 * ser, no dataset da Fase 1, um caso de alto risco cardiovascular, e por
 * ser o mesmo relato que o extrator de sintomas da Fase 2 classificou
 * como triagem de risco ALTO. O wearable desta fase, portanto, monitora
 * um paciente que o proprio projeto ja havia sinalizado - as tres fases
 * se ligam pela mesma chave primaria.
 */
#define ID_PACIENTE        "CARD-0056"
#define ID_DISPOSITIVO     "PURKINJE-WEAR-01"
#define VERSAO_FIRMWARE    "3.1.0"

/* ---------------------------------------------------------------------
 * 2. MAPEAMENTO DE PINOS (ESP32 DevKit v1)
 * --------------------------------------------------------------------- */
#define PINO_DHT           15   // DHT22: temperatura + umidade (sensor 1)
#define PINO_BTN_PULSO      4   // Pushbutton: simula o pulso arterial
#define PINO_BTN_ENLACE     5   // Pushbutton: liga/desliga o enlace simulado
#define PINO_LED_ALERTA    18   // LED vermelho: alerta clinico ativo
#define PINO_LED_ONLINE    19   // LED verde: enlace com a nuvem estabelecido
/* O MPU6050 (sensor 2, acelerometro) usa o barramento I2C padrao:
 * SDA = GPIO 21, SCL = GPIO 22. Nao precisa de #define. */

/* ---------------------------------------------------------------------
 * 3. REDE E BROKER MQTT
 * ---------------------------------------------------------------------
 * Wokwi-GUEST e a rede virtual aberta do simulador Wokwi (sem senha).
 * Em hardware real, troque pelo SSID e senha da rede do paciente.
 */
#define WIFI_SSID          "Wokwi-GUEST"
#define WIFI_SENHA         ""
#define WIFI_CANAL         6     // acelera a associacao no Wokwi

/* Broker publico do HiveMQ: nao exige cadastro, o que torna o projeto
 * reproduzivel por qualquer avaliador sem criar conta. Para usar o
 * HiveMQ Cloud com TLS e autenticacao, veja a secao 3.4 do relatorio da
 * Parte 2 e defina USAR_TLS como 1. */
#define MQTT_HOST          "broker.hivemq.com"
#define MQTT_PORTA         1883
#define USAR_TLS           0
#define MQTT_USUARIO       ""
#define MQTT_SENHA         ""

/* O prefixo inclui o nome do grupo para evitar colisao de topicos com
 * outros grupos da turma, ja que o broker publico e compartilhado. */
#define TOPICO_BASE        "cardioia/purkinje/" ID_PACIENTE

#define TOPICO_TELEMETRIA  TOPICO_BASE "/telemetria"  // amostras ao vivo
#define TOPICO_HISTORICO   TOPICO_BASE "/historico"   // backlog sincronizado
#define TOPICO_ALERTA      TOPICO_BASE "/alerta"      // eventos clinicos
#define TOPICO_STATUS      TOPICO_BASE "/status"      // online/offline (LWT)

#define MQTT_KEEPALIVE     30    // segundos

/* Atencao a uma limitacao real da biblioteca: o PubSubClient publica
 * sempre em QoS 0. Este valor e aplicado a assinatura e a mensagem de
 * Last Will, que a biblioteca suporta. A garantia de "ao menos uma
 * entrega" para a telemetria e obtida na camada de aplicacao: quando
 * mqtt.publish() devolve falso, a amostra volta para o buffer e e
 * reenviada no ciclo seguinte (ver loop() e sincronizar()). */
#define MQTT_QOS           1

/* ---------------------------------------------------------------------
 * 4. CADENCIA DE AMOSTRAGEM (degradacao graciosa)
 * ---------------------------------------------------------------------
 * Online, amostramos a cada 5 s. Offline, reduzimos para 15 s. A troca
 * nao e economia de energia: e extensao de autonomia do buffer. Com a
 * mesma memoria, triplicamos a janela de tempo que conseguimos cobrir
 * sem conexao, ao custo de uma resolucao temporal menor - aceitavel
 * porque a histerese de alerta (secao 6) continua operando em cima de
 * amostras consecutivas, nao de um intervalo fixo em segundos.
 */
#define INTERVALO_ONLINE_MS    5000UL
#define INTERVALO_OFFLINE_MS  15000UL

/* ---------------------------------------------------------------------
 * 5. DIMENSIONAMENTO DO BUFFER DE RESILIENCIA
 * ---------------------------------------------------------------------
 * Estrategia: dois buffers circulares separados por prioridade clinica.
 *
 *   buf_rotina  -> amostras normais. Em overflow, descarta a mais antiga.
 *   buf_critico -> amostras em alerta. So sobrescreve apos encher.
 *
 * A razao de separar e simples e defensavel: num buffer circular unico,
 * um periodo longo offline apagaria justamente o episodio de taquicardia
 * que motivou o monitoramento, porque ele seria o dado mais antigo. O
 * evento clinico e o dado de maior valor e precisa de garantia propria.
 *
 * Dimensionamento (ver analise/dimensionar_buffer.py):
 *   2880 amostras x 12 bytes = 34,6 KB -> ~6,6% da SRAM de 520 KB do ESP32
 *   2880 amostras x 15 s (cadencia offline) = 43.200 s = 12 horas
 *
 * Doze horas cobrem o cenario de negocio alvo: monitoramento domiciliar,
 * em que a falha de conectividade tipica e uma queda de energia ou de
 * link residencial resolvida dentro de um turno. Passado esse limite, o
 * dispositivo preserva os 480 registros criticos (2 h de evento continuo)
 * e sacrifica a rotina, que tem valor epidemiologico, nao diagnostico.
 */
#define CAPACIDADE_ROTINA   2400
#define CAPACIDADE_CRITICO   480

/* Quantas amostras enviar por ciclo durante a sincronizacao. Enviar o
 * backlog inteiro de uma vez bloquearia o loop e estouraria o keepalive
 * do MQTT, derrubando a conexao justamente quando ela acabou de voltar. */
#define LOTE_SINCRONIZACAO    20

/* ---------------------------------------------------------------------
 * 6. LIMIARES CLINICOS E HISTERESE
 * ---------------------------------------------------------------------
 * Os limiares de frequencia cardiaca seguem as faixas usuais de triagem
 * em adulto. A histerese exige que a condicao se mantenha por N amostras
 * consecutivas antes de disparar: um unico batimento mal lido pelo
 * sensor nao pode acionar um alerta medico. Esse filtro roda no proprio
 * dispositivo - e o nucleo do argumento de Edge Computing desta fase,
 * porque significa que o alerta nao depende da nuvem estar acessivel.
 */
#define FC_TAQUICARDIA       120   // bpm
#define FC_BRADICARDIA        50   // bpm
#define TEMP_FEBRE          38.0   // graus Celsius
#define TEMP_HIPOTERMIA     35.0   // graus Celsius
#define AMOSTRAS_HISTERESE     3   // confirmacoes consecutivas

/* Acelerometro: magnitude em mili-g, descontada a gravidade. */
#define MOV_IMPACTO_MG      2500   // pico compativel com queda
#define MOV_REPOUSO_MG        60   // abaixo disso, consideramos imobilidade
#define IMOBILIDADE_AMOSTRAS  40   // 40 x 15 s = 10 min parado

/* Se nenhum pulso chegar nesse intervalo, tratamos como PERDA DE SINAL
 * (eletrodo solto), nao como bradicardia. Distinguir falha de sensor de
 * evento clinico evita o alarme falso que leva equipes a ignorar o
 * monitor - a chamada fadiga de alarme. */
#define TIMEOUT_PULSO_MS    4000UL

/* ---------------------------------------------------------------------
 * 7. ARMAZENAMENTO PERSISTENTE (opcional, apenas em chip real)
 * ---------------------------------------------------------------------
 * O SPIFFS e volatil no Wokwi: o enunciado reconhece isso e nao computa
 * o item. O codigo esta implementado e compilado condicionalmente, de
 * modo que o mesmo firmware grave em /cardioia.csv quando carregado num
 * ESP32 fisico. Defina como 1 antes de gravar no hardware.
 */
#define USAR_SPIFFS            0
#define ARQUIVO_SPIFFS       "/cardioia.csv"

#endif  // CONFIG_H
