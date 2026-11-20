"""Cliente único para provedores compatíveis com o protocolo da OpenAI (ADR-012).

Gemini (Google AI Studio), OpenRouter e Ollama expõem o mesmo endpoint de chat completions,
então provedor e modelo são configuração (config/models.toml), não código.

Uso rápido:  python -m concurso.llm smoke     # testa cada avaliador com uma questão sintética
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import tomllib
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .config import CONFIG, ROOT


@dataclass(frozen=True)
class Rater:
    name: str
    provider: str
    base_url: str
    api_key_env: str
    model: str
    rpm: float
    daily_limit: int = 0
    json_mode: bool = True


@dataclass
class LLMResult:
    data: dict
    raw: str
    model_reported: str          # o provedor pode resolver um alias para um ID mais específico
    latency_s: float
    usage: dict = field(default_factory=dict)


def load_raters(path=CONFIG / "models.toml") -> dict[str, Rater]:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    return {name: Rater(name=name, **spec) for name, spec in cfg["raters"].items()}


def parse_json(text: str) -> dict | None:
    """Aceita JSON puro, JSON dentro de cerca ```json ou o primeiro objeto {...} do texto."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidates = [text, fenced.group(1) if fenced else None]
    if "{" in text and "}" in text:
        candidates.append(text[text.index("{"): text.rindex("}") + 1])
    for c in candidates:
        if not c:
            continue
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


class LLMClient:
    def __init__(self, rater: Rater):
        load_dotenv(ROOT / ".env")
        self.rater = rater
        api_key = os.environ.get(rater.api_key_env) or ("ollama" if rater.provider == "ollama" else None)
        if not api_key:
            raise RuntimeError(f"Chave {rater.api_key_env} ausente no .env (ver docs/SETUP_IA.md)")
        # max_retries=0: o controle de novas tentativas e de ritmo é nosso (limites gratuitos são apertados)
        self.client = OpenAI(api_key=api_key, base_url=rater.base_url, max_retries=0, timeout=300)
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = self._last_call + 60.0 / self.rater.rpm - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def chat_json(self, system: str, user: str, max_attempts: int = 5) -> LLMResult:
        last_error: Exception | None = None
        for attempt in range(max_attempts):
            self._throttle()
            kwargs = dict(
                model=self.rater.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            if self.rater.json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            t0 = time.monotonic()
            try:
                resp = self.client.chat.completions.create(**kwargs)
            except RateLimitError as e:          # 429: limite por minuto ou diário
                last_error = e
                time.sleep(min(15 * 2 ** attempt, 300))
                continue
            except (APIConnectionError, APITimeoutError) as e:
                last_error = e
                time.sleep(10 * (attempt + 1))
                continue
            except APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    time.sleep(10 * (attempt + 1))
                    continue
                if e.status_code == 400 and self.rater.json_mode and "response_format" in str(e):
                    # alguns modelos não aceitam json_mode: tenta de novo pedindo JSON só pelo prompt
                    self.rater = Rater(**{**self.rater.__dict__, "json_mode": False})
                    last_error = e
                    continue
                raise
            latency = time.monotonic() - t0
            if not resp.choices:
                last_error = RuntimeError("resposta sem choices")
                continue
            text = resp.choices[0].message.content or ""
            data = parse_json(text)
            if data is None:
                last_error = ValueError(f"resposta não é JSON: {text[:200]!r}")
                continue
            usage = resp.usage.model_dump() if resp.usage else {}
            return LLMResult(data=data, raw=text, model_reported=resp.model or self.rater.model,
                             latency_s=round(latency, 1), usage=usage)
        raise RuntimeError(f"[{self.rater.name}] falhou após {max_attempts} tentativas: {last_error}")


# --- teste de fumaça -------------------------------------------------------------------------
# Questão SINTÉTICA, escrita para o teste (não é de nenhuma prova).
_SMOKE_SYSTEM = (
    "Você classifica questões de concurso. Responda SOMENTE com um objeto JSON com as chaves "
    '"cenario" ("sem_cenario" ou "cenario_hipotetico"), '
    '"demanda_cognitiva" ("recordar_texto", "reconhecer_conceito", "aplicar_a_fatos" ou "calcular_ou_contar") e '
    '"evidencia" (trecho curto do enunciado que justifica).'
)
_SMOKE_USER = """Questão:
Considere a seguinte situação hipotética: Marta, servidora de uma autarquia estadual, concedeu licença a um
particular sem observar a forma exigida em lei. Meses depois, a Administração identificou o vício, que é sanável
e não causou prejuízo a terceiros. Nesse caso, o ato
(A) deve ser obrigatoriamente revogado.
(B) pode ser convalidado pela própria Administração.
(C) é inexistente e não produz efeitos.
(D) só pode ser anulado pelo Poder Judiciário.
(E) torna-se válido automaticamente após 30 dias."""


def smoke(names: list[str] | None = None) -> int:
    raters = load_raters()
    failures = 0
    for name, rater in raters.items():
        if names and name not in names:
            continue
        try:
            r = LLMClient(rater).chat_json(_SMOKE_SYSTEM, _SMOKE_USER, max_attempts=3)
            print(f"[{name}] OK  modelo={r.model_reported}  {r.latency_s}s  -> {json.dumps(r.data, ensure_ascii=False)}")
        except Exception as e:  # noqa: BLE001 — é um diagnóstico, queremos ver qualquer falha
            failures += 1
            print(f"[{name}] FALHOU  modelo={rater.model}: {type(e).__name__}: {str(e)[:300]}")
    return failures


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 2 and sys.argv[1] == "smoke":
        sys.exit(1 if smoke(sys.argv[2:] or None) else 0)
    print(__doc__)
