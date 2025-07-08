#!/usr/bin/env python3
"""
Interactive setup wizard for CNPJ Data Pipeline.
Helps users configure their environment for the CNPJ data pipeline.
"""

import sys
from pathlib import Path
import os

def print_header():
    """Print the setup wizard header."""
    print("\n" + "=" * 50)
    print("CNPJ Data Pipeline - Setup Wizard")
    print("=" * 50 + "\n")


def detect_system_resources():
    """Detect and display system resources."""
    try:
        import psutil

        memory_gb = psutil.virtual_memory().total / (1024**3)
        cpu_count = psutil.cpu_count()
        print("System Resources Detected:")
        print(f"  Memory: {memory_gb:.1f} GB")
        print(f"  CPUs: {cpu_count}")
        return memory_gb, cpu_count
    except ImportError:
        print("Unable to detect system resources (psutil not installed)")
        return None, None

def get_database_configuration():
    """Get database configuration from user."""
    print("\nDatabase Configuration:")
    print("Currently supported backends: PostgreSQL, SQLite\n")

    backend = input("Select database backend [postgresql/sqlite] (default: postgresql): ") \
              .strip().lower() or "postgresql"

    if backend not in ("postgresql", "sqlite"):
        print("\nOther database backends are not yet implemented.")
        sys.exit(1)

    config = {"DATABASE_BACKEND": backend}

    if backend == "postgresql":
        print("\nPostgreSQL Configuration:")
        config.update({
            "POSTGRES_HOST": input("Host [localhost]: ").strip() or "localhost",
            "POSTGRES_PORT": input("Port [5432]: ").strip() or "5432",
            "POSTGRES_NAME": input("Database name [cnpj]: ").strip() or "cnpj",
            "POSTGRES_USER": input("User [postgres]: ").strip() or "postgres",
            "POSTGRES_PASSWORD": input("Password: ").strip(),
        })

    elif backend == "sqlite":
        print("\nSQLite Configuration:")
        db_file = input(f"SQLite file path [cnpj.db]: ").strip() or "cnpj.db"
        config["SQLITE_DB_FILE"] = db_file
        import sqlite3
        # path to initialization SQL script (same as postgres)
        init_script_path = os.path.join("init-db", "postgres.sql")
        # conect and 
        conn = sqlite3.connect(db_file)
        try:
            with open(init_script_path, "r", encoding="utf-8") as f:
                sql_script = f.read()

            # executescript() will run all statements in the file
            conn.executescript(sql_script)
            print(f"Initialized database with {init_script_path}")
        finally:
            conn.close()


    return config

def get_processing_configuration(memory_gb=None, cpu_count=None):
    """Get processing configuration."""
    print("\nProcessing Configuration:")

    if memory_gb is not None:
        if memory_gb < 8:
            strategy = "memory_constrained"
            print(f"  Recommended: Memory Constrained (you have {memory_gb:.1f}GB RAM)")
        elif memory_gb < 32:
            strategy = "high_memory"
            print(f"  Recommended: High Memory (you have {memory_gb:.1f}GB RAM)")
        else:
            strategy = "distributed"
            print(f"  Recommended: Distributed (you have {memory_gb:.1f}GB RAM)")

        use_recommended = (
            input("\nUse recommended strategy? (y/n) [y]: ").lower().strip()
        )
        if use_recommended in ["", "y", "yes"]:
            return {"PROCESSING_STRATEGY": strategy}

    print("\nAvailable strategies:")
    print("  1. memory_constrained - For systems with <8GB RAM")
    print("  2. high_memory - For systems with 8-32GB RAM")
    print("  3. distributed - For systems with >32GB RAM")
    print("  4. auto - Automatically detect (default)")

    choice = input("\nEnter choice (1-4) [4]: ").strip()
    strategies = {
        "1": "memory_constrained",
        "2": "high_memory",
        "3": "distributed",
        "4": "auto",
    }
    strategy = strategies.get(choice, "auto")

    return {"PROCESSING_STRATEGY": strategy}


def get_optional_settings():
    """Get optional settings."""
    print("\nOptional Settings (press Enter for defaults):")

    config = {}

    batch_size = input("Batch size [50000]: ").strip()
    if batch_size:
        config["BATCH_SIZE"] = batch_size

    max_memory = input("Max memory percent [80]: ").strip()
    if max_memory:
        config["MAX_MEMORY_PERCENT"] = max_memory

    temp_dir = input("Temp directory [./temp]: ").strip()
    if temp_dir:
        config["TEMP_DIR"] = temp_dir

    return config


def write_env_file(config):
    """Write configuration to .env file."""
    env_path = Path(".env")

    # Read existing .env if it exists
    existing_config = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    existing_config[key] = value

    # Merge with new config
    existing_config.update(config)

    # Write to .env file
    with open(env_path, "w") as f:
        f.write("# CNPJ Data Pipeline Configuration\n")
        f.write("# Generated by setup wizard\n\n")

        for key, value in existing_config.items():
            f.write(f"{key}={value}\n")

    print(f"\n✅ Configuration saved to {env_path}")


def check_requirements():
    """Check if required packages are installed."""
    print("\nChecking requirements...")

    missing_packages = []
    required_packages = [
        "requests",
        "beautifulsoup4",
        "polars",
        "psycopg2",
        "psutil",
        "tqdm",
    ]

    for package in required_packages:
        try:
            if package == "psycopg2":
                import psycopg2  # noqa: F401
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
        install = input("Install missing packages? (y/n) [y]: ").lower().strip()
        if install in ["", "y", "yes"]:
            # Import subprocess at the top level to avoid B404 warning
            import subprocess  # nosec B404 - subprocess needed for package installation

            try:
                # Use psycopg2-binary for easier installation
                if "psycopg2" in missing_packages:
                    missing_packages.remove("psycopg2")
                    missing_packages.append("psycopg2-binary")

                # Explicitly set shell=False for security (B603)
                subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + missing_packages,
                    check=True,
                    shell=False,  # nosec B603 - shell=False is secure, args are controlled
                    timeout=300,  # Add timeout for safety
                )
                print("✅ Packages installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install packages: {e}")
                print("Please install manually:")
                print(f"  pip install {' '.join(missing_packages)}")
                return False
            except subprocess.TimeoutExpired:
                print("❌ Package installation timed out")
                print("Please install manually:")
                print(f"  pip install {' '.join(missing_packages)}")
                return False
    else:
        print("✅ All required packages are installed")

    return True


def main():
    """Main setup wizard function."""
    print_header()

    # Check requirements first
    if not check_requirements():
        return

    # Detect system resources
    memory_gb, cpu_count = detect_system_resources()

    # Collect configuration
    config = {}

    # Database configuration
    db_config = get_database_configuration()
    config.update(db_config)

    # Processing configuration
    proc_config = get_processing_configuration(memory_gb, cpu_count)
    config.update(proc_config)

    # Optional settings
    opt_config = get_optional_settings()
    config.update(opt_config)

    # Write configuration
    write_env_file(config)

    # Final instructions
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Ensure your database is running")
    print("2. Create the CNPJ database and tables (see docs/)")
    print("3. Run the data pipeline: python main.py")
    print("\nFor more information, see README.md")


if __name__ == "__main__":
    main()
