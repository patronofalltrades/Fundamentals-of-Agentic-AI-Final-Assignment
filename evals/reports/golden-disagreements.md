# Golden 50 vs Jev: disagreements for human adjudication

Run `golden-jev-r1` (label_config `typesafe/jev-latest:prompt-v1:extract-v2:schema-a5-v1`). Listed: every case where topic or intent differs, or severity differs by 2 or more.
`Rubric favours` is the orchestrator's reading of `docs/specs/GRADING_CONTRACT.md`, offered for review — not a ruling. Golden labels were not changed and never enter prompts.

Tally: rubric appears to favour Jev 20, gold 1, unclear/ambiguous 9 (+1 leaning Jev).

| Rubric favours | Gold (topic/intent/sev) | Jev (topic/intent/sev) | Review text | Rule |
|---|---|---|---|---|
| gold | support/complaint/2 | playback/complaint/4 | Update: I reached out to Spotify Support and with some help from Sarah I was able to get the app working again. Old Post:Normally, the app w… | Contacting support and its response = `support`. |
| ambiguous | catalog/complaint/5 | other/complaint/2 | Staff must be full of mentally ill kool-aid heads. Banning conservative music that speaks truth. Spotify is doing all they can to protect pe… | Topic `catalog` is plausible (removed music); severity 5 needs explicit financial/privacy/data harm, so 2–3 fits the rubric better. |
| ambiguous | catalog/praise/1 | other/praise/1 | Spotify is awesome and and very diverse :) | 'Diverse' may praise the catalog (`catalog`) or be general praise (`other`). |
| ambiguous | playback/unclear/2 | usability/complaint/2 | I like it but god I hate it when the music Interrupts my ads | A joke/inversion about ads; `usability` (ad interruptions) or `unclear`. |
| ambiguous | other/unclear/1 | catalog/complaint/2 | Lhat ng song nasa spotify | Tagalog, roughly 'all songs are on Spotify' (catalog praise?) — `needs_review` territory. |
| unreviewed | other/unclear/3 | other/complaint/2 | I hate this app and sweden .I love islam |  |
| ambiguous | playback/complaint/5 | usability/complaint/3 | Are you out of your mind? This is dangerous! Listening to music in a normal volume and suddenly an add starts and my ears feel like they exp… | Loud ad = `usability` (ad interruptions) or `playback` (audio); severity 5 is reserved for financial/privacy/data harm. |
| ambiguous | billing/unclear/1 | other/unclear/1 | Beth, we all got to give me a free dollar to go with 3 months, bro I can't be like | Unclear text; `billing` vs `other` both defensible. |
| ambiguous | usability/complaint/4 | catalog/complaint/3 | 1-Lyrics not getting loaded, 2-can't go back to or start song where to wanted. Pathetic update | Tie rule: first specific problem is lyrics (`catalog`); seeking is `usability`. |
| ambiguous | usability/complaint/4 | billing/complaint/3 | Too expensive and the free version is pretty much unusable with constant ads... Every two or three songs.. Forget it | Price (`billing`) and ads (`usability`) both stated; tie rule says first mentioned = price. |
| jev? | playback/complaint/2 | playback/complaint/4 | Very poor updates as we cannot playback the songs and most bad updates are happening it is affecting the spotify quality | Topic agrees (`playback`); 'cannot play back songs' is a blocked core task (4) per the scale. |
| jev | access/praise/1 | other/praise/1 | Great app use it every chance I get | General praise is `other`; nothing about login/account. |
| jev | usability/praise/1 | other/praise/1 | It's really an amazing experience with Spotify...I love it🥰 | General praise is `other`. |
| jev | usability/praise/1 | other/praise/1 | I just loved it | General praise is `other`. |
| jev | usability/complaint/4 | other/complaint/2 | Hate this application 🤮🤮🤮🤮🤮🤮 | General 'bad app' is a complaint without a specific defect: `other`, severity 2 (generic criticism). |
| jev | usability/praise/1 | other/praise/1 | Excellent | General praise is `other`. |
| jev | usability/praise/1 | other/praise/1 | good ❤❤🔊🔊 | General praise is `other`. |
| jev | access/unclear/1 | billing/praise/1 | Duo Premium .... No ads at all! | Not login/account access; a premium-plan remark is `billing` (or `other`), praise of no ads. |
| jev | support/complaint/2 | playback/complaint/3 | Very good but wen I play my song it o ly plays a little bit then it stops I updated my phone and it worked but it happend again they need to… | Playback stops = `playback`; no contact with support is described. |
| jev | usability/complaint/3 | other/complaint/2 | This app is bad work | Generic criticism: `other`, severity 2. |
| jev | usability/complaint/2 | catalog/complaint/3 | asem, lirik nya kdang gaada kek mana?? | Lyrics availability is `catalog` by definition. |
| jev | other/complaint/4 | other/unclear/1 | We are boycotting Swedish app in our protest against Sweden for their desrecpect & desceration of our holy book Qur'an | Bare boycott slogan without a product complaint = `unclear`, severity 1. |
| jev | usability/praise/1 | catalog/praise/1 | I LOVE that I was able to put in only a few songs I like and Spotify gave me recommendations for an AWESOME Playlist...!!! | Recommendations are `catalog` by definition. |
| jev | usability/praise/1 | other/praise/1 | I absolutely love Spotify, to me is one of the best Music Apps. Great job Spotify!!! | General praise is `other`. |
| jev | support/request/1 | usability/request/2 | Please ye ads ko thoda kumm Karo harr ek song ke baad ad 🙏🙄 | Ad interruptions are `usability`; not a support contact. |
| jev | usability/complaint/5 | usability/cancellation/3 | Deleting this App. The new update suck, we can't choose our fvrt songs after some clicks, we can't CHOOSE song after a song played, and we c… | 'Deleting this App' = `cancellation` (precedence); severity 5 needs financial/privacy/data harm. |
| jev | support/request/5 | playback/complaint/4 | What is happening with Spotify?? Recently I'm trying to play a song but it doesn't working. So I unstalled and thn again install it now I ca… | Cannot play/open = `playback` complaint, severity 4; no support contact or financial harm. |
| jev | catalog/request/2 | usability/request/1 | The only thing Spotify lacks is the ability to organize saved  albums/artists into collections. Would definitely deserve 5 stars if it  incl… | Library/collection management is `usability` (queue/playlist management). |
| jev | usability/praise/1 | catalog/praise/1 | I find Spotify very good, it finds and play whatever music you want and also adds songs that you might like, judging from your playlist if y… | First praised feature is finding music / recommendations = `catalog`. |
| jev | usability/unclear/2 | downloads/complaint/4 | paying for subscribing but unable to play in offline mode really? | Offline listening is `downloads`; a reported failure is a `complaint`. |
| jev | other/complaint/2 | usability/complaint/2 | Worst app ever too much ad | Ads are `usability`. |

**How to resolve.** For each row, either correct the golden label to the rubric, or keep it and add the other value to `accepted_*` (the checker accepts several labels for genuinely ambiguous cases). Then re-run `python3 evals/build_gold.py` and `python3 evals/score_gold.py --run runs/golden-jev-r1`.
