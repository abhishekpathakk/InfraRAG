# Create AWS DMS Source Filter Rules for an Organization Migration

This runbook describes how to generate AWS DMS [table mapping rules](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Tasks.CustomizingTasks.TableMapping.html) with **source-side filter conditions** so that a DMS task only replicates rows belonging to a specific set of organization IDs from the legacy cell (`gitlab.com` / `staging.gitlab.com`) into a target protocell.

This is used during the [Cohort 0 migration](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/organization-data-migration/cohort0/) and was developed in [tenant-services/team#400](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400).

> [!warning]
> DMS does **not** currently support PostgreSQL declarative partitioned tables in an org-move context. See [tenant-services/team#419](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/419) for the known issue. Filter rules generated here will still exclude / fail on partitioned parents (e.g. `p_ci_*`, `issue_search_data`, `merge_request_commits_metadata`).

## Prerequisites

- Access to the source database host (a rails console server is fine, e.g. `console-ro-01-sv-gstg.c.gitlab-staging-1.internal`).
- The numeric `organization_id` of every test/target organization to be migrated.
- Python 3 to run the conversion script below.

## Background — why filters are tricky

DMS filters are applied at the source as a `WHERE` clause on `SELECT`. A few important constraints learned in [#400](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400):

- One selection rule per table (no wildcards when filters are used).
- Filter values are always strings, even for numeric columns.
- Multiple conditions on the same column are **OR**ed; conditions on different columns are **AND**ed.
- Filters are not re-evaluated for already-migrated rows during CDC, so only filter on **immutable** columns.
- The sharding-key column is frequently **not** the standard `organization_id` / `project_id` / `namespace_id` / `user_id`. Examples include `group_id`, `target_project_id`, `member_namespace_id`, `root_namespace_id`, `shared_group_id`, `snippet_project_id`, `security_policy_management_project_id`, etc. ([reference](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400#note_3261284933)).
- Some tables have multi-column sharding keys with a `num_nonnulls(...) = 1` constraint and need one rule per column.

We generate rules programmatically from `db/docs/*.yml` `sharding_key` metadata in two steps:

1. Generate per-table `COPY ... WHERE ... IN (...)` statements scoped to the target organization(s).
2. Convert those `COPY` statements into a DMS `table-mappings.json`.

## Step 1 — generate per-org `COPY` statements

We reuse the [`generate-org-copy-statements`](https://gitlab.com/gitlab-org/gitlab-development-kit/-/blob/5576e4bf2245aae07afa811d2b0a702d607a964b/support/cells/generate-org-copy-statements) script from GDK. It must be run **on a host that can connect to the source database**, because it resolves the `namespace_id`s and `project_id`s belonging to the target organizations.

In staging, that means a rails console node:

```bash
# Copy the script and db/docs YAMLs onto the source host
console-ro-01-sv-gstg.c.gitlab-staging-1.internal:~$ mkdir gdk && cd gdk &&git clone --depth 1 --filter=blob:none --sparse \
  https://gitlab.com/gitlab-org/gitlab.git && cd gitlab && git sparse-checkout set db/docs && cd ..

console-ro-01-sv-gstg.c.gitlab-staging-1.internal:~/gdk$ export PGPASSWORD=$(sudo /bin/cat /etc/gitlab/gitlab.rb \
    | perl -ne 'm/gitlab_rails.*db_password.*?"(.*)"$/ && do { print $1 }')
  export PGSSLCOMPRESSION=0
  PSQL='/opt/gitlab/embedded/bin/psql --no-password
    --host=replica.patroni.service.consul --port=5432
    --username=gitlab --dbname=gitlabhq_production -c'
console-ro-01-sv-gstg.c.gitlab-staging-1.internal:~gdk/$ mkdir -p support/cells && curl -s https://gitlab.com/gitlab-org/gitlab-development-kit/-/raw/842683b221768e46576469012e339ad20e4112fd/support/cells/generate-org-copy-statements > support/cells/generate-org-copy-statements
console-ro-01-sv-gstg.c.gitlab-staging-1.internal:~gdk/$ chmod +x support/cells/generate-org-copy-statements && cd support/cell
console-ro-01-sv-gstg.c.gitlab-staging-1.internal:~gdk/support/cell$ ./generate-org-copy-statements --organization-ids <COMMA_SEPRATED_ORGANIZATION_IDs> -s main -p "$PSQL"
console-ro-01-sv-gstg.c.gitlab-staging-1.internal:~gdk/support/cell$ ./generate-org-copy-statements --organization-ids <COMMA_SEPRATED_ORGANIZATION_IDs> -s ci -p "$PSQL"
```

Pass multiple organization IDs as a comma-separated list, e.g. `--organization-ids 3000283,3000285`. Filters for both `main` and `ci` databases because mapping from organization ID to project ID only exists in `main` database [reference](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400#note_3314053949).

The output is a list of statements like:

```sql
COPY ( SELECT projects.* FROM projects WHERE projects.id IN (19571592) ) TO STDOUT WITH (FORMAT CSV, HEADER)
COPY ( SELECT issues.*   FROM issues   WHERE issues.namespace_id IN (29923411,29923412) ) TO STDOUT WITH (FORMAT CSV, HEADER)
```

## Step 2 — convert `COPY` statements into a DMS `table-mappings.json`

Use the `convert-to-dms.py` from helper (originally posted by Tarun (`@tkhandelwal3`) in [#400](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400#note_3315024789)) to translate `COPY ... WHERE col IN (...)` into DMS `selection` rules with `eq` filter conditions.

Save the script below as `convert-to-dms.py` and run:

```bash
# basic usage — writes ./dms-mappings.json
python3 convert-to-dms.py -i main-copy-statements.sql -o main-table-mappings.json

# pipe form
cat main-copy-statements.sql | python3 convert-to-dms.py --stdout > main-table-mappings.json

# also emit parallel-load table-settings rules for declarative-partitioned parents (p_*)
python3 convert-to-dms.py \
  -i ci-copy-statements.sql \
  -o ci-table-mappings.json \
  --schema public \
  --parallel-load-partitioned
```

Run once per database cluster (`main`, `ci`, `sec`).

The script:

- Merges duplicate `(table, column)` entries and dedups values.
- Warns on `(table, column1)` / `(table, column2)` conflicts (real sharding-key conflicts) and keeps the first.
- Skips and warns on malformed `COPY` lines instead of aborting.
- Optionally emits `table-settings` rules with `parallel-load: { type: partitions-auto }` for tables prefixed `p_` (configurable via `--partition-prefix`).

The resulting `*-table-mappings.json` looks like:

```json
{
  "rules": [
    {
      "rule-type": "selection",
      "rule-id": "1",
      "rule-name": "1",
      "object-locator": { "schema-name": "public", "table-name": "projects" },
      "rule-action": "include",
      "filters": [
        {
          "filter-type": "source",
          "column-name": "id",
          "filter-conditions": [
            { "filter-operator": "eq", "value": "19571592" }
          ]
        }
      ]
    }
  ]
}
```

### `convert-to-dms.py`

<details>
<summary>Full script</summary>

```python
#!/usr/bin/env python3
"""
copy_to_dms.py — Convert PostgreSQL COPY statements to AWS DMS table-mappings JSON.

Input format (single- or multi-line):
    COPY ( SELECT <table>.* FROM <table> WHERE <table>.<column> IN (<values>) ) TO STDOUT WITH (FORMAT CSV, HEADER)

Usage:
    python3 copy_to_dms.py -i copy.sql                    # writes ./dms-mappings.json
    python3 copy_to_dms.py -i copy.sql -o my-rules.json
    cat copy.sql | python3 copy_to_dms.py --stdout > rules.json
    python3 copy_to_dms.py -i copy.sql --schema public --parallel-load-partitioned

Stats are printed to stderr; JSON is written to the output file (or stdout with --stdout).
Malformed COPY statements are warned about but don't abort the run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict

DEFAULT_OUTPUT = "dms-mappings.json"

# Tolerates: optional schema-qualified table in FROM, whitespace/newline variations,
# optional schema-qualified column in WHERE (e.g., schema.table.col).
COPY_PATTERN = re.compile(
    r"""
    COPY\s*\(\s*                              # COPY (
    SELECT\s+[\w.]+\.\*\s+                    # SELECT <table_or_alias>.*
    FROM\s+(?:\w+\.)?(?P<table>\w+)\s+        # FROM [schema.]<table>
    WHERE\s+(?:\w+\.)?\w+\.(?P<column>\w+)\s+ # WHERE [schema.]<table>.<column>
    IN\s*\(\s*(?P<values>[^)]*?)\s*\)         # IN (v1, v2, ...)
    \s*\)                                     # closing paren of subquery
    """,
    re.IGNORECASE | re.VERBOSE,
)

ParsedRow = tuple[str, str, list[str]]  # (table, column, values)


def _split_values(values_str: str) -> list[str]:
    """
    Split IN-clause body on commas, respecting single/double quotes.
    Handles SQL-style doubled-quote escapes (e.g., 'it''s' -> it's).
    Strips surrounding quotes and dedupes while preserving order.
    """
    out: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    n = len(values_str)
    while i < n:
        c = values_str[i]
        if quote is not None:
            if c == quote:
                # Doubled quote inside string = escaped quote
                if i + 1 < n and values_str[i + 1] == quote:
                    buf.append(c)
                    i += 2
                    continue
                quote = None  # close: drop quote char itself
            else:
                buf.append(c)
        else:
            if c in ("'", '"'):
                quote = c  # open: drop quote char itself
            elif c == ",":
                v = "".join(buf).strip()
                if v:
                    out.append(v)
                buf = []
            else:
                buf.append(c)
        i += 1
    v = "".join(buf).strip()
    if v:
        out.append(v)
    return list(dict.fromkeys(out))  # dedup, preserve order


def parse(text: str) -> tuple[list[ParsedRow], list[str]]:
    """Parse COPY statements from text (multi-line aware). Returns (rows, malformed)."""
    rows: list[ParsedRow] = []
    matched_spans: list[tuple[int, int]] = []

    for m in COPY_PATTERN.finditer(text):
        rows.append((m.group("table"), m.group("column"), _split_values(m.group("values"))))
        matched_spans.append(m.span())

    # Best-effort malformed detection: any "COPY (" not contained in a successful match.
    malformed: list[str] = []
    for cm in re.finditer(r"COPY\s*\(", text, re.IGNORECASE):
        start = cm.start()
        if any(s <= start < e for s, e in matched_spans):
            continue
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", start)
        if line_end == -1:
            line_end = len(text)
        malformed.append(text[line_start:line_end].strip()[:120])

    return rows, malformed


def merge_rows(rows: list[ParsedRow]) -> tuple[list[ParsedRow], list[str]]:
    """
    Collapse entries with the same table.

    Same (table, column): merge values, dedup, preserve order.
    Same table, different column: real conflict — keep the first, warn loudly.
    """
    by_table: dict[str, ParsedRow] = {}
    warnings: list[str] = []

    for table, column, values in rows:
        if table not in by_table:
            by_table[table] = (table, column, list(values))
            continue
        _t, existing_column, existing_values = by_table[table]
        if existing_column != column:
            warnings.append(
                f"table '{table}': filter column conflict "
                f"({existing_column!r} vs {column!r}); keeping {existing_column!r}"
            )
            continue
        merged = list(dict.fromkeys(existing_values + values))
        by_table[table] = (table, existing_column, merged)

    return list(by_table.values()), warnings


def selection_rule(rule_id: int, schema: str, table: str, column: str, values: list[str]) -> dict:
    return {
        "rule-type": "selection",
        "rule-id": str(rule_id),
        "rule-name": str(rule_id),
        "object-locator": {"schema-name": schema, "table-name": table},
        "rule-action": "include",
        "filters": [{
            "filter-type": "source",
            "column-name": column,
            "filter-conditions": [{"filter-operator": "eq", "value": v} for v in values],
        }],
    }


def parallel_load_rule(rule_id: int, schema: str, table: str, parallel_type: str) -> dict:
    return {
        "rule-type": "table-settings",
        "rule-id": str(rule_id),
        "rule-name": f"parallel-{table}",
        "object-locator": {"schema-name": schema, "table-name": table},
        "parallel-load": {"type": parallel_type},
    }


def build_mapping(
    rows: list[ParsedRow],
    schema: str,
    parallel_load_partitioned: bool,
    partition_prefix: str,
    parallel_type: str,
) -> dict:
    rules: list[dict] = []
    rid = 1

    for table, column, values in rows:
        if not values:
            print(f"WARNING: skipping {table} (empty IN clause)", file=sys.stderr)
            continue
        rules.append(selection_rule(rid, schema, table, column, values))
        rid += 1

    if parallel_load_partitioned:
        for table, _c, _v in rows:
            if table.startswith(partition_prefix):
                rules.append(parallel_load_rule(rid, schema, table, parallel_type))
                rid += 1

    return {"rules": rules}


def print_stats(
    rows: list[ParsedRow],
    malformed: list[str],
    merge_warnings: list[str],
    partition_prefix: str,
) -> None:
    by_value: dict[str, int] = defaultdict(int)
    by_column: dict[str, int] = defaultdict(int)
    partitioned: list[str] = []

    for table, column, values in rows:
        # Sort for stable grouping regardless of source order
        by_value[",".join(sorted(values))] += 1
        by_column[column] += 1
        if table.startswith(partition_prefix):
            partitioned.append(table)

    print(f"Parsed {len(rows)} table(s) after merge", file=sys.stderr)
    print("\nFilter value groups:", file=sys.stderr)
    for k, n in sorted(by_value.items()):
        print(f"  IN ({k}): {n} table(s)", file=sys.stderr)
    print("\nFilter columns:", file=sys.stderr)
    for k, n in sorted(by_column.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {k}: {n}", file=sys.stderr)
    if partitioned:
        print(f"\nDeclarative-partitioned tables ('{partition_prefix}*'): {len(partitioned)}", file=sys.stderr)
        print("  (consider --parallel-load-partitioned for these)", file=sys.stderr)
    if merge_warnings:
        print(f"\nWARNING: {len(merge_warnings)} table-level conflict(s):", file=sys.stderr)
        for w in merge_warnings:
            print(f"  {w}", file=sys.stderr)
    if malformed:
        print(f"\nWARNING: {len(malformed)} malformed COPY statement(s) skipped:", file=sys.stderr)
        for line in malformed[:10]:
            print(f"  {line}", file=sys.stderr)
        if len(malformed) > 10:
            print(f"  ... and {len(malformed) - 10} more", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Convert PostgreSQL COPY statements to AWS DMS table-mappings JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            f"  %(prog)s -i copy.sql                       # writes ./{DEFAULT_OUTPUT}\n"
            "  %(prog)s -i copy.sql -o my-rules.json\n"
            "  cat copy.sql | %(prog)s --stdout > rules.json\n"
            "  %(prog)s -i copy.sql --schema public --parallel-load-partitioned\n"
        ),
    )
    p.add_argument("-i", "--input", help="Input file (default: stdin)")
    p.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output file (default: {DEFAULT_OUTPUT}). Ignored if --stdout is set.",
    )
    p.add_argument(
        "--stdout",
        action="store_true",
        help="Write JSON to stdout instead of a file (useful for piping)",
    )
    p.add_argument("--schema", default="public", help="schema-name for object-locator (default: public)")
    p.add_argument(
        "--parallel-load-partitioned",
        action="store_true",
        help="Emit table-settings rules with parallel-load for tables matching --partition-prefix",
    )
    p.add_argument(
        "--partition-prefix",
        default="p_",
        help="Prefix identifying declarative-partitioned parent tables (default: p_)",
    )
    p.add_argument(
        "--parallel-type",
        default="partitions-auto",
        choices=["partitions-auto", "subpartitions-auto"],
        help="parallel-load type used when --parallel-load-partitioned is set (default: partitions-auto)",
    )
    p.add_argument("--quiet", action="store_true", help="Suppress stats on stderr")
    args = p.parse_args()

    if args.input:
        with open(args.input) as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    rows, malformed = parse(text)

    if not rows:
        print("ERROR: no COPY statements parsed from input", file=sys.stderr)
        if malformed:
            print(f"  ({len(malformed)} malformed statement(s) found)", file=sys.stderr)
        return 1

    rows, merge_warnings = merge_rows(rows)

    mapping = build_mapping(
        rows,
        schema=args.schema,
        parallel_load_partitioned=args.parallel_load_partitioned,
        partition_prefix=args.partition_prefix,
        parallel_type=args.parallel_type,
    )
    out_text = json.dumps(mapping, indent=2)

    if args.stdout:
        sys.stdout.write(out_text + "\n")
    else:
        with open(args.output, "w") as f:
            f.write(out_text + "\n")
        if not args.quiet:
            print(f"Wrote {args.output}", file=sys.stderr)

    if not args.quiet:
        print_stats(rows, malformed, merge_warnings, args.partition_prefix)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

</details>

## Step 3 — sanity check before applying

Before uploading the mappings to DMS:

- Skim the `stderr` summary printed by `convert-to-dms.py`: number of tables, filter columns used, and partitioned-table count.
- Spot-check a handful of tables with non-standard sharding keys to confirm the column was picked correctly: e.g. `merge_requests.target_project_id`, `members.member_namespace_id`, `group_group_links.shared_group_id`.
- Cross-reference the `p_` prefixed tables and known problem tables against [tenant-services/team#419](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/419). Expect failures on:
  - `main`: `issue_search_data`, `merge_request_commits_metadata`, `merge_request_diff_commits_b5377a7a34`, `ai_audit_events`
  - `ci`: `p_ci_stages`, `p_ci_pipelines`, `p_ci_builds`, `p_ci_build_names`, `p_ci_build_sources`, `p_ci_job_artifacts`, `p_ci_job_definitions`, `p_ci_job_definition_instances`, `p_ci_runner_machine_builds`, `ci_job_artifact_states`
- Confirm the DMS source role has `SELECT` on every table in the mapping. In our last run we hit `permission denied (SqlState 42501)` on `ai_audit_events`, `ai_vectorizable_file_upload_states`, `bulk_import_export_upload_upload_states`, `scan_result_policy_violation_details`, `security_policy_schedule_pipelines` ([reference](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400#note_3315313718)).

## Step 4 — apply to the DMS task

1. Open the AWS DMS console for the relevant region (e.g. `us-east-1`).
2. Select the migration task for the cluster.
3. **Modify** → **Table mappings** → **JSON editor**, paste the contents of the generated `*-table-mappings.json`.
4. Save and start (or restart) the task.

Enable CloudWatch logging on the task before running — this was essential for diagnosing partitioned-table failures and permission errors ([reference](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400#note_3315024789)).

## Step 5 — observe

Useful checks:

- **Table statistics** view in the DMS console: filter by `Table state = Table error` to see failed tables.
- CloudWatch logs for `[SOURCE_UNLOAD]`, `[METADATA_MANAGE]`, `[TARGET_LOAD]` events.
- On the target cell, confirm rows arrived (e.g. `https://<cell-host>/admin/organizations`).

## Re-running for a new set of organizations

The full procedure is idempotent on the script side. To migrate a different/extended set:

1. Re-run **Step 1** with the new `--organization-ids` list.
2. Re-run **Step 2** to regenerate the mapping JSON.
3. Re-apply in **Step 4**.

Do not edit the generated JSON by hand — regenerate. The script intentionally produces deterministic, diffable output.

## Known issues / gotchas

- **Partitioned tables fail.** Tracked in [tenant-services/team#419](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/419). Do not rely on DMS for these; alternative replication is being evaluated in [#415](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/415) / [#416](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/416).
- **Reference / `copy_all` tables** (e.g. `plans`, `application_setting_terms`) should be excluded from the DMS mapping and seeded via the cell-provisioning sync mechanism — see [tenant-services/team#418](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/418) and [cells-infrastructure/team#482](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/cells-infrastructure/team/-/work_items/482).
- **Cell sequences must be initialized** before running DMS, otherwise the topology service's ID claim will collide with migrated IDs ([past failure on cell-8](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400#note_3281963967)). Follow the [sequence fix guide](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/cells-infrastructure/team/-/issues/668#note_3099902348) before kicking off the task.
- **Replication-instance sizing**: `dms.t3.small` (2 vCPU / 2 GB) OOMs (exit 9) on multi-subtask loads of GitLab-sized data. Use at least `dms.c5.xlarge` (4 vCPU / 8 GB). See AWS [sizing guide](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_BestPractices.SizingReplicationInstance.html) and the [retro in #329](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/329#note_2975358319).
- **`idle_in_transaction_session_timeout`** on the source has previously killed DMS connections during full load. If hit, set `postgresql['idle_in_transaction_session_timeout'] = 0` in `gitlab.rb` on the source and reconfigure ([reference](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/329#note_2975358319)).

## References

- [tenant-services/team#400](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/400) — origin discussion and scripts
- [tenant-services/team#419](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/419) — DMS partitioned-table limitation
- [tenant-services/team#418](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/418) — `copy_all` reference table sync
- [GDK `generate-org-copy-statements`](https://gitlab.com/gitlab-org/gitlab-development-kit/-/blob/master/support/cells/generate-org-copy-statements)
- [DMS Blueprint](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/organization-data-migration/dms-blueprint/)
- [Cohort 0 Migration Plan](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/organization-data-migration/cohort0/)
- [AWS DMS Table Mapping docs](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Tasks.CustomizingTasks.TableMapping.html)
- [AWS DMS PostgreSQL source limitations](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Source.PostgreSQL.html#CHAP_Source.PostgreSQL.Limitations)
