# Meditation collectibles

The atlas includes all ten published meditation locations, covering 18 meditation actions. Open **Collectibles** and search for **meditation**. The source reports that any 15 actions count toward the completion checklist. The ordinary sites can be used once with each character after character switching unlocks in Chapter 2. [PowerPyx meditation guide](https://www.powerpyx.com/gta-6-all-meditation-spot-locations/)

Jason’s House is a Chapter 1 venue pin. Follow Lucia to the balcony when she offers the lesson. It adds one action, and the source has yet to confirm whether it is required for Positive Mental Attitude. The final Ascent Mountain spot appears after the preceding meditations. [PowerPyx meditation guide](https://www.powerpyx.com/gta-6-all-meditation-spot-locations/) · [Down to Earth walkthrough](https://www.powerpyx.com/gta-6-down-to-earth-walkthrough/) · [GTADB Jason’s House venue](https://map.gtadb.org/#VI,L266)

## Pin evidence

Nine locations use the selected purple in-game map marker shown in PowerPyx’s wide pause-map screenshot. The point stored for each screenshot is the tip of the highlighted pin, measured in the original 1920 × 1080 image. The local matcher aligned screenshots against the registered references using roads, coastline and similar map features. The nine accepted fits had 323–741 inliers. Held-out p90 residuals were 1.96–4.93 canonical atlas pixels. Repeating registration at a different JPEG quality and downsampling size changed the stored results by at most 0.72 atlas pixels. These numbers measure map registration. The on-foot interaction prompt can be offset from the map marker. The tighter screenshots lacked enough map context to pass registration and were excluded. [PowerPyx screenshot guide](https://www.powerpyx.com/gta-6-all-meditation-spot-locations/) · [In-game map reference](https://www.powerpyx.com/gta-6-full-world-map-revealed/)

The public data contains source links, screenshot hashes, selected pixel coordinates and registration metrics. Source images stay out of the distribution. The Ascent Mountain record retains the older summit guide ID to preserve player progress and votes.

## Verification

Run `python -B -m unittest discover -s tests -p test_collectible_guides.py -v` to check set coverage, the venue linkage, and marker provenance. The test also verifies the screenshot hashes when the local evidence cache is present.
