import { Component, ElementRef, signal, ViewChild } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatTooltipModule } from '@angular/material/tooltip';
import { TextFieldModule } from '@angular/cdk/text-field';
import { Anexo, Mensagem, TipoAnexo } from '../../core/models/mensagem.model';

const EXTENSOES_ACEITAS: TipoAnexo[] = [
  'sql', 'doc', 'docx', 'csv', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg',
];

@Component({
  selector: 'app-chat',
  imports: [
    DatePipe,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatTooltipModule,
    TextFieldModule,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent {
  @ViewChild('inputArquivo') inputArquivo!: ElementRef<HTMLInputElement>;

  readonly mensagens = signal<Mensagem[]>([]);
  readonly anexosPendentes = signal<Anexo[]>([]);
  readonly textoInput = signal<string>('');

  readonly formatosAceitos = EXTENSOES_ACEITAS.map(ext => `.${ext}`).join(',');

  aoEnviar(): void {
    const conteudo = this.textoInput().trim();
    const anexos = this.anexosPendentes();

    if (!conteudo && anexos.length === 0) return;

    const mensagem: Mensagem = {
      id: crypto.randomUUID(),
      papel: 'usuario',
      conteudo,
      anexos,
      criadoEm: new Date(),
    };

    this.mensagens.update(anterior => [...anterior, mensagem]);
    this.textoInput.set('');
    this.anexosPendentes.set([]);
  }

  aoPressionarTecla(evento: KeyboardEvent): void {
    if (evento.key === 'Enter' && !evento.shiftKey) {
      evento.preventDefault();
      this.aoEnviar();
    }
  }

  aoSelecionarArquivo(evento: Event): void {
    const input = evento.target as HTMLInputElement;
    if (!input.files) return;

    const arquivos = Array.from(input.files);
    const anexos: Anexo[] = arquivos.map(arquivo => ({
      nome: arquivo.name,
      tipo: this.extrairExtensao(arquivo.name),
      tamanho: arquivo.size,
    }));

    this.anexosPendentes.update(anterior => [...anterior, ...anexos]);
    input.value = '';
  }

  removerAnexo(indice: number): void {
    this.anexosPendentes.update(anterior => anterior.filter((_, i) => i !== indice));
  }

  abrirSeletorArquivo(): void {
    this.inputArquivo.nativeElement.click();
  }

  formatarTamanho(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private extrairExtensao(nomeArquivo: string): TipoAnexo {
    const ext = nomeArquivo.split('.').pop()?.toLowerCase() as TipoAnexo;
    return EXTENSOES_ACEITAS.includes(ext) ? ext : 'txt';
  }
}
