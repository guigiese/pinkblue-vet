import React from 'react';
import { Box, Text, useInput } from 'ink';

interface Props {
  onBack: () => void;
}

export default function HelpScreen({ onBack }: Props) {
  useInput((_input, key) => {
    if (key.escape || _input === 'q') onBack();
  });

  return (
    <Box flexDirection="column" padding={1}>
      <Box borderStyle="round" borderColor="cyan" flexDirection="column" padding={1}>
        <Text bold color="cyan"> Ajuda — Folha de Pagamento PinkBlue Vet</Text>
        <Text> </Text>

        <Text bold>FLUXO RECOMENDADO</Text>
        <Text color="dim">  1. Coloque evidências em pool/inbox/[bucket]/</Text>
        <Text color="dim">  2. Abra Pool de Evidências → indexe → processe com IA</Text>
        <Text color="dim">  3. Revise e aceite as extrações</Text>
        <Text color="dim">  4. Feche a folha e veja os resultados</Text>
        <Text> </Text>

        <Text bold>BUCKETS DO POOL</Text>
        <Text color="dim">  contabilidade/  → PDFs da contabilidade (folha CLT)</Text>
        <Text color="dim">  simplesvet/     → Exports do SimplesVet (comissões, vendas)</Text>
        <Text color="dim">  ponto/          → Arquivos de ponto bruto</Text>
        <Text color="dim">  whatsapp/       → Texto de WhatsApp com batidas/horários</Text>
        <Text color="dim">  imagens/        → Fotos de ponto, recibos (OCR futuro)</Text>
        <Text color="dim">  manual/         → Planilhas manuais (.xlsx, .csv)</Text>
        <Text color="dim">  outros/         → Qualquer outro arquivo</Text>
        <Text> </Text>

        <Text bold>TELAS E ATALHOS</Text>
        <Text color="dim">  Resultados      ↑↓ navegar  Enter detalhar  r recalcular</Text>
        <Text color="dim">  Pool            ↑↓ navegar  p processar com IA</Text>
        <Text color="dim">                  i indexar pool  a aceitar  x rejeitar</Text>
        <Text color="dim">  Revisão IA      ↑↓ navegar  e editar entrada</Text>
        <Text color="dim">                  a aceitar todos  x rejeitar</Text>
        <Text color="dim">  Edição          ↑↓ campo  Enter editar campo  s salvar  Esc voltar</Text>
        <Text color="dim">  Fechar folha    Roda automaticamente ao entrar</Text>
        <Text> </Text>

        <Text bold>MODOS DE REMUNERAÇÃO</Text>
        <Text color="dim">  valor_importado         CLT — salário bruto importado</Text>
        <Text color="dim">  horista                 horas × valor-hora</Text>
        <Text color="dim">  comissao_percentual     base × percentual</Text>
        <Text color="dim">  comissao_com_piso_diario comissão ou piso, o maior</Text>
        <Text> </Text>

        <Text bold>CATEGORIAS DE LANÇAMENTO</Text>
        <Text color="green">  Proventos: valor_importado · horas_trabalhadas · producao_vet</Text>
        <Text color="green">             comissao_tosa · bonus_manual · credito_manual · reembolso</Text>
        <Text color="red">  Descontos: adiantamento · consumo_em_aberto · desconto_manual</Text>
        <Text color="red">             falha_veterinaria</Text>
        <Text> </Text>

        <Text bold>ARQUIVOS DE SAÍDA</Text>
        <Text color="dim">  saida/resultado.json    resultado completo estruturado</Text>
        <Text color="dim">  saida/resultado.md      relatório legível</Text>
        <Text color="dim">  saida/resultado.csv     tabela resumida</Text>
        <Text color="dim">  saida/memoria_calculo.csv  trilha de cada cálculo</Text>
        <Text> </Text>

        <Text color="dim">  q / Esc  voltar ao menu</Text>
      </Box>
    </Box>
  );
}
