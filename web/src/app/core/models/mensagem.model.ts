export type PapelMensagem = 'usuario' | 'assistente';

export type TipoAnexo = 'sql' | 'doc' | 'docx' | 'csv' | 'xls' | 'xlsx' | 'txt' | 'png' | 'jpg' | 'jpeg';

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
}
