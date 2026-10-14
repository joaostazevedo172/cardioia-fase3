# Descrições para o YouTube — CardioIA Fase 3

Três vídeos, prontos para copiar e colar. Cada bloco traz **título**, **descrição** (já com capítulos cronometrados) e **tags**.

> **Visibilidade:** o enunciado só exige vídeo para o **Ir Além 2**, e exige que ele seja postado como **não listado**. Os outros dois são material extra — a visibilidade fica a seu critério.

> **Vídeos publicados:**
> - Fase 3 — principal: <https://www.youtube.com/watch?v=24XwCsWnDNU>
> - Ir Além 1: <https://www.youtube.com/watch?v=2YEolRwrxQs>
> - Ir Além 2 (não listado): <https://youtu.be/psNuK_W5dCM>

---

## 1. Vídeo da entrega principal — Fase 3

**Título** *(copie esta linha)*

```
CardioIA Fase 3 — Monitoramento Contínuo: IoT no Peito do Paciente | FIAP
```

**Descrição**

```
Protótipo de wearable cardiológico em ESP32 que captura sinais vitais, decide
localmente se há um evento clínico, sobrevive a quedas de conectividade e
transmite por MQTT para um painel em Node-RED.

Projeto CardioIA — Fase 3 — Grupo Purkinje
FIAP — Graduação em Inteligência Artificial — Turma 2TIAOR-2026

A tese do vídeo: num dispositivo médico, as decisões difíceis não são de
código, são de critério. O que contar como alerta, o que descartar como ruído,
o que preservar quando a memória acaba.

DESTAQUES TÉCNICOS

• Decisão clínica na borda — o alerta acende no próprio dispositivo, antes de
  qualquer pacote chegar à nuvem
• Histerese de três amostras: uma leitura ruim isolada não aciona alarme
• Buffer circular separado por prioridade clínica (2400 rotina + 480 críticas)
• 12 horas de autonomia offline em 33,8 KB — 6,49% da SRAM do ESP32
• Cadência adaptativa: 5 s com enlace, 15 s sem
• MQTT com Last Will para distinguir "paciente sem alterações" de "parei de
  receber dados do paciente"
• Dashboard com gráfico, medidores, LED virtual e histórico de eventos

O NÚMERO QUE JUSTIFICA O PROJETO

Simulamos uma queda de conexão de 18 horas. Com uma fila única, 37% do
histórico clínico se perde — justamente o início do episódio, que é a parte
mais valiosa para o diagnóstico. Com duas filas separadas por prioridade,
nada se perde. Mesma memória nos dois casos.

CAPÍTULOS

00:00 O alerta que não dependeu da nuvem
00:18 Três fases, uma chave: o paciente CARD-0056
00:40 O circuito e os dois sensores
01:05 A decisão clínica mora no dispositivo
01:35 As três regras que evitam o alarme falso
02:06 Duas filas, não uma
02:35 Por que doze horas de autonomia
03:00 MQTT e o Last Will
03:28 Do normal ao alerta no dashboard
03:58 A prova do Edge Computing
04:30 Resultados
04:46 Encerramento

INTEGRANTES

Miriã Leal Mantovani — RM567811
João Pedro Santos Azevedo — RM566701

LINKS

Repositório: https://github.com/joaostazevedo172/cardioia-fase3
Projeto no Wokwi: https://wokwi.com/projects/477609293767887873

STACK

ESP32 · DHT22 · MPU6050 · MQTT (HiveMQ) · Node-RED · Wokwi

#FIAP #IoT #ESP32 #MQTT #NodeRED #EdgeComputing #SaudeDigital #Cardiologia
#InteligenciaArtificial #Wokwi
```

**Tags** *(campo de tags do YouTube, separadas por vírgula)*

```
FIAP, CardioIA, IoT, ESP32, MQTT, Node-RED, Edge Computing, saúde digital, cardiologia, wearable, Wokwi, inteligência artificial, telemetria, HiveMQ, DHT22, MPU6050
```

---

## 2. Vídeo do Ir Além 1 — REST e e-mail

**Título**

```
CardioIA Fase 3 — Ir Além 1: Comunicação automatizada com REST e e-mail | FIAP
```

**Descrição**

```
Serviço em Python que fecha o ciclo entre o wearable da Fase 3 e a equipe
clínica: consome e envia sinais vitais por uma API REST, detecta risco com as
mesmas regras do firmware e dispara e-mail automaticamente em caso de alerta.

Projeto CardioIA — Fase 3 — Ir Além 1 — Grupo Purkinje
FIAP — Graduação em Inteligência Artificial — Turma 2TIAOR-2026

SEM NENHUMA DEPENDÊNCIA EXTERNA

Roda com "python executar_demo.py" em qualquer máquina com Python 3.9 ou
superior. Sem pip install, sem ambiente virtual, sem credenciais. O envio fala
SMTP de verdade contra um servidor que implementamos em cerca de cinquenta
linhas, porque o módulo smtpd foi removido no Python 3.12 e aiosmtpd seria
dependência externa.

O DETALHE DE QUE MAIS NOS ORGULHAMOS

Um teste lê o config.h do firmware, em linguagem C, e compara os limiares valor
a valor com os do serviço em Python. Se divergirem, a suíte quebra.

Sem esse teste a divergência seria silenciosa e perversa: o paciente veria o LED
vermelho aceso no peito enquanto a central não receberia e-mail nenhum. Um
sistema de monitoramento que discorda de si mesmo é pior que um que não
monitora, porque produz confiança injustificada.

RESULTADO DA EXECUÇÃO

540 amostras consumidas · 13 requisições HTTP · 10 eventos detectados
5 e-mails enviados e 5 suprimidos pela janela anti-repetição

Metade dos eventos não virou mensagem, e é esse o comportamento desejado: dez
notificações para cinco situações clínicas distintas seria ruído.

CAPÍTULOS

00:00 O e-mail que ninguém escreveu
00:16 O que o serviço faz
00:36 Os cinco módulos
01:00 A API REST: consome e envia
01:22 As quatro propriedades da detecção de risco
01:48 O teste que compara com o firmware
02:12 Quem recebe mensagem, e quem não recebe
02:36 Resultados e encerramento

INTEGRANTES

Miriã Leal Mantovani — RM567811
João Pedro Santos Azevedo — RM566701

LINKS

Repositório: https://github.com/joaostazevedo172/cardioia-fase3
Pasta: ir-alem-1/

#FIAP #Python #API #REST #RPA #SMTP #SaudeDigital #IoT #Automacao
```

**Tags**

```
FIAP, CardioIA, Python, API REST, RPA, automação, SMTP, e-mail automatizado, saúde digital, IoT, http.server, urllib, testes automatizados
```

---

## 3. Vídeo do Ir Além 2 — séries temporais

> ⚠️ **Este é o único vídeo exigido pelo enunciado, e ele precisa ser publicado como NÃO LISTADO.** Depois de subir, cole o link no README da pasta `ir-alem-2/`.

**Título**

```
CardioIA Fase 3 — Ir Além 2: IA em séries temporais de saúde | Regressão logística × neurônio LIF | FIAP
```

**Descrição**

```
Comparação entre um classificador tradicional (regressão logística) e uma rede
neuromórfica simples (neurônio integra-e-dispara com vazamento) na detecção de
episódios arrítmicos em séries de frequência cardíaca geradas pelo wearable
ESP32 da Fase 3.

Projeto CardioIA — Fase 3 — Ir Além 2 — Grupo Purkinje
FIAP — Graduação em Inteligência Artificial — Turma 2TIAOR-2026

A IDEIA CENTRAL

O que separa um episódio arrítmico de um artefato de movimento não é o valor da
frequência: é a persistência do desvio. Um pico isolado de 130 bpm é ruído;
130 bpm por quinze leituras é um evento clínico.

O firmware resolve isso com um contador de histerese explícito. O neurônio
resolve o mesmo problema sem contador nenhum, pela dinâmica da membrana: a
corrente carrega o potencial, o vazamento o descarrega. A constante de tempo é
a histerese, em tempo contínuo.

RESULTADOS (conjunto de teste, 360 janelas)

Regressão logística (com contagem) — 97,78% de acurácia, F1 0,9712
Regressão logística (série crua) ... 96,94% de acurácia, F1 0,9606
Neurônio LIF ...................... 95,56% de acurácia, F1 0,9416

Latência de detecção: 19,9 leituras do LIF contra 36 da regressão — 81 segundos
antes, na cadência do wearable.

ANÁLISE CRÍTICA

Treinamos a regressão em duas variantes de propósito. Boa parte da vantagem
dela vem de um único atributo bem escolhido pelo projetista, não do
classificador: com a série crua ela cai para 96,94%.

O LIF perde 11 episódios contra 5 da regressão. Em aplicação clínica, falso
negativo custa mais que falso positivo, e esse é o argumento mais forte contra
usá-lo sozinho. Em compensação, ele guarda um número — o potencial de membrana
— em vez da janela inteira, o que num ESP32 com 520 KB de SRAM não é detalhe
estético.

Recomendação híbrida: o neurônio na borda, pela latência e pela memória; a
regressão na névoa, com a janela completa, confirmando.

A DESCOBERTA

O neurônio, ajustado por busca exaustiva em 180 combinações e sem saber nada de
fisiologia, convergiu para a mesma estratégia que escrevemos à mão no firmware:
exigir persistência antes de acreditar no desvio.

Duas formas muito distintas de pensar o problema chegaram à mesma ideia. Isso
sugere que a histerese não foi escolha arbitrária de projeto, e sim a resposta
natural para distinguir sinal de artefato em séries fisiológicas.

CAPÍTULOS

00:00 O mesmo neurônio, dois resultados
00:18 O experimento: tradicional contra neuromórfico
00:40 Persistência, não valor
01:04 Os dados, difíceis de propósito
01:28 Regressão logística em duas variantes
01:52 O neurônio integra-e-dispara
02:18 Resultados
02:44 A diferença estrutural: latência
03:10 Análise crítica
03:34 A descoberta

METODOLOGIA

1200 janelas de 36 leituras (3 min cada), 840 de treino e 360 de teste,
estratificadas. Rótulo apurado pela mesma regra de histerese do firmware.
Semente 20260806, a mesma desde a Fase 1 — os números são reproduzíveis.

INTEGRANTES

Miriã Leal Mantovani — RM567811
João Pedro Santos Azevedo — RM566701

LINKS

Repositório: https://github.com/joaostazevedo172/cardioia-fase3
Pasta: ir-alem-2/ (notebook, relatório comparativo e figuras)

#FIAP #InteligenciaArtificial #SeriesTemporais #Neuromorfico #SpikingNeuralNetwork
#RegressaoLogistica #MachineLearning #SaudeDigital #Python #scikitlearn
```

**Tags**

```
FIAP, CardioIA, inteligência artificial, séries temporais, neuromórfico, spiking neural network, LIF, regressão logística, machine learning, scikit-learn, Python, saúde digital, arritmia, classificação binária
```

---

## Checklist de publicação

- [ ] Gravar a narração de cada vídeo seguindo o `voice-script.txt` da pasta correspondente
- [ ] **Ir Além 2 como NÃO LISTADO** — é exigência do enunciado
- [ ] Usar o `brag.jpg` de cada pasta como miniatura
- [ ] Colar o link do Ir Além 2 no README de `ir-alem-2/`
- [ ] Colar os demais links no README principal, seção 10
- [ ] Conferir se os capítulos apareceram (o YouTube só os reconhece se o primeiro for 00:00 e houver pelo menos três)

---

*Todos os números citados vêm de execução real: `resultados/metricas.json`, `saida/relatorio_execucao.json` e `analise/dimensionar_buffer.py`. Nenhum foi estimado.*
