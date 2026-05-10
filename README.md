# FSRS Preset Manager

Manage FSRS deck options from one table instead of opening every preset one by one.

## What it does

- Shows your FSRS presets in a single window.
- Edits preset FSRS version on Anki builds that expose the FSRS picker.
- Edits preset Desired Retention.
- Runs Optimize for a preset.
- Runs Evaluate for a preset.
- Shows the current FSRS parameters for each preset.
- Opens Anki's Deck Options screen for a preset.
- Applies one FSRS version or one Desired Retention value to every preset currently shown in the table.
- Optionally expands presets to show the decks using them.
- Allows deck-level Desired Retention overrides when deck rows are shown.

## Deck View

Deck rows are hidden by default. Enable **Show decks** to see which decks use each preset.

When deck rows are visible, the **Deck Override** column lets you set or clear a deck-specific Desired Retention. Clearing the checkbox makes the deck use the preset Desired Retention again.

## Empty Preset Filter

**Hide empty presets** is enabled by default.

It hides presets that:

- are not used by any deck, or
- are used only by decks with no review history.

Disable it if you want to see every preset.

## Bulk Preset Values

Use **Default FSRS** and **Apply FSRS to All Presets** to set the same FSRS version on every preset currently shown in the table.

Use **Default DR** and **Apply DR to All Presets** to set the same Desired Retention on every preset currently shown in the table.

Click **Save** to write the changed preset values to Anki.

On Anki builds without the FSRS picker field, the FSRS column and bulk FSRS control are hidden automatically.

## FSRS-7 Fork Options

If your Anki build supports these fork-specific FSRS-7 options, the add-on shows two extra columns:

- Include same-day reviews in FSRS-7 optimize
- Include same-day reviews in FSRS-7 evaluate

On Anki builds without FSRS-7 support, these columns are hidden automatically.

## Compatibility

The add-on supports current Anki main-branch FSRS presets and forks with FSRS-7-specific fields. It only writes FSRS version values when Anki already exposes an FSRS version field in the deck options data.

The Desired Retention editor uses the add-on config key `desired_retention_minimum` as its lower limit. The default is `0.7` for Anki's normal 70% minimum. If your fork allows lower values, set this config value lower, for example `0.1`.

If a preset or deck already has a Desired Retention below the configured limit, the add-on keeps that lower value editable.

## How to Use

Open Anki, then go to:

**Tools -> FSRS Preset Manager**

## Notes

- The add-on uses Anki's own FSRS optimize/evaluate backend.
- Optimize changes the preset's FSRS parameters.
- Evaluate only reports metrics; it does not change parameters.
- Deck-specific Desired Retention overrides are only visible when **Show decks** is enabled.
