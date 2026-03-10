import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { EntradaAgente, RespostaAgente } from '../models/mensagem.model';

const URL_BASE_API = 'http://localhost:8000/api/v1/engenheiro-prompt';

@Injectable({ providedIn: 'root' })
export class AgentePromptService {
  private readonly http = inject(HttpClient);

  enviarMensagem(entrada: EntradaAgente): Observable<RespostaAgente> {
    return this.http.post<RespostaAgente>(`${URL_BASE_API}/`, entrada);
  }
}
