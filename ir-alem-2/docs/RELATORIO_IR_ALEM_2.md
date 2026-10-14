# Relatório comparativo — Ir Além 2
## Inteligência Artificial em séries temporais de saúde
### Regressão logística × neurônio integra-e-dispara com vazamento (LIF)

**Projeto:** CardioIA — Fase 3 — **Grupo:** Purkinje — FIAP — Turma 2TIAOR-2026
**Integrantes:** Miriã Leal Mantovani (RM567811) · João Pedro Santos Azevedo (RM566701)
**Paciente:** CARD-0056 — **Semente:** 20260806

---

## 1. O problema e os dados

O wearable da Fase 3 detecta arritmia por uma regra explícita: três leituras consecutivas fora da faixa clínica. A pergunta deste Ir Além é se um modelo aprendido reconhece os mesmos episódios na série que o próprio dispositivo produz, e o que se ganha ou se perde ao trocar a regra por aprendizado.

Cada exemplo é uma janela de **36 leituras** de frequência cardíaca — três minutos à cadência de 5 s do wearable. O rótulo vem da mesma regra de histerese do firmware. Foram geradas **1200 janelas** (38,8 % com episódio), separadas em 840 de treino e 360 de teste, de forma estratificada.

O gerador foi deixado difícil de propósito. Um gerador ingênuo produziria normais em torno de 74 bpm e anômalas em torno de 140, e qualquer classificador acertaria tudo — o que não mediria nada. Em vez disso: a frequência basal varia de 58 a 92 bpm, de modo que o valor absoluto sozinho não separa as classes; metade das janelas normais contém picos transitórios que cruzam o limiar por uma ou duas leituras, sem configurar episódio; os episódios começam em posições aleatórias e duram de 4 a 20 leituras. **120 das 360 janelas de teste são normais e contêm leitura fora da faixa** — é nelas que a comparação fica interessante.

## 2. Os dois métodos

**Regressão logística.** Recebe a janela inteira de uma vez: as 36 leituras na ordem original mais estatísticas de posição e dispersão. Treinamos duas variantes, e a comparação entre elas é deliberada. A segunda acrescenta a contagem de leituras fora da faixa — que não é o rótulo, porque o rótulo exige consecutividade e contagem não guarda ordem, mas é um substituto muito bom. Avaliar as duas separa dois efeitos que de outro modo ficariam misturados: o que o modelo linear extrai da série crua, e o quanto uma única estatística bem escolhida pelo projetista resolve o problema. Não entregamos o comprimento da maior sequência consecutiva, que *é* a regra de rotulagem e seria vazamento.

**Neurônio LIF.** Processa uma leitura por vez. A corrente de entrada é proporcional ao quanto a leitura está fora da faixa clínica e vale zero dentro dela; o potencial de membrana integra essa corrente e vaza continuamente:

```
V[t+1] = V[t] · (1 − Δt/τ) + I[t] · Δt       se V > V_limiar: dispara, V ← 0
```

Quatro parâmetros, todos com significado físico, ajustados por busca exaustiva em grade (180 combinações) no conjunto de treino. A configuração escolhida foi **τ = 9,0 · limiar = 1,8 · ganho = 0,6 · mínimo de 1 disparo**.

Não há gradiente: o disparo é uma descontinuidade e a rede tem quatro parâmetros. Retropropagação exigiria substitutos deriváveis, maquinaria desproporcional ao problema. A busca exaustiva cobre o espaço inteiro em segundos e deixa explícito o que foi explorado.

## 3. Resultados

| Modelo | Acurácia | Precisão | Revocação | F1 | AUC | FP | FN |
|---|---|---|---|---|---|---|---|
| Regressão (série crua) | 0,9694 | 0,9640 | 0,9571 | 0,9606 | 0,9955 | 5 | 6 |
| **Regressão (com contagem)** | **0,9778** | **0,9783** | **0,9643** | **0,9712** | **0,9986** | **3** | **5** |
| Neurônio LIF | 0,9556 | 0,9627 | 0,9214 | 0,9416 | 0,9584 | 5 | 11 |

**Latência de detecção**

| Modelo | Leituras até reconhecer | Equivalente em tempo |
|---|---|---|
| Neurônio LIF | 19,9 em média (mediana 19, mínimo 3) | 99 s |
| Regressão | 36, por construção | 180 s |

**Robustez ao artefato** — nas 120 janelas normais com leitura fora da faixa: regressão crua 5 falsos positivos (4,2 %), regressão com contagem 3 (2,5 %), LIF 5 (4,2 %).

**Custo por janela** — regressão: 84 operações sobre 42 atributos, em rajada no fim da janela. LIF: 108 operações, 3 por leitura, distribuídas no tempo.

## 4. Discussão

**A regressão logística venceu em acurácia, e vale entender por quê.** A variante com contagem tem acesso a uma estatística quase suficiente para o rótulo: uma janela com quinze leituras altas quase certamente as tem em sequência. Boa parte da vitória é da engenharia de atributos, não do classificador — a variante com série crua perde 0,9 ponto de acurácia, embora continue forte, porque as estatísticas de dispersão já carregam muito do sinal. Reportar as duas variantes é o que torna essa leitura possível; com apenas a melhor delas, "a regressão venceu" não diria se o mérito foi do modelo ou do projetista.

**O LIF perdeu em acurácia e ganhou em latência**, e essa troca é consequência da arquitetura, não de ajuste. Ele decide no instante em que a membrana cruza o limiar, em média **16 leituras antes** — cerca de **81 segundos** na cadência do wearable. Numa triagem cardiológica, 81 segundos são relevantes. A regressão, por construção, só decide quando a janela inteira chegou.

**Onde o LIF é frágil.** Erra mais nas janelas com artefato transitório forte, porque sua única defesa é o vazamento: se o artefato for longo o bastante, a membrana carrega. Reduzir τ diminui esse erro mas aumenta a latência — o compromisso é explícito e inescapável, e está exposto em um único parâmetro, o que é uma virtude de projeto. A revocação de 0,9214 contra 0,9643 da regressão significa 11 episódios perdidos contra 5 em 360 janelas; numa aplicação clínica real, falso negativo custa mais que falso positivo, e esse seria o argumento mais forte contra adotar o LIF sozinho.

**Onde o LIF é insubstituível.** Ele guarda um número — o potencial — em vez da janela inteira. No ESP32 da Fase 3, com 520 KB de SRAM e um buffer de resiliência já dimensionado em 34 KB, essa diferença não é estética: rodar a regressão a bordo exigiria acumular 36 leituras e executar 84 operações em rajada; o LIF executa 3 operações por leitura e nunca guarda a janela. Em hardware neuromórfico dedicado, apenas o disparo consome energia.

## 5. Conclusão

A conclusão mais interessante não é qual modelo vence. É que o neurônio LIF, ajustado por busca em grade e sem saber nada de fisiologia, **convergiu para a mesma estratégia que escrevemos à mão no firmware**: exigir persistência antes de acreditar no desvio. A constante de vazamento escolhida pelo ajuste cumpre exatamente o papel do contador de histerese de três amostras.

Duas formas muito distintas de pensar o problema — uma estatística, outra dinâmica — chegaram à mesma ideia. Isso sugere que a histerese não foi uma escolha arbitrária de projeto na Fase 3, e sim a resposta natural para distinguir sinal de artefato em séries fisiológicas.

Para o CardioIA, a recomendação prática é híbrida: **o LIF na borda**, pela latência e pelo custo de memória, decidindo quando acionar o alerta local; **a regressão na névoa**, com a janela completa e mais atributos, confirmando ou descartando o que a borda levantou. É a mesma divisão de responsabilidades que a Fase 3 já adota entre o ESP32 e o Node-RED.

## 6. Limitações

As séries são sintéticas e reproduzíveis pela semente 20260806 — reproduzem o modelo do nosso wearable, não a variabilidade de uma população real. O rótulo vem da regra do firmware, de modo que os modelos aprendem a imitar essa regra e não um diagnóstico médico independente. O LIF é um único neurônio, não uma rede: uma camada com vários neurônios de constantes de tempo diferentes cobriria episódios de durações distintas, e é o passo natural seguinte. Por fim, a comparação de custo conta operações aritméticas, que é uma aproximação grosseira de consumo energético real.

---

*Documento sob licença CC BY 4.0 — Grupo Purkinje, FIAP 2026.*
