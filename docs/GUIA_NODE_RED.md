# Guia de instalação e execução do Node-RED

**CardioIA — Fase 3 — Grupo Purkinje**

Este guia leva do zero ao dashboard funcionando. Tempo estimado: 10 minutos.

---

## 1. Pré-requisito: Node.js

O Node-RED roda sobre Node.js 18 ou superior. Verifique:

```bash
node --version
npm --version
```

Se não estiver instalado, baixe a versão LTS em <https://nodejs.org>. No Windows, aceite a opção de adicionar ao PATH.

## 2. Instalar o Node-RED

```bash
npm install -g --unsafe-perm node-red
```

No Windows, abra o PowerShell **como administrador** para este comando.

## 3. Iniciar

```bash
node-red
```

Deixe esse terminal aberto — fechá-lo encerra o servidor. A saída termina com algo como:

```
Server now running at http://127.0.0.1:1880/
```

Abra **<http://localhost:1880>** no navegador. Essa é a tela de edição.

## 4. Instalar a paleta do dashboard

O flow usa widgets que não vêm na instalação base.

1. Menu (☰, canto superior direito) → **Manage palette**
2. Aba **Install**
3. Buscar `node-red-dashboard`
4. Clicar em **Install** no resultado `node-red-dashboard` e confirmar

Alternativa por linha de comando:

```bash
cd ~/.node-red
npm install node-red-dashboard
# reinicie o node-red depois
```

> **Só isso.** O flow foi montado de propósito para depender apenas do `node-red-dashboard`. O LED de alerta e a tabela de eventos foram feitos com `ui_template` em vez de nós de terceiros, justamente para você não ter de caçar módulos.

## 5. Importar o flow

1. Menu (☰) → **Import**
2. Clicar em **select a file to import**
3. Escolher `nodered/flows.json` deste repositório
4. Clicar em **Import**
5. Clicar em **Deploy** (botão vermelho, canto superior direito)

Os quatro nós MQTT da esquerda devem exibir, em poucos segundos, um quadradinho verde com a palavra **connected**. Se aparecer *connecting* e não mudar, veja a seção 8.

## 6. Abrir o dashboard

**<http://localhost:1880/ui>**

Você verá três grupos:

- **Sinais vitais em tempo real** — gráfico de frequência cardíaca, gauge de temperatura, gauge de umidade
- **Alertas e estado do enlace** — LED virtual, fila de sincronização, estado do dispositivo
- **Histórico de eventos clínicos** — tabela das 20 últimas ocorrências

Enquanto o ESP32 não estiver publicando, o gráfico mostra *aguardando o dispositivo...*. É o comportamento esperado.

## 7. Ligar o ESP32

Com o Node-RED rodando, inicie a simulação no Wokwi. Em poucos segundos:

- o **estado do dispositivo** muda para `ONLINE — recebendo telemetria`
- os gauges saem do zero
- o gráfico começa a desenhar

Toque o botão **PULSO** (vermelho) no Wokwi num ritmo regular e veja a linha de frequência cardíaca responder.

## 8. Problemas comuns

**Os nós MQTT ficam em *connecting* e não conectam.**
Firewall ou proxy corporativo bloqueando a porta 1883 de saída. Teste em outra rede (um roteamento por celular resolve na maioria dos casos). Alternativa: usar a porta 8884 sobre WebSocket, marcando *Enable secure connection* e trocando o endereço para `wss://broker.hivemq.com:8884/mqtt` nas propriedades do broker — e, no firmware, manter 1883, pois o Wokwi não tem a mesma restrição.

**Conecta, mas nada aparece no painel.**
Confira se os tópicos batem. O firmware publica em `cardioia/purkinje/CARD-0056/...`, com `CARD-0056` vindo de `ID_PACIENTE` em `config.h`. Se você mudou o identificador, precisa mudar nos quatro nós MQTT também. Para diagnosticar, arraste um nó **debug** e ligue-o na saída de `telemetria (ao vivo)`: a aba Debug mostra o que está chegando.

**Aparecem dados de outro grupo.**
O broker é público e compartilhado. Se outro grupo usou o mesmo tópico, troque o segmento `purkinje` em `TOPICO_BASE` (config.h) e nos nós MQTT por algo exclusivo.

**`ui_template` renderiza o HTML como texto.**
A paleta `node-red-dashboard` não foi instalada ou o Node-RED não foi reiniciado depois da instalação. Volte à seção 4.

**`npm install -g` falha com erro de permissão (Linux/macOS).**
Use `sudo npm install -g --unsafe-perm node-red`.

**Porta 1880 já em uso.**
`node-red -p 1881` e acesse em `localhost:1881`.

## 9. Exportar o flow para a entrega

Para gerar a evidência de dashboard pedida no enunciado:

1. Menu (☰) → **Export**
2. Aba **All flows**
3. **Download** — salve como `nodered/flows_exportado.json` no repositório

E tire os prints do `/ui` com o dispositivo publicando, um deles durante um alerta ativo (LED vermelho) e outro durante a sincronização do backlog (contador da fila maior que zero). Guarde em `evidencias/`.

---

*Grupo Purkinje — FIAP 2TIAOR-2026 — CC BY 4.0*
