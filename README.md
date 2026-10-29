# DocAuth AI - Prototipo Academico

Aplicacao Web para apoio a verificacao de autenticidade de documentos institucionais.

## Credenciais de demonstracao

- Administrador: `admin@example.com` / `admin123`
- Funcionario: `funcionario@example.com` / `func123`
-

## Como executar

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python run.py
```

Depois abra `http://127.0.0.1:5000`.

## Observacao sobre OCR

Para imagens JPG/PNG e PDFs digitalizados, a aplicacao usa o Tesseract. O caminho
`C:\Program Files\Tesseract-OCR\tesseract.exe` e detetado automaticamente; se o
Tesseract estiver noutro local, defina `TESSERACT_CMD` com o caminho do executavel.
As dependencias Python para renderizar PDFs digitalizados sao instaladas por
`requirements.txt`. PDFs com texto embutido continuam a usar essa camada de texto
diretamente. O OCR de PDFs esta limitado as primeiras 3 paginas por predefinicao.
Para melhor reconhecimento de documentos em portugues, instale tambem os dados
de idioma `por` do Tesseract; sem eles, o OCR recorre ao idioma `eng`.
Na pagina de resultado, use **Reanalisar com regras atualizadas** para atualizar
analises antigas e, se necessario, selecionar o modelo original correto. O numero
do certificado, o numero de processo e o numero do documento de identificacao sao
apresentados separadamente; a consulta ao registro oficial usa o numero do certificado.

## Estrutura

- `app/models.py`: modelo relacional.
- `app/routes/`: rotas da aplicacao.
- `app/services/`: OCR, processamento, risco e relatorios.
- `app/templates/`: interface Web.
- `uploads/`: documentos carregados localmente.
