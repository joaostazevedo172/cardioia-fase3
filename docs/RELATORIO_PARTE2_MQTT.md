# Relatório — Parte 2
## Transmissão para a nuvem e visualização (Fog / Cloud Computing)

**Projeto:** CardioIA — Fase 3 — Monitoramento Contínuo
**Grupo:** Purkinje — FIAP — Turma 2TIAOR-2026
**Paciente monitorado:** CARD-0056 — **Dispositivo:** PURKINJE-WEAR-01 — **Firmware:** 3.1.0

---

## 1. Visão geral da arquitetura

A Parte 2 completa o ciclo de dados em IoT aplicado à saúde: **captura → processamento → transmissão → visualização → alerta**. A Parte 1 resolveu as duas primeiras etapas dentro do dispositivo; esta resolve as três seguintes, distribuindo responsabilidades em três camadas.

```
  CAMADA DE BORDA (Edge)              CAMADA DE NÉVOA/NUVEM (Fog/Cloud)
  ──────────────────────              ─────────────────────────────────
   ESP32 + DHT22 + MPU6050
   • amostragem adaptativa
   • avaliação clínica           MQTT        broker.hivemq.com
   • buffer prioritário      ──────────►    (TCP 1883 / TLS 8883)
   • LED de alerta local                            │
                                                    │ assinatura
                                                    ▼
                                           Node-RED (Fog)
                                           • normalização
                                           • roteamento
                                           • memória de eventos
                                                    │
                                                    ▼
                                           Dashboard (HTTP)
                                           gráfico · gauges · LED · tabela
```

A divisão não é cosmética. O alerta clínico é decidido na **borda**, porque não pode depender de conectividade. A agregação, o roteamento e a memória de curto prazo ficam na **névoa** (Node-RED), que é onde há CPU e disco sobrando e onde a lógica pode ser alterada sem reprogramar o dispositivo. A **nuvem** (broker) é apenas o transporte desacoplado. Essa separação é o que permite que o sistema continue clinicamente útil durante uma falha de rede, em vez de simplesmente parar.

## 2. Por que MQTT

O protocolo foi escolhido por três características que importam neste cenário:

**Publish/subscribe desacoplado.** O ESP32 não conhece o Node-RED, e o Node-RED não conhece o ESP32 — ambos conhecem apenas tópicos. Acrescentar um segundo assinante (a automação de e-mail do Ir Além 1, por exemplo, ou um painel na central médica) não exige alterar o firmware. Em telemetria médica isso é decisivo, porque atualizar firmware de dispositivo implantado é caro e arriscado.

**Payload leve sobre TCP persistente.** Cada amostra ocupa cerca de 200 bytes de JSON. HTTP exigiria reabrir conexão e carregar cabeçalhos a cada envio — num dispositivo que publica a cada 5 segundos por meses, o custo em energia e em dados móveis é proibitivo.

**Last Will e retenção.** O MQTT oferece garantias que o sistema precisa e que o HTTP simples não dá de graça, descritas a seguir.

## 3. Projeto dos tópicos e do payload

### 3.1 Hierarquia de tópicos

```
cardioia/purkinje/CARD-0056/telemetria   amostras ao vivo
cardioia/purkinje/CARD-0056/historico    backlog sincronizado após queda
cardioia/purkinje/CARD-0056/alerta       apenas eventos clínicos
cardioia/purkinje/CARD-0056/status       online/offline (retida + LWT)
```

O prefixo inclui o nome do grupo porque o broker público é compartilhado — sem ele, dois grupos da turma publicariam no mesmo tópico e um veria os dados do outro. O terceiro nível é o `id_paciente`, a mesma chave das Fases 1 e 2, o que torna a hierarquia extensível: acrescentar um segundo paciente é acrescentar um ramo, não reescrever o esquema.

Separar `telemetria` de `historico` resolve um problema real. Quando o enlace volta, o dispositivo despeja centenas de amostras antigas. Se elas chegassem pelo mesmo tópico da telemetria ao vivo, o painel mostraria um valor de duas horas atrás como se fosse a leitura do instante — um erro de interpretação com consequência clínica. Separados, o dashboard trata cada um como merece.

O tópico `alerta` existe para que assinantes interessados apenas em eventos não precisem filtrar o fluxo inteiro. Reduz tráfego e simplifica integrações externas.

### 3.2 Estrutura do payload

```json
{
  "disp": "PURKINJE-WEAR-01",
  "pac": "CARD-0056",
  "t": 1245,
  "bpm": 128,
  "temp": 37.4,
  "umid": 55,
  "mov": 18,
  "alerta": true,
  "motivo": "TAQUICARDIA",
  "origem": "live",
  "backlog": 0,
  "perdidas": 0
}
```

Os campos `backlog` e `perdidas` são observabilidade, não dado clínico: informam quantas amostras ainda aguardam sincronização e quantas o buffer teve de descartar. Perda silenciosa de dado clínico é inaceitável, então o número viaja junto e aparece no painel. O campo `origem` distingue leitura ao vivo de registro sincronizado.

A serialização é feita com `snprintf`, não com ArduinoJson. Para um payload fixo de doze campos, a montagem manual gasta menos memória, elimina uma dependência e é auditável linha a linha — o que em dispositivo médico tem valor próprio.

### 3.3 Qualidade de serviço e Last Will

A garantia desejada é *at least once*: uma amostra duplicada é inofensiva para o painel, enquanto uma perdida não é. Aqui há uma limitação real da biblioteca que vale registrar em vez de esconder — **o PubSubClient publica sempre em QoS 0**. O `MQTT_QOS 1` definido em `config.h` se aplica à assinatura e à mensagem de Last Will, que a biblioteca suporta, mas não à telemetria.

Obtivemos a garantia na **camada de aplicação**. Quando `mqtt.publish()` devolve falso, a amostra não é descartada: ela volta para o buffer de prioridade correspondente e é reenviada no ciclo seguinte, tanto no fluxo ao vivo (`loop()`) quanto na drenagem do backlog (`sincronizar()`). O efeito prático é equivalente a QoS 1 para o que importa — nenhuma amostra se perde por falha de transporte — com a diferença de que a retentativa é nossa e não do protocolo. Migrar para uma biblioteca com QoS 1 nativo (ArduinoMqttClient, por exemplo) simplificaria o código, e é a mudança que faríamos antes de um uso real.

O **Last Will and Testament** é o detalhe mais importante desta seção. Ao conectar, o dispositivo registra no broker a mensagem `{"estado":"offline"}` no tópico de status. Se ele parar de responder sem se despedir — bateria acabada, travamento, paciente fora de alcance — o próprio broker publica essa mensagem. Sem isso, o dashboard não conseguiria distinguir **"paciente sem alterações"** de **"parei de receber dados do paciente"**. As duas situações produzem a mesma tela imóvel, e a segunda é uma emergência silenciosa. A mensagem de `online` é publicada com flag *retained*, de modo que quem abrir o painel depois já encontre o estado corrente sem esperar a próxima amostra.

### 3.4 Broker: público agora, TLS em produção

O firmware aponta por padrão para `broker.hivemq.com:1883`, broker público que não exige cadastro — escolha deliberada para que qualquer avaliador reproduza o projeto sem criar conta. Isso é adequado para o protótipo e **inadequado para dados reais de saúde**: o tópico é legível por qualquer um que o conheça, e dado de saúde é dado pessoal sensível pela LGPD (Art. 5º II e Art. 11), como documentamos na governança da Fase 1.

O caminho para produção já está no código. Basta, em `config.h`:

```c
#define USAR_TLS      1
#define MQTT_HOST     "SEU-CLUSTER.s1.eu.hivemq.cloud"
#define MQTT_PORTA    8883
#define MQTT_USUARIO  "cardioia"
#define MQTT_SENHA    "..."
```

O firmware troca `WiFiClient` por `WiFiClientSecure` e passa credenciais no `connect()`. Em produção real, o `setInsecure()` presente no código deve ser substituído pela fixação do certificado da autoridade do broker — sem isso, o TLS criptografa mas não autentica o servidor, e a conexão fica exposta a interceptação ativa.

## 4. Sincronização do backlog pela rede

Quando o enlace volta, a função `sincronizar()` drena o buffer em **lotes de 20 amostras por ciclo**, chamando `mqtt.loop()` entre envios. O motivo é concreto: despejar 2880 mensagens de uma vez bloquearia o laço principal por dezenas de segundos, estourando o *keepalive* de 30 s e derrubando a conexão justamente no momento em que ela acabou de voltar — um sistema que se autossabota ao se recuperar. Os críticos saem primeiro. Se uma publicação falhar no meio, a amostra é devolvida ao buffer e a sincronização recomeça no ciclo seguinte: nenhum registro é descartado por falha de rede.

## 5. Configuração do dashboard em Node-RED

### 5.1 Nós e encadeamento

O arquivo `nodered/flows.json` é importável diretamente (Menu → Import). O flow tem quatro entradas MQTT e dois nós de função:

| Nó | Tipo | Papel |
|---|---|---|
| `telemetria (ao vivo)` | mqtt in | assina o tópico de telemetria, QoS 1, saída já parseada como JSON |
| `histórico (backlog)` | mqtt in | assina o tópico de sincronização |
| `alerta (eventos)` | mqtt in | assina apenas eventos clínicos |
| `status (LWT)` | mqtt in | assina o estado do dispositivo |
| `normalizar e rotear` | function | valida o payload e distribui em cinco saídas |
| `acumular eventos` | function | mantém as 20 últimas ocorrências em contexto de flow |
| `estado do dispositivo` | function | traduz o LWT em texto para o painel |

A função `normalizar e rotear` concentra a única regra de negócio da camada de névoa: **amostras do backlog não atualizam os medidores**. Elas alimentam apenas o gráfico, que é uma série temporal e sabe onde posicionar o ponto. Um gauge mostrando valor antigo como se fosse atual induziria o profissional ao erro — a mesma preocupação que motivou separar os tópicos.

O histórico de eventos vive no Node-RED, em `flow.context`, e não no dispositivo. A divisão é proposital: a memória do ESP32 serve à resiliência, não à consulta clínica. Quem consulta histórico é a camada que tem disco.

### 5.2 Widgets do painel

| Widget | Tipo | Configuração |
|---|---|---|
| Frequência cardíaca | `ui_chart` linha | 0–300 bpm, janela de 10 min, séries separadas para ao vivo e sincronizado |
| Temperatura corporal | `ui_gauge` | 30–42 °C, segmentos em 35 °C e 38 °C (hipotermia / normal / febre) |
| Umidade relativa | `ui_gauge` | 0–100 %, segmentos em 30 % e 70 % |
| LED virtual de alerta | `ui_template` | círculo que alterna verde/vermelho com halo, mais o motivo e os valores correntes |
| Fila de sincronização | `ui_text` | contador de amostras pendentes |
| Estado do enlace | `ui_text` | ONLINE / OFFLINE alimentado pelo LWT |
| Histórico de eventos | `ui_template` | tabela das 20 últimas ocorrências com hora, motivo, FC, temperatura e origem |

O teto do gráfico é **300 bpm**, e não os 200 de uma faixa fisiológica usual, porque 300 é exatamente o valor em que o firmware satura a leitura (`ler_bpm()`). Um eixo mais curto que o domínio do dado produz linha cortada no topo, e leitura cortada num painel clínico é defeito: o profissional não consegue distinguir "bateu o teto do gráfico" de "bateu o teto do sensor". Fazendo o eixo cobrir exatamente o que o dispositivo é capaz de reportar, nenhum ponto pode cair fora.

Os limiares dos segmentos dos gauges **espelham exatamente** os limiares do firmware (`TEMP_FEBRE 38.0`, `TEMP_HIPOTERMIA 35.0`). Essa coerência é intencional: se o painel desenhasse uma faixa de alerta diferente daquela que o dispositivo usa para decidir, o profissional veria verde na tela enquanto o LED do paciente está vermelho.

O indicador de alerta foi feito com `ui_template` em vez de um nó de LED de terceiros para que o flow dependa **apenas** do `node-red-dashboard`. Menos dependências significa que o avaliador importa e roda sem caçar módulos.

### 5.3 Instalação

Resumido aqui; passo a passo completo em `docs/GUIA_NODE_RED.md`.

```bash
npm install -g --unsafe-perm node-red
node-red
# em outro terminal, ou pelo menu Manage palette:
#   instalar node-red-dashboard
```

Editor em `http://localhost:1880`, painel em `http://localhost:1880/ui`.

## 6. Limites de alerta e a lógica de notificação

| Condição | Limiar | Confirmações | Origem da decisão |
|---|---|---|---|
| Taquicardia | FC > 120 bpm | 3 amostras | borda |
| Bradicardia | FC < 50 bpm | 3 amostras | borda |
| Febre | T > 38,0 °C | 3 amostras | borda |
| Hipotermia | T < 35,0 °C | 3 amostras | borda |
| Queda | impacto > 2500 mg | imediata | borda |
| Imobilidade | < 60 mg por 10 min **e** ritmo alterado | 40 amostras | borda |
| Sinal ausente | sem pulso por 4 s | imediata | borda |
| Dispositivo mudo | sem mensagem no keepalive | — | broker (LWT) |

Todas as decisões clínicas são tomadas na borda; o dashboard **exibe**, não decide. A única condição detectada fora do dispositivo é a última — e ela só pode ser detectada fora, porque um dispositivo que parou não tem como anunciar que parou.

## 7. Eficiência, segurança e boas práticas

**Eficiência.** A cadência adaptativa (5 s online, 15 s offline) reduz em dois terços a taxa de gravação durante a contingência, que é quando a memória é o recurso escasso. O payload compacto e a conexão TCP persistente mantêm o consumo de dados em torno de 3,5 MB por mês por paciente a 5 s — viável até em plano M2M básico.

**Segurança.** O protótipo usa broker público sem autenticação, o que está documentado como limitação e não como decisão de arquitetura. O caminho para TLS com credenciais está implementado e descrito na seção 3.4. O payload não transporta nome, CPF ou data de nascimento: apenas o pseudônimo `CARD-0056`, que só é reidentificável com acesso à base da Fase 1 — pseudonimização coerente com o princípio da necessidade da LGPD.

**Boas práticas.** Alocação estática dos buffers (alocação dinâmica em dispositivo de longa duração fragmenta a heap e falha dias depois do deploy, quando ninguém está olhando); todos os parâmetros clínicos e de rede isolados em `config.h`, sem números mágicos no código de controle; contabilização explícita de amostras descartadas; e degradação parcial em vez de falha total — sem o MPU6050, o sistema segue operando com os demais sensores.

## 8. Limitações reconhecidas

O pulso é simulado por botão, então a frequência cardíaca reflete a mão do operador, não eletrofisiologia — e há um efeito de escala que observamos na execução: o Wokwi roda a simulação abaixo do tempo real (medimos cerca de 30 % num navegador com outras abas abertas), e como o firmware calcula os intervalos com `millis()`, que é tempo simulado, um toque a cada 500 ms de relógio de parede é lido como ~150 ms pelo dispositivo, inflando a frequência até o teto de 300 bpm. O cálculo está correto; o que está fora de escala é o relógio do simulador. O teto de 300 bpm cumpriu aqui exatamente o papel para o qual foi escrito, impedindo que um valor fisiologicamente impossível se propagasse para o painel; o DHT22 mede temperatura ambiente e não corporal, com precisão de ±0,5 °C, insuficiente para decisão clínica real; o SPIFFS é volátil no simulador, conforme o próprio enunciado reconhece; e o broker público não oferece confidencialidade. Nenhuma dessas limitações compromete a demonstração arquitetural, que é o objetivo da fase — mas todas precisariam ser resolvidas antes de qualquer uso com paciente real, e registrá-las é parte do que entendemos por desenvolvimento responsável.

---

*Documento sob licença CC BY 4.0 — Grupo Purkinje, FIAP 2026.*
