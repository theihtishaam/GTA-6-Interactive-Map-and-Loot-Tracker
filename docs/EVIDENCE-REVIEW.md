# Gameplay evidence review

The atlas reviews already collected GTA VI gameplay reports before displaying them. It uses the source text and position evidence in the local cache. The review makes no network requests or model calls. It issues one of three labels.

| Label | Meaning for the map |
| --- | --- |
| Single-source report | The loaded reports contain one usable source for this claim. Broad guides, weak evidence and unanswered questions stay in this group. |
| Corroborated | Independent publishers describe the same specific activity at a named atlas venue, or they report closely matching gameplay grid coordinates for a distinctive subject. A venue pin stays approximate. |
| Needs review | A source reports a correction, possible patch, stale location or retraction, or independent reports disagree about coordinates. The atlas hides the map pin pending review and keeps the evidence links available. |

A label describes the state of the collected evidence. It does not independently establish that a report was tested in the game, that a game update caused a change, or that the activity is available in every chapter or game version. Check the linked source and its requirements before travelling.

## Comparison rules

- Match the game category and distinctive subject words. Separate explicit numbering, chapter, variant and security tiers. Keep different named venues and multi-location guides separate.
- Require affirmative gameplay text and a shared catalogue venue ID or two explicitly reported game grid points before corroborating. A shared catalogue ID supports venue agreement only. Proximity alone does not support a generic reward or a different object.
- Treat equivalent publisher domains as one host. Ignore matching source digests, copied excerpts, links to the same primary evidence and declared reposts when deciding independence.
- Convert normalized positions to the atlas’s signed game frame for distance comparison. Explicit reports with qualifying subjects can agree within 50 grid units. Differences of at least 250 grid units in the same named venue or region, or for an explicitly unique subject, require review. In-between distances stay single-source unless a separate venue match applies.
- Preserve all input records. Corrections can restore a pin on the next review because the hidden coordinates are a display decision. A corrected version replaces the earlier claim in the evidence inputs.

The source material shows why the distinction matters. PowerPyx’s meditation guide separates the named site, the path to its in-game prompt, and an unresolved chapter-specific trophy requirement. Its world map labels regions and predefined activities. A map anchor and an acquisition claim therefore need their own evidence. [Firsthand meditation guide](https://www.powerpyx.com/gta-6-all-meditation-spot-locations/) · [Published in-game map legend](https://www.powerpyx.com/gta-6-full-world-map-revealed/) · [Atlas map coordinate frame](MAP-DATA.md)

## Developer use

`review_reports(reports)` returns a list in input order with new top-level dictionaries. Each adds `verification: {status,label,reason,sources:[{name,url}]}`. The status values are `single-source`, `corroborated` and `review`. The last value sets the returned `x` and `y` to null. Pass raw collected evidence on each review, rather than feeding a prior reviewed projection back into the cache. When available, the verification excerpt follows the original public source text beyond the short display blurb.

Run the offline scenarios with:

```sh
python -B -m unittest discover -s tests -p test_report_verification.py -v
```
