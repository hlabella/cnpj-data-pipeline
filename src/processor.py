import logging
import polars as pl
from pathlib import Path
from typing import Tuple, Optional
import tempfile
import psutil
import os
import gc

logger = logging.getLogger(__name__)

# Simple mapping of file patterns to table names
FILE_MAPPINGS = {
    "CNAECSV": "cnaes",
    "MOTICSV": "motivos",
    "MUNICCSV": "municipios",
    "NATJUCSV": "naturezas_juridicas",
    "PAISCSV": "paises",
    "QUALSCSV": "qualificacoes_socios",
    "EMPRECSV": "empresas",
    "ESTABELE": "estabelecimentos",
    "SOCIOCSV": "socios",
    "SIMPLESCSV": "dados_simples",
}

# Column mappings for different file types
COLUMN_MAPPINGS = {
    "CNAECSV": {0: "codigo", 1: "descricao"},
    "MOTICSV": {0: "codigo", 1: "descricao"},
    "MUNICCSV": {0: "codigo", 1: "descricao"},
    "NATJUCSV": {0: "codigo", 1: "descricao"},
    "PAISCSV": {0: "codigo", 1: "descricao"},
    "QUALSCSV": {0: "codigo", 1: "descricao"},
    "EMPRECSV": {
        0: "cnpj_basico",
        1: "razao_social",
        2: "natureza_juridica",
        3: "qualificacao_responsavel",
        4: "capital_social",
        5: "porte",
        6: "ente_federativo_responsavel",
    },
    "ESTABELE": {
        0: "cnpj_basico",
        1: "cnpj_ordem",
        2: "cnpj_dv",
        3: "identificador_matriz_filial",
        4: "nome_fantasia",
        5: "situacao_cadastral",
        6: "data_situacao_cadastral",
        7: "motivo_situacao_cadastral",
        8: "nome_cidade_exterior",
        9: "pais",
        10: "data_inicio_atividade",
        11: "cnae_fiscal_principal",
        12: "cnae_fiscal_secundaria",
        13: "tipo_logradouro",
        14: "logradouro",
        15: "numero",
        16: "complemento",
        17: "bairro",
        18: "cep",
        19: "uf",
        20: "municipio",
        21: "ddd_1",
        22: "telefone_1",
        23: "ddd_2",
        24: "telefone_2",
        25: "ddd_fax",
        26: "fax",
        27: "correio_eletronico",
        28: "situacao_especial",
        29: "data_situacao_especial",
    },
    "SOCIOCSV": {
        0: "cnpj_basico",
        1: "identificador_de_socio",
        2: "nome_socio",
        3: "cnpj_cpf_do_socio",
        4: "qualificacao_do_socio",
        5: "data_entrada_sociedade",
        6: "pais",
        7: "representante_legal",
        8: "nome_do_representante",
        9: "qualificacao_do_representante_legal",
        10: "faixa_etaria",
    },
    "SIMPLESCSV": {
        0: "cnpj_basico",
        1: "opcao_pelo_simples",
        2: "data_opcao_pelo_simples",
        3: "data_exclusao_do_simples",
        4: "opcao_pelo_mei",
        5: "data_opcao_pelo_mei",
        6: "data_exclusao_do_mei",
    },
}

# Numeric columns that need comma-to-point conversion
NUMERIC_COLUMNS = {
    "EMPRECSV": ["capital_social"],
    "ESTABELE": [],
    "SIMPLESCSV": [],
    "SOCIOCSV": [],
}

# Date columns that need cleaning
DATE_COLUMNS = {
    "EMPRECSV": [],
    "ESTABELE": [
        "data_situacao_cadastral",
        "data_inicio_atividade",
        "data_situacao_especial",
    ],
    "SIMPLESCSV": [
        "data_opcao_pelo_simples",
        "data_exclusao_do_simples",
        "data_opcao_pelo_mei",
        "data_exclusao_do_mei",
    ],
    "SOCIOCSV": ["data_entrada_sociedade"],
}

# Reference data enhancements
REFERENCE_ENHANCEMENTS = {
    "MOTICSV": {"source": "serpro", "ref_type": "motivos", "code_column": "codigo"},
    "PAISCSV": {"source": "hardcoded", "ref_type": "paises", "code_column": "codigo"},
    # Future enhancements can be added here
}


class Processor:
    """Handles processing and transforming CSV files."""

    def __init__(self, config):
        self.config = config
        self.debug = config.debug

    def _log_memory_usage(self, context: str):
        """Log current memory usage if debug mode is enabled."""
        if self.debug:
            memory = psutil.virtual_memory()
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()

            logger.debug(f"[{context}] Memory Status:")
            logger.debug(
                f"  System: {memory.percent:.1f}% used ({memory.used / 1024**3:.2f}GB / {memory.total / 1024**3:.2f}GB)"
            )
            logger.debug(f"  Process RSS: {process_memory.rss / 1024**3:.2f}GB")
            logger.debug(f"  Process VMS: {process_memory.vms / 1024**3:.2f}GB")

    def _get_file_size_mb(self, file_path: Path) -> float:
        """Get file size in MB."""
        return file_path.stat().st_size / (1024 * 1024)

    def _get_file_type(self, filename: str) -> Optional[str]:
        """Determine file type from filename."""
        filename_upper = filename.upper()

        for pattern in FILE_MAPPINGS.keys():
            if pattern in filename_upper:
                if self.debug:
                    logger.debug(f"File type detected: {pattern} for {filename}")
                return pattern

        logger.warning(f"Unknown file type for: {filename}")
        return None

    def _convert_file_encoding_chunked(
        self, input_file: Path, output_file: Optional[Path] = None
    ) -> Path:
        """Convert file encoding from ISO-8859-1 to UTF-8 using chunked reading for large files."""
        if output_file is None:
            temp_fd, temp_path = tempfile.mkstemp(suffix=".utf8.csv")
            output_file = Path(temp_path)
            os.close(temp_fd)

        file_size_mb = self._get_file_size_mb(input_file)
        logger.info(f"Converting encoding for {input_file.name} ({file_size_mb:.2f}MB)")

        if self.debug:
            logger.debug(
                f"Using chunk size: {self.config.encoding_chunk_size / 1024**2:.2f}MB"
            )

        self._log_memory_usage("Before encoding conversion")

        try:
            with open(
                input_file,
                "r",
                encoding="ISO-8859-1",
                buffering=self.config.encoding_chunk_size,
            ) as infile:
                with open(
                    output_file,
                    "w",
                    encoding="UTF-8",
                    buffering=self.config.encoding_chunk_size,
                ) as outfile:
                    chunk_count = 0
                    while True:
                        chunk = infile.read(self.config.encoding_chunk_size)
                        if not chunk:
                            break

                        outfile.write(chunk)
                        chunk_count += 1

                        if self.debug and chunk_count % 10 == 0:
                            logger.debug(
                                f"Processed {chunk_count * self.config.encoding_chunk_size / 1024**2:.2f}MB"
                            )
                            self._log_memory_usage(
                                f"During encoding (chunk {chunk_count})"
                            )

            converted_size_mb = self._get_file_size_mb(output_file)
            logger.info(f"Encoding conversion complete: {converted_size_mb:.2f}MB")
            self._log_memory_usage("After encoding conversion")

            return output_file

        except Exception as e:
            logger.error(f"Error converting file encoding: {str(e)}")
            if output_file.exists():
                output_file.unlink()
            raise

    def _enhance_motivos_data(
        self, df: Optional[pl.DataFrame] = None, db=None, table_name: str = "motivos"
    ) -> Optional[pl.DataFrame]:
        """
        Enhance motivos data with missing codes from SERPRO.

        Args:
            df: DataFrame with official motivos data (for normal processing)
            db: Database adapter (for chunked processing)
            table_name: Table name for database operations

        Returns:
            Enhanced DataFrame if df was provided, None if working with database
        """
        try:
            from src.reference_data import ReferenceDataManager

            ref_manager = ReferenceDataManager(self.config)

            # Get existing codes either from dataframe or database
            if df is not None:
                # Normal processing - get codes from dataframe
                existing_codes = set(df["codigo"].to_list())
                logger.info(f"Official MOTICSV contains {len(existing_codes)} codes")
            else:
                # Chunked processing - get codes from database
                if db is None:
                    raise ValueError("Either df or db must be provided")

                with db.cursor() as cur:
                    cur.execute(f"SELECT codigo FROM {table_name}")  # nosec B608
                    existing_codes = {row[0] for row in cur.fetchall()}
                logger.info(
                    f"Official MOTICSV loaded {len(existing_codes)} codes to database"
                )

            # Get only missing codes from SERPRO
            missing_df = ref_manager.diff_motivos_data(existing_codes)

            if missing_df is not None and len(missing_df) > 0:
                if df is not None:
                    # Normal processing - concatenate dataframes
                    enhanced_df = pl.concat([df, missing_df])
                    logger.info(
                        f"Enhanced motivos: {len(existing_codes)} official + {len(missing_df)} SERPRO = {len(enhanced_df)} total"
                    )
                    return enhanced_df
                else:
                    # Chunked processing - load to database
                    logger.info(
                        f"Loading {len(missing_df)} missing motivos codes from SERPRO"
                    )
                    db.bulk_upsert(missing_df, table_name)

                    # Log final count
                    with db.cursor() as cur:
                        cur.execute(f"SELECT COUNT(*) FROM {table_name}")  # nosec B608
                        final_count = cur.fetchone()[0]
                    logger.info(f"Total motivos codes after enhancement: {final_count}")
            else:
                logger.info("No additional motivos codes needed from SERPRO")

            # Return original df if no enhancement needed (or None for db mode)
            return df

        except ImportError:
            logger.warning(
                "ReferenceDataManager not available, using official data only"
            )
            return df
        except Exception as e:
            logger.error(f"Failed to enhance motivos data: {e}")
            return df  # Return original data on error

    def _enhance_paises_data(
        self, df: Optional[pl.DataFrame] = None, db=None, table_name: str = "paises"
    ) -> Optional[pl.DataFrame]:
        """
        Enhance paises data with missing codes from hardcoded data.

        Args:
            df: DataFrame with official paises data (for normal processing)
            db: Database adapter (for chunked processing)
            table_name: Table name for database operations

        Returns:
            Enhanced DataFrame if df was provided, None if working with database
        """
        try:
            from src.reference_data import ReferenceDataManager

            ref_manager = ReferenceDataManager(self.config)

            # Get existing codes either from dataframe or database
            if df is not None:
                # Normal processing - get codes from dataframe
                existing_codes = set(df["codigo"].to_list())
                logger.info(f"Official PAISCSV contains {len(existing_codes)} codes")
            else:
                # Chunked processing - get codes from database
                if db is None:
                    raise ValueError("Either df or db must be provided")

                with db.cursor() as cur:
                    cur.execute(f"SELECT codigo FROM {table_name}")  # nosec B608
                    existing_codes = {row[0] for row in cur.fetchall()}
                logger.info(
                    f"Official PAISCSV loaded {len(existing_codes)} codes to database"
                )

            # Get only missing codes from hardcoded data
            missing_df = ref_manager.diff_paises_data(existing_codes)

            if missing_df is not None and len(missing_df) > 0:
                if df is not None:
                    # Normal processing - concatenate dataframes
                    enhanced_df = pl.concat([df, missing_df])
                    logger.info(
                        f"Enhanced paises: {len(existing_codes)} official + {len(missing_df)} hardcoded = {len(enhanced_df)} total"
                    )
                    return enhanced_df
                else:
                    # Chunked processing - load to database
                    logger.info(
                        f"Loading {len(missing_df)} missing paises codes from hardcoded data"
                    )
                    db.bulk_upsert(missing_df, table_name)

                    # Log final count
                    with db.cursor() as cur:
                        cur.execute(f"SELECT COUNT(*) FROM {table_name}")  # nosec B608
                        final_count = cur.fetchone()[0]
                    logger.info(f"Total paises codes after enhancement: {final_count}")
            else:
                logger.info("No additional paises codes needed from hardcoded data")

            # Return original df if no enhancement needed (or None for db mode)
            return df

        except ImportError:
            logger.warning(
                "ReferenceDataManager not available, using official data only"
            )
            return df
        except Exception as e:
            logger.error(f"Failed to enhance paises data: {e}")
            return df  # Return original data on error

    def _enhance_reference_data(
        self,
        file_type: str,
        df: Optional[pl.DataFrame] = None,
        db=None,
        table_name: str = None,
    ) -> Optional[pl.DataFrame]:
        """Generic method to enhance any reference data."""
        if file_type not in REFERENCE_ENHANCEMENTS:
            return df

        enhancement_config = REFERENCE_ENHANCEMENTS[file_type]

        # Delegate to specific enhancement method based on source
        if enhancement_config["source"] == "serpro":
            return self._enhance_motivos_data(df=df, db=db, table_name=table_name)
        elif enhancement_config["source"] == "hardcoded":
            return self._enhance_paises_data(df=df, db=db, table_name=table_name)

        return df

    def process_file(self, file_path: Path) -> Tuple[pl.DataFrame, str]:
        """Process a single CSV file and return dataframe and table name."""
        utf8_file = None
        try:
            file_size_mb = self._get_file_size_mb(file_path)
            logger.info(f"Processing file: {file_path.name} ({file_size_mb:.2f}MB)")

            self._log_memory_usage("Start of process_file")

            # Determine file type
            file_type = self._get_file_type(file_path.name)
            if not file_type:
                raise ValueError(f"Cannot determine file type for {file_path.name}")

            # Convert file encoding
            if self.debug:
                logger.debug("Starting encoding conversion...")
            utf8_file = self._convert_file_encoding_chunked(file_path)

            # Force garbage collection after encoding conversion
            gc.collect()
            self._log_memory_usage("After GC post-encoding")

            # Check if file is too large for direct loading
            utf8_size_mb = self._get_file_size_mb(utf8_file)

            if utf8_size_mb > self.config.max_file_size_mb:
                logger.warning(
                    f"File size ({utf8_size_mb:.2f}MB) exceeds max_file_size_mb ({self.config.max_file_size_mb}MB)"
                )
                logger.info("Using chunked processing approach...")

                # For very large files, process in chunks
                return self._process_large_file_chunked(utf8_file, file_type)
            else:
                # Use regular processing for moderate files
                if self.debug:
                    logger.debug("Starting CSV parsing...")

                # Read with normal polars for files under the limit
                df = pl.read_csv(
                    utf8_file,
                    separator=";",
                    encoding="utf8",
                    has_header=False,
                    null_values=[""],
                    ignore_errors=True,
                    infer_schema_length=0,
                    low_memory=False,
                )

                # Apply transformations directly to dataframe
                df = self._apply_transformations(df, file_type)

                self._log_memory_usage("After processing")

                # Get table name
                table_name = FILE_MAPPINGS[file_type]

                # ENHANCEMENT: Check if this file type needs reference data enhancement
                enhanced_df = self._enhance_reference_data(
                    file_type=file_type, df=df, table_name=table_name
                )
                if enhanced_df is not None:
                    df = enhanced_df

                logger.info(f"Processed {len(df)} rows for table {table_name}")
                return df, table_name

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            self._log_memory_usage("Error in process_file")
            raise
        finally:
            # Clean up the UTF-8 converted file
            if utf8_file and utf8_file.exists():
                try:
                    utf8_file.unlink()
                    logger.debug(f"Deleted converted file: {utf8_file}")
                except Exception as e:
                    logger.warning(f"Could not delete temporary file {utf8_file}: {e}")

    def _transform_country_codes(self, df: pl.DataFrame) -> pl.DataFrame:
        """Ensure country codes are properly padded to 3 digits."""
        if "pais" in df.columns:
            df = df.with_columns(
                pl.when(pl.col("pais").is_not_null() & (pl.col("pais") != ""))
                .then(
                    pl.col("pais")
                    .cast(pl.Utf8)
                    .str.strip_chars()
                    .str.zfill(3)  # Pad with zeros to 3 digits
                )
                .otherwise(pl.col("pais"))
                .alias("pais")
            )
            logger.debug("Transformed country codes to 3-digit format")
        return df

    def _apply_transformations(self, df: pl.DataFrame, file_type: str) -> pl.DataFrame:
        """Apply necessary transformations to the dataframe (non-lazy version)."""
        try:
            # Get column mapping for this file type
            col_mapping = COLUMN_MAPPINGS.get(file_type, {})

            # Rename columns
            if col_mapping:
                # Create new column names list
                new_columns = []
                for i in range(len(df.columns)):
                    new_columns.append(col_mapping.get(i, f"column_{i}"))
                df = df.rename(dict(zip(df.columns, new_columns)))

            # Convert numeric columns (comma to point)
            numeric_cols = NUMERIC_COLUMNS.get(file_type, [])
            for col in numeric_cols:
                if col in df.columns:
                    df = df.with_columns(
                        pl.col(col).str.replace(",", ".").cast(pl.Float64, strict=False)
                    )

            # Clean date columns
            date_cols = DATE_COLUMNS.get(file_type, [])
            for col in date_cols:
                if col in df.columns:
                    df = df.with_columns(
                        pl.when(pl.col(col) == "0")
                        .then(None)
                        .otherwise(pl.col(col))
                        .alias(col)
                    )

            # Transform country codes for estabelecimentos
            if file_type == "ESTABELE":
                df = self._transform_country_codes(df)

            return df

        except Exception as e:
            logger.error(f"Error applying transformations to {file_type}: {e}")
            raise

    def _process_large_file_chunked(
        self, file_path: Path, file_type: str
    ) -> Tuple[None, str]:
        """Process very large files in chunks, loading directly to database."""
        logger.info("Processing large file in chunks with direct database loading...")

        chunk_size = 1_000_000  # Smaller chunks
        table_name = FILE_MAPPINGS[file_type]

        # We need database access here
        from src.database.factory import create_database_adapter

        db = create_database_adapter(self.config)

        try:
            # First, get a small sample to understand the structure
            sample_df = pl.read_csv(
                file_path,
                separator=";",
                encoding="utf8",
                has_header=False,
                null_values=[""],
                ignore_errors=True,
                infer_schema_length=0,
                n_rows=100,
            )

            # Apply transformations to understand the schema
            sample_df = self._apply_transformations(sample_df, file_type)
            expected_columns = sample_df.columns

            if self.debug:
                logger.debug(f"Expected columns: {expected_columns}")

            # Process file in chunks
            offset = 0
            batch_num = 0
            total_processed = 0

            while True:
                batch_num += 1
                logger.info(f"Processing batch {batch_num} (offset: {offset:,})")
                self._log_memory_usage(f"Before batch {batch_num}")

                # Read a chunk
                chunk_df = pl.read_csv(
                    file_path,
                    separator=";",
                    encoding="utf8",
                    has_header=False,
                    null_values=[""],
                    ignore_errors=True,
                    infer_schema_length=0,
                    skip_rows=offset,
                    n_rows=chunk_size,
                )

                if len(chunk_df) == 0:
                    break

                # Apply transformations
                chunk_df = self._apply_transformations(chunk_df, file_type)

                # Load this chunk directly to database
                logger.info(
                    f"Loading batch {batch_num} to database ({len(chunk_df):,} rows)"
                )
                db.bulk_upsert(chunk_df, table_name)

                total_processed += len(chunk_df)
                offset += len(chunk_df)

                # Explicitly delete the chunk and force garbage collection
                del chunk_df

                # Periodic GC
                if batch_num % 3 == 0:
                    logger.debug(f"Running aggressive GC after batch {batch_num}")
                    gc.collect()
                    gc.collect()  # Second pass
                else:
                    gc.collect()  # Single pass for other batches

                self._log_memory_usage(f"After batch {batch_num} (post GC)")

                # Break if we read less than chunk_size (end of file)
                if offset % chunk_size != 0:
                    break

            logger.info(
                f"Completed chunked processing: {total_processed:,} total rows processed"
            )

            # ENHANCEMENT: Check if this file type needs reference data enhancement
            if total_processed > 0:
                self._enhance_reference_data(
                    file_type=file_type, db=db, table_name=table_name
                )

            # Return None for dataframe since we already loaded to DB
            return None

        except Exception as e:
            logger.error(f"Error in chunked processing: {e}")
            raise
