# Publicar uma versão do RH Fácil no GitHub

Repositório configurado no RH Fácil: `JoaoTrindade-redes/RhFacil.API`

## Primeira configuração

1. Clone o repositório vazio:

```bash
git clone git@github.com:JoaoTrindade-redes/RhFacil.API.git
cd RhFacil.API
```

2. Copie os arquivos do projeto RH Fácil para dentro do repositório.
3. Faça o primeiro commit e envie para o GitHub.
4. Gere o executável Windows com `1_GERAR_EXECUTAVEL.bat`.
5. Publique uma Release com a mesma versão do programa, por exemplo `v0.3.7`.

## Para cada nova versão

1. Atualize `VERSION` em `app.py`.
2. Atualize `version_info.txt`.
3. Gere com `1_GERAR_EXECUTAVEL.bat`.
4. Crie uma Release no GitHub usando a mesma versão como tag, por exemplo `v0.3.8`.
5. Anexe o ZIP gerado:

```text
RH_Facil_v0.3.8_Portatil_Windows_x64.zip
```

6. Publique a Release.

O RH Fácil consulta a Release mais recente pela API pública do GitHub. O asset precisa seguir o padrão de nome acima para ser reconhecido pelo atualizador.

## Importante

- Não coloque o banco de dados real dos clientes no ZIP da Release.
- Não coloque tokens ou senhas do GitHub no programa.
- Não reutilize uma tag de versão já publicada; publique uma nova versão.
- Teste a nova versão localmente antes de publicar.
- O repositório precisa ter uma Release publicada para o atualizador encontrar uma versão.
- O arquivo de atualização deve conter `RH Facil.exe` e `RH Facil Updater.exe`.
