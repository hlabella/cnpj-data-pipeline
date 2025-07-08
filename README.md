# 🇧🇷 CNPJ Data Pipeline

Pipeline modular para processar dados CNPJ da Receita Federal. Processa 60+ milhões de empresas brasileiras com suporte a múltiplos bancos de dados.

**[English version below](#-cnpj-data-pipeline-english)** 👇

## Características Principais

- **Arquitetura Modular**: Separação clara de responsabilidades com camada de abstração de banco de dados
- **Multi-Banco**: PostgreSQL e SQLite totalmente suportado, com placeholders para MySQL, BigQuery
- **Processamento Inteligente**: Adaptação automática da estratégia baseada em recursos disponíveis
- **Downloads Paralelos**: Estratégia configurável para otimizar velocidade de download
- **Processamento Incremental**: Rastreamento de arquivos processados para evitar duplicações
- **Performance Otimizada**: Operações bulk eficientes com tratamento de conflitos
- **Configuração Simples**: Setup interativo + variáveis de ambiente

## Início Rápido

```bash
# Clone o repositório
git clone https://github.com/cnpj-chat/cnpj-data-pipeline
cd cnpj-data-pipeline

# Opção 1: Setup interativo (recomendado)
make setup

# Opção 2: Setup manual
make install
make env
# Editar .env com suas configurações
make run
```

### Com Docker

```bash
# Iniciar PostgreSQL
make docker-db

# Executar pipeline
make docker-run

# Parar containers
make docker-stop

# Limpar tudo (containers + volumes)
make docker-clean
```

## Configuração (.env)

### Essencial

```bash
# Database
DATABASE_BACKEND=postgresql

# Future support
# DATABASE_BACKEND=mysql
# DATABASE_BACKEND=bigquery
# DATABASE_BACKEND=sqlite

# Performance
BATCH_SIZE=50000              # Batch size
MAX_MEMORY_PERCENT=80         # Max memory usage
```

### Otimizações

```bash
# Downloads
DOWNLOAD_STRATEGY=parallel    # ou sequential
DOWNLOAD_WORKERS=4           # Para downloads paralelos
KEEP_DOWNLOADED_FILES=false  # true economiza bandwidth em re-execuções

# Diretórios
TEMP_DIR=./temp              # Para arquivos temporários
```

## Agendamento Mensal

A Receita atualiza os dados mensalmente. Configure execução automática:

```bash
# Linux/Mac (cron) - dia 5 às 2h
0 2 5 * * cd /path/to/cnpj-pipeline && make run >> logs/scheduled.log 2>&1

# Ou use o scheduler da sua plataforma (Task Scheduler, Kubernetes CronJob, etc.)
```

## Arquitetura

```
cnpj-data-pipeline/
├── src/
│   ├── config.py            # Auto-detecção de recursos
│   ├── downloader.py        # Download com retry
│   ├── processor.py         # Parsing otimizado
│   ├── download_strategies/ # Sequential/Parallel
│   └── database/            # Abstração PostgreSQL
├── main.py                  # Entry point
├── setup.py                 # Assistente interativo
└── Makefile                 # Comandos úteis
```

## Fluxo de Processamento

1. **Descoberta**: Localiza dados mais recentes da Receita
2. **Download**: Baixa ZIPs com retry automático
3. **Processamento**: Parse otimizado dos CSVs
4. **Carga**: Bulk insert no PostgreSQL
5. **Rastreamento**: Marca arquivos processados

## Performance

| Sistema | Memória | Tempo Estimado |
|---------|---------|----------------|
| VPS básico | 4GB | ~6 horas |
| Servidor padrão | 16GB | ~2 horas |
| High-end | 64GB+ | ~1 hora |

## Comandos Úteis

```bash
make logs           # Ver logs recentes
make clean          # Limpar temporários
make clean-data     # Remover downloads (pede confirmação)
```

## Desenvolvimento

### Adicionando Novo Backend

1. Criar adapter em `src/database/seu_banco.py`
2. Implementar métodos abstratos de `DatabaseAdapter`
3. Registrar no factory em `src/database/factory.py`
4. Criar arquivo de requirements em `requirements/seu_banco.txt`

---

# 🇧🇷 CNPJ Data Pipeline (English)

Modular pipeline for processing Brazilian CNPJ (company registry) data. Processes 60+ million companies with optimized PostgreSQL support.

## Key Features

- **Smart Processing**: Auto-adapts to available resources
- **Advanced Filtering**: Filter by state, CNAE, and company size via CLI
- **Parallel Downloads**: Configurable strategy for optimized download speed
- **Incremental**: Tracks processed files
- **Optimized**: Efficient bulk operations
- **Easy Config**: Interactive setup + env vars

## Quick Start

```bash
# Clone repository
git clone https://github.com/cnpj-chat/cnpj-data-pipeline
cd cnpj-data-pipeline

# Option 1: Interactive setup (recommended)
make setup

# Option 2: Manual setup
make install
make env
# Edit .env with your settings
make run
```

### With Docker

```bash
# Start PostgreSQL
make docker-db

# Run pipeline
make docker-run

# Stop containers
make docker-stop

# Clean everything (containers + volumes)
make docker-clean
```


## Configuration (.env)

### Essential

```bash
# Database
DATABASE_BACKEND=postgresql

# Future support
# DATABASE_BACKEND=mysql
# DATABASE_BACKEND=bigquery
# DATABASE_BACKEND=sqlite

# Performance
BATCH_SIZE=50000              # Batch size
MAX_MEMORY_PERCENT=80         # Max memory usage
```

### Optimizations

```bash
# Downloads
DOWNLOAD_STRATEGY=parallel    # or sequential
DOWNLOAD_WORKERS=4           # For parallel downloads
KEEP_DOWNLOADED_FILES=false  # true saves bandwidth on re-runs

# Directories
TEMP_DIR=./temp              # For temporary files
```

## Monthly Scheduling

Government updates data monthly. Set up automatic execution:

```bash
# Linux/Mac (cron) - 5th day at 2 AM
0 2 5 * * cd /path/to/cnpj-pipeline && make run >> logs/scheduled.log 2>&1

# Or use your platform's scheduler (Task Scheduler, Kubernetes CronJob, etc.)
```

## Architecture

```
cnpj-data-pipeline/
├── src/
│   ├── config.py            # Resource auto-detection
│   ├── downloader.py        # Download with retry
│   ├── processor.py         # Optimized parsing
│   ├── filters/             # Filter system
│   ├── download_strategies/ # Sequential/Parallel
│   └── database/            # PostgreSQL abstraction
├── main.py                  # Entry point
├── setup.py                 # Interactive wizard
└── Makefile                 # Useful commands
```

## Processing Flow

1. **Discovery**: Finds latest government data
2. **Download**: Gets ZIPs with auto-retry
3. **Filtering**: Applies selected filters
4. **Processing**: Optimized CSV parsing
5. **Loading**: Bulk insert to PostgreSQL
6. **Tracking**: Marks processed files

## Performance

| System | Memory | Estimated Time |
|--------|--------|----------------|
| Basic VPS | 4GB | ~6 hours |
| Standard server | 16GB | ~2 hours |
| High-end | 64GB+ | ~1 hour |

## Useful Commands

```bash
make logs           # View recent logs
make clean          # Clean temporary files
make clean-data     # Remove downloads (asks confirmation)
```

---

Made with ❤️ for the Brazilian tech community
