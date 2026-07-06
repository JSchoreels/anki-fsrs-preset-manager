# FSRS data touched by the add-on

This add-on reads and updates Anki deck option data through Anki's deck manager APIs.

## Preset data

Preset rows map to deck configuration records returned by `mw.col.decks.all_config()`.

The add-on reads and writes:

- `desiredRetention` / `desired_retention`: preset-level desired retention.
- `new.delays`: Anki legacy deck-config learning steps, stored as minute values.
- `lapse.delays`: Anki legacy deck-config relearning steps, stored as minute values.
- `learnSteps` / `learn_steps` and `relearnSteps` / `relearn_steps`: newer/proto-like step keys supported by the helper layer when the legacy `new.delays` / `lapse.delays` fields are not present.
- `fsrsVersion` / `fsrs_version`: preset-level FSRS picker value. The fork currently stores FSRS 7 as `0`, FSRS 6 as `1`, FSRS 5 as `2`, and FSRS 4 as `3`. If absent, the add-on treats the preset as the Anki main-branch shape before the FSRS picker and does not show or write the FSRS version column.
- `fsrsParams7`, `fsrsParams6`, `fsrsParams5`, `fsrsParams4` and snake-case variants: shown in the FSRS params column with each value truncated to at most 3 decimal places; optimize updates the parameter list matching the selected FSRS version.
- `fsrs7IncludeSameDayOptimize` / `fsrs7IncludeSameDayEvaluate`: auxiliary legacy deck-config keys used by the local Anki fork for FSRS-7 same-day flags.

When available, the FSRS-7 same-day keys are:

- `fsrs7IncludeSameDayOptimize`
- `fsrs7IncludeSameDayEvaluate`

Missing same-day keys are shown as disabled in this add-on. The add-on only shows a same-day option as checked when the corresponding key is explicitly `true`.

On Anki builds without FSRS-7 support, the same-day columns are hidden and FSRS params are read in Anki main-branch order: `fsrsParams6`, then `fsrsParams5`, then `fsrsParams4`.

The bulk FSRS control changes the preset-level `fsrsVersion` / `fsrs_version` field for every preset currently shown in the table that already has an FSRS picker field. The values are written only when the user clicks Save, or when another action first saves the table before running. The add-on always offers FSRS 7 and FSRS 6 when the picker exists, and also offers older FSRS versions when matching parameter fields are present in the preset payload.

The bulk Desired Retention control changes the preset-level Desired Retention fields for every preset currently shown in the table. The values are written only when the user clicks Save, or when another action first saves the table before running.

The Learning steps and Relearning steps columns read and write preset-level step arrays. The editor displays these with Anki's deck-options step format: space-separated whole values with `s`, `m`, `h`, or `d` suffixes, such as `10m 1h 1d`. A bare number is parsed as minutes. Empty step text writes an empty list. Values that Anki's parser treats as zero are ignored. When a legacy Anki deck-config payload contains both nested legacy delays and ignored top-level step keys, the add-on uses and updates the nested legacy delays.

The bulk step control changes both preset-level step arrays for every preset currently shown in the table. The values are normalized through the same parser before they are copied into preset rows. They are written only when the user clicks Save, or when another action first saves the table before running.

## Deck data

Deck rows map to normal decks returned by `mw.col.decks.all_names_and_ids(include_filtered=False)`.

The add-on reads:

- `conf`: preset assignment, used only for grouping decks under presets.
- `cards` and `revlog`: used by the default-on empty-preset filter. A preset is hidden when no deck uses it, or when cards in its assigned decks have no review-log rows.

The add-on reads and writes:

- `desiredRetention` / `desired_retention`: deck-level desired retention override.

When the deck override checkbox is cleared, the deck-level desired retention is written as `None`, so Anki falls back to the preset desired retention.

The desired-retention editor reads the add-on config key `desired_retention_minimum` as its lower bound. The default config value is `0.7`, matching Anki's normal 70% minimum. The value is stored as a fraction, so `0.5` means 50%.

If any existing preset or deck already stores a lower desired-retention value than the configured minimum, the editor uses that lower existing value so it can continue editing data that is already present in the collection.

## Optimize and evaluate

Optimize uses Anki's `compute_fsrs_params` backend method, then writes the returned parameters to the preset and saves it through `mw.col.decks.update_config()`.

The optimize request includes the number of relearning steps whose cumulative delay is still under one day.

Evaluate uses Anki's `evaluate_params_legacy` backend method with the preset's selected FSRS parameters. For FSRS-7 presets, the request includes the stored same-day evaluate flag.
