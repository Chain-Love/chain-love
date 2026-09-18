# Chain.Love Outreach Registry

This directory tracks external outreach performed under the [Chain.Love ecosystem discovery bounty program](https://github.com/Chain-Love/chain-love/discussions/3731).

The registry exists to prevent:

* multiple active submissions to the same organization;
* repeated outreach to organizations that previously rejected Chain.Love;
* repeated attempts against destinations where contribution is currently blocked;
* outreach to organizations that explicitly asked not to be contacted.

The registry tracks external outreach attempts and their current state.

An outreach attempt may use whatever contribution mechanism is required by the destination project, including a pull request, issue, proposal, discussion, form, or another externally visible submission path.

Internally prepared or approved patches are not added unless:

* an authorized outreacher has made an external submission; or
* the outreacher has verified that the destination currently provides no usable submission path and the attempt is recorded as `blocked`.

## Registry

Outreach history is stored in `registry.csv`.

Each row represents one Chain.Love outreach attempt for a destination organization.

### Columns

* `organization` — destination organization or GitHub repository owner.
* `repository` — destination repository in `owner/repository` format.
* `external_url` — full URL of the external contribution artifact or submission path used for the outreach attempt, such as a pull request, issue, proposal, discussion, form, or similar destination-required workflow. May be blank only when `status=blocked` and no external submission URL exists.
* `status` — current state of the outreach attempt.
* `status_date` — date on which the current status was set, in `YYYY-MM-DD` format.
* `outreacher` — GitHub username of the authorized Chain.Love outreacher responsible for the attempt.
* `comment` — optional context about the submission, outcome, restrictions, or blocked state.

### Example

```csv
organization,repository,external_url,status,status_date,outreacher,comment
example-org,example-org/docs,"https://github.com/example-org/docs/pull/45",merged,2026-09-10,Adisaok,Accepted and published by the destination project.
another-org,another-org/developer-docs,"https://github.com/another-org/developer-docs/issues/123",submitted,2026-09-12,harunsulaiman,Destination requires an issue to be approved before a pull request may be opened.
blocked-org,blocked-org/docs,,blocked,2026-09-14,Adisaok,External pull request and issue creation are restricted to repository collaborators.
no-contact-org,no-contact-org/docs,"https://github.com/no-contact-org/docs/pull/77",rejected,2026-09-14,Adisaok,DO_NOT_CONTACT: Maintainer explicitly requested no further Chain.Love outreach.
```

## Statuses

Only the following statuses are allowed:

### `submitted`

An external contribution has been submitted using the workflow accepted or required by the destination project and is awaiting a decision or next step.

The `external_url` may point to a pull request, issue, proposal, discussion, form, or another externally visible artifact required by the destination contribution process.

Examples include:

* a pull request awaiting review;
* an issue awaiting maintainer approval before a pull request may be opened;
* a proposal or discussion required before implementation;
* another destination-specific contribution artifact that represents an active Chain.Love submission.

Only one active `submitted` entry may exist for a destination organization at a time unless the Chain.Love core team explicitly approves otherwise.

### `merged`

The destination project accepted the contribution and the requested Chain.Love addition was incorporated into the destination project.

This status may be used even when the contribution process did not use a pull request, as long as the destination ultimately accepted and published the proposed addition.

### `rejected`

The destination project rejected or closed the proposal without accepting the requested Chain.Love addition.

A rejected organization must not receive another Chain.Love outreach for at least 90 days from `status_date`.

After the cooldown expires, a new outreach is not automatically allowed. The previous rejection must still be reviewed before another submission is authorized.

### `blocked`

The destination currently provides no usable path for the authorized outreacher to submit the approved contribution.

This may include cases where:

* pull request creation is restricted to repository collaborators;
* issue creation is restricted;
* the required submission form or contribution channel is unavailable;
* contribution permissions prevent the outreacher from completing the required external action;
* the destination contribution process requires a maintainer-mediated action that has not yet been provided.

`blocked` may represent either a temporary or effectively permanent restriction.

A `blocked` row must describe the reason in `comment`.

`external_url` may be blank when no external artifact could be created. If there is a relevant external page documenting or representing the blocked contribution path, it may be recorded instead.

A blocked destination must not receive repeated outreach attempts through the same unavailable path unless:

* the destination's contribution rules or permissions have changed;
* a maintainer provides a new submission path; or
* the Chain.Love core team explicitly authorizes another attempt.

When a blocked destination later becomes actionable, update the existing row or create the appropriate new outreach record according to the actual submission flow.

## Do-not-contact requests

If a destination maintainer explicitly asks Chain.Love not to contact the organization again, the entry must:

* use `rejected` as its status; and
* begin the `comment` field with the exact marker `DO_NOT_CONTACT:`.

Example:

`DO_NOT_CONTACT: Maintainer explicitly requested no further Chain.Love outreach.`

Organizations with a `DO_NOT_CONTACT:` entry must not receive future outreach unless the restriction is explicitly removed by the Chain.Love core team.

## Pre-submission check

Before starting a new external outreach attempt, the outreacher must search the registry by `organization`.

Do not submit if:

1. the organization already has an active entry with `status=submitted`;
2. the organization has a `rejected` entry less than 90 days old;
3. any entry for the organization contains `DO_NOT_CONTACT:`;
4. the organization has a relevant `blocked` entry and the documented restriction has not changed.

Previous `merged`, older `rejected`, or `blocked` entries must be reviewed before another outreach is authorized, to avoid duplicate submissions or repeated attempts against the same restriction.

## Updating the registry

When an external contribution is submitted:

1. Add a new row if no current row represents that outreach attempt.
2. Set `status` to `submitted`.
3. Set `external_url` to the URL of the external pull request, issue, proposal, discussion, form, or other destination-required contribution artifact.
4. Set `status_date` to the date the external submission was made.
5. Add context to `comment` when the submission mechanism is not self-explanatory.

When an approved outreach cannot be externally submitted because the destination provides no usable submission path:

1. Add a row with `status=blocked`.
2. Set `status_date` to the date the restriction was verified.
3. Leave `external_url` blank if no external artifact exists.
4. Explain the blocking condition in `comment`.

When the destination makes a final decision:

1. Change `status` to either `merged` or `rejected`.
2. Replace `status_date` with the date of that decision.
3. Preserve the relevant `external_url`.
4. Add relevant context to `comment` when necessary.

When a previously blocked destination becomes actionable:

1. Verify that the documented restriction has changed or that a new approved submission path exists.
2. Record the external submission and change the current state to `submitted`, or add a new outreach row if preserving the separate attempt is more appropriate.
3. Set `external_url` to the new external contribution artifact.
4. Update `status_date`.
5. Preserve enough context in `comment` to explain the transition from `blocked`.

Rows must not be deleted after an outreach attempt has been recorded. The registry is intended to preserve outreach history.
