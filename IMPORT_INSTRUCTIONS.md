# Fast Import Instructions for Organizations CSV → Supabase

## System Specs
- **CPU Cores:** 16
- **RAM:** 30GB (21GB available)
- **CSV Size:** 7.7GB
- **Target:** Supabase/PostgreSQL

## Optimized Performance Settings

For maximum speed on your 16-core server with a 7.7GB file:

```bash
# Add these to your .env file for fastest performance
export CSV2PG_PERFORMANCE_WORKERS=12           # 75% of CPU cores
export CSV2PG_PERFORMANCE_CONCURRENCY=6        # Half of workers
export CSV2PG_PERFORMANCE_BATCH_SIZE=100MB     # Large batches for big file
export CSV2PG_PERFORMANCE_PREFETCH_ROWS=50000  # More rows in memory
export CSV2PG_PERFORMANCE_WORK_MEM=1GB         # Increased for operations
export CSV2PG_PERFORMANCE_MAINTENANCE_WORK_MEM=4GB  # Increased for indexes
```

## Step-by-Step Import Process

### Step 1: Update .env with Performance Settings

```bash
cd /root/Projects/csv2pg-ai-schema-infer

# Add performance settings to .env
cat >> .env << 'EOF'

# High Performance Settings for 16-core server + 7.7GB file
CSV2PG_PERFORMANCE_WORKERS=12
CSV2PG_PERFORMANCE_CONCURRENCY=6
CSV2PG_PERFORMANCE_BATCH_SIZE=100MB
CSV2PG_PERFORMANCE_PREFETCH_ROWS=50000
CSV2PG_PERFORMANCE_WORK_MEM=1GB
CSV2PG_PERFORMANCE_MAINTENANCE_WORK_MEM=4GB
EOF
```

### Step 2: Update Database Connection

Update your `DATABASE_URL` in `.env` with your Supabase credentials:

```bash
# Edit .env and update:
DATABASE_URL=postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# Or for direct connection (faster, but limited connections):
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
```

**Important:** Use the **connection pooler** (port 6543) for pgloader with high concurrency!

### Step 3: Run the Import

```bash
cd /root/Projects/csv2pg-ai-schema-infer

# Full import with Gemini 2.5 Pro inference
uv run csv2pg-ai-schema-infer import-csv \
  /root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv \
  --model gemini-2.5-pro \
  --sample-rows 200 \
  --chunk-size 20 \
  --table-name organizations \
  --output-dir ./output/organizations_import \
  --verbose
```

### Step 4: Monitor the Import

The import will:
1. ✅ Sample 200 rows from the 7.7GB CSV (~30 seconds)
2. ✅ Run Gemini 2.5 Pro inference on 156 columns (~1-2 minutes)
3. ✅ Generate pgloader config with optimized settings
4. ✅ Generate import bash script
5. ✅ Show you the generated files

**You'll be prompted before the actual import runs!**

### Step 5: Review Generated Files

Before importing, review:

```bash
# Check the inferred schema
cat output/organizations_import/organizations.load

# Check the import script
cat output/organizations_import/import_organizations.sh
```

### Step 6: Execute the Import

If you ran with `--dry-run`, or if you want to run it manually:

```bash
cd output/organizations_import
bash import_organizations.sh
```

Or let the CLI do it automatically (it will ask for confirmation).

## Expected Performance

With these settings on your 16-core server:

- **Sampling:** ~30 seconds
- **AI Inference:** ~1-2 minutes (Gemini 2.5 Pro)
- **pgloader Import:** ~5-8 minutes for 7.7GB
- **Total Time:** ~10 minutes end-to-end

**Import Rate:** ~800-1000MB/minute with 12 workers

## Alternative: Just Generate Config (No Import)

If you want to review everything first:

```bash
uv run csv2pg-ai-schema-infer import-csv \
  /root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv \
  --model gemini-2.5-pro \
  --sample-rows 200 \
  --dry-run
```

This generates all files but doesn't run the import.

## Troubleshooting

### If pgloader isn't installed:

```bash
# Ubuntu/Debian
sudo apt-get install pgloader

# Or build from source
sudo apt-get install sbcl
git clone https://github.com/dimitri/pgloader
cd pgloader
make pgloader
sudo cp build/bin/pgloader /usr/local/bin/
```

### If you hit connection limits:

Use Supabase connection pooler (port 6543) instead of direct connection (port 5432):
```
postgresql://postgres.REF:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

### If memory issues occur:

Reduce batch size and prefetch:
```bash
export CSV2PG_PERFORMANCE_BATCH_SIZE=50MB
export CSV2PG_PERFORMANCE_PREFETCH_ROWS=25000
```

## What You'll Get

After the import completes:

```
✅ Table: organizations
✅ Rows: ~millions (depending on CSV)
✅ Columns: 156 (sanitized from dots to underscores)
✅ Primary Key: identifier_uuid (automatically detected)
✅ Indexes: Created after load for performance
✅ Types: Gemini-inferred (UUID, timestamptz, bigint, numeric, text, etc.)
```

## CLI Command Summary

**Full auto import:**
```bash
uv run csv2pg-ai-schema-infer import-csv \
  /root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv \
  --model gemini-2.5-pro \
  --sample-rows 200 \
  --verbose
```

**With custom table name:**
```bash
uv run csv2pg-ai-schema-infer import-csv \
  /root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv \
  --model gemini-2.5-pro \
  --table-name cb_organizations \
  --sample-rows 200
```

**Dry run (preview only):**
```bash
uv run csv2pg-ai-schema-infer import-csv \
  /root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv \
  --model gemini-2.5-pro \
  --sample-rows 200 \
  --dry-run
```

**Force overwrite existing files:**
```bash
uv run csv2pg-ai-schema-infer import-csv \
  /root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv \
  --model gemini-2.5-pro \
  --force
```

---

## Quick Start (Copy-Paste Ready)

```bash
# 1. Navigate to project
cd /root/Projects/csv2pg-ai-schema-infer

# 2. Add high-performance settings
cat >> .env << 'EOF'

# High Performance Settings
CSV2PG_PERFORMANCE_WORKERS=12
CSV2PG_PERFORMANCE_CONCURRENCY=6
CSV2PG_PERFORMANCE_BATCH_SIZE=100MB
CSV2PG_PERFORMANCE_PREFETCH_ROWS=50000
CSV2PG_PERFORMANCE_WORK_MEM=1GB
CSV2PG_PERFORMANCE_MAINTENANCE_WORK_MEM=4GB
EOF

# 3. Update DATABASE_URL in .env with your Supabase credentials
nano .env  # Or use your preferred editor

# 4. Run the import
uv run csv2pg-ai-schema-infer import-csv \
  /root/Data/CB-CSV-date-2025-08-21/organizations.2025-09-21.032206db.csv \
  --model gemini-2.5-pro \
  --sample-rows 200 \
  --verbose
```

That's it! The tool will handle everything else automatically. 🚀
