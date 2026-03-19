export type PapelMensagem = 'usuario' | 'assistente';

export type TipoAnexo = 'sql' | 'doc' | 'docx' | 'csv' | 'xls' | 'xlsx' | 'txt' | 'png' | 'jpg' | 'jpeg';

export type FaseAgente = 'coletando' | 'finalizado' | 'implementado';

export interface Anexo {
  nome: string;
  tipo: TipoAnexo;
  tamanho: number;
}

export interface Mensagem {
  id: string;
  papel: PapelMensagem;
  conteudo: string;
  anexos: Anexo[];
  criadoEm: Date;
  markdownFinal?: string;
}

export interface MensagemHistorico {
  papel: PapelMensagem;
  conteudo: string;
}

export interface EntradaAgente {
  mensagem: string;
  historico: MensagemHistorico[];
}

export interface RespostaAgente {
  resposta: string;
  fase: FaseAgente;
  markdown_final: string | null;
  prompt_engenharia: string | null;
  arquivos_implementados: string[];
}
