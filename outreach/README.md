# Chain.Love Outreach Registry

This directory tracks external outreach performed under the [Chain.Love ecosystem discovery bounty program](https://github.com/Chain-Love/chain-love/discussions/3731).

The registry exists to prevent:

* multiple active submissions to the same organization;
* repeated outreach to organizations that previously rejected Chain.Love;
* outreach to organizations that explicitly asked not to be contacted.

The registry tracks **external submissions only**. Internally prepared or approved patches are not added until an authorized outreacher actually opens an external pull request.

## Registry

Outreach history is stored in `registry.csv`.

Each row represents one external Chain.Love outreach attempt.

### Columns

* `organization` — destination organization or GitHub repository owner.
* `repository` — destination repository in `owner/repository` format.
* `external_pr` — full URL of the external pull request.
* `status` — current state of the external submission.
* `status_date` — date on which the current status was set, in `YYYY-MM-DD` format.
* `outreacher` — GitHub username of the authorized Chain.Love outreacher who submitted the external PR.
* `comment` — optional context about the outcome or restrictions.

### Example

```csv
organization,repository,external_pr,status,status_date,outreacher,comment
example-org,example-org/docs,"https://github.com/example-org/docs/pull/45",merged,2026-09-10,Adisaok,Accepted and published by the destination project.
another-org,another-org/developer-docs,"https://github.com/another-org/developer-docs/pull/18",rejected,2026-09-12,harunsulaiman,Maintainer declined the proposed addition.
no-contact-org,no-contact-org/docs,"https://github.com/no-contact-org/docs/pull/77",rejected,2026-09-14,Adisaok,DO_NOT_CONTACT: Maintainer explicitly requested no further Chain.Love outreach.
```

## Statuses

Only the following statuses are allowed:

### `submitted`

The external pull request has been opened and is awaiting a decision.

Only one `submitted` entry may exist for a destination organization at a time.

### `merged`

The destination project accepted and merged the external pull request.

### `rejected`

The destination project rejected or closed the proposal without merging it.

A rejected organization must not receive another Chain.Love outreach for at least 90 days from `status_date`.

After the cooldown expires, a new outreach is not automatically allowed. The previous rejection must still be reviewed before another submission is authorized.

## Do-not-contact requests

If a destination maintainer explicitly asks Chain.Love not to contact the organization again, the entry must:

* use `rejected` as its status; and
* begin the `comment` field with the exact marker `DO_NOT_CONTACT:`.

Example:

`DO_NOT_CONTACT: Maintainer explicitly requested no further Chain.Love outreach.`

Organizations with a `DO_NOT_CONTACT:` entry must not receive future outreach unless the restriction is explicitly removed by the Chain.Love core team.

## Pre-submission check

Before opening any external pull request, the outreacher must search the registry by `organization`.

Do not submit if:

1. the organization already has an entry with `status=submitted`;
2. the organization has a `rejected` entry less than 90 days old;
3. any entry for the organization contains `DO_NOT_CONTACT:`.

Previous `merged` or older `rejected` entries must be reviewed before another outreach is authorized, to avoid repeated submissions to the same organization.

## Updating the registry

When an external pull request is opened:

1. Add a new row.
2. Set `status` to `submitted`.
3. Set `status_date` to the date the PR was opened.

When the destination makes a final decision:

1. Change `status` to either `merged` or `rejected`.
2. Replace `status_date` with the date of that decision.
3. Add relevant context to `comment` when necessary.

Rows must not be deleted after an outreach attempt has been recorded. The registry is intended to preserve outreach history.
