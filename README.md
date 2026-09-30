# RH Fácil — v0.3.7

Versão de **Estabilidade e Usabilidade** do sistema de gestão de admissões.

## O que mudou nesta versão

- Exclusão de admissões com confirmação e escolha de manter ou excluir o PDF.
- **Lixeira** com restauração e retenção de 30 dias antes da exclusão definitiva.
- Histórico do cadastro: criação, alterações, geração de PDF, exclusão e restauração.
- Detecção de CPF duplicado antes de salvar.
- Dashboard com admissões do mês, rascunho, total de fichas e último backup.
- Salvamento automático do rascunho com atraso de aproximadamente 650 ms após a última alteração.
- Consultas ViaCEP e IBGE executadas em segundo plano, evitando congelar a janela.
- Município não encontrado: opção **Outra cidade...** para informar manualmente.
- Nascimento de trabalhador estrangeiro não bloqueia a etapa quando UF/cidade de nascimento não forem informadas.
- Campos condicionais passam a aparecer/desaparecer sem reconstruir a etapa inteira.
- Setas ↑/↓ navegam entre campos; ←/→ continuam disponíveis para cursor/texto.
- Índices SQLite para CPF, nome, função e data de admissão; SQLite com WAL, foreign keys e busy timeout.
- Tabela de admissões com visual mais consistente e menu lateral destacando a tela atual.
- Mensagens de sucesso importantes aparecem também na barra de status.
- Botão **IMPRIMIR** para fichas PDF.
- **RESTAURAR BACKUP**, criando automaticamente um backup de segurança antes da restauração.
- Revisões de escala/DPI para notebooks menores e Windows com 125%/150%.


## Atualização automática

A v0.3.7 adiciona um mecanismo de atualização via **GitHub Releases**. O aplicativo consulta a última Release em segundo plano ao abrir, compara a versão instalada e, quando houver uma versão mais nova, oferece o download e a instalação.

O processo usa dois executáveis na pasta do programa:

- `RH Facil.exe` — aplicativo principal.
- `RH Facil Updater.exe` — atualizador separado, usado depois que o aplicativo principal é fechado.

O pacote de atualização é um `.zip` publicado como asset da Release, com nome no formato `RH_Facil_vX.Y.Z_Portatil_Windows_x64.zip`. O GitHub informa o digest SHA-256 do asset, e o RH Fácil valida esse digest antes de aplicar o pacote.

### Configuração do repositório

Abra **Configurações → Atualizações** e informe o repositório público no formato `dono/repositorio` ou cole a URL do GitHub. Depois clique em **SALVAR REPOSITÓRIO**. A partir daí, o programa passa a consultar esse repositório a cada abertura.

O repositório padrão desta versão já está configurado como `JoaoTrindade-redes/RhFacil.API` em `atualizador.py`.

### Publicar uma nova versão

1. Altere a versão no `app.py` e `version_info.txt`.
2. Gere o executável com `1_GERAR_EXECUTAVEL.bat`.
3. Crie uma Release no GitHub com a tag correspondente, por exemplo `v0.3.8`.
4. Anexe o arquivo `RH_Facil_v0.3.8_Portatil_Windows_x64.zip`.
5. Publique a Release.
6. Na próxima abertura, os clientes que estiverem na v0.3.7 verão a atualização disponível.

A atualização substitui somente os arquivos do programa. O banco, fichas PDF, currículos, backups e demais dados ficam na pasta configurada em `Documentos\RH Fácil` e não fazem parte do processo de atualização.

## Mantido para versões futuras

- Banco de Currículos e pipeline de candidatos.
- Gestão completa de funcionários, férias, treinamentos, benefícios e desligamentos.
- Outras expansões de RH planejadas para a linha 0.4+.

## Estrutura de dados

Por padrão:

```text
RH Fácil\
├── Banco de Dados\rh_facil.db
├── Fichas PDF\
├── Currículos\
└── Backups\
```

O banco recebe migrações automáticas para manter compatibilidade com versões anteriores.

## Como executar

### Desenvolvimento

1. Instale Python 3.11 ou 3.12 de 64 bits.
2. Execute `pip install -r requirements.txt`.
3. Execute `python app.py` ou `iniciar.bat`.

### Executável Windows

Use `1_GERAR_EXECUTAVEL.bat` em um computador de compilação com Python 3.11/3.12 de 64 bits. O pacote gerado é uma pasta portátil e não exige Python no notebook de uso.

**Importante:** copie a pasta inteira gerada pelo PyInstaller, não apenas o EXE.
