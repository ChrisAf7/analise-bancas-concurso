# SETUP_IA — O que você precisa configurar (uma vez, ~10 min)

O projeto usa **só planos gratuitos**. Nenhum dos passos abaixo pede cartão de crédito. **Não ative
faturamento (billing)** em nenhum provedor: sem faturamento, não há como ser cobrado.

As chaves ficam no arquivo `.env` na raiz do projeto. Esse arquivo **nunca vai para o git**
(o repositório é público). Copie `.env.example` para `.env` e preencha.

## 1. Avaliador A — Google AI Studio (Gemini)

1. Entre em <https://aistudio.google.com/> com uma conta Google.
2. Abra a opção de chaves de API ("Get API key") e crie uma chave num projeto novo.
3. Cole no `.env`: `GEMINI_API_KEY=...`
4. Os limites gratuitos variam por modelo e por projeto. Eles aparecem na página de *rate limits*
   do próprio AI Studio. O pipeline respeita os limites com pausas automáticas.

Observação: no plano gratuito, o Google pode usar as entradas para melhorar os produtos. Aqui só
enviamos texto de provas públicas, então isso é aceitável.

## 2. Avaliador B — OpenRouter (modelos abertos `:free`)

1. Crie uma conta em <https://openrouter.ai/>. Login com Google ou GitHub serve.
2. Na área de chaves (*Keys*), crie uma chave.
3. Cole no `.env`: `OPENROUTER_API_KEY=...`
4. Use apenas modelos cujo ID termina em `:free`. Sem créditos comprados, o limite é de
   **20 requisições por minuto e 50 por dia**. Por isso o pipeline manda de 5 a 10 questões por
   requisição, o que dá mais de 250 questões por dia.
5. Se um modelo `:free` recusar a requisição por política de dados, habilite nas configurações de
   privacidade da conta a opção que permite endpoints gratuitos que podem usar os dados. Pelo mesmo
   motivo do item 1, isso é aceitável aqui.

## 3. (Opcional) Avaliador C — Ollama, local

Só se você quiser um terceiro avaliador, sem limite e offline. Instale pelo site <https://ollama.com/>
e rode `ollama pull` do modelo indicado em `config/models.toml`. Nesta máquina (16 GB de RAM, sem GPU
dedicada detectada) ele vai ser **lento**. Não é necessário para o MVP.

## 4. Git: proteger seu e-mail no repositório público

O seu `git config` global usa o e-mail pessoal, e num repositório público ele fica visível em todo
commit. Antes do primeiro commit, rode **dentro desta pasta**:

```
git config user.name "Seu Nome"
git config user.email "SEU_ID+SEU_USUARIO@users.noreply.github.com"
```

O endereço *noreply* exato aparece no GitHub em *Settings → Emails*, com a opção "Keep my email
addresses private". Essa configuração vale só para este repositório.

## 5. Conferência

Depois de preencher o `.env`, me avise. O primeiro passo do MVP (spike) faz uma chamada de teste a
cada provedor e registra no `config/models.toml` os modelos gratuitos disponíveis naquele dia.
