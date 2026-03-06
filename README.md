## Infrastructure schema & meta guide

This guide explains how to **add new categories and columns for the Chain.Love platform**:

- `tools/schema.json` – the JSON Schema.
- `meta/categories.json` – category metadata.
- `meta/columns.json` – column metadata.

Data files are **out of scope** here. They live in a `main` branch and are covered by the [respective README.md.](https://github.com/Chain-Love/chain-love/blob/main/README.md).

---

## 1. Files and responsibilities

- **`tools/schema.json`**
  - Defines the top-level properties for each category:
    - `apis`, `explorers`, `oracles`, etc.
  - For each category, defines a JSON Schema object in `$defs`:
    - Example: `$defs/apis`, `$defs/wallets`, etc.
    - Each schema lists the **fields** (properties) for that category.
  - Defines:
    - `$defs.columns`: list of **category keys** and says each value is an array of strings (column keys). We only care that this exists and contains all category keys.
    - `$defs.categoryMeta`: shape of category metadata.
    - `$defs.columnMeta`: shape of column metadata.
    - `$defs.providerMeta`: shape of provider metadata, including the list of allowed category keys.

- **`meta/categories.json`**
  - Concrete content for `meta.categories`.
  - Object: category key → `categoryMeta`.
  - Each value must match `$defs.categoryMeta`:
    - `key`, `label`, `icon`, `description`.

- **`meta/columns.json`**
  - Concrete content for `meta.columns`.
  - Object: column key → `columnMeta`.
  - Each value must match `$defs.columnMeta`:
    - `key`, `label`, `icon`, `description`, `filter`, `sorting`, `pinning`, `cellType`.

**Important consistency rules:**

- **Category keys** must be consistent across:
  - `tools/schema.json`:
    - top-level properties in `properties` (e.g. `"apis"`);
    - `$defs.columns.properties` keys;
    - `providerMeta.properties.categories.items.enum`.
  - `meta/categories.json`:
    - object key and its `key` field.

- **Column (field) keys** must be consistent across:
  - `tools/schema.json`:
    - property names inside `$defs.<category>.properties`.
  - `meta/columns.json`:
    - object key and its `key` field.

---

## 2. Adding a category

**Goal:** introduce a new category (e.g. `newCategoryKey`) and define its fields and metadata.

### Files to edit

- `tools/schema.json`
- `meta/categories.json`
- `meta/columns.json`

### Step 1 – Update `tools/schema.json`

1. **Add the category as a top-level property** in `"properties"`:

   ```json
   "newCategoryKey": {
     "type": "array",
     "items": { "$ref": "#/$defs/newCategoryKey" }
   }
   ```

2. **Define the category item schema in `$defs`**:

   ```json
   "newCategoryKey": {
     "type": "object",
     "additionalProperties": false,
     "properties": {
       "slug": { "type": "string" },
       "provider": { "type": "string" },
       "planType": { "type": "string" },
       "price": { "type": ["string", "null"] },
       "customField": { "type": ["string", "null"] }
     },
     "required": [
       "slug",
       "provider",
       "planType",
       "price",
       "customField"
     ]
   }
   ```

   This defines the **set of fields** for this category:
   `slug`, `provider`, `planType`, `price`, `customField`, etc.

3. **Add the category key to `$defs.columns.properties`**:

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

   This ensures that a `columns.newCategoryKey` array is allowed by the schema.

4. **Add the category key to `providerMeta.categories.enum`**:

   Add `"newCategoryKey"` to the enum list in:

```json
"$defs.providerMeta.properties.categories.items.enum"
```

### Step 2 – Update `meta/categories.json`

Add a new entry:

```json
"newCategoryKey": {
  "key": "newCategoryKey",
  "label": "Human readable name",
  "icon": "lucide:SomeIcon",
  "description": "Short explanation of this category."
}
```

Requirements:

- `key` must exactly match the JSON key: `"newCategoryKey"`.
- Object must match the `categoryMeta` schema.

### Step 3 – Update `meta/columns.json` for all new fields

For **each field** defined in `$defs.newCategoryKey.properties` that should have UI metadata, add a `columnMeta` entry in `meta/columns.json`.

Example for the fields above:

```json
"slug": {
  "key": "slug",
  "label": "Slug",
  "icon": null,
  "description": null,
  "filter": null,
  "sorting": null,
  "pinning": null,
  "cellType": null,
  "group": "identity"
},
"provider": {
  "key": "provider",
  "label": "Provider",
  "icon": "lucide:Unplug",
  "description": "Service provider (company/organization).",
  "filter": "searchableMultiSelect",
  "sorting": "string",
  "pinning": "left",
  "cellType": "provider",
  "group": "identity"
},
"planType": {
  "key": "planType",
  "label": "Plan",
  "icon": "plan.svg||lucide:ClipboardList",
  "description": "Plan type.",
  "filter": "searchableMultiSelect",
  "sorting": "string",
  "pinning": null,
  "cellType": "planType",
  "group": "serviceDetails"
},
"price": {
  "key": "price",
  "label": "Price",
  "icon": "lucide:BadgeDollarSign",
  "description": "Price / cost.",
  "filter": "range",
  "sorting": "number",
  "pinning": null,
  "cellType": "numericRange",
  "group": "pricing"
},
"customField": {
  "key": "customField",
  "label": "Custom field",
  "icon": "lucide:Info",
  "description": "What this field means.",
  "filter": null,
  "sorting": "string",
  "pinning": null,
  "cellType": null,
  "group": "serviceDetails"
}
```

**Rule for humans and AI:**  
Every field in `$defs.newCategoryKey.properties` that should be visible / filterable must have a matching entry in `meta/columns.json`.

---

## 3. Removing a category

Assume the category key is `oldCategoryKey`.

### Files to edit

- `tools/schema.json`
- `meta/categories.json`
- `meta/columns.json` (optional, see note below)

### Step 1 – Update `tools/schema.json`

1. **Remove the top-level property** from `"properties"`:

   ```json
   "oldCategoryKey": {
     ...
   }
   ```

2. **Remove the `$defs.oldCategoryKey` schema** from `$defs`.

3. **Remove the key from `$defs.columns.properties`**:

   ```json
   "oldCategoryKey": { "type": "array", "items": { "type": "string" } }
   ```

4. **Remove the key from `providerMeta.categories.enum`**.

### Step 2 – Update `meta/categories.json`

Remove the entire entry:

```json
"oldCategoryKey": { ... }
```

### Step 3 – (Optional) Clean up column metadata

Some column keys may be used **only in this category**.  
If you want to remove such columns completely:

1. For each field key defined in `$defs.oldCategoryKey.properties`:
   - Search in `tools/schema.json` to see if that key appears in any other `$defs.<category>.properties`.
   - **Only if it does NOT appear anywhere else**, you may safely remove its entry from `meta/columns.json`.

2. If a field key is shared with other categories, **do not remove it** from `meta/columns.json`.

This avoids accidentally deleting column metadata that is still needed.

---

## 4. Adding a column (field)

Here we only care about schema + meta in this branch.

**Rule:** A field in a category schema must always have a matching entry in `meta/columns.json`. We never add a field to the schema without adding (or reusing) its column metadata.

There are two scenarios:

1. **Add an existing column to another category** – the field key already exists in `meta/columns.json` and in at least one `$defs.<category>.properties`. You only add it to one more category. Changes are **only in `tools/schema.json`**.
2. **Add a brand new field** – the field key does not exist anywhere yet. Changes are in **both** `tools/schema.json` and `meta/columns.json`.

### Scenario 1 – Add an existing column to another category

The field (e.g. `existingField`) already has a `columnMeta` entry in `meta/columns.json` and is used in at least one category. You want to use it in one more category, e.g. `someCategory`.

**Files to edit:** only `tools/schema.json`.

1. In `$defs.someCategory.properties`, add the property (same shape as in other categories that already have it), e.g.:

   ```json
   "existingField": { "type": ["string", "null"] }
   ```

2. If this field must always be present for `someCategory`, add `"existingField"` to `$defs.someCategory.required`.

Do **not** change `meta/columns.json` – the column metadata already exists.

### Scenario 2 – Add a brand new field

The field (e.g. `newField`) does not exist in any category schema nor in `meta/columns.json`. You add it to category `someCategory`.

**Files to edit:** `tools/schema.json` and `meta/columns.json`.

1. **`tools/schema.json` – extend the category in two places**

   - In **`$defs.someCategory.properties`**, add:

     ```json
     "newField": {
       "type": ["string", "null"]
     }
     ```

   - In **`$defs.someCategory.required`**, add `"newField"` if this field must always be present for this category.

2. **`meta/columns.json` – add column metadata**

   Add a new entry:

   ```json
   "newField": {
     "key": "newField",
     "label": "New field",
     "icon": "lucide:Info",
     "description": "What this field means.",
     "filter": null,
     "sorting": "string",
     "pinning": null,
     "cellType": null,
     "group": "serviceDetails"
   }
   ```

After this, the schema and column metadata stay in sync.

---

## 5. Removing a column (field)

Again, we only work with schema + meta in this branch.

There are two levels of removal:

1. Remove a field from a specific category’s schema, but leave it for others.
2. Remove a field completely from all schemas and metadata.

### Files to edit

- `tools/schema.json`
- `meta/columns.json` (only if field is fully removed everywhere)

### Case A – Remove field from one category only

Assume `fieldKey` is used in multiple categories and you want to stop using it in `someCategory`, but keep it elsewhere.

1. **`tools/schema.json`**
   - In `$defs.someCategory.properties`, delete the `"fieldKey"` property.
   - If `"fieldKey"` appears in the `"required"` list for `someCategory`, remove it there as well.

2. **`meta/columns.json`**
   - **Do not change** anything here as long as `fieldKey` is still used in at least one other category.

This keeps the column metadata available for other categories that still use the field.

### Case B – Remove field completely

Assume `fieldKey` should no longer exist in **any** category.

1. **`tools/schema.json`**
   - Remove `"fieldKey"` from `properties` of every `$defs.<category>` where it appears.
   - Remove `"fieldKey"` from `required` arrays in those categories, if present.

2. **`meta/columns.json`**
   - Remove the entire `"fieldKey": { ... }` entry.

**Before doing Case B**, make sure that:

- `fieldKey` is not present in any `$defs.<category>.properties` in `tools/schema.json`.
- You really do not want this field in any category anymore.

---

## 6. Checklist for humans and AI agents

When asked to **add a category**, an agent should:

1. Edit `tools/schema.json`:
   - Add new top-level category array in `properties`.
   - Add new `$defs.<categoryKey>` object with its fields (in `properties` and `required`).
   - Add `<categoryKey>` to `$defs.columns.properties`.
   - Add `<categoryKey>` to `providerMeta.categories.enum`.
2. Edit `meta/categories.json`:
   - Add `categoryMeta` entry with `key`, `label`, `icon`, `description`.
3. Edit `meta/columns.json`:
   - Add `columnMeta` entries for **every new field** in `$defs.<categoryKey>.properties`.

When asked to **remove a category**, an agent should:

1. Edit `tools/schema.json`:
   - Remove the category from root `properties`.
   - Remove `$defs.<categoryKey>`.
   - Remove `<categoryKey>` from `$defs.columns.properties`.
   - Remove `<categoryKey>` from `providerMeta.categories.enum`.
2. Edit `meta/categories.json`:
   - Remove the category entry.
3. Optionally clean up `meta/columns.json`:
   - Only remove column entries that are not used in any other `$defs.<category>.properties`.

When asked to **add a column/field**, an agent should:

- **If adding an existing column to another category** (field key already in `meta/columns.json` and in at least one category schema):
  - Edit only `tools/schema.json`: add the field to `$defs.<category>.properties` and, if required, to `$defs.<category>.required` for the target category.
- **If adding a brand new field** (field key does not exist anywhere):
  - Edit `tools/schema.json`: add the field to `$defs.<category>.properties` and, if required, to `$defs.<category>.required`.
  - Edit `meta/columns.json`: add a `columnMeta` entry for the new field key.

When asked to **remove a column/field**, an agent should:

- If removal is per-category:
  - Remove the field from `$defs.<category>.properties` and from `$defs.<category>.required` for that category.
  - Leave `meta/columns.json` unchanged if other categories still use the field.
- If removal is global:
  - Remove the field from `properties` and `required` of every `$defs.<category>` where it appears.
  - Remove its entry from `meta/columns.json`.

