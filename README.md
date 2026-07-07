<div align="center">

![Radar Concursos Banner](Radar%20Concursos.png)

# 🎯 Radar Concursos

### _Monitorando Oportunidades. Conectando Sonhos._

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![GitHub Actions](https://img.shields.io/badge/GitHub-Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/ispectr3/RadarConcursos/test.yml?style=for-the-badge&label=Tests)](https://github.com/ispectr3/RadarConcursos/actions/workflows/test.yml)
[![Dashboard](https://img.shields.io/badge/Dashboard-GitHub%20Pages-blue?style=for-the-badge)](https://ispectr3.github.io/RadarConcursos)

</div>

---

## 📡 Sobre

O **Radar Concursos** é um bot automatizado que monitora concursos públicos brasileiros. Ele escaneia 5+ fontes, extrai dados com IA (Gemini → Groq → Free API pool), e notifica via Telegram com resumo, salário, prazo de inscrição e link.

Tudo roda 100% grátis no GitHub Actions — sem servidor, sem cartão de crédito.

---

## ✨ Funcionalidades

| Recurso | Descrição |
|---|---|
| 🎯 **5 Fontes** | Ache Concursos, PCI Concursos, Folha Dirigida, Gran Cursos, Estratégia |
| 🤖 **IA Multi-camada** | Gemini → Groq → Free API (smart-chat) — fallback automático com rate limiting |
| 🔔 **Telegram** | Notificação com salário, prazo, resumo, link direto |
| 📬 **Email** | Notificação opcional via SMTP |
| 📊 **Dashboard Web** | FastAPI + GitHub Pages com estáticas, filtros e busca |
| 📅 **Google Calendar** | Cria eventos automaticamente com datas de prova/inscrição |
| 🔑 **Key Watcher** | Monitora keys free, auto-atualiza FREE_API_ENTRIES via API |
| 🧪 **Testes** | pytest com cobertura de urlnorm, models, scraping, formatter |
| ⚡ **CI/CD** | GitHub Actions: scan 6/6h + testes no push + deploy Pages |

---

## 🚀 Quick Start (GitHub Actions)

### 1. Fork / Clone

```bash
git clone https://github.com/ispectr3/RadarConcursos.git
cd RadarConcursos
```

### 2. Secrets no GitHub

Vá em **Settings → Secrets and variables → Actions → Secrets** e adicione:

| Secret | Obrigatório | Descrição |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token do [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | ✅ | Canal ou grupo (`@radarconcursosbr` ou chat ID) |
| `GEMINI_API_KEY` | ❌ (recomendado) | Chave da [Google AI Studio](https://aistudio.google.com) |
| `GROQ_API_KEY` | ❌ | Chave do [Groq Console](https://console.groq.com) |
| `FREE_API_ENTRIES` | ❌ | JSON array de keys do [free-llm-api-keys](https://github.com/alistaitsacle/free-llm-api-keys) |

> `FREE_API_ENTRIES` exemplo:
> ```json
> [{"key": "sk-xxx", "base_url": "https://aiapiv2.pekpik.com/v1", "model": "smart-chat"}]
> ```

Opcionais:
| Secret | Descrição |
|---|---|
| `KEYWATCH_CHAT_ID` | Seu chat ID pessoal (key watcher manda pra você, não pro canal) |
| `GH_TOKEN` | PAT com escopo `repo` — ativa **auto-update** do FREE_API_ENTRIES |
| `SMTP_*` | Config de email para notificações alternativas |

### 3. Rodar

**Actions → Radar Concursos → Run workflow**

O cron roda a cada 6h automaticamente.

---

## 🏠 Rodar Local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha suas credenciais
python main.py         # modo scheduler
# ou
python run_once.py     # um ciclo único
```

---

## 📁 Estrutura

```
RadarConcursos/
├── main.py                  # Scheduler + ciclo principal
├── run_once.py              # Um ciclo (GitHub Actions)
├── scraping.py              # 5 scrapers de editais
├── enrich.py                # IA: Gemini → Groq → Free API
├── notifications.py         # Telegram + Email
├── formatter.py             # Formatação das mensagens
├── storage.py               # SQLite CRUD
├── dashboard.py             # FastAPI (localhost)
├── generate_static_site.py  # Gera HTML estático para Pages
├── keywatch.py              # Monitor de keys free, auto-update
├── digest.py                # Resumo diário
├── calendar_integration.py  # Google Calendar
├── config.py                # Settings via .env
├── models.py                # Dataclass Edital
├── http_util.py             # HTTP helpers
├── urlnorm.py               # Normalização de URL
├── tests/                   # pytest (26 testes)
└── .github/workflows/
    ├── scraper.yml          # Scan 6/6h + deploy Pages
    ├── keywatch.yml         # Monitor keys 3/3h
    └── test.yml             # pytest no push
```

---

## 🗺️ Roadmap / Próximos

- [ ] **Dashboard público** ✅ via GitHub Pages
- [ ] **Testes automatizados** ✅ pytest
- [ ] **Auto-update FREE_API_ENTRIES** ✅ via Key Watcher
- [ ] **Dependabot** ✅ pip + actions
- [ ] **Google Calendar** — ver [guia](#-google-calendar)
- [ ] **Mais fontes** — PRs bem-vindos

---

## 📅 Google Calendar

1. Vá em [Google Cloud Console](https://console.cloud.google.com)
2. Crie um projeto → **APIs & Services → Credentials**
3. **Create Credentials → OAuth 2.0 Client IDs → Desktop Application**
4. Baixe o JSON e salve como `credentials.json`
5. Autorize:
   ```bash
   python -c "from calendar_integration import authenticate_google; authenticate_google()"
   ```
6. Cole o conteúdo de `token.pickle` (convertido para string) em `GOOGLE_CALENDAR_CREDS`

---

## 🔑 Key Watcher

O **Key Watcher** verifica o repositório [free-llm-api-keys](https://github.com/alistaitsacle/free-llm-api-keys) a cada 3h. Se detectar keys novas de `smart-chat`:

1. Te avisa no Telegram (privado, `KEYWATCH_CHAT_ID`)
2. Se `GH_TOKEN` estiver configurado, **atualiza automaticamente** o secret `FREE_API_ENTRIES`

---

## 🧪 Testes

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE).

---

## 📬 Contato

[@ispectr3](https://github.com/ispectr3) — issues e PRs são bem-vindos!
