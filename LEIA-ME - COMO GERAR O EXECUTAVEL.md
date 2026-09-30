# RH Fácil v0.3.7 — Kit para gerar o executável Windows

Este kit gera uma versão **autônoma/offline** do RH Fácil para Windows 11 64 bits.

A versão gerada NÃO baixa Python, NÃO executa `pip` no notebook da usuária e NÃO precisa de Python instalado na máquina final.

## Onde compilar

Faça a compilação em um computador com:

- Windows 10 ou Windows 11 de 64 bits;
- Python 3.11 ou 3.12 de 64 bits instalado;
- internet somente durante a compilação, para instalar PyInstaller e as bibliotecas;
- aproximadamente 1 GB livre para o ambiente de compilação.

Depois de compilado, o notebook onde sua esposa usará o RH Fácil não precisará de internet para iniciar o programa.

## Passo a passo

1. Extraia este ZIP para uma pasta normal, por exemplo:

   `C:\RH_Facil_Build`

2. Dê dois cliques em:

   `1_GERAR_EXECUTAVEL.bat`

3. Aguarde a mensagem **COMPILAÇÃO CONCLUÍDA**.

4. Para testar no mesmo computador, abra:

   `dist\RH Facil\RH Facil.exe`

   ou dê dois cliques em:

   `2_TESTAR_EXECUTAVEL.bat`

5. O processo também cria automaticamente:

   `RH_Facil_v0.3.7_Portatil_Windows_x64.zip`

6. Copie ESSE ZIP para o notebook Lenovo.

7. No Lenovo, extraia o ZIP inteiro e abra:

   `RH Facil.exe`

## Muito importante

Não envie somente `RH Facil.exe`.

A compilação utiliza o modo **one-folder**, então a pasta `RH Facil` contém o executável e todos os componentes do Python necessários para funcionar.

A estrutura ficará semelhante a:

```text
RH Facil\
├── RH Facil.exe
└── _internal\
    ├── python3xx.dll
    ├── customtkinter\
    ├── reportlab\
    └── ...
```

É isso que elimina o problema da versão anterior, que tentava baixar o ambiente na primeira abertura.

## Onde os dados ficam

Por padrão, os dados não ficam dentro da pasta do programa. Eles ficam em:

`Documentos\RH Fácil`

Com a estrutura:

```text
RH Fácil\
├── Banco de Dados\
│   └── rh_facil.db
├── Fichas PDF\
├── Currículos\
└── Backups\
```

O caminho pode ser alterado pelo próprio menu:

**CONFIGURAÇÕES → ARMAZENAMENTO**

## Se o Windows mostrar SmartScreen

Como este é um software próprio e ainda não possui certificado de assinatura de código, o Windows pode exibir:

**O Windows protegeu o computador**

Nesse caso:

1. Clique em **Mais informações**.
2. Confira se o arquivo é o `RH Facil.exe` que você acabou de compilar.
3. Clique em **Executar assim mesmo**.

## Se a compilação falhar

Execute:

`GERAR_COM_LOG.bat`

Ele criará:

`build_log.txt`

Envie esse arquivo ao ChatGPT para análise.

## Arquivos importantes do kit

- `app.py` — núcleo das telas e fluxo do RH Fácil v0.3.7
- `banco.py` — conexão e proteção SQLite
- `validacoes.py` — validações de CPF/CNPJ e normalização
- `widgets.py` — campos e componentes reutilizáveis
- `pdf.py` — utilitários da geração de PDF
- `armazenamento.py` — utilitários de arquivos/armazenamento
- `telas.py` — helpers visuais de navegação
- `rh_facil.db` — banco inicial
- `RH_Facil.spec` — configuração do PyInstaller
- `requirements-build.txt` — bibliotecas usadas no build
- `1_GERAR_EXECUTAVEL.bat` — compilação automática
- `2_TESTAR_EXECUTAVEL.bat` — abre o executável criado
- `GERAR_COM_LOG.bat` — compilação com diagnóstico
- `LIMPAR_BUILD.bat` — remove somente arquivos de compilação

## Recomendação

Para essa fase de testes, use a distribuição em pasta (`one-folder`). Ela costuma ser mais confiável para CustomTkinter e facilita encontrar problemas.

Quando o RH Fácil estiver estabilizado, o próximo passo pode ser criar um instalador tradicional do Windows com atalho no Menu Iniciar e na Área de Trabalho.
