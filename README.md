## Infrastructure schema & meta guide

This guide explains how to **add new categories and columns for the Chain.Love platform**:

- `tools/schema.json` – the JSON Schema.
- `meta/categories.json` – category metadata.
- `meta/columns.json` – column metadata.

Data files are not documented in detail in this guide. Their structure and contribution flow are described in the `main` branch README: [README.md](https://github.com/Chain-Love/chain-love/blob/main/README.md).  
However, schema/meta changes in this branch must be mirrored in data tables on `main` (for example when adding/removing categories or columns).

---

## 1. Files and responsibilities

- **`tools/schema.json`**
  - Defines the top-level properties for each category:
    - `apis`, `explorers`, `oracles`, etc.
    - For each category, defines a JSON Schema object in `$defs`:
      - Example: `$defs/apis`, `$defs/wallets`, etc.
    - In each category schema, `properties` defines each column:
      - expected data type (`string`, `boolean`, `array`, nullable unions like `["string", "null"]`), whether `null` is allowed for that column can be left empty;
      - optional `examples` for selected columns (for example `planType`, `historicalData`, `technology`, `apiType`). `examples` are guidance values for contributor UI: users can choose suggested values or enter their own values.
      - `required` defines which column keys must exist in every generated data table for the specific category. For CSV tables, this means the CSV header (row 1) for that category must include all required columns. Cell values can be empty/`null` if the column type in `properties` allows it.  
  - Defines:
    - `$defs.columns`: schema for the top-level `columns` property in the generated JSON. `columns` is an object where:
      - each key is a category key (for example `wallets`, `apis`);
      - each value is an array of column keys (strings) that the UI uses to render the table columns for that category (including ordering).
      This schema restricts which category keys are allowed and enforces that each mapping value is an array of strings.
      If you add or remove a category, update `$defs.columns.properties` accordingly.
    - `$defs.categoryMeta`: JSON Schema for one object in generated `meta.categories[<categoryKey>]` (UI metadata for a category). Fields:
      - `key` (required, string): must equal `<categoryKey>` and match the category key used in `tools/schema.json` (for example `apis`, `wallets`, `agents`).
      - `label` (required, string): human-readable category title shown in the UI (for example `MCP Servers`).
      - `icon` (optional, string or `null`): icon reference passed to the UI image component. Common formats:
        - `lucide:<IconName>` (Lucide icon from `lucide-react`; name may be normalized from kebab/snake case).
        - `http://` / `https://` (remote image URL).
        - `asset:…` or a filename like `something.svg` (resolved relative to the configured assets base URL).
        - `local:…` (limited built-in images, if supported by the UI).
        - Multiple candidates separated by `||` are tried in order until one loads successfully (for example `plan.svg||lucide:ClipboardList`).
        - Use `null` when no icon is needed.
      - `description` (optional, string or `null`): short functional description of what this category contains.
      - `defaultSorting` (optional, string or `null`): **column key** (`ColumnMeta.key`) to use as the default sort for this category’s table (for example `rank` for `agents`). It only applies if that column exists in the category’s column metadata and the column is sortable (for example `sorting` must not be `'none'` in `columnMeta`). If omitted, rows are typically shown in source order (for example CSV row order).
    - `$defs.columnMeta`: JSON Schema for one object in generated `meta.columns[<columnKey>]` (UI metadata for a table column). Fields:
      - `key` (required, string): must equal `<columnKey>` and match the column key used in category data (`$defs.<category>.properties`) and in the top-level `columns.<category>` ordering list.
      - `label` (required, string): human-readable column title in the UI.
      - `icon` (optional, string or `null`): same semantics as category icons — a string for SmartImage / multiSrc (`lucide:…`, `http(s)://…`, `asset:…` / `*.svg`, `local:…`, and `a||b` fallbacks). Use `null` when no icon is needed.
      - `description` (optional, string or `null`): short helper text for contributors/users where applicable.
      - `filter` (optional, string or `null`): selects how the column participates in the filter panel. Only these values are recognized; anything else behaves like no filter (`none`):
        - `none` — no column filter (`enableColumnFilter: false`).
        - `select` — single value selection (booleans may use Yes/No style controls).
        - `multiSelect` — multiple values without search.
        - `searchableMultiSelect` — multiple values with search (typical for `provider`-like columns).
        - `range` — numeric “at least” threshold (numbers are parsed from string cell values where needed).
        - `dateRange` — timestamp range in milliseconds.
      - `sorting` (optional, string or `null`): if `none`, sorting for this column is disabled (`enableSorting: false`). Any other value enables sorting; the grid uses `sortingFn: 'auto'`. Values like `string`, `number`, `boolean`, `date`, `arrayLength` are semantic hints (especially for server-side comparison); they are not a closed JSON Schema enum.
      - `pinning` (optional, string or `null`): only `left` and `right` are applied as pinned columns; any other value is ignored (no pinning).
      - `cellType` (optional, string or `null`): optional renderer hint. Supported values in the UI type system are:
        - `arrayPopover`, `tagsPopover`, `numericRange`, `slaNumeric`, `agent`
        Rendering usually prefers a registry match by **column `key` first**, then falls back to `cellType`. Prefer aligning with existing columns: a custom cell is often wired by `key` (for example `provider`) rather than inventing a new `cellType` string that is not in the registry.
      - `group` (optional, string or `null`): groups fields within contributor service forms. When possible, use existing section values from the contributor UI (e.g., identity, serviceDetails, capabilities, pricingAndSlas — refer to meta/columns.json for current values). The `schema.json` does not enforce a specific list; you may introduce new groups using camelCase even if they are not yet in use.

    - `$defs.providerMeta`: JSON Schema for one object under generated `meta.providers[<providerSlug>]` (provider profile shown in the UI). Field meanings and CSV formatting rules (for example `logoPath`, `website` vs social handles) are documented in the data repo: [references/README.md](https://github.com/Chain-Love/chain-love/blob/main/references/README.md).
      When you change provider data shape, update this schema accordingly:
      - `properties` **columns**: if you add/remove/rename columns in `references/providers/providers.csv`, reflect the same keys/types in `providerMeta.properties` and `providerMeta.required`, and keep generated `meta.providers` consistent.
      - `categories` is a non-empty, unique array of category keys. Allowed values are enforced by `categories.items.enum` in `tools/schema.json` (see `providerMeta.properties.categories`). Whenever you add or remove an infrastructure category, update that enum so provider `categories` stays aligned with the category set used elsewhere in the schema.

- **`meta/categories.json`**
  - Concrete content for `meta.categories`.
  - Object: category key → `categoryMeta`.
  - Each value must match `$defs.categoryMeta`:
    - `key`, `label`, `icon`, `description`, `defaultSorting`.

- **`meta/columns.json`**
  - Concrete content for `meta.columns`.
  - Object: column key → `columnMeta`.
  - Each value must match `$defs.columnMeta`:
    - `key`, `label`, `icon`, `description`, `filter`, `sorting`, `pinning`, `cellType`, `group`.

**Important consistency rules:**

- **Category keys** must be consistent across:
  - `tools/schema.json`:
    - top-level properties in `properties` (e.g. `"apis"`);
    - `$defs.<category>` keys;
    - `$defs.columns.properties.<category>`
    - `providerMeta.properties.categories.items.enum`.
  - `meta/categories.json`:
    - object key and its `key` value.

- **Column keys** must be consistent across:
  - `tools/schema.json`:
    - column object inside `$defs.<category>.properties`.
    - column key inside `$defs.<category>.required`
  - `meta/columns.json`:
    - object key and its `key` value.

---

## 2. Adding a category

**Goal:** introduce a new category (e.g. `newCategoryKey`) and define its columns and metadata.

### Files to edit

- `tools/schema.json`
- `meta/categories.json`
- `meta/columns.json`

### Step 1 – Update `tools/schema.json`

1. **Add the category as a top-level property** in `"properties"`:

   This entry is added so the schema knows which categories are allowed at the top level of the document. Because the root schema sets `"additionalProperties": false`, the category key must be declared here—otherwise your data will fail validation.

   ```json
   "newCategoryKey": {
     "type": "array",
     "items": { "$ref": "#/$defs/newCategoryKey" }
   }
   ```

2. **Define the category item schema in `$defs`**:

   Add a $defs.newCategoryKey object (same key as step 1).
   Under $defs.<category>, list every column for this category in properties, and use it to define the type of each column (including nullable types where needed).
   List in required every column key that must be present on every row for this category.
   For more detail (including CSV notes and examples), see section 1.

   ```json
   "newCategoryKey": {
     "type": "object",
     "additionalProperties": false,
     "properties": {
       "slug": { "type": "string" },
       "provider": { "type": "string" },
       "planType": { "type": "string" },
       "price": { "type": ["string", "null"] },
       "customColumn": { "type": ["string", "null"] }
     },
     "required": [
       "slug",
       "provider",
       "planType",
       "price",
       "customColumn"
     ]
   }
   ```

3. **Add the category key to `$defs.columns.properties`**:

   Register newCategoryKey under top-level columns so the schema allows that category’s column-order array (details in section 1). Without this entry, columns.newCategoryKey is rejected.

   ```json
   "columns": {
     "type": "object",
     "additionalProperties": false,
     "properties": {
       ...
       "newCategoryKey": { "type": "array", "items": { "type": "string" } }
     }
   }
   ```

4. **Add the category key to `providerMeta.categories.enum`**:

   Add `"newCategoryKey"` to the enum list in:

```json
"$defs.providerMeta.properties.categories.items.enum"
```
   Update this list so the new category key is a valid value wherever providers reference infrastructure categories.

### Step 2 – Update `meta/categories.json`

Add a new entry whose **object key** is the category key (here `newCategoryKey`). Each value must match `$defs.categoryMeta` — see **section 1** (`$defs.categoryMeta`) for what each field means (`key`, `label`, `icon`, `description`, `defaultSorting`).

```json
"newCategoryKey": {
  "key": "newCategoryKey",
  "label": "Human readable name",
  "icon": "lucide:SomeIcon",
  "description": "Short explanation of this category.",
  "defaultSorting": "column key"
}
```

- `key` must exactly match the object key (`"newCategoryKey"`).
- `defaultSorting` is optional; if set, it must be a **column key** that exists in `meta/columns.json` for this category (see **section 1**).

### Step 3 – Update `meta/columns.json` for all new columns

For **each new column** you add under `$defs.newCategoryKey.properties` that should appear in the UI (labels, filters, sorting, etc.), add an entry in `meta/columns.json`: the **object key** is the column key, and the value must match `$defs.columnMeta`. See **section 1** (`$defs.columnMeta`) for what each field means (`key`, `label`, `icon`, `description`, `filter`, `sorting`, `pinning`, `cellType`, `group`).

Example for the columns above:

```json
"customColumn": {
  "key": "customColumn",
  "label": "Custom column",
  "icon": "lucide:Info",
  "description": "What this column means.",
  "filter": null,
  "sorting": "string",
  "pinning": null,
  "cellType": null,
  "group": "serviceDetails"
}
```

**Rule for humans and AI:**  
Every column in `$defs.newCategoryKey.properties` that should be visible / filterable must have a matching entry in `meta/columns.json`.

---

## 3. Removing a category

Assume the category key is `oldCategoryKey`.

### Before you edit

Copy the list of **column keys** from `$defs.oldCategoryKey.properties` in `tools/schema.json` (or keep a diff / the previous commit) **before** you delete that `$defs` block in Step 1. You need that list for **Step 3** — after removal, `$defs.oldCategoryKey` no longer exists.

### Files to edit

- `tools/schema.json`
- `meta/categories.json`
- `meta/columns.json` (optional — only when removing keys that are not used in any other category)

### Step 1 – Update `tools/schema.json`

1. **Remove the top-level category property** from root `"properties"`:

   This is the inverse of **§2** Step 1.1. **Delete** the entire entry:

    ```json
    "oldCategoryKey": { "type": "array", "items": { "$ref": "#/$defs/oldCategoryKey" } }
    ``` 
   (do not leave an empty stub).

2. **Remove `$defs.oldCategoryKey`** from `$defs`:

   Delete the **entire** object for that key under `$defs` (inverse of **§2** Step 1.2) — not just individual fields:

   ```json
   "oldCategoryKey": {
     "type": "object",
     "additionalProperties": false,
     "properties": {
       ...
     },
     "required": [
       ...
     ]
   }
   ```

3. **Remove the key from `$defs.columns.properties`**:

   Remove the `"oldCategoryKey": { "type": "array", "items": { "type": "string" } }` line (inverse of **§2** Step 1.3). The top-level `columns` mapping must not list a category that no longer exists. See **section 1** (`$defs.columns`).

   ```json
   "oldCategoryKey": { "type": "array", "items": { "type": "string" } }
   ```

4. **Remove the category key from `providerMeta.categories.enum`**:

   Remove `"oldCategoryKey"` from the enum in:

   ```json
   "$defs.providerMeta.properties.categories.items.enum"
   ```

   That enum is the **whitelist** of infrastructure category keys allowed in `meta.providers[*].categories` (inverse of **§2** Step 1.4). After this change, validation will reject that value on providers.

### Step 2 – Update `meta/categories.json`

Remove the entire object keyed by `oldCategoryKey` (same top-level key as in **§2** Step 2). See **section 1** (`$defs.categoryMeta`) for what that entry represented.

Delete this whole key–value pair from `meta/categories.json`:

```json
"oldCategoryKey": {
  "key": "oldCategoryKey",
  "label": "...",
  "icon": "...",
  "description": "...",
  "defaultSorting": "..."
}
```

### Step 3 – (Optional) Clean up `meta/columns.json`

Use the **column key list** you saved in **Before you edit** for `oldCategoryKey` (before removing the schema in Step 1):

1. For each column key, search `tools/schema.json` — check whether that key still appears in any **other** `$defs.<category>.properties`.
2. **Only if** it does **not** appear anywhere else, you may remove its entire entry from `meta/columns.json`.
3. If a column key is **shared** with another category, **do not** remove it.

See **section 1** (`$defs.columnMeta` / `meta/columns.json`). This avoids deleting `columnMeta` that other categories still use.

**Rule for humans and AI:**  
Never remove a `meta/columns.json` key until you have confirmed it is unused in every remaining `$defs.<category>` schema.

### Data on `main`

On the `main` branch, remove category data for `oldCategoryKey` and stop referencing it from providers:

- **`references/offers/<oldCategoryKey>.csv`** — delete this file if it exists (offers table for the category).
- **`listings/all-networks/<oldCategoryKey>.csv`** — delete this file if it exists.
- **`listings/specific-networks/<network>/<oldCategoryKey>.csv`** — delete this file under **each** `<network>` directory that contains it (one CSV per network where the category had listings).

Contribution layout and workflows are described in the [main branch README](https://github.com/Chain-Love/chain-love/blob/main/README.md);

---

## 4. Adding a column

**Goal:** Add a column to one category’s row schema, ensure UI metadata exists (new keys only), and update **all** category CSV tables on `main` so generated data and column order stay valid.

**Rule:** Every column that appears in `$defs.<category>.properties` must either **reuse** an existing `columnMeta` entry in `meta/columns.json` (same column key) or **add** a new one. See **section 1** (`$defs.<category>`, `$defs.columnMeta`, `meta/columns.json`).

There are two scenarios:

1. **Reuse an existing column key** in another category — the key already exists in `meta/columns.json` and in at least one `$defs.<category>.properties`. You only extend `$defs.someCategory` in `tools/schema.json` on this branch; you **do not** duplicate `columnMeta`.
2. **Add a brand-new column key** — the key does not exist yet. You change **`tools/schema.json`** and **`meta/columns.json`** on this branch.

In **both** scenarios you must update **category data on `main`** (see **Data on `main`** below).

### Files to edit

- `tools/schema.json`
- `meta/columns.json` **only** in scenario 2.
- **`main` branch:** all CSV files for the affected category (see **Data on `main`**).

### Scenario 1 – Reuse an existing column in another category

The column key (e.g. `existingColumn`) already has a `columnMeta` entry in `meta/columns.json` and appears in at least one other `$defs.<category>.properties`. You add the same key to category `someCategory`.

#### Step 1 – Update `tools/schema.json`

1. **Extend `$defs.someCategory.properties`** — add the property with the **same JSON type** as in other categories that already use this column (copy shape from an existing `$defs` block if unsure). For more detail on types, `required`, `examples`, and CSV behaviour, see **section 1** (`$defs.<category>`).

   ```json
   "existingColumn": { "type": ["string", "null"] }
   ```

2. **Update `$defs.someCategory.required`** — add `"existingColumn"` here:

   ```json
   "required": [
     ...
     "existingColumn"
   ]
   ```

   For more detail, see **section 1** (`$defs.<category>`).

#### Step 2 – `meta/columns.json`

Do **not** add another entry — `existingColumn` is already defined. See **section 1** (`$defs.columnMeta`) if you need to adjust shared UI behaviour (affects every category that uses that key).

Then update **Data on `main`** (below).

### Scenario 2 – Add a brand-new column

The key (e.g. `newColumn`) does not exist in any `$defs.<category>.properties` nor in `meta/columns.json`. You add it to category `someCategory`.

#### Step 1 – Update `tools/schema.json`

Under **`$defs.someCategory`**, add the column to `properties` and, if needed, to `required`. Field semantics match **§2** Step 1.2: `properties` lists types per column; `required` lists mandatory keys; See **section 1**.

```json
"newColumn": {
  "type": ["string", "null"]
}
```

Add `"newColumn"` here:

```json
"required": [
  ...
  "newColumn"
]
```

For more detail, see **section 1** (`$defs.<category>`).

#### Step 2 – Update `meta/columns.json`

Add a top-level entry whose **object key** is `newColumn` and whose value matches `$defs.columnMeta`. For what each field means and how to set it, see **section 1** (`$defs.columnMeta`) — `key`, `label`, `icon`, `description`, `filter`, `sorting`, `pinning`, `cellType`, `group`.

For example:
```json
"newColumn": {
  "key": "newColumn",
  "label": "New column",
  "icon": "lucide:Info",
  "description": "What this column means.",
  "filter": null,
  "sorting": "string",
  "pinning": null,
  "cellType": null,
  "group": "serviceDetails"
}
```

**Rule for humans and AI:**  
Every new column key that should be visible / filterable in the UI needs a complete `columnMeta` entry consistent with **section 1**.

Then update **Data on `main`** (below).

### Data on `main`

Generated JSON (including top-level `columns.<category>` column order) is driven from **CSV headers** for that category on `main`. After changing the schema on this branch, mirror the new column in **every** relevant file for category `someCategory`:

- `references/offers/<someCategory>.csv`
- `listings/all-networks/<someCategory>.csv`
- `listings/specific-networks/<network>/<someCategory>.csv` (each network that lists this category)

Add the column name to the **header row** (and fill cells per your data; required columns must be satisfied for every row). Layout, conventions, and contribution flow: [main branch README](https://github.com/Chain-Love/chain-love/blob/main/README.md); this mirrors the note at the top of this guide.

---

## 5. Removing a column

**Goal:** Drop a column from one category’s row schema or remove the column key from the whole platform, keep `meta/columns.json` consistent, and update **CSV data on `main`** (remove the column from headers/rows where applicable).

**Rule:** Edits to `$defs.<category>.properties` / `required` follow **section 1**. For `columnMeta` removal, see **section 1** (`$defs.columnMeta` / `meta/columns.json`).

There are two scenarios (inverse of **§4**):

1. **Remove the column from one category only** — the key still exists in `meta/columns.json` and in at least one **other** `$defs.<category>.properties`. You only change `$defs.someCategory` in `tools/schema.json` on this branch; you **do not** remove `columnMeta`.
2. **Remove the column key everywhere** — the key no longer appears in **any** category schema. You change **`tools/schema.json`** and **`meta/columns.json`** on this branch.

In **both** scenarios you must update **category data on `main`** (see **Data on `main`** below).

### Files to edit

- `tools/schema.json`;
- `meta/columns.json` **only** in scenario 2.
- **`main` branch:** all CSV files for each category you change (see **Data on `main`**).

### Scenario 1 – Column still used in other categories

The column key (e.g. `columnKey`) still appears in at least one other `$defs.<category>.properties`. You remove it only from category `someCategory`. **Inverse of §4** Scenario 1.

#### Step 1 – Update `tools/schema.json`

1. **In `$defs.someCategory.properties`** — delete the `"columnKey"` entry:

   ```json
   "columnKey": { ... }
   ```

2. **In `$defs.someCategory.required`** — remove `"columnKey"` from the array:

   ```json
   "required": [
     ...
   ]
   ```

   For more detail, see **section 1** (`$defs.<category>`).

#### Step 2 – `meta/columns.json`

**Do not** remove the `columnKey` entry — other categories still use it. See **section 1** (`$defs.columnMeta`) only if you are adjusting shared UI behaviour (affects every category that still uses that key).

Then update **Data on `main`** (below).

### Scenario 2 – Column key removed everywhere

The key (e.g. `columnKey`) should not appear in **any** `$defs.<category>.properties`. **Inverse of §4** Scenario 2.

**Before you edit:** Search `tools/schema.json` for `"columnKey"` under every `$defs.<category>.properties` so you know which categories and CSVs on `main` you must touch.

#### Step 1 – Update `tools/schema.json`

- Remove `"columnKey"` from `properties` in **every** `$defs.<category>` where it appears.
- Remove `"columnKey"` from every `required` array where it appears.

See **section 1** (`$defs.<category>`).

#### Step 2 – Update `meta/columns.json`

Remove the entire top-level entry:

```json
"columnKey": {
  "key": "columnKey",
  ...
}
```

For what that object contained, see **section 1** (`$defs.columnMeta`).

**Rule for humans and AI:**  
Do not delete the `meta/columns.json` entry until `columnKey` is gone from **every** `$defs.<category>.properties` in `tools/schema.json`.

Then update **Data on `main`** (below).

### Data on `main`

- **Scenario 1:** Remove `columnKey` from the **header row** (and row data) in **every** CSV for **`someCategory`** only:
  - `references/offers/<someCategory>.csv`
  - `listings/all-networks/<someCategory>.csv`
  - `listings/specific-networks/<network>/<someCategory>.csv` (each relevant network)

- **Scenario 2:** Remove `columnKey` from the CSVs of **every** category that had it (match the categories you changed in Step 1).

Layout and conventions: [main branch README](https://github.com/Chain-Love/chain-love/blob/main/README.md); this mirrors the note at the top of this guide.

---

## 6. Checklist for humans and AI agents

Full steps, examples, and field semantics are in **§2–§5** and **section 1**. Use this list as a quick map.

When asked to **add a category**, an agent should:

1. Edit `tools/schema.json`:
   - Add new top-level category array in `properties`.
   - Add new `$defs.<categoryKey>` object with its columns (in `properties` and `required`).
   - Add `<categoryKey>` to `$defs.columns.properties`.
   - Add `<categoryKey>` to the enum **`$defs.providerMeta.properties.categories.items.enum`** (whitelist for `meta.providers[*].categories`).
2. Edit `meta/categories.json`:
   - Add `categoryMeta` entry with `key`, `label`, `icon`, `description`, `defaultSorting` (see **section 1** / **§2** Step 2).
3. Edit `meta/columns.json`:
   - Add `columnMeta` entries for **every new column** in `$defs.<categoryKey>.properties` that should appear in the UI (see **§2** Step 3).
4. **On `main`:** add or update category CSVs and related data so they match the new category (see the intro at the top of this guide and the [main branch README](https://github.com/Chain-Love/chain-love/blob/main/README.md); schema/meta on this branch must stay consistent with those tables).

When asked to **remove a category**, an agent should:

1. **Before editing schema:** copy the column keys from `$defs.<categoryKey>.properties` (needed for optional `meta/columns.json` cleanup — see **§3** Before you edit).
2. Edit `tools/schema.json`:
   - Remove the category from root `properties`.
   - Remove `$defs.<categoryKey>`.
   - Remove `<categoryKey>` from `$defs.columns.properties`.
   - Remove `<categoryKey>` from **`$defs.providerMeta.properties.categories.items.enum`**.
3. Edit `meta/categories.json`:
   - Remove the category entry.
4. Optionally clean up `meta/columns.json`:
   - Only remove column entries that are not used in any other `$defs.<category>.properties` (see **§3** Step 3).
5. **On `main`:** remove category CSV files and stop referencing the category from providers (see **§3** Data on `main` and the [main branch README](https://github.com/Chain-Love/chain-love/blob/main/README.md)).

When asked to **add a column**, an agent should:

- **§4 Scenario 1** (reuse an existing column key in another category):
  - Edit `tools/schema.json`: add the column to `$defs.<category>.properties` and, if required, to `$defs.<category>.required` for the target category.
  - Do **not** add a duplicate `columnMeta` entry in `meta/columns.json`.
- **§4 Scenario 2** (brand-new column key):
  - Edit `tools/schema.json`: add the column to `$defs.<category>.properties` and, if required, to `$defs.<category>.required`.
  - Edit `meta/columns.json`: add a `columnMeta` entry for the new column key.
- **On `main`:** update all CSV files for that category (`references/offers/`, `listings/all-networks/`, `listings/specific-networks/<network>/`) so the new column is in every header row (see **§4** and the [main branch README](https://github.com/Chain-Love/chain-love/blob/main/README.md)).

When asked to **remove a column**, an agent should:

- **§5 Scenario 1** (column key still used in other categories):
  - Edit `tools/schema.json`: remove the column from `$defs.<category>.properties` and from `$defs.<category>.required` for the target category only.
  - Leave `meta/columns.json` unchanged.
  - On `main`, remove the column from that category’s CSV files (see **§5**).
- **§5 Scenario 2** (column key removed everywhere):
  - Edit `tools/schema.json`: remove the column from every `$defs.<category>` where it appears.
  - Remove its entry from `meta/columns.json`.
  - On `main`, remove the column from every affected category CSV (see **§5**).

