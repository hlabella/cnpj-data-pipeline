# Requirements Structure

This directory contains modular requirements files for different database backends and deployment scenarios.

## Files

- **`base.txt`** - Core dependencies required by all configurations
- **`postgres.txt`** - PostgreSQL database adapter (default)
- **`mysql.txt`** - MySQL database adapter (placeholder for future implementation)
- **`bigquery.txt`** - BigQuery database adapter (placeholder for future implementation)

## Installation

### Default (PostgreSQL)
```bash
pip install -r requirements.txt
# or
pip install -r requirements/postgres.txt
```

### MySQL (when implemented)
```bash
pip install -r requirements/mysql.txt
```

### BigQuery (when implemented)
```bash
pip install -r requirements/bigquery.txt
```

## Adding New Dependencies

- Add core dependencies to `base.txt`
- Add database-specific dependencies to the appropriate backend file
- Update version constraints consistently across files
