/* =====================================================================
 *  CardioIA - Fase 3 - Monitoramento Continuo (IoT no Peito do Paciente)
 *  Grupo Purkinje - FIAP - Turma 2TIAOR-2026
 *
 *  tipos.h - estruturas de dados do firmware.
 *
 *  POR QUE ESTE ARQUIVO EXISTE
 *
 *  Os tipos poderiam estar no proprio .ino, mas nao funcionariam la. O
 *  pre-processador do Arduino gera automaticamente os prototipos de
 *  todas as funcoes do sketch e os insere no topo do arquivo, logo apos
 *  os #include. Uma funcao como
 *
 *      void buffer_push(BufferCircular& b, const Amostra& a)
 *
 *  teria seu prototipo emitido ANTES da definicao de BufferCircular, e a
 *  compilacao falha com "does not name a type". Movendo as estruturas
 *  para um cabecalho incluido no topo, elas passam a ser conhecidas
 *  antes dos prototipos gerados, e o problema desaparece.
 *
 *  Esse detalhe nao aparece em nenhuma analise estatica do codigo: so a
 *  compilacao real revela. Foi assim que o encontramos.
 * ===================================================================== */

#ifndef TIPOS_H
#define TIPOS_H

#include <Arduino.h>

/* Codigos de motivo. Guardados como 1 byte na amostra em vez de string:
 * economiza 15 bytes por registro, o que em 2880 registros representa
 * 43 KB - a diferenca entre caber e nao caber na SRAM. A traducao para
 * texto so acontece na hora de publicar. */
enum Motivo : uint8_t {
  M_NORMAL        = 0,
  M_TAQUICARDIA   = 1,
  M_BRADICARDIA   = 2,
  M_FEBRE         = 3,
  M_HIPOTERMIA    = 4,
  M_QUEDA         = 5,
  M_IMOBILIDADE   = 6,
  M_SINAL_AUSENTE = 7
};

/* 12 bytes por amostra. A temperatura vai como inteiro x10 (365 = 36,5 C)
 * porque float ocuparia 4 bytes e nao traria precisao util para um
 * termometro de +-0,5 C. */
struct Amostra {
  uint32_t t_s;        // segundos desde o boot
  uint16_t bpm;        // frequencia cardiaca (0 = sinal ausente)
  int16_t  temp_c10;   // temperatura em decimos de grau
  uint16_t mov_mg;     // magnitude de aceleracao em mili-g
  uint8_t  umid;       // umidade relativa em %
  uint8_t  motivo;     // codigo de Motivo
};

/* Buffer circular classico. Mantemos o contador de descartadas porque
 * perda silenciosa de dado clinico e inaceitavel: o numero e publicado
 * junto da telemetria e aparece no dashboard. */
struct BufferCircular {
  Amostra* dados;
  uint16_t capacidade;
  uint16_t inicio;
  uint16_t qtd;
  uint32_t descartadas;
};

#endif  // TIPOS_H
