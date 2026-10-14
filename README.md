<p align="center">
  <a href="https://www.fiap.com.br/">
    <img src="https://raw.githubusercontent.com/lfusca/templateFiap/main/assets/logo-fiap.png" alt="FIAP" border="0" width="40%" height="40%">
  </a>
</p>

<br>

# CardioIA — Fase 3
## Monitoramento Contínuo — IoT no Peito do Paciente

### Grupo Purkinje

---

## 👨‍🎓 Integrantes

| Integrante | RM | Turma |
|---|---|---|
| Miriã Leal Mantovani | RM567811 | 2TIAOR-2026 |
| João Pedro Santos Azevedo | RM566701 | 2TIAOR-2026 |

## 👩‍🏫 Professores

### Tutor
- Leonardo Ruiz Orabona

### Coordenador
- André Godoi Chiovato

---

## 📜 Sumário

- [1. Sobre o projeto](#1-sobre-o-projeto)
- [2. O que foi construído](#2-o-que-foi-construído)
- [3. Arquitetura](#3-arquitetura)
- [4. Decisões técnicas que valem explicação](#4-decisões-técnicas-que-valem-explicação)
- [5. Pré-requisitos](#5-pré-requisitos)
- [6. Como rodar](#6-como-rodar)
- [7. Roteiro de demonstração](#7-roteiro-de-demonstração)
- [8. Troubleshooting](#8-troubleshooting)
- [9. Estrutura de pastas](#9-estrutura-de-pastas)
- [10. Vídeo de demonstração](#10-vídeo-de-demonstração)
- [11. Ir Além](#11-ir-além)
- [12. Histórico de versões](#12-histórico-de-versões)
- [13. Licença](#13-licença)
- [14. Agradecimentos](#14-agradecimentos)

---

## 1. Sobre o projeto

Protótipo funcional de um **wearable torácico de monitoramento cardiológico domiciliar**, construído sobre ESP32. O dispositivo captura sinais vitais, decide localmente se há um evento clínico, sobrevive a quedas de conectividade sem perder o histórico que importa, e publica tudo via MQTT para um dashboard em tempo real.

O paciente monitorado é o **CARD-0056**, e essa escolha costura as três fases do CardioIA. É o mesmo identificador do dataset da Fase 1, onde aparece na faixa de alto risco cardiovascular, e o mesmo relato que o extrator de sintomas da Fase 2 classificou como triagem de risco **ALTO**. O wearable desta fase monitora alguém que o próprio projeto já havia sinalizado — as três fases se ligam pela mesma chave primária, `id_paciente`.

| Fase | Entregou | Chave de ligação |
|---|---|---|
| Fase 1 | Dataset numérico, textual e de imagens de ECG | `id_paciente` |
| Fase 2 | Extração de sintomas + classificador de risco | `id_paciente` |
| **Fase 3** | **Wearable IoT + Edge + MQTT + dashboard** | **`id_paciente`** |

## 2. O que foi construído

**Parte 1 — Edge Computing**

- Leitura de dois sensores distintos: **DHT22** (temperatura e umidade) e **MPU6050** (acelerômetro), mais pulso arterial simulado por pushbutton
- Avaliação clínica **dentro do dispositivo**, com histerese de três amostras
- Enlace Wi‑Fi simulado por variável booleana, alternado por botão
- **Buffer circular separado por prioridade clínica** — 2400 posições de rotina + 480 críticas
- Cadência adaptativa: 5 s online, 15 s offline — 12 horas de autonomia sem conexão
- Sincronização do backlog com críticos primeiro, em lotes
- SPIFFS implementado sob a flag `USAR_SPIFFS`, **não validado em hardware físico** — o item é opcional e o enunciado reconhece que o simulador não o executa

**Parte 2 — Fog / Cloud**

- Publicação MQTT em quatro tópicos (telemetria, histórico, alerta, status)
- **Last Will and Testament** para detectar dispositivo mudo, e garantia *at least once* implementada na camada de aplicação (o PubSubClient publica em QoS 0 — a amostra cuja publicação falha volta para o buffer)
- Dashboard Node-RED com gráfico de FC, dois gauges, LED virtual de alerta, fila de sincronização e tabela de eventos
- Caminho para HiveMQ Cloud com TLS documentado e implementado sob flag

**Extras do grupo**

- `analise/dimensionar_buffer.py` — justifica quantitativamente o tamanho do buffer e demonstra, por simulação, por que duas filas preservam mais evento clínico que uma

### 2.1 O que o enunciado pede e onde está

| Entregável exigido | Onde está |
|---|---|
| Circuito no Wokwi com ESP32 e ao menos dois sensores | [projeto no Wokwi](https://wokwi.com/projects/477609293767887873) · `wokwi/diagram.json` |
| Código-fonte do firmware comentado | `src/cardioia_wearable.ino`, `src/config.h`, `src/tipos.h` |
| Simulação de conectividade por variável booleana | `enlace_ativo` em `src/cardioia_wearable.ino`, alternada pelo botão do GPIO 5 |
| Armazenamento local com estratégia de dimensionamento justificada | `BufferCircular` em `src/tipos.h` · justificativa em `docs/RELATORIO_PARTE1_EDGE.md` §5 e §6 · simulação em `analise/dimensionar_buffer.py` |
| Relatório da Parte 1 (Edge) | `docs/RELATORIO_PARTE1_EDGE.md` |
| Transmissão MQTT para a nuvem | `publicar_*()` em `src/cardioia_wearable.ino` · tópicos em `docs/RELATORIO_PARTE2_MQTT.md` §3 |
| Dashboard com visualização e alertas | `nodered/flows.json` · guia em `docs/GUIA_NODE_RED.md` · capturas em `evidencias/` |
| Relatório da Parte 2 (Fog/Cloud) | `docs/RELATORIO_PARTE2_MQTT.md` |
| Documento-resumo da entrega | `docs/CardioIA_Fase3_Documento_Resumo.pdf` |
| Repositório público com README | este repositório |

## 3. Arquitetura

```
  CAMADA DE BORDA (Edge)              CAMADA DE NÉVOA/NUVEM (Fog/Cloud)
  ──────────────────────              ─────────────────────────────────
   ESP32 + DHT22 + MPU6050
   • amostragem adaptativa
   • avaliação clínica           MQTT        broker.hivemq.com
   • buffer prioritário      ──────────►    (TCP 1883 / TLS 8883)
   • LED de alerta local                            │
                                                    ▼
                                           Node-RED (Fog)
                                           • normalização e roteamento
                                           • memória de eventos
                                                    │
                                                    ▼
                                           Dashboard (HTTP)
                                           gráfico · gauges · LED · tabela
```

### Circuito

| Componente | Pino ESP32 | Função |
|---|---|---|
| DHT22 | GPIO 15 | Temperatura e umidade |
| MPU6050 | GPIO 21 (SDA) / GPIO 22 (SCL) | Movimento e impacto |
| Botão PULSO (vermelho) | GPIO 4 | Pulso arterial simulado |
| Botão ENLACE (azul) | GPIO 5 | Liga/desliga o enlace |
| LED ALERTA (vermelho) | GPIO 18 | Alerta clínico ativo |
| LED ONLINE (verde) | GPIO 19 | Enlace estabelecido |

## 4. Decisões técnicas que valem explicação

**Dois buffers, não um.** Num buffer circular único, uma queda de enlace longa apagaria exatamente o episódio de taquicardia que motivou o monitoramento, porque ele seria o dado mais antigo. Separamos a fila de rotina da fila crítica. A simulação em `analise/dimensionar_buffer.py` mostra o efeito com a mesma memória total: numa queda de 18 horas com 5 % de alertas, o FIFO único perde 37 % do histórico clínico e a fila prioritária não perde nada.

**Degradação graciosa da cadência.** Offline, a amostragem cai de 5 s para 15 s. Não é economia de energia — é extensão de autonomia: com a mesma memória, triplicamos a janela de contingência coberta. A histerese continua operando sobre amostras consecutivas, não sobre segundos, então a detecção não se degrada junto.

**Falha de sensor não é evento clínico.** Sem pulso por 4 segundos, o firmware reporta `SINAL_AUSENTE` — eletrodo solto — e não bradicardia. Confundir as duas coisas produz o alarme falso que leva equipes a ignorar o monitor. Pelo mesmo raciocínio, imobilidade só vira alerta acompanhada de ritmo alterado: paciente parado com ritmo normal está dormindo, não desmaiado.

**Last Will and Testament.** O broker publica `offline` se o dispositivo parar sem se despedir. Sem isso, o painel não distingue *"paciente sem alterações"* de *"parei de receber dados do paciente"* — as duas produzem a mesma tela imóvel, e a segunda é uma emergência silenciosa.

**Tópicos separados para ao vivo e histórico.** Quando o enlace volta, o dispositivo despeja centenas de amostras antigas. No mesmo tópico da telemetria, o painel mostraria um valor de duas horas atrás como se fosse o instante atual — erro de interpretação com consequência clínica.

**Alocação estática.** Alocação dinâmica em dispositivo embarcado de longa duração fragmenta a heap e falha dias depois do deploy, num momento em que ninguém está olhando.

## 5. Pré-requisitos

| Item | Versão | Para quê |
|---|---|---|
| Conta no [Wokwi](https://wokwi.com) | — | Simular o ESP32 |
| [Node.js](https://nodejs.org) | 18 ou superior | Rodar o Node-RED |
| Node-RED | 3.x | Dashboard |
| `node-red-dashboard` | 3.x | Widgets do painel |
| Python | 3.9 ou superior | Apenas para o script de dimensionamento (opcional) |

Nenhum hardware físico é necessário. O projeto roda inteiramente em simulação.

## 6. Como rodar

### 6.1 Simulação no Wokwi

**Opção A — abrir o projeto pronto**

Acesse o link do projeto (seção 10) e clique em ▶ **Start**.

**Opção B — montar do zero**

1. Criar novo projeto ESP32 em <https://wokwi.com/projects/new/esp32>
2. Colar `src/cardioia_wearable.ino` na aba `sketch.ino`
3. Criar a aba `config.h` (menu ▾ ao lado das abas → **New file...**) e colar `src/config.h`
4. Criar a aba `tipos.h` da mesma forma e colar `src/tipos.h`
5. Colar `wokwi/diagram.json` na aba `diagram.json`
6. Abrir a aba **Library Manager** e, pelo botão **+**, adicionar: `PubSubClient`, `DHT sensor library` e `Adafruit MPU6050`
7. Clicar em ▶ **Start**

> **Importante no passo 6:** não basta colar o `libraries.txt`. O Library Manager mantém estado próprio, e colar o arquivo não registra as bibliotecas — a compilação falha com `PubSubClient.h: No such file or directory`. Use o botão **+**. As dependências (`Adafruit Unified Sensor`, `Adafruit BusIO`) são resolvidas sozinhas.

A primeira compilação leva de 1 a 3 minutos na fila do servidor gratuito do Wokwi.

### 6.2 Dashboard

```bash
npm install -g --unsafe-perm node-red
node-red
```

Abra <http://localhost:1880>, instale `node-red-dashboard` em **Manage palette → Install**, importe `nodered/flows.json` em **Import**, clique em **Deploy** e abra <http://localhost:1880/ui>.

Passo a passo detalhado em [`docs/GUIA_NODE_RED.md`](docs/GUIA_NODE_RED.md).

### 6.3 Script de dimensionamento (opcional)

```bash
python analise/dimensionar_buffer.py
```

Não requer bibliotecas externas. Imprime a tabela de dimensionamento e a simulação comparativa das duas estratégias de buffer, e grava `analise/dimensionamento.csv`.

## 7. Roteiro de demonstração

A sequência abaixo exercita todos os critérios da rubrica em cerca de três minutos.

1. **Iniciar** a simulação e o Node-RED. O estado muda para `ONLINE` e os gauges saem do zero.
2. **Tocar o botão PULSO** (vermelho) num ritmo regular. Dois toques por segundo produzem ~120 bpm. A linha do gráfico responde.
3. **Acelerar os toques** até passar de 120 bpm e manter por três amostras. O LED vermelho acende, o Serial anuncia `>>> ALERTA CLÍNICO NA BORDA: TAQUICARDIA` e o LED virtual do dashboard fica vermelho.
4. **Pressionar o botão ENLACE** (azul). O LED verde apaga, o Serial mostra `*** ENLACE PERDIDO ***` e as linhas mudam de `ENVIO` para `BUFFER`, com o contador `fila` crescendo.
5. **Continuar tocando o pulso em ritmo alto.** O Serial continua anunciando alertas e o LED vermelho continua aceso — **offline**. É a prova de que a decisão clínica mora na borda.
6. **Pressionar ENLACE novamente.** O Serial mostra `[SYNC]`, as amostras críticas saem primeiro (`SYNC-C`), depois a rotina (`SYNC-R`), e a fila volta a zero. No dashboard, a série *FC sincronizada* aparece no gráfico.

## 8. Troubleshooting

**O Wokwi não encontra `config.h` ou `tipos.h`.**
Cada um precisa estar numa aba própria do projeto, com o nome exato. Use o menu ▾ ao lado das abas → **New file...**. Atenção: o campo do diálogo às vezes vem pré-preenchido com o nome do arquivo atual — selecione tudo (Ctrl+A) antes de digitar, ou o nome sai concatenado.

**`'BufferCircular' does not name a type` / `'Amostra' was not declared in this scope`.**
As `struct` saíram de `tipos.h` e voltaram para o `.ino`. O pré-processador do Arduino gera os protótipos de todas as funções do sketch e os insere logo após os `#include` — antes de qualquer definição feita no corpo do arquivo. Um protótipo como `void buffer_push(BufferCircular&, const Amostra&)` é emitido antes de a struct existir, e a compilação quebra. Por isso os tipos moram num cabeçalho. Esse erro não aparece em nenhuma análise estática: só a compilação real revela.

**`PubSubClient.h: No such file or directory`.**
As bibliotecas não foram registradas. Colar o conteúdo na aba Library Manager não funciona — use o botão **+** do painel. Veja a nota no passo 6 da seção 6.1.

**Não consigo renomear um arquivo no Wokwi pela automação.**
O "Rename" do editor usa um diálogo nativo do navegador que congela a página para ferramentas automatizadas. Renomeie manualmente, ou apague e recrie o arquivo com o nome certo.

**Erro de compilação em `Adafruit_MPU6050.h`.**
A `libraries.txt` deve conter `Adafruit MPU6050`, `Adafruit Unified Sensor` e `Adafruit BusIO`. As três são necessárias — a última é dependência silenciosa das outras.

**O DHT22 devolve `nan`.**
Normal nas primeiras leituras: o sensor precisa de cerca de 2 segundos após o `begin()`. O firmware trata o `nan` e substitui por 0 sem derrubar o ciclo.

**O LED de alerta não acende mesmo com FC alta.**
A histerese exige **três amostras consecutivas** acima de 120 bpm. Online, isso leva 15 segundos de toque sustentado. Mantenha o ritmo.

**A frequência cardíaca sobe direto para 300 bpm.**
300 é o teto de segurança do firmware, e o culpado é o relógio do simulador. O Wokwi roda abaixo do tempo real — medimos cerca de 30 % com outras abas abertas — e o firmware calcula os intervalos com `millis()`, que é tempo *simulado*. Um toque a cada 500 ms no seu relógio chega ao dispositivo como ~150 ms, o que daria 400 bpm. O cálculo está certo; a escala do relógio é que não está.

Duas saídas: feche as outras abas e deixe a janela do Wokwi em foco, acompanhando o indicador de % ao lado do cronômetro (quanto mais perto de 100 %, mais o ritmo real bate com o medido); ou simplesmente calibre pelo olho, ajustando o ritmo até o painel estabilizar entre 120 e 140 bpm.

**O botão PULSO não registra nada.**
O cálculo precisa de pelo menos dois toques para ter um intervalo. Depois de 4 segundos sem toque, o firmware reporta `SINAL_AUSENTE` e zera a FC — é o comportamento projetado, não um defeito.

**Os nós MQTT do Node-RED ficam em *connecting*.**
Firewall bloqueando a porta 1883 de saída. Teste em outra rede. Detalhes e alternativa por WebSocket em `docs/GUIA_NODE_RED.md`.

**Aparecem dados que não são meus no dashboard.**
O broker público é compartilhado. Troque o segmento `purkinje` em `TOPICO_BASE` (`config.h`) e nos quatro nós MQTT por algo exclusivo do grupo.

**Buffer de rotina satura rápido demais.**
É esperado se você deixar offline por muito tempo. O Serial avisa, e as amostras críticas continuam preservadas — é exatamente o comportamento que a estratégia de dois buffers garante.

## 9. Estrutura de pastas

```
cardioia-fase3/
├── src/
│   ├── cardioia_wearable.ino      # firmware completo, comentado
│   ├── config.h                   # todos os parâmetros, sem números mágicos
│   └── tipos.h                    # structs e enums (ver nota no item 8)
├── wokwi/
│   ├── diagram.json               # circuito do simulador
│   └── libraries.txt              # dependências do Arduino
├── nodered/
│   └── flows.json                 # dashboard importável
├── analise/
│   ├── dimensionar_buffer.py      # justificativa quantitativa do buffer
│   └── dimensionamento.csv        # saída do script
├── docs/
│   ├── RELATORIO_PARTE1_EDGE.md   # relatório da Parte 1
│   ├── RELATORIO_PARTE2_MQTT.md   # relatório da Parte 2
│   ├── GUIA_NODE_RED.md           # instalação passo a passo
│   └── ROTEIRO_VIDEO.md           # falas e direções do vídeo
├── ir-alem-1/                     # REST + automação de e-mail
├── ir-alem-2/                     # séries temporais: regressão × LIF
├── evidencias/                    # prints do dashboard e do circuito
├── LICENSE
└── README.md
```

## 10. Vídeo de demonstração

**Link do projeto no Wokwi:** <https://wokwi.com/projects/477609293767887873>

**Vídeo da entrega principal:** <https://www.youtube.com/watch?v=24XwCsWnDNU>

> O enunciado não exige vídeo nas Partes 1 e 2. Este foi gravado como material complementar, e percorre o processo pedido: captura, processamento na borda, transmissão, visualização e alerta.

## 11. Ir Além

Os dois desafios opcionais desta fase estão em subpastas deste mesmo repositório, cada uma com README, código e relatório próprios.

### [`ir-alem-1/`](ir-alem-1/) — Comunicação automatizada com REST e e-mail

API REST em Python que serve a telemetria do CARD-0056, cliente que consome e envia, lógica de verificação de risco e disparo automático de e-mail.

**Sem nenhuma dependência externa.** Roda com `python executar_demo.py` em qualquer máquina com Python 3.9+, sem `pip install`, sem ambiente virtual e sem credenciais. O envio fala SMTP de verdade contra um servidor que implementamos em cerca de cinquenta linhas, e arquiva as mensagens em `.eml`.

Última execução: 540 amostras consumidas, 13 requisições HTTP, 10 eventos detectados, **5 e-mails enviados e 5 suprimidos** pela janela anti-repetição.

Os limiares clínicos são os mesmos do firmware, e isso é **verificado por teste**: `testes/test_coerencia_firmware.py` lê o `src/config.h` e compara valor a valor. Se os dois divergirem, a suíte quebra.

### [`ir-alem-2/`](ir-alem-2/) — IA em séries temporais de saúde

Comparação entre regressão logística e um neurônio integra-e-dispara com vazamento (LIF) na detecção de episódios arrítmicos, sobre séries geradas pelo próprio wearable desta fase.

| Modelo | Acurácia | F1 | Latência de detecção |
|---|---|---|---|
| Regressão (série crua) | 0,9694 | 0,9606 | 36 leituras |
| Regressão (com contagem) | 0,9778 | 0,9712 | 36 leituras |
| Neurônio LIF | 0,9556 | 0,9416 | **19,9 leituras** |

A regressão vence em acurácia; o LIF detecta **81 segundos antes** e guarda um número em vez da janela inteira.

A descoberta central: o neurônio, ajustado por busca em grade e sem saber nada de fisiologia, **convergiu para a mesma estratégia que escrevemos à mão no firmware** — exigir persistência antes de acreditar no desvio. A constante de vazamento faz o papel do contador de histerese.

### Vídeos

| Entrega | Vídeo | Exigido pelo enunciado |
|---|---|---|
| Fase 3 — principal | <https://www.youtube.com/watch?v=24XwCsWnDNU> | não |
| Ir Além 1 | <https://www.youtube.com/watch?v=2YEolRwrxQs> | não |
| **Ir Além 2** | <https://youtu.be/psNuK_W5dCM> | **sim, até 4 min** |

## 12. Histórico de versões

| Versão | Data | O que mudou |
|---|---|---|
| 1.0.0 | 06/08/2026 | Firmware da Parte 1: leitura dos sensores, avaliação clínica na borda, histerese e buffer circular único |
| 1.1.0 | 06/08/2026 | Buffer separado por prioridade clínica, cadência adaptativa e o script de dimensionamento que justifica os dois tamanhos |
| 1.2.0 | 06/08/2026 | Parte 2: publicação MQTT, Last Will, retenção de status e sincronização do backlog em lotes |
| 1.3.0 | 06/08/2026 | Dashboard em Node-RED, guia de instalação e captura das evidências |
| 1.3.1 | 06/08/2026 | Correção: `ymax` do gráfico de 200 para 300, acompanhando o limite do firmware |
| 1.3.2 | 06/08/2026 | Correção: estruturas movidas para `src/tipos.h` — o pré-processador do Arduino emite os protótipos antes das definições do `.ino` |
| 1.4.0 | 06/08/2026 | Ir Além 1 e Ir Além 2 como subpastas, com relatórios e documentos próprios |
| 1.5.0 | 13/10/2026 | Links dos vídeos no YouTube, mapa de entregáveis e histórico de versões |

## 13. Licença

<img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg" width="30"> <img src="https://mirrors.creativecommons.org/presskit/icons/by.svg" width="30">

Este trabalho está licenciado sob **[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)**.

## 14. Agradecimentos

Ao tutor Leonardo Ruiz Orabona e ao coordenador André Godoi Chiovato, pela condução do PBL CardioIA, e à FIAP pela estrutura de laboratório maker disponibilizada à turma.
