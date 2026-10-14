# Relatório — Parte 1
## Armazenamento e processamento local (Edge Computing)

**Projeto:** CardioIA — Fase 3 — Monitoramento Contínuo
**Grupo:** Purkinje — FIAP — Turma 2TIAOR-2026
**Paciente monitorado:** CARD-0056 — **Dispositivo:** PURKINJE-WEAR-01 — **Firmware:** 3.1.0

---

### 1. O que o dispositivo é

O protótipo simula um wearable torácico de monitoramento cardiológico domiciliar. Ele acompanha um paciente específico — **CARD-0056** — e essa escolha não é arbitrária: é o mesmo identificador do dataset construído na Fase 1, onde o paciente aparece na faixa de alto risco cardiovascular, e é o mesmo relato que o extrator de sintomas da Fase 2 classificou como triagem de risco **ALTO**. As três fases do projeto se ligam pela mesma chave primária, `id_paciente`. O wearable desta fase monitora, portanto, alguém que o próprio projeto já havia sinalizado.

### 2. Sensores e sinais capturados

| Sinal | Origem | Pino | Papel clínico |
|---|---|---|---|
| Temperatura corporal | DHT22 | GPIO 15 | Detecção de febre e hipotermia |
| Umidade relativa | DHT22 | GPIO 15 | Contexto ambiental do paciente |
| Frequência cardíaca | Pushbutton | GPIO 4 | Pulso arterial simulado (toque no ritmo desejado) |
| Movimento / impacto | MPU6050 (I²C) | GPIO 21/22 | Detecção de queda e de imobilidade prolongada |

O DHT22 é o sensor obrigatório e conta como um sensor, conforme o enunciado. O **MPU6050** é o segundo sensor de escolha livre do grupo. O botão de pulso é o estímulo sugerido pelo próprio enunciado para simular batimentos.

A frequência cardíaca é derivada dos **intervalos entre toques**, não da contagem numa janela fixa. A interrupção `isr_pulso()` registra o instante de cada toque com 120 ms de *debounce*, e `ler_bpm()` converte a média dos quatro últimos intervalos em batimentos por minuto. A escolha é deliberada: contagem por janela exigiria esperar a janela inteira fechar antes de reagir, o que atrasaria a detecção de uma taquicardia; a média de quatro intervalos responde em poucos segundos e ainda filtra a irregularidade natural da mão humana. O *debounce* de 120 ms também funciona como teto fisiológico — acima de 500 bpm não há batimento, há ruído mecânico do botão.

### 3. Fluxo de funcionamento

```
   [DHT22] ---+
   [MPU6050] -+--> amostrar() --> avaliar() --> enlace ativo?
   [BOTÃO] ---+                      |            |        |
                                     |           sim      não
                               (LED de alerta)    |        |
                                          publicar_mqtt  bufferizar
                                                   |        |
                                                   |   (enlace volta)
                                                   |        |
                                                   +<-- sincronizar
```

A cada ciclo o firmware lê os três sensores, monta um registro de 12 bytes, submete-o à avaliação clínica e só então decide o destino. O enlace é uma **variável booleana** (`enlace_ativo`), como pede o enunciado, controlada pelo botão do GPIO 5 — o que permite demonstrar a resiliência sem derrubar o Wi‑Fi de verdade dentro do simulador. Em todos os casos a amostra é impressa no Monitor Serial com o destino explícito (`ENVIO`, `BUFFER`, `SYNC-C`, `SYNC-R`), que é a evidência pedida para esta parte.

### 4. A decisão clínica mora na borda

O ponto central do argumento de Edge Computing deste projeto é a função `avaliar()`. Ela classifica cada amostra em NORMAL, TAQUICARDIA, BRADICARDIA, FEBRE, HIPOTERMIA, QUEDA, IMOBILIDADE ou SINAL_AUSENTE **dentro do dispositivo**. Se a nuvem cair, o alerta continua sendo detectado, o LED vermelho continua acendendo e a amostra continua entrando na fila prioritária. A nuvem é o canal de notificação, não o cérebro do sistema — e essa é a diferença entre um wearable médico e um sensor conectado.

Três decisões de projeto merecem registro:

**Histerese.** Taquicardia, bradicardia, febre e hipotermia só disparam após **três amostras consecutivas** na condição. O contador zera assim que a condição deixa de valer, de modo que leituras alternadas nunca acumulam até o limiar. Uma leitura isolada ruim não pode acionar um alerta médico.

**Impacto não tem histerese.** Uma queda é um evento único que não se repete na amostra seguinte; esperar confirmação perderia justamente o evento que se queria detectar. Por isso `mov_mg >= 2500` dispara imediatamente.

**Falha de sensor não é evento clínico.** Se nenhum pulso chegar em 4 segundos, o firmware reporta SINAL_AUSENTE — eletrodo solto — e **não** bradicardia. Confundir as duas coisas produz o alarme falso que leva equipes a ignorar o monitor, a chamada fadiga de alarme. Pelo mesmo raciocínio, imobilidade só vira alerta se vier acompanhada de ritmo alterado: paciente parado com ritmo normal está dormindo, não desmaiado.

### 5. Estratégia de resiliência: dois buffers, não um

O enunciado pede que o grupo escolha uma estratégia de armazenamento limitado alinhada ao modelo de negócio. A nossa é um **buffer circular separado por prioridade clínica**:

- `buf_rotina` — 2400 posições — amostras normais. Em saturação, descarta a mais antiga.
- `buf_critico` — 480 posições — amostras em alerta. Fila independente.

A razão de separar é direta. Num buffer circular único, uma queda de enlace mais longa que a autonomia projetada apagaria exatamente o episódio de taquicardia que motivou o monitoramento — porque ele seria o dado mais antigo. O evento clínico é o dado de maior valor e precisa de garantia própria. Na sincronização, os críticos são drenados primeiro.

O script `analise/dimensionar_buffer.py` quantifica o ganho simulando uma queda de 18 horas (50 % além do projetado), com a **mesma memória total** nas duas estratégias:

| Prob. de alerta | Amostras geradas | Alertas ocorridos | Salvos — FIFO único | Salvos — prioridade |
|---|---|---|---|---|
| 2 % | 4320 | 86 | 60 | **87** |
| 5 % | 4320 | 216 | 136 | **217** |
| 10 % | 4320 | 432 | 265 | **421** |

Com 5 % de alertas, o FIFO único perde 37 % do histórico clínico; a fila prioritária não perde nada. O custo é ter descartado mais amostras de rotina, que têm valor epidemiológico, não diagnóstico.

### 6. Dimensionamento quantitativo

| Amostras | Memória | % da SRAM | Autonomia offline | Cabe no orçamento | Atinge o alvo |
|---|---|---|---|---|---|
| 1440 | 16,9 KB | 3,25 % | 6,0 h | sim | não |
| 2160 | 25,3 KB | 4,87 % | 9,0 h | sim | não |
| **2880** | **33,8 KB** | **6,49 %** | **12,0 h** | **sim** | **sim** |
| 4320 | 50,6 KB | 9,74 % | 18,0 h | não | sim |

A configuração adotada é a **menor que satisfaz as duas restrições**: 2880 amostras de 12 bytes, 33,8 KB, 6,49 % da SRAM de 520 KB do ESP32, dentro do orçamento de 48 KB que nos impusemos para deixar folga à pilha Wi‑Fi e ao heap do cliente MQTT.

As 12 horas vêm do modelo de negócio: em monitoramento domiciliar, a falha de conectividade típica é uma queda de energia ou de link residencial resolvida dentro de um turno. O buffer crítico sozinho cobre 2 horas de evento contínuo — além disso, o paciente já estaria sob cuidado presencial.

A autonomia só chega a 12 horas por causa de uma segunda decisão: **degradação graciosa da cadência**. Online, o dispositivo amostra a cada 5 s; offline, a cada 15 s. Com a mesma memória, triplicamos a janela coberta, ao custo de resolução temporal — aceitável porque a histerese opera sobre amostras consecutivas, não sobre um intervalo fixo em segundos.

### 7. Sobre o SPIFFS

O enunciado reconhece que o SPIFFS é volátil nos simuladores e não computa o item. O código está implementado e compilado condicionalmente (`USAR_SPIFFS` em `config.h`): com a flag em 1, o mesmo firmware grava cada leitura em `/cardioia.csv` num ESP32 físico e **apaga o arquivo** assim que o backlog chega a zero, exatamente como descrito no enunciado. No simulador, a flag fica em 0 e o Monitor Serial cumpre o papel de evidência de resiliência, conforme a alternativa autorizada.

### 8. Como reproduzir

1. Abrir o projeto no Wokwi (link no README).
2. Deixar a simulação rodando; tocar o botão **PULSO** (vermelho) num ritmo regular — cerca de dois toques por segundo produzem ~120 bpm.
3. Observar as linhas `ENVIO` no Monitor Serial.
4. Pressionar o botão **ENLACE** (azul). O LED verde apaga, o cabeçalho `*** ENLACE PERDIDO ***` aparece e as linhas passam a `BUFFER`, com o contador `fila` crescendo.
5. Acelerar os toques no botão de pulso até ultrapassar 120 bpm por três amostras: o LED vermelho acende e o Serial anuncia `>>> ALERTA CLÍNICO NA BORDA: TAQUICARDIA` — **mesmo offline**. É a demonstração de que a decisão não depende da nuvem.
6. Pressionar **ENLACE** novamente. O Serial mostra `[SYNC]`, as amostras críticas saem primeiro (`SYNC-C`), depois a rotina (`SYNC-R`), e a fila volta a zero.

---

*Documento sob licença CC BY 4.0 — Grupo Purkinje, FIAP 2026.*
