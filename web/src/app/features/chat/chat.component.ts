import { Component, ElementRef, OnDestroy, ViewChild, inject, signal, afterNextRender, Injector } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatTooltipModule } from '@angular/material/tooltip';
import { TextFieldModule } from '@angular/cdk/text-field';
import { Subscription } from 'rxjs';

import { Anexo, MensagemHistorico, Mensagem, TipoAnexo } from '../../core/models/mensagem.model';
import { AgentePromptService } from '../../core/services/agente-prompt.service';

const EXTENSOES_ACEITAS: TipoAnexo[] = [
  'sql', 'doc', 'docx', 'csv', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg',
];

const DELAY_IMPLEMENTANDO_MS = 6000;

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
export class ChatComponent implements OnDestroy {
  @ViewChild('inputArquivo') inputArquivo!: ElementRef<HTMLInputElement>;
  @ViewChild('areaMensagens') areaMensagens!: ElementRef<HTMLDivElement>;

  private readonly agentePromptService = inject(AgentePromptService);
  private readonly injector = inject(Injector);
  private subscricaoAtiva: Subscription | null = null;
  private timeoutImplementando: ReturnType<typeof setTimeout> | null = null;

  readonly mensagens = signal<Mensagem[]>([]);
  readonly anexosPendentes = signal<Anexo[]>([]);
  readonly textoInput = signal<string>('');
  readonly carregando = signal<boolean>(false);
  readonly conversaFinalizada = signal<boolean>(false);
  readonly faseBubble = signal<'pensando' | 'implementando'>('pensando');

  readonly formatosAceitos = EXTENSOES_ACEITAS.map(ext => `.${ext}`).join(',');

  aoEnviar(): void {
    const conteudo = this.textoInput().trim();
    const anexos = this.anexosPendentes();

    if ((!conteudo && anexos.length === 0) || this.carregando() || this.conversaFinalizada()) return;

    const historico: MensagemHistorico[] = this.mensagens().map(m => ({
      papel: m.papel,
      conteudo: m.conteudo,
    }));

    const mensagemUsuario: Mensagem = {
      id: crypto.randomUUID(),
      papel: 'usuario',
      conteudo,
      anexos,
      criadoEm: new Date(),
    };

    this.mensagens.update(anterior => [...anterior, mensagemUsuario]);
    this.textoInput.set('');
    this.anexosPendentes.set([]);
    this.carregando.set(true);
    this.faseBubble.set('pensando');
    this.timeoutImplementando = setTimeout(
      () => this.faseBubble.set('implementando'),
      DELAY_IMPLEMENTANDO_MS,
    );
    this.rolarParaFinal();

    this.subscricaoAtiva = this.agentePromptService
      .enviarMensagem({ mensagem: conteudo, historico })
      .subscribe({
        next: resposta => {
          this.limparTimeoutImplementando();
          const mensagemAssistente: Mensagem = {
            id: crypto.randomUUID(),
            papel: 'assistente',
            conteudo: resposta.resposta,
            anexos: [],
            criadoEm: new Date(),
            markdownFinal: resposta.markdown_final ?? undefined,
          };
          this.mensagens.update(anterior => [...anterior, mensagemAssistente]);
          this.carregando.set(false);
          this.faseBubble.set('pensando');
          this.rolarParaFinal();

          if (resposta.fase === 'implementado') {
            this.conversaFinalizada.set(true);
            setTimeout(() => window.location.reload(), 3000);
          } else if (resposta.fase === 'finalizado') {
            this.conversaFinalizada.set(true);
          }
        },
        error: () => {
          this.limparTimeoutImplementando();
          this.carregando.set(false);
          this.faseBubble.set('pensando');
        },
      });
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

  private rolarParaFinal(): void {
    afterNextRender(() => {
      const el = this.areaMensagens?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    }, { injector: this.injector });
  }

  novaConversa(): void {
    this.limparTimeoutImplementando();
    this.mensagens.set([]);
    this.anexosPendentes.set([]);
    this.textoInput.set('');
    this.carregando.set(false);
    this.conversaFinalizada.set(false);
    this.faseBubble.set('pensando');
    this.subscricaoAtiva?.unsubscribe();
    this.subscricaoAtiva = null;
  }

  baixarMarkdown(conteudo: string): void {
    const blob = new Blob([conteudo], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `prompt-engenharia-${Date.now()}.md`;
    link.click();
    URL.revokeObjectURL(url);
  }

  formatarTamanho(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  ngOnDestroy(): void {
    this.limparTimeoutImplementando();
    this.subscricaoAtiva?.unsubscribe();
  }

  private limparTimeoutImplementando(): void {
    if (this.timeoutImplementando !== null) {
      clearTimeout(this.timeoutImplementando);
      this.timeoutImplementando = null;
    }
  }

  private extrairExtensao(nomeArquivo: string): TipoAnexo {
    const ext = nomeArquivo.split('.').pop()?.toLowerCase() as TipoAnexo;
    return EXTENSOES_ACEITAS.includes(ext) ? ext : 'txt';
  }
}
