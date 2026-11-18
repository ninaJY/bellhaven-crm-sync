# Bellhaven reconciliation report

Website facilities: **35** · CRM records: **121**

All suggestions require human review. No CRM updates were performed.

## A_MATCH_NO_CHANGE (10)

- **Bellhaven of Maplewood** — CRM `001L3LGR6W69J8DYYV`; No change
- **Bellhaven of New Carlisle** — CRM `001AQGPZ5G5VRES536`; No change
- **Bellhaven of Wooster** — CRM `001W5G121A7SMRP58M`; No change
- **Bellhaven Terrace of Akron** — CRM `0019Y4J61ZBG4R00CD`; No change
- **Bellhaven of Saline** — CRM `001MVVAPY6U5TVYRC4`; No change
- **Bellhaven of Meadville** — CRM `001KC1NG7EZDEKKA3T`; No change
- **Bellhaven Woods of Toledo** — CRM `0014DHACE6WQU3RMM5`; No change
- **Bellhaven of Kalamazoo** — CRM `001NSHWKQD0YJLPQ20`; No change
- **Bellhaven Court of Altoona** — CRM `0011D2P3CWSHMF81C8`; No change
- **Bellhaven of Owosso** — CRM `001EGU7BMJ942ZTRE6`; No change
  - Review: 2 geographically plausible CRM candidates; review survivor and other accounts

## B_MINOR_FIELD_UPDATE (12)

- **Bellhaven of Goshen** — CRM `001JQER1RMYKNRLNME`; phone: (517) 409-8156 -> (330) 405-6040
- **Bellhaven of Defiance** — CRM `001R4PXTUD9R6FNN8V`; phone: (231) 238-4862 -> (330) 691-2711
- **Bellhaven of Marion** — CRM `0015L38R1Z5947ZZP7`; phone: (330) 314-3109 -> (517) 847-7948
- **Bellhaven Rehabilitation & Nursing of Grove City** — CRM `001TZCSTBZFM6K5BGN`; name: Bellhaven Rehab and Nursing of Grove City -> Bellhaven Rehabilitation & Nursing of Grove City
- **Bellhaven at Sycamore Ridge** — CRM `00191H7JR16471SZ34`; name: Bellhaven of Sycamore Ridge -> Bellhaven at Sycamore Ridge | phone: (419) 982-7764 -> (260) 365-6510
- **The Arbors at Bellhaven - Dayton** — CRM `0010KJFP601YNTZVDA`; name: Arbors at Bellhaven Dayton -> The Arbors at Bellhaven - Dayton | phone: (216) 659-9837 -> (260) 254-7592
- **Bellhaven Healthcare Centre of Ashland** — CRM `001RJ0D7Z5MAZN5HX5`; name: Bellhaven Health Care Center of Ashland -> Bellhaven Healthcare Centre of Ashland | phone: (734) 319-7813 -> (517) 314-5115
- **Bellhaven of Port Clinton** — CRM `001UELXDAKFRKB8932`; phone: (614) 512-8712 -> (330) 733-6423
  - Review: 2 geographically plausible CRM candidates; review survivor and other accounts
- **Bellhaven Shores of Erie** — CRM `001CVBBCSDM7YHN220`; phone: (419) 495-1741 -> (614) 792-9343
  - Review: 2 geographically plausible CRM candidates; review survivor and other accounts | Website has multiple care offerings; CRM care_type is single-valued; do not overwrite
- **Bellhaven Gardens of Monroe** — CRM `001U1750VLVJAGG1S5`; phone: (814) 291-2902 -> (814) 412-2218
  - Review: 3 geographically plausible CRM candidates; review survivor and other accounts
- **Bellhaven of Ashtabula** — CRM `001NXP9X46CWEPSLSV`; note: EMPTY -> Website physical address: 3156 W Prospect Rd, Ashtabula, OH 44004. Verify whether CRM billing_street should change.
  - Review: CRM billing_street is a PO Box; preserve until billing vs physical address is verified
- **Bellhaven of Portsmouth** — CRM `001CF3LDWVRGL09P4F`; billing_zip: 45626 -> 45662

## C_REPARENT_EXISTING (2)

- **Bellhaven Meadows of Findlay** — CRM `001UKEFGADQ8YCZ4YM`; parent_id: EMPTY -> 0015QAPLGS3FVYEEEM | phone: (330) 975-2492 -> (231) 533-2969
  - Review: Website has multiple care offerings; CRM care_type is single-valued; do not overwrite
- **Bellhaven Crossings of Lima** — CRM `001LGFPBJY4N9MB6KL`; parent_id: 001FJZYHR7MLFMNPLL -> 0015QAPLGS3FVYEEEM | phone: (734) 872-9575 -> (231) 539-3617

## D_CHOW_CREATE_AND_LINK (2)

- **Bellhaven of Tiffin** — CRM `001U6RW32TY0WSXZZB`; chow_current_account: EMPTY -> <NEW_ACCOUNT_ID_AFTER_CREATE>
  - Review: SOP: existing account has revenue history AND outstanding AR > 0; DO NOT update old parent or any old fields
- **Bellhaven of Marietta** — CRM `001A34WFSUYHCRBLFT`; chow_current_account: EMPTY -> <NEW_ACCOUNT_ID_AFTER_CREATE>
  - Review: SOP: existing account has revenue history AND outstanding AR > 0; DO NOT update old parent or any old fields

## E_RENAME_OR_REPARENT (5)

- **Bellhaven of Kettering** — CRM `001WR41PYNWXCAE2X4`; name: Kettering Care Centre -> Bellhaven of Kettering | parent_id: 001FJZYHR7MLFMNPLL -> 0015QAPLGS3FVYEEEM | phone: (419) 600-2603 -> (231) 269-5449
  - Review: 3 geographically plausible CRM candidates; review survivor and other accounts | Candidate selection is a review hint; inspect all competing records before approving
- **Bellhaven of Zanesville** — CRM `001H1JMVZWP46D5VUF`; name: Cedar Trail of Zanesville -> Bellhaven of Zanesville | parent_id: 001FWSQ30SFW6S7604 -> 0015QAPLGS3FVYEEEM | phone: (517) 817-8191 -> (814) 599-2533
- **Bellhaven of Chagrin Falls** — CRM `001RJU1X4NBWC1Q0G7`; name: Riverbend Manor Care Center -> Bellhaven of Chagrin Falls | phone: (517) 457-9548 -> (231) 283-7448
- **Bellhaven Willow Creek** — CRM `0017MN2JYAJBDS8WQZ`; name: Sunny Acres Retirement Home -> Bellhaven Willow Creek | phone: (216) 898-7925 -> (419) 394-5494
- **Bellhaven of Chesterton** — CRM `0013NUZQHQUEZ8DXEG`; name: Chesterton Senior Commons -> Bellhaven of Chesterton

## F_CREATE_NEW (4)

- **Bellhaven of Batavia** — CRM `<CREATE>`; CREATE new account
  - Review: No eligible same-address or same-name+city/state CRM match
- **Bellhaven at Union Square** — CRM `<CREATE>`; CREATE new account
  - Review: No eligible same-address or same-name+city/state CRM match
- **Bellhaven of Carlisle** — CRM `<CREATE>`; CREATE new account
  - Review: No eligible same-address or same-name+city/state CRM match
- **Amberly Manor** — CRM `<CREATE>`; CREATE new account
  - Review: No eligible same-address or same-name+city/state CRM match

## CRM cleanup (10)

- **Bellhaven Care Center of Alliance** `00116ETS45BL7DTQP7` — NOT_ON_CURRENT_WEBSITE: status: Active -> Needs Review | note: EMPTY -> Not on current Bellhaven website roster; verify closure, divestiture, or rename before changing parent/status. Revenue=0; outstanding AR=0.
- **Bellhaven of Coldwater** `0016PVXH4B25HWR7QE` — NOT_ON_CURRENT_WEBSITE: status: Active -> Needs Review | note: EMPTY -> Not on current Bellhaven website roster; verify closure, divestiture, or rename before changing parent/status. Revenue=0; outstanding AR=0.
- **Bellhaven of Owosso** `001QU150PM4Z15UA71` — DUPLICATE_CONFIDENT: status: Active -> Inactive | duplicate_of_account: EMPTY -> 001EGU7BMJ942ZTRE6
- **Bellhaven of Sandusky** `001SXSF4ELF0Z2LGDM` — NOT_ON_CURRENT_WEBSITE: status: Active -> Needs Review | note: EMPTY -> Not on current Bellhaven website roster; verify closure, divestiture, or rename before changing parent/status. Revenue=130000; outstanding AR=5200.
- **Cedar Trail of Monroe** `0011AB44D05WLA9HTX` — CROSS_PARENT_OR_AMBIGUOUS_SAME_ADDRESS: Manual review; no automatic mutation
- **Harborview Nursing & Rehab of Port Clinton** `001JD2MWRA74LTSN24` — CROSS_PARENT_OR_AMBIGUOUS_SAME_ADDRESS: Manual review; no automatic mutation
- **Harborview Shores of Erie** `001BLYF02K97SZLZHH` — CROSS_PARENT_OR_AMBIGUOUS_SAME_ADDRESS: Manual review; no automatic mutation
- **Kettering Nursing & Rehabilitation** `0016KTS1UAWBRXS09J` — CROSS_PARENT_OR_AMBIGUOUS_SAME_ADDRESS: Manual review; no automatic mutation
- **Kettering Senior Campus** `001B7XZAA3AFALS9GP` — CROSS_PARENT_OR_AMBIGUOUS_SAME_ADDRESS: Manual review; no automatic mutation
- **Monroe Gardens Care Center** `00159PL81N38KM4FHM` — CROSS_PARENT_OR_AMBIGUOUS_SAME_ADDRESS: Manual review; no automatic mutation
