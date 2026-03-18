from github import Github

from app.core.configuracoes import configuracoes


class ServicoGitHub:
    def __init__(self) -> None:
        self._cliente = Github(configuracoes.github_token.get_secret_value())  # type: ignore[union-attr]
        self._repo = self._cliente.get_repo(configuracoes.github_repo)

    def criar_pull_request(
        self,
        nome_branch: str,
        titulo: str,
        descricao: str,
        arquivos: list[dict],
    ) -> str:
        branch_base = configuracoes.github_branch_base
        sha_base = self._repo.get_branch(branch_base).commit.sha

        self._repo.create_git_ref(f"refs/heads/{nome_branch}", sha_base)

        for arquivo in arquivos:
            self._repo.create_file(
                path=arquivo["caminho"],
                message=f"feat: adiciona {arquivo['caminho']}",
                content=arquivo["conteudo"],
                branch=nome_branch,
            )

        pr = self._repo.create_pull(
            title=titulo,
            body=descricao,
            head=nome_branch,
            base=branch_base,
        )

        return pr.html_url
