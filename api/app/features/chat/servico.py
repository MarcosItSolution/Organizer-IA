from app.features.chat.esquemas import MensagemEntrada, MensagemSaida


class ServicoChat:
    def processar_mensagem(self, mensagem: MensagemEntrada) -> MensagemSaida:
        return MensagemSaida(resposta=f"Mensagem recebida: {mensagem.texto}")
