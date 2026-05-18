# Title Alternatives — Cases 1–6

Five title alternatives per case for A/B testing. Generated using the rubric below. Use these to repost a case under a different title if the original underperforms, or to test which pattern works best in your audience.

---

## The title rubric (codified from what's working)

Every good true-crime Short title hits at least 3 of these 5 levers:

1. **Specific concrete detail** — a number, a name, a place, a weapon, a date. Vague titles die.
2. **Counter-intuitive juxtaposition** — pair two things the viewer doesn't expect together ("NFL player ↔ Medicare fraud", "Pilot ↔ insider trading", "Negotiator ↔ working for the gang")
3. **Active verb in present or past tense** — "He stole," "They followed," "She tipped"
4. **≤80 characters before `#shorts`** — so the title isn't truncated above the fold on mobile
5. **Open loop / question implied** — title hints there's more to the story than the title itself reveals

**Avoid:** "You won't believe..." / "SHOCKING!" / "WAIT FOR IT" / clickbait imperatives. They tank credibility on a forensic channel and YouTube's algorithm now downweights them.

**Always end with `#shorts`** — the format tag is the first hashtag YouTube reads.

---

## Case 01 — GothFerrari (DELIVERED)

**Shipped:** When Hackers Couldn't Steal Your Crypto, They Sent Him #shorts

**Alternatives:**
1. They Sent A 20-Year-Old With A Brick To Steal The Bitcoin #shorts
2. The "Instrument Of Last Resort" In A $250M Crypto Heist #shorts
3. He Broke A Window In New Mexico To Steal 100 Bitcoin #shorts
4. The Burglar The Hackers Called When Their Tricks Failed #shorts
5. iCloud Tracked The Victim. Then He Smashed The Window. #shorts

## Case 02 — Ransomware Negotiator (Angelo Martino)

**Shipped:** The Negotiator Was Working For The Hackers #shorts

**Alternatives:**
1. He Was Paid To Fight Ransomware. He Sold Out His Clients. #shorts
2. The Cybersecurity Negotiator Who Worked For BlackCat #shorts
3. He Leaked His Clients' Insurance Limits To The Hackers #shorts
4. $10 Million In Assets Seized From A Ransomware Negotiator #shorts
5. The Inside Man Inside The Cyber Incident Response Firm #shorts

## Case 03 — Fugitive Crypto Scam (Daren Li)

**Shipped:** He Pleaded Guilty. Then He Cut Off His Ankle Monitor. #shorts

**Alternatives:**
1. Sentenced To 20 Years — To An Empty Chair #shorts
2. He Pled Guilty In November. He Disappeared In December. #shorts
3. The Cambodian Crypto Scam That Laundered $73 Million #shorts
4. Pig-Butchering: Fake Romance, Fake Trading Platforms, Real $73M #shorts
5. He Cut Off His Ankle Monitor And Vanished. He's Still Out There. #shorts

## Case 04 — Cargo Heist (Perez-Gonzalez crew)

**Shipped:** They Followed The Truck. When The Driver Stopped, They Drove Off With It. #shorts

**Alternatives:**
1. $2 Million In Oculus Headsets — Stolen By Following The Truck #shorts
2. They Painted Over The Logos And Drove It To Miami #shorts
3. The Crew That Stole Meta And Microsoft Trucks For 18 Months #shorts
4. 14 Heists. $5M+ In Cargo. They Just Followed The Drivers. #shorts
5. When The Trucker Stopped For Coffee, The Trailer Was Gone #shorts

## Case 05 — NFL Player Medicare Fraud (Joel French)

**Shipped:** He Played In The NFL. Then He Stole $197M From Disabled Veterans. #shorts

**Alternatives:**
1. The NFL Player Who Built 8 Shell Companies To Bilk Medicare #shorts
2. Overseas Call Centers Faked Senior Consent For Medical Braces #shorts
3. He Drove $10,000 To Orlando In A Bag To Buy Insurance Info #shorts
4. $197 Million Stolen From Medicare. A Former NFL Player Built It. #shorts
5. The Call Centers Altered The Recordings To Fake Patient Consent #shorts

## Case 06 — DNA Scam (Salahaldeen)

**Shipped:** They Knocked On Your Door. They Asked For Your DNA. They Billed Medicare $522M. #shorts

**Alternatives:**
1. They Harvested DNA From Seniors At Health Fairs. They Billed Medicare $522M. #shorts
2. The $522 Million Genetic Testing Scam — From Door To Door #shorts
3. He Tried To Flee To Mexico With A Stolen ID. He Didn't Make It. #shorts
4. 4 Labs. 11 Co-Conspirators. $522 Million In Fake Genetic Tests. #shorts
5. Doctors Who Never Met The Patients Signed Off On Their DNA Tests #shorts

---

## How to use this for A/B testing

If a case underperforms in its first 72 hours (CTR < 4%, or 3-second hold < 60%):

1. Pick an alternative title from this file that uses a different lever (e.g., if your shipped title was character-driven, try a stat-driven alternative)
2. Re-upload the same mp4 under the new title — `python scripts/upload_to_youtube.py --case 02` after manually clearing the case from `_posted.json`
3. Compare 72-hour metrics on the new title vs. the original
4. Lock in the winning pattern for future cases

Caveat: YouTube can detect re-uploads of identical content as duplicates. Wait at least 7 days between attempts and consider re-rendering with a different visual treatment if you want to test multiple titles on the same case.
