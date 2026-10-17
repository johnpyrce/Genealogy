# Website review: changes and remaining decisions

Updated October 17, 2026.

## Completed in this editorial pass

- Fixed the Home heading and browser title and made the reading suggestions clickable.
- Linked the census, passenger manifests, citizenship papers, naturalization reverse, and the newly available Stanley naturalization card to their existing local detail pages.
- Preserved the removal of the external FamilySearch citation. Stanley's 1941 card is now hosted in the America collection.
- Corrected remaining spelling and grammar, simplified the surname, tree, download, and analytics explanations, and clarified that missing information is unknown.
- Added notes explaining conflicting dates and possible record matches without changing registry facts or choosing between accounts.
- Added full-size image and image-download links, full-window tree links, and routes back to the America story and between photo collections. Converted scans retain their original pixel dimensions.
- Added separate display captions and reconstruction/colorization notes; original filenames, stable photo URLs, gallery ordering, and legacy redirects remain unchanged apart from the newly supplied 1941 card joining its filename-sorted position.
- Added a confidence key, source-chart links and section anchors, and actual chart IDs in the tree's person details.
- Linked the official Auschwitz Memorial transport list, which independently identifies Bronisław Gościński as prisoner 403, born March 20, 1920 in Muszyna, transferred to Buchenwald in 1944, and a survivor. See entry 403, PDF page 23: https://www.auschwitz.org/gfx/auschwitz/userfiles/_public/2020_news/lista_wiezniow_i_transportu_polakow_do_auschwitz_14_czerwca_1940.pdf.

## Decisions or evidence needed from John

These are requests for evidence or choices; no one needs to edit code manually. Supply the answer/source and the site can be updated from it. An unresolved point may stay explicitly uncertain.

1. **Joseph's death date.** The charts and timeline say 1940; a photograph filename says December 1939. Check a death certificate, obituary, funeral card, or another dated family record. Send the source rather than choosing from the filename alone.
2. **Birth and immigration discrepancies.** If you want these resolved, supply the records supporting Joseph's 1879/1881 birth years, Sophie's differing birth years, Charles/Karol's 1917/1919 and Bernice/Bronisława's 1913/1914 birth years. The 1905 Josef Pyrc and 1913 Zofia Goscinska manifests, the possible Joseph naturalization index matches, and the marriage-location disagreement also need identifying evidence. The website now presents them as alternatives.
3. **Ship photograph and traveler.** Confirm what the picture captioned “1913 - Sophie on Kaiser Wilhelm III” depicts and whether it is actually associated with Sophie. The narrative's manifest names Kaiser Wilhelm II. The display caption now preserves the original identification as unconfirmed.
4. **Pronunciation and photo identities.** Confirm the family pronunciation of Pyrć versus Pyrc, ideally with a Polish-speaking relative or a recording. Confirm Andrew's surname in the “Gocinski” photograph and identify the unnamed people where possible. Clear typography fixes were made; unresolved identities were not guessed.
5. **Bronisław's detailed story.** Provide the original memoir, interview, or document behind the detailed narrative. Confirm the “Mallhof”/“Malhof” camp reading, his mother's surname (the narrative says Miczułka; the registry uses Miczulska), and the sibling count. The Memorial entry supports only the specific details cited above, not every event in the narrative.
6. **Access preference for the separate Family Archive.** Decide whether archive.pyrce.org should remain public or should have restricted access like the genealogy site. It is a separate application; this editorial pass does not change its sharing or build a shared email gate. If it should be restricted, specify who should be allowed.
7. **Google Drive permissions.** Confirm that intended relatives can open the military-record document and any other original files you want them to see, using a browser signed out of your Google account. The two preview pages sampled in the access review loaded anonymously, but not every original/download was verified. Approving an email on genealogy.pyrce.org does not grant Google Drive access.

## Optional additions

- Supply sourced material for Miczulski and Rams surname histories if you want those pages. The Names index now accurately describes the three histories currently available.
- Supply evidence of a documented Doliwa lineage only if you want to assert a connection. The coat of arms is now explicitly historical context, with no established connection to this family.

## Remaining technical limitation

The analytics top bar still includes the shared Data app actions. The copied dashboard guide protects that infrastructure: “Do not edit, replace, delete, shadow, hide, disable, or bypass them during ordinary app creation or revision.” No supported hide-toolbar option was found in the available component reference, and the ordinary runtime recognizes hosted mode by its *.chatgpt.site hostname. This pass edits authored report content, not the protected runtime or permissions. A separate, explicitly scoped custom-domain reader-mode/runtime change would be needed to address those controls; do not hide them with CSS. See [the local dashboard guide](../apps/analytics-dashboard/AGENTS.md).

## Validation

Validation passed: all 36 Python regression tests, all 18 visitor-access tests, registry validation, the dashboard and site build, 2,053 internal file references, and 106 HTML fragment links. Browser checks covered the Home links/title, the local Stanley card, download choices, the revised analytics summary and table label, and person search with S2/S3 source links. External checks found 17 URLs returning HTTP 200; three URLs had local certificate-chain errors and two returned 403. The newly cited Memorial PDF was independently retrieved through web browsing. These external-tool limits do not establish that the destinations are broken. The completion message records publication state. Historical disputes remain unresolved; no registry fact or family relationship is changed by the editorial work.
