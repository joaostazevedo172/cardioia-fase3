# Roteiro do vídeo — Ir Além 2

**CardioIA — Fase 3 — Grupo Purkinje**
**Duração alvo:** 3 min 40 s (o limite é 4 min) — **YouTube: não listado**

> O enunciado do Ir Além 2 **exige** vídeo com análise crítica. É o único vídeo obrigatório desta fase.

---

## Preparação

- [ ] Notebook aberto e **já executado**, com todas as saídas visíveis
- [ ] Zoom do navegador em 100 %, janela maximizada
- [ ] Ensaie uma vez: o tempo some rápido na seção de resultados
- [ ] Não leia o roteiro — use como guia e fale com suas palavras

---

## Bloco 1 — O problema (0:00 – 0:35)

**Tela:** topo do notebook, título e tabela comparativa dos dois métodos.

> "Olá. Sou o João Pedro, RM 566701, com a Miriã Leal Mantovani, RM 567811, do grupo Purkinje. Este é o Ir Além 2 da Fase 3 do CardioIA: comparar um classificador tradicional com uma rede neuromórfica em séries temporais de sinais vitais."

> "O wearable que construímos na Fase 3 detecta arritmia por uma regra explícita: três leituras consecutivas fora da faixa clínica. A pergunta aqui é se um modelo aprendido reconhece os mesmos episódios — e o que se ganha, ou se perde, ao trocar a regra por aprendizado."

## Bloco 2 — Os dados, e por que são difíceis (0:35 – 1:10)

**Ação:** rolar até o histograma de frequência máxima.

> "São 1200 janelas de 36 leituras, três minutos cada, geradas pelo mesmo modelo do nosso wearable, para o mesmo paciente CARD-0056."

> "E deixamos o problema difícil de propósito. Olhem este gráfico: se bastasse olhar o pico da janela, as duas classes estariam separadas. Elas se sobrepõem porque metade das janelas normais tem um artefato de movimento que cruza o limiar por uma ou duas leituras. **O que distingue episódio de artefato não é o valor, é a persistência.**"

## Bloco 3 — A intuição do neurônio (1:10 – 2:00)

**Ação:** mostrar a figura dos dois painéis com o potencial de membrana. **Esta é a figura mais importante do vídeo — dê tempo a ela.**

> "E é aqui que o modelo neuromórfico fica interessante. Um neurônio integra-e-dispara com vazamento acumula corrente quando a leitura está fora da faixa, e vaza continuamente."

**Ação:** apontar o painel esquerdo.

> "No artefato transitório, o potencial sobe até 1,65, não alcança o limiar de 1,8, e vaza. Não dispara."

**Ação:** apontar o painel direito.

> "No episódio sustentado, o desvio vence o vazamento, cruza o limiar e dispara na leitura 17."

> "Repare no que aconteceu: **a constante de tempo do vazamento faz o papel do contador de histerese que escrevemos à mão no firmware** — só que em tempo contínuo, sem contador nenhum."

## Bloco 4 — Resultados (2:00 – 2:50)

**Ação:** mostrar a tabela comparativa e o gráfico de barras.

> "A regressão logística venceu em acurácia: 97,8 % contra 95,6 % do LIF."

> "Mas treinamos a regressão em duas variantes de propósito. Com a série crua ela faz 96,9 %; só chega a 97,8 % quando damos a contagem de leituras fora da faixa. Ou seja, **boa parte da vantagem é da engenharia de atributos, não do classificador**. Reportar só a melhor variante esconderia isso."

**Ação:** mostrar o histograma de latência.

> "E aqui está a diferença que não é de ajuste, é de arquitetura. A regressão só decide quando a janela inteira chegou — 36 leituras, por construção. O neurônio decide no instante do disparo: em média 19,9 leituras. **Dezesseis leituras antes, ou 81 segundos.** Numa triagem cardiológica, 81 segundos importam."

## Bloco 5 — Análise crítica (2:50 – 3:30)

**Tela:** seção de conclusão do notebook.

> "Sendo honesto sobre as limitações: o LIF perde 11 episódios contra 5 da regressão. Em aplicação clínica, falso negativo custa mais que falso positivo, e esse é o argumento mais forte contra usar o LIF sozinho."

> "A defesa dele contra artefato é só o vazamento. Diminuir o tau reduz o falso positivo mas aumenta a latência — o compromisso é explícito, e está num parâmetro só."

> "Onde ele é insubstituível: guarda um número, o potencial, em vez da janela inteira. No ESP32, com 520 KB de SRAM e um buffer de resiliência que já ocupa 34, isso não é detalhe estético."

> "Nossa recomendação é híbrida: **LIF na borda**, pela latência e pela memória; **regressão na névoa**, com a janela completa, confirmando. É a mesma divisão que a Fase 3 já faz entre o ESP32 e o Node-RED."

## Bloco 6 — Fechamento (3:30 – 3:40)

> "A conclusão que mais nos chamou atenção não é qual modelo vence. É que o neurônio, ajustado por busca em grade e sem saber nada de fisiologia, convergiu para a mesma estratégia que escrevemos à mão: exigir persistência antes de acreditar no desvio. Duas formas muito diferentes de pensar o problema chegaram à mesma ideia. Obrigado."

---

## Checklist

- [ ] Menos de 4 minutos
- [ ] A figura do potencial de membrana aparece com tempo para ser lida
- [ ] Os números 97,8 % / 95,6 % / 81 segundos são ditos em voz alta
- [ ] A análise crítica (bloco 5) não foi cortada — **é critério de avaliação**
- [ ] Upload como **não listado**
- [ ] Link colado no README do `ir-alem-2/` e no README principal

---

## Descrição para o YouTube

```
CardioIA — Fase 3 — Ir Além 2: IA em séries temporais de saúde
Grupo Purkinje — FIAP — Turma 2TIAOR-2026

Comparação entre regressão logística e um neurônio integra-e-dispara com
vazamento (LIF) na detecção de episódios arrítmicos em séries de frequência
cardíaca geradas pelo wearable ESP32 da Fase 3.

Resultados:
• Regressão logística: 97,8% de acurácia, F1 0,971
• Neurônio LIF: 95,6% de acurácia, F1 0,942
• LIF detecta 81 segundos antes (19,9 leituras contra 36)
• LIF guarda um número; a regressão guarda a janela inteira

A descoberta central: o neurônio, ajustado sem nenhum conhecimento de
fisiologia, convergiu para a mesma estratégia escrita à mão no firmware —
exigir persistência antes de acreditar no desvio.

Repositório: https://github.com/joaostazevedo172/cardioia-fase3

#FIAP #IA #SeriesTemporais #Neuromorfico #SpikingNeuralNetwork #SaudeDigital
```
