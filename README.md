# Remove BG API

API HTTP para remoção de fundo de imagens com FastAPI e `rembg`. O projeto pode ser publicado diretamente no Render ou em outro provedor compatível com Docker, sem depender de Cloudflare Tunnel ou de um computador local ligado.

## Endpoint

```http
POST /remove-background
Content-Type: multipart/form-data
```

O arquivo deve ser enviado no campo `file`. A resposta é uma imagem PNG com transparência.

```bash
curl -X POST "http://localhost:8000/remove-background" \
  -H "X-API-Key: SUA_CHAVE" \
  -F "file=@foto.jpg" \
  --output foto-sem-fundo.png
```

O cabeçalho `X-API-Key` só é obrigatório quando a variável de ambiente `API_KEY` estiver configurada.

## Execução com Docker

```bash
docker build -t remove-bg .
docker run --rm -p 8000:8000 -e API_KEY="SUA_CHAVE" remove-bg
```

Depois, acesse:

- API: `http://localhost:8000/`
- Health check: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

## Deploy no Render

O repositório inclui um `render.yaml`. No Render:

1. Escolha **New Blueprint**.
2. Conecte este repositório.
3. Confirme a criação do serviço `movex-remove-bg`.
4. Aguarde o build do Docker e verifique se `/health` responde com `status: ok`.
5. Copie a URL pública e configure o backend principal para chamar `https://SEU-SERVICO/remove-background`.
6. Copie o valor gerado para `API_KEY` e configure o backend principal para enviá-lo em `X-API-Key`.

O modelo leve `u2netp` é baixado durante a construção da imagem Docker. Isso evita o download do modelo toda vez que o serviço reiniciar e reduz o consumo de memória para permitir o teste no plano gratuito.

## Variáveis de ambiente

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `PORT` | `8000` | Porta HTTP. Normalmente definida pelo provedor. |
| `REMBG_MODEL` | `u2netp` | Modelo utilizado pelo `rembg`. |
| `MAX_UPLOAD_MB` | `10` | Tamanho máximo da imagem recebida. |
| `MAX_CONCURRENT_JOBS` | `1` | Quantidade de processamentos simultâneos. |
| `WEB_CONCURRENCY` | `1` | Quantidade de workers Uvicorn. Mantenha `1` em planos com pouca memória. |
| `OMP_NUM_THREADS` | `1` | Limita as threads usadas pelo ONNX Runtime. |
| `API_KEY` | vazio | Se preenchida, protege o endpoint com `X-API-Key`. |
| `CORS_ORIGINS` | vazio | Origens permitidas, separadas por vírgula, se houver chamada direta de navegador. |
| `LOG_LEVEL` | `INFO` | Nível dos logs. |

## Memória

O Blueprint começa com `plan: free` e `u2netp` para testar em 512 MB de RAM. O processamento pode ser lento por causa do limite de CPU. Se a qualidade do recorte não for suficiente, altere o modelo para `u2net`; nesse caso, use preferencialmente uma instância com pelo menos 2 GB de RAM.

## Integração com o backend

```python
import os
import requests

response = requests.post(
    os.environ["REMOVE_BG_URL"],
    files={"file": (filename, image_bytes, content_type)},
    headers={"X-API-Key": os.environ["REMOVE_BG_API_KEY"]},
    timeout=120,
)
response.raise_for_status()
png_bytes = response.content
```

Não armazene `API_KEY` no repositório. Configure-a apenas nas variáveis de ambiente do serviço de remoção e do backend principal.
