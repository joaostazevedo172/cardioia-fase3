# Roteiro de demonstração em vídeo

**CardioIA — Fase 3 — Grupo Purkinje**

> ⚠️ **Atenção:** o enunciado da Fase 3 **não exige vídeo** para as Partes 1 e 2. Os entregáveis são o link do Wokwi, o código, os prints do dashboard e os dois relatórios. Este roteiro existe porque uma gravação curta é a melhor evidência de funcionamento que você pode anexar — e porque, se o grupo decidir fazer o Ir Além 2, o vídeo passa a ser obrigatório lá.

**Duração alvo:** 3 min 30 s
**Formato:** gravação de tela com narração

---

## Preparação (antes de gravar)

- [ ] Node-RED rodando, flow importado, `/ui` aberto numa aba
- [ ] Wokwi aberto noutra aba, simulação **parada**
- [ ] Monitor Serial visível no Wokwi
- [ ] Janelas organizadas: Wokwi à esquerda, dashboard à direita (ou alterne com Alt+Tab)
- [ ] Faça um ensaio completo antes de gravar — o ritmo dos toques no botão precisa estar na mão

---

## Bloco 1 — Abertura (0:00 – 0:25)

**Tela:** README do repositório no GitHub.

> "Olá. Eu sou o João Pedro, RM 566701, do grupo Purkinje. Esta é a Fase 3 do CardioIA: um wearable de monitoramento cardíaco construído sobre ESP32, que captura sinais vitais, decide sozinho se existe um evento clínico, sobrevive a quedas de conexão e publica tudo num dashboard em tempo real."

**Ação:** rolar até a tabela das três fases.

> "O paciente monitorado é o CARD-0056 — o mesmo identificador do dataset da Fase 1 e do classificador de risco da Fase 2. As três fases se ligam pela mesma chave."

## Bloco 2 — O circuito (0:25 – 0:50)

**Tela:** aba `diagram.json` do Wokwi, com o circuito visível.

> "O enunciado pede no mínimo dois sensores distintos. O DHT22 dá temperatura e umidade. O segundo é o MPU6050, um acelerômetro, que detecta impacto e imobilidade. O pulso arterial é simulado pelo botão vermelho. O botão azul liga e desliga o enlace — é a variável booleana que o enunciado pede."

## Bloco 3 — Funcionamento normal (0:50 – 1:30)

**Ação:** iniciar a simulação. Esperar o cabeçalho no Serial.

> "Na partida, o firmware declara o dimensionamento do buffer: 2880 amostras, 34 kilobytes, doze horas de autonomia offline. Já volto nesse número."

**Ação:** tocar o botão PULSO em ritmo regular. Mostrar o Serial e depois o dashboard.

> "Cada toque é um batimento. O dispositivo calcula a frequência pelos intervalos entre toques e publica via MQTT. No dashboard aparecem o gráfico de frequência cardíaca, os medidores de temperatura e umidade, e o LED virtual verde."

## Bloco 4 — Alerta na borda (1:30 – 2:05)

**Ação:** acelerar os toques e **manter** acima de 120 bpm.

> "Agora acelero o ritmo. Passando de 120 batimentos por minuto, o firmware não dispara de imediato: ele exige três amostras consecutivas. Essa histerese existe para que uma leitura ruim isolada não acione um alerta médico."

**Ação:** mostrar o LED vermelho aceso e a linha no Serial.

> "Alerta de taquicardia, decidido **dentro do dispositivo**. O LED do paciente acendeu antes de qualquer pacote sair para a nuvem."

## Bloco 5 — Resiliência offline (2:05 – 2:50)

**Ação:** pressionar o botão ENLACE.

> "Derrubo o enlace. O LED verde apaga e as linhas mudam de ENVIO para BUFFER — a amostragem continua, agora a cada quinze segundos em vez de cinco, para esticar a autonomia do buffer."

**Ação:** continuar tocando em ritmo alto. Apontar o LED vermelho.

> "E repare: o alerta continua sendo detectado, offline. É isso que separa um wearable médico de um sensor conectado — a nuvem é o canal de notificação, não o cérebro."

**Ação:** mostrar o contador `fila` crescendo.

> "O buffer é duplo: uma fila para amostras de rotina e outra, independente, para as amostras em alerta. Num buffer único, uma queda longa apagaria justamente o início do episódio, que é a parte mais valiosa do diagnóstico. Eu simulei isso: numa queda de dezoito horas, o FIFO único perde trinta e sete por cento do histórico clínico. A fila prioritária não perde nada."

## Bloco 6 — Sincronização (2:50 – 3:15)

**Ação:** pressionar ENLACE de novo.

> "Reconecto. O firmware drena o backlog em lotes, críticas primeiro — SYNC-C antes de SYNC-R. Em lotes porque despejar tudo de uma vez bloquearia o laço e estouraria o keepalive do MQTT, derrubando a conexão no exato momento em que ela voltou."

**Ação:** mostrar o dashboard com a série *FC sincronizada*.

> "No painel, o histórico sincronizado entra como série separada e não mexe nos medidores — um gauge mostrando valor de duas horas atrás como se fosse agora induziria o profissional ao erro."

## Bloco 7 — Fechamento (3:15 – 3:30)

**Tela:** dashboard completo.

> "Captura, processamento na borda, transmissão por MQTT, visualização e alerta: o ciclo completo de dados em IoT aplicado à saúde. Código, circuito, flow do Node-RED e os dois relatórios estão no repositório. Obrigado."

---

## Checklist de gravação

- [ ] Áudio limpo, sem ruído de fundo
- [ ] Zoom suficiente no Serial para o texto ser legível em tela cheia
- [ ] O LED vermelho aparece aceso **durante o trecho offline** — é o momento mais importante do vídeo
- [ ] A transição BUFFER → SYNC-C → SYNC-R aparece completa
- [ ] Menos de 4 minutos
- [ ] Upload no YouTube como **não listado**
- [ ] Link colado na seção 10 do README

---

## Sugestão de descrição para o YouTube

```
CardioIA — Fase 3 — Monitoramento Contínuo com ESP32, MQTT e Node-RED
Grupo Purkinje — FIAP — Turma 2TIAOR-2026

Protótipo de wearable de monitoramento cardiológico domiciliar que captura
sinais vitais (DHT22 + MPU6050 + pulso simulado), avalia eventos clínicos na
própria borda, mantém buffer circular com prioridade clínica para sobreviver a
quedas de conexão, e publica via MQTT para um dashboard em Node-RED.

Destaques técnicos:
• Decisão clínica no dispositivo, com histerese de três amostras
• Buffer duplo (rotina + crítico) — 12 h de autonomia offline
• Cadência adaptativa: 5 s online, 15 s offline
• MQTT com QoS 1 e Last Will and Testament
• Dashboard com gráfico, gauges, LED virtual e histórico de eventos

Repositório: https://github.com/SEU-USUARIO/cardioia-fase3
Projeto no Wokwi: https://wokwi.com/projects/SEU-PROJETO

#FIAP #IoT #ESP32 #MQTT #NodeRED #EdgeComputing #SaudeDigital
```

---

*Grupo Purkinje — FIAP 2TIAOR-2026 — CC BY 4.0*
