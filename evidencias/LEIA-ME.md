# Evidências

O enunciado exige, na Parte 2, "prints evidenciando a aplicação **ou** export do
dashboard no Node-RED". Entregamos os dois.

## Arquivos desta pasta

| Arquivo | O que mostra |
|---|---|
| `dashboard_normal.png` | Operação normal: LED virtual verde, 53 bpm em repouso, 36,6 °C, dispositivo ONLINE, fila zerada e nenhum evento no histórico |
| `dashboard_alerta.png` | Alerta clínico: LED vermelho, TAQUICARDIA, dois eventos já registrados no histórico |
| `dashboard_sync.png` | Resiliência: a legenda mostra as duas séries, *FC ao vivo* e *FC sincronizada*; a linha azul são as amostras recuperadas do buffer, e o histórico traz o mesmo evento com origem `sincronizado` |
| `circuito_wokwi.png` | Circuito montado: DHT22, MPU6050, botões PULSO e ENLACE, LEDs de alerta e de enlace |
| `circuito_alerta.png` | O mesmo circuito com o **LED ALERTA aceso em vermelho**: a decisão clínica tomada na borda, antes de qualquer pacote sair para a nuvem |
| `circuito_sincronizacao.png` | Circuito no momento da reconexão, com o LED ONLINE restabelecido |
| `flows_exportado.json` | Export completo do flow (menu ☰ → Export → All flows → Download), 22 nós |

## Sobre o Monitor Serial

O firmware imprime cada amostra no Serial com o destino explícito (`ENVIO`,
`BUFFER`, `SYNC-C`, `SYNC-R`), conforme o enunciado da Parte 1 pede. A versão
atual da interface web do Wokwi, porém, não expõe o painel de Monitor Serial:
o container da simulação contém apenas os controles, o cronômetro e o
visualizador do circuito. Verificamos a árvore de componentes da página para
confirmar que não se trata de painel recolhido nem de limitação de altura.

Isso não compromete a evidência de resiliência offline, por dois motivos. O
enunciado não exige print do Serial em nenhuma das duas partes. E a mesma
informação chega ao dashboard pela telemetria: o campo `backlog` do payload
alimenta o contador "Amostras aguardando sincronizacao", e as amostras
recuperadas chegam pelo tópico `/historico`, aparecendo no gráfico como a série
separada *FC sincronizada*. O print `dashboard_sync.png` mostra o buffer sendo
drenado de forma mais legível do que o texto do terminal mostraria.

Em um ESP32 físico, com `USAR_SPIFFS` em 1, o mesmo firmware grava as leituras
em `/cardioia.csv` e apaga o arquivo ao concluir a sincronização.

## Como reproduzir a cena de sincronização

1. Com a simulação rodando e o pulso sendo tocado, pressione o botão **ENLACE**
   (azul). O LED verde ONLINE apaga.
2. Continue tocando o PULSO por 20 a 30 segundos. As amostras vão para o buffer.
3. Pressione **ENLACE** novamente. O dispositivo drena o backlog em lotes,
   críticas primeiro.
4. No dashboard, o gráfico ganha a série *FC sincronizada* e o contador da fila
   sobe e volta a zero. Capture nesse momento.
